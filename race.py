import threading
from mcpi.minecraft import Minecraft
from mcpi import block
import input_system as inp
from time import sleep, time
import random

mc = Minecraft.create()

ROAD_WIDTH = 7
ROAD_LENGTH = 50
PLAYER_LANE = 3
BASE_GAME_SPEED = 0.05

ROAD_BLOCK = block.STONE.id
LINE_BLOCK = block.WOOL.id
GRASS_BLOCK = block.GRASS.id
PLAYER_CAR_ID = block.WOOL.id
PLAYER_CAR_DATA = 11
ENEMY_CAR_ID = block.WOOL.id
NITRO_DATA = 14
COIN_BLOCK = 14 
GLOWSTONE = 89
LEAVES = block.LEAVES.id
FENCE = block.FENCE.id
REDSTONE_BLOCK = 152

VEHICLE_TYPES = {
    'motorcycle': {'w': 1, 'h': 1, 'l': 1, 'speed': 2, 'score': 20, 'colors': [15]},
    'car':        {'w': 1, 'h': 1, 'l': 2, 'speed': 5, 'score': 10, 'colors': [1, 4, 5]},
    'truck':      {'w': 2, 'h': 2, 'l': 3, 'speed': 7, 'score': 5,  'colors': [14, 8]}
}

SPAWN_POOL = ['car', 'car', 'motorcycle', 'truck']

class Entity:
    def __init__(self, x, z, road_info):
        self.x, self.z = x, z
        self.rx, self.ry, self.rz = road_info
        self.active = True

class Enemy(Entity):
    def __init__(self, x, z, v_type, road_info):
        super().__init__(x, z, road_info)
        cfg = VEHICLE_TYPES[v_type]
        self.w, self.h, self.l = cfg['w'], cfg['h'], cfg['l']
        self.speed_delay, self.score = cfg['speed'], cfg['score']
        self.color = random.choice(cfg['colors'])
        self.counter = 0

    def draw(self, clear=False):
        b = block.AIR.id if clear else ENEMY_CAR_ID
        d = 0 if clear else self.color
        for dx in range(self.w):
            for dy in range(self.h):
                for dz in range(self.l):
                    mc.setBlock(self.x + dx, self.ry + dy + 1, self.z + dz, b, d)

    def is_blocked(self, others):
        for e in others:
            if e == self or not e.active: continue
            if self.x < e.x + e.w and self.x + self.w > e.x:
                if e.z < self.z and self.z - e.z <= self.l + 1:
                    return True
        return False

    def move(self, others, nitro):
        self.counter += 2 if nitro else 1
        if self.counter >= self.speed_delay:
            if self.is_blocked(others):
                return False
            self.counter = 0
            self.draw(True)
            self.z -= 1
            if self.z < self.rz:
                self.active = False
                return True
            self.draw()
        return False

    def check_collision(self, px, pz):
        return self.z <= pz < self.z + self.l and self.x <= px < self.x + self.w

class Bonus(Entity):
    def __init__(self, x, z, road_info):
        super().__init__(x, z, road_info)
        
    def draw(self, clear=False):
        b = block.AIR.id if clear else COIN_BLOCK
        mc.setBlock(self.x, self.ry + 1, self.z, b)

    def move(self, nitro):
        self.draw(True)
        self.z -= (2 if nitro else 1)
        if self.z < self.rz:
            self.active = False
        else:
            self.draw()

def build_environment(pos):
    x, y, z = pos
    mc.setBlocks(x - 10, y, z, x + 15, y + 10, z + ROAD_LENGTH, block.AIR.id)
    mc.setBlocks(x - 10, y - 1, z, x + 15, y - 1, z + ROAD_LENGTH, block.GRASS.id)
    for i in range(ROAD_LENGTH):
        for j in range(ROAD_WIDTH):
            mc.setBlock(x + j, y, z + i, ROAD_BLOCK)
        mc.setBlock(x - 1, y, z + i, block.OBSIDIAN.id)
        mc.setBlock(x + ROAD_WIDTH, y, z + i, block.OBSIDIAN.id)
    return x, y, z

