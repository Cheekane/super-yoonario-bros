"""Tile map: parsing, collision queries, tile mutation, and rendering."""
import pygame

from .constants import TILE, VIEW_W, VIEW_H
from . import levels as leveldata

SOLID = set("XB?MU=[]{}b#TJ")
ONEWAY = "-"
HAZARD_SPIKE = "^"
HAZARD_LAVA = "L"
BUMPABLE = set("B?MU")
EMPTY = "."


class Level:
    def __init__(self, level_id):
        self.id = level_id
        info = leveldata.LEVELS[level_id]
        self.info = info
        self.theme = info["theme"]
        self.ice = info["ice"]
        self.boss_hp = info["boss_hp"]
        rows = info["build"]()
        self.h = len(rows)
        self.w = len(rows[0])
        self.grid = [list(r) for r in rows]
        self.diffs = {}                     # (tx,ty) -> code, for net sync
        self.spawn = (2 * TILE, 2 * TILE)
        self.enemy_spawns = []              # (kind, tx, ty)
        self.coin_spawns = []               # (tx, ty)
        self.platform_spawns = []           # (axis, tx, ty)
        self.checkpoints = []               # (tx, ty) sorted by x
        self.flag = None                    # (tx, ty_top, ty_bottom)
        self.turrets = []                   # (tx, ty) cannon blocks
        self.firebars = []                  # (tx, ty) rotating fire pivots
        self.boss_spawn = None
        self._extract()
        self.pixel_w = self.w * TILE
        self.pixel_h = self.h * TILE

    # -- parsing --

    def _extract(self):
        g = self.grid
        for ty in range(self.h):
            for tx in range(self.w):
                c = g[ty][tx]
                if c == "P":
                    self.spawn = (tx * TILE, ty * TILE)
                    g[ty][tx] = EMPTY
                elif c in "EKSWHD":
                    self.enemy_spawns.append(({"E": "grub", "K": "shell",
                                               "S": "spiny", "W": "flit",
                                               "H": "hopper", "D": "dozer"}[c],
                                              tx, ty))
                    g[ty][tx] = EMPTY
                elif c == "T":
                    self.turrets.append((tx, ty))
                elif c == "R":
                    self.firebars.append((tx, ty))
                    g[ty][tx] = EMPTY
                elif c == "C":
                    self.coin_spawns.append((tx, ty))
                    g[ty][tx] = EMPTY
                elif c == "o":
                    self.platform_spawns.append(("h", tx, ty))
                    g[ty][tx] = EMPTY
                elif c == "v":
                    self.platform_spawns.append(("v", tx, ty))
                    g[ty][tx] = EMPTY
                elif c == "A":
                    self.checkpoints.append((tx, ty))
                    g[ty][tx] = EMPTY
                elif c == "*":
                    self.boss_spawn = (tx, ty)
                    g[ty][tx] = EMPTY
                elif c == "(":
                    self.enemy_spawns.append(("plant", tx, ty))
                    g[ty][tx] = "["
                    if tx + 1 < self.w and g[ty][tx + 1] == ")":
                        g[ty][tx + 1] = "]"
                elif c == "F":
                    ty2 = ty
                    while ty2 + 1 < self.h and g[ty2 + 1][tx] not in SOLID:
                        ty2 += 1
                    self.flag = (tx, ty, ty2)
                    g[ty][tx] = EMPTY
        self.checkpoints.sort()

    # -- queries --

    def tile(self, tx, ty):
        if 0 <= tx < self.w and 0 <= ty < self.h:
            return self.grid[ty][tx]
        if tx < 0 or tx >= self.w:
            return "X"                       # level edges are walls
        return EMPTY                         # open above and below

    def is_solid(self, tx, ty):
        return self.tile(tx, ty) in SOLID

    def is_oneway(self, tx, ty):
        return self.tile(tx, ty) == ONEWAY

    def set_tile(self, tx, ty, code):
        if 0 <= tx < self.w and 0 <= ty < self.h:
            self.grid[ty][tx] = code
            self.diffs[(tx, ty)] = code

    def apply_diffs(self, diffs):
        """Apply [(tx,ty,code), ...] from a network snapshot."""
        for tx, ty, code in diffs:
            if self.grid[ty][tx] != code:
                self.grid[ty][tx] = code
                self.diffs[(tx, ty)] = code

    def diff_list(self):
        return [(tx, ty, c) for (tx, ty), c in self.diffs.items()]

    def rect_hits(self, rect, pred):
        """Tiles matching pred(code) that intersect rect. Returns [(tx,ty,code)]."""
        x0 = max(0, rect.left // TILE)
        x1 = min(self.w - 1, (rect.right - 1) // TILE)
        y0 = max(0, rect.top // TILE)
        y1 = min(self.h - 1, (rect.bottom - 1) // TILE)
        out = []
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                c = self.grid[ty][tx]
                if pred(c):
                    out.append((tx, ty, c))
        return out

    # -- rendering --

    def draw(self, surf, sprites, cam_x, cam_y, anim_t):
        tiles = sprites.tiles[self.theme]
        qframe = tiles["qblock"] if int(anim_t * 3) % 2 == 0 else tiles["qblock2"]
        lava = tiles["lava"] if int(anim_t * 4) % 2 == 0 else tiles["lava2"]
        x0 = max(0, int(cam_x) // TILE)
        x1 = min(self.w - 1, (int(cam_x) + VIEW_W) // TILE + 1)
        y0 = max(0, int(cam_y) // TILE)
        y1 = min(self.h - 1, (int(cam_y) + VIEW_H) // TILE + 1)
        g = self.grid
        for ty in range(y0, y1 + 1):
            for tx in range(x0, x1 + 1):
                c = g[ty][tx]
                if c == EMPTY:
                    continue
                px, py = tx * TILE - int(cam_x), ty * TILE - int(cam_y)
                if c == "X":
                    above = g[ty - 1][tx] if ty > 0 else EMPTY
                    surf.blit(tiles["ground" if above not in SOLID else "dirt"], (px, py))
                elif c == "B":
                    surf.blit(tiles["brick"], (px, py))
                elif c in "?MU":
                    surf.blit(qframe, (px, py))
                elif c == "#":
                    surf.blit(tiles["used"], (px, py))
                elif c == "=":
                    surf.blit(tiles["solid"], (px, py))
                elif c == "-":
                    surf.blit(tiles["platform"], (px, py))
                elif c == "[":
                    surf.blit(tiles["pipe_tl"], (px, py))
                elif c == "]":
                    surf.blit(tiles["pipe_tr"], (px, py))
                elif c == "{":
                    surf.blit(tiles["pipe_l"], (px, py))
                elif c == "}":
                    surf.blit(tiles["pipe_r"], (px, py))
                elif c == "^":
                    surf.blit(tiles["spike"], (px, py))
                elif c == "L":
                    surf.blit(lava, (px, py))
                elif c == "b":
                    surf.blit(tiles["bridge"], (px, py))
                elif c == "T":
                    surf.blit(tiles["turret"], (px, py))
                elif c == "J":
                    surf.blit(tiles["spring"], (px, py))
        # flag pole
        if self.flag:
            tx, ty_top, ty_bot = self.flag
            px = tx * TILE - int(cam_x)
            for ty in range(ty_top, ty_bot + 1):
                py = ty * TILE - int(cam_y)
                surf.blit(tiles["pole" if ty > ty_top else "flag"], (px, py))
        # checkpoints
        for tx, ty in self.checkpoints:
            surf.blit(tiles["checkpoint"],
                      (tx * TILE - int(cam_x), (ty - 1) * TILE - int(cam_y)))
