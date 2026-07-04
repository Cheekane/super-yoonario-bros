"""Overworld map: walk a hero token between level nodes across three worlds."""
import math

import pygame

from .constants import VIEW_W, VIEW_H, CHARACTERS
from .sprites import THEMES, CHAR_COLORS
from .levels import LEVELS
from .hud import text, box
from .menu import Scene, TitleScene

MAP_W = VIEW_W * 3
TOKEN_SPEED = 130.0

# (x, y) of each level node across the 960px map; castles sit higher
NODE_POS = [
    (44, 148), (114, 120), (186, 148), (258, 100),        # Green Hills
    (338, 148), (408, 118), (478, 148), (548, 98),        # Sandy Dunes
    (628, 148), (698, 118), (768, 148), (852, 92),        # Frostpeak
]
WORLD_X = [(0, 320), (320, 640), (640, 960)]
WORLD_THEMES = ["grass", "desert", "ice"]


class MapScene(Scene):
    def __init__(self, app, focus=None):
        super().__init__(app)
        unlocked = app.save["unlocked"]
        node = focus if focus is not None else app.save.data.get("map_pos", 0)
        self.node = max(0, min(node, unlocked - 1, len(LEVELS) - 1))
        self.x, self.y = NODE_POS[self.node]
        self.target = self.node
        self.cam_x = 0.0
        self.walk_t = 0.0
        app.audio.play_music("menu")

    # ------------------------------------------------------------- update

    def update(self, dt, events):
        unlocked = self.app.save["unlocked"]
        moving = (self.x, self.y) != NODE_POS[self.target]
        for e in events:
            if e.type != pygame.KEYDOWN:
                continue
            if e.key == pygame.K_ESCAPE:
                self.app.switch(TitleScene(self.app))
                return
            if moving:
                continue
            if e.key in (pygame.K_LEFT, pygame.K_a) and self.target > 0:
                self.target -= 1
                self.app.audio.play("select")
            elif e.key in (pygame.K_RIGHT, pygame.K_d) \
                    and self.target + 1 < min(unlocked, len(LEVELS)):
                self.target += 1
                self.app.audio.play("select")
            elif e.key in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE):
                self.app.save["map_pos"] = self.node
                self.app.save.write()
                self.app.audio.play("confirm")
                from .app import GameScene
                self.app.switch(GameScene(self.app, "sp", self.node))
                return
        # walk the token toward the target node
        tx, ty = NODE_POS[self.target]
        dx, dy = tx - self.x, ty - self.y
        dist = math.hypot(dx, dy)
        if dist > 1:
            step = min(dist, TOKEN_SPEED * dt)
            self.x += dx / dist * step
            self.y += dy / dist * step
            self.walk_t += dt
        else:
            self.x, self.y = tx, ty
            self.node = self.target
        # camera follows token
        want = max(0.0, min(self.x - VIEW_W / 2, MAP_W - VIEW_W))
        self.cam_x += (want - self.cam_x) * min(1.0, 6 * dt)

    # ------------------------------------------------------------- draw

    def draw(self, surf):
        cam = int(self.cam_x)
        unlocked = self.app.save["unlocked"]
        # world-themed sky bands with soft blend seams
        for (x0, x1), theme in zip(WORLD_X, WORLD_THEMES):
            r = pygame.Rect(x0 - cam, 0, x1 - x0, VIEW_H)
            surf.fill(THEMES[theme]["sky"], r.clip(surf.get_rect()))
        # ground strip + hills
        for (x0, x1), theme in zip(WORLD_X, WORLD_THEMES):
            tiles = self.app.sprites.tiles[theme]
            for gx in range(x0, x1, 16):
                sx = gx - cam
                if -16 <= sx <= VIEW_W:
                    surf.blit(tiles["ground"], (sx, VIEW_H - 32))
                    surf.blit(tiles["dirt"], (sx, VIEW_H - 16))
            hill = THEMES[theme]["bg"]
            for i in range(3):
                hx = x0 + 50 + i * 100 - cam
                if -80 <= hx <= VIEW_W + 80:
                    pygame.draw.circle(surf, hill, (hx, VIEW_H - 30), 16)
        # path between nodes (dotted)
        for i in range(len(NODE_POS) - 1):
            (ax, ay), (bx, by) = NODE_POS[i], NODE_POS[i + 1]
            steps = max(4, int(math.hypot(bx - ax, by - ay) // 10))
            col = (255, 255, 255) if i + 1 < unlocked else (150, 150, 160)
            for s in range(steps + 1):
                px = ax + (bx - ax) * s / steps - cam
                py = ay + (by - ay) * s / steps
                if 0 <= px <= VIEW_W:
                    pygame.draw.circle(surf, col, (int(px), int(py) + 8), 1)
        # nodes
        for i, (nx, ny) in enumerate(NODE_POS):
            sx = nx - cam
            if not -24 <= sx <= VIEW_W + 24:
                continue
            locked = i >= unlocked
            cleared = str(i) in self.app.save["best"]
            castle = LEVELS[i]["boss_hp"] > 0
            if castle:
                self._draw_castle(surf, sx, ny + 8, locked)
            else:
                col = (110, 110, 120) if locked else \
                    (120, 220, 120) if cleared else (235, 70, 60)
                pygame.draw.circle(surf, (30, 30, 40), (sx, ny + 8), 7)
                pygame.draw.circle(surf, col, (sx, ny + 8), 5)
            if i == self.node and (self.x, self.y) == NODE_POS[self.node]:
                lv = LEVELS[i]
                text(surf, f"{lv['world']}-{lv['index']}", sx, ny + 18,
                     (255, 255, 255), 7, center=True)
        # hero token
        color = CHARACTERS[self.app.save["character"]]["color"]
        frames = self.app.sprites.heroes[(color, False)]["small"]
        moving = (self.x, self.y) != NODE_POS[self.target]
        img = frames[int(self.walk_t * 8) % 2] if moving else frames[0]
        if moving and NODE_POS[self.target][0] < self.x:
            img = pygame.transform.flip(img, True, False)
        surf.blit(img, (int(self.x - cam) - 8, int(self.y) - 10))
        # header + info bar
        lv = LEVELS[self.node]
        wname = ["Green Hills", "Sandy Dunes", "Frostpeak"][lv["world"] - 1]
        text(surf, wname, VIEW_W // 2, 8, (255, 255, 255), 12, center=True)
        box(surf, 0, VIEW_H - 60, VIEW_W, 26, (0, 0, 40))
        text(surf, f"{lv['world']}-{lv['index']}  {lv['name']}", 8, VIEW_H - 54,
             (255, 224, 88), 9)
        best = self.app.save["best"].get(str(self.node))
        if best:
            text(surf, f"best {best['score']}", VIEW_W - 78, VIEW_H - 54,
                 (160, 255, 160), 8)
        text(surf, f"lives x{self.app.session_lives}", VIEW_W - 60, VIEW_H - 44,
             (255, 255, 255), 8)
        text(surf, "arrows: travel   enter: play   esc: title",
             8, VIEW_H - 44, (220, 220, 240), 7)

    @staticmethod
    def _draw_castle(surf, x, y, locked):
        body = (110, 110, 120) if locked else (150, 150, 162)
        dark = (70, 70, 80)
        pygame.draw.rect(surf, body, (x - 8, y - 8, 16, 12))
        for tx in (-8, -2, 4):
            pygame.draw.rect(surf, body, (x + tx, y - 12, 4, 5))
        pygame.draw.rect(surf, dark, (x - 2, y - 2, 4, 6))
        if not locked:
            pygame.draw.polygon(surf, (235, 70, 60),
                                [(x, y - 16), (x, y - 11), (x + 5, y - 14)])
            pygame.draw.line(surf, (240, 240, 240), (x, y - 16), (x, y - 11))