def update_scenery(rx, ry, rz, offset):
    for i in range(ROAD_LENGTH):
        for j in [2, 4]:
            if (i + offset) % 4 == 0:
                mc.setBlock(rx + j, ry, rz + i, LINE_BLOCK, 0)
            else:
                mc.setBlock(rx + j, ry, rz + i, ROAD_BLOCK)
    if offset % 10 == 0:
        mc.setBlock(rx - 3, ry + 1, rz + ROAD_LENGTH - 1, LEAVES)
        mc.setBlock(rx + ROAD_WIDTH + 2, ry + 1, rz + ROAD_LENGTH - 1, FENCE)
        mc.setBlock(rx + ROAD_WIDTH + 2, ry + 2, rz + ROAD_LENGTH - 1, GLOWSTONE)

def draw_player(rx, ry, rz, lane, pz, nitro, clear=False):
    b = block.AIR.id if clear else PLAYER_CAR_ID
    d = NITRO_DATA if (nitro and not clear) else PLAYER_CAR_DATA
    mc.setBlock(rx + lane, ry + 1, rz + pz, b, d)
    mc.setBlock(rx + lane, ry + 1, rz + pz - 1, b, d)
    mc.setBlock(rx + lane, ry + 2, rz + pz, b, 0)
    if nitro and not clear:
        mc.setBlock(rx + lane, ry + 1, rz + pz - 2, REDSTONE_BLOCK)
    else:
        mc.setBlock(rx + lane, ry + 1, rz + pz - 2, block.AIR.id)

def can_spawn_here(lane, enemies, rz):
    for e in enemies:
        if (e.x - (e.rx)) == lane and e.z > rz + ROAD_LENGTH - 4:
            return False
    return True

def main():
    mc.postToChat("FAST NITRO RALLY")
    p = mc.player.getTilePos()
    r_info = build_environment((p.x, p.y, p.z + 5))
    rx, ry, rz = r_info
    lane, pz, score, lives = PLAYER_LANE, 3, 0, 3
    enemies, bonuses, road_offset = [], [], 0
    spawn_t, spawn_i = time(), 1.5
    nitro_end, nitro_cooldown = 0, 0
    mc.player.setTilePos(rx + lane, ry + 5, rz + pz)
    
    while lives > 0:
        now = time()
        nitro_active = now < nitro_end
        current_speed = BASE_GAME_SPEED / 2 if nitro_active else BASE_GAME_SPEED
        road_offset += (2 if nitro_active else 1)
        update_scenery(rx, ry, rz, road_offset)

        if inp.wasPressedSinceLast(inp.LEFT) and lane < ROAD_WIDTH - 2:
            draw_player(rx, ry, rz, lane, pz, nitro_active, True)
            lane += 2
        if inp.wasPressedSinceLast(inp.RIGHT) and lane > 1:
            draw_player(rx, ry, rz, lane, pz, nitro_active, True)
            lane -= 2
        if inp.wasPressedSinceLast(inp.UP) and now > nitro_cooldown:
            nitro_end, nitro_cooldown = now + 3, now + 8
            mc.postToChat("NITRO!")
        if inp.wasPressedSinceLast(inp.ESCAPE): break

        if now - spawn_t > (spawn_i / 2 if nitro_active else spawn_i):
            event = random.random()
            if event < 0.04:
                bonuses.append(Bonus(rx + random.choice([1, 3, 5]), rz + ROAD_LENGTH - 2, r_info))
            elif event < 0.8:
                vt = random.choice(SPAWN_POOL)
                sl = random.choice([1, 3, 5])
                if vt == 'truck' and sl > 4: sl = 4
                if can_spawn_here(sl, enemies, rz):
                    enemies.append(Enemy(rx + sl, rz + ROAD_LENGTH - 4, vt, r_info))
            spawn_t = now
            spawn_i = max(0.6, spawn_i - 0.005)

        for b in bonuses:
            if b.active:
                b.move(nitro_active)
                if b.z == rz + pz and b.x == rx + lane:
                    score += 50
                    mc.postToChat("COIN!")
                    b.draw(True)
                    b.active = False

        for e in enemies:
            if e.active:
                if e.move(enemies, nitro_active):
                    score += (e.score * 2 if nitro_active else e.score)
                if e.check_collision(rx + lane, rz + pz):
                    lives -= 1
                    mc.postToChat("CRASH! L: " + str(lives))
                    e.draw(True)
                    e.active = False
                    sleep(0.5)

        enemies = [e for e in enemies if e.active]
        bonuses = [b for b in bonuses if b.active]
        draw_player(rx, ry, rz, lane, pz, nitro_active)
        sleep(current_speed)

    mc.postToChat("FINAL SCORE: " + str(score))

if __name__ == '__main__':
    try: main()
    except Exception as e: print(e)