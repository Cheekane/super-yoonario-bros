"""Procedural pixel-art sprites and tiles. No external asset files.

Sprites are defined as string grids where each character indexes a palette;
'.' is transparent. Tiles are drawn with primitives, tinted per world theme.
"""
import pygame

from .constants import TILE

# --- Colors -----------------------------------------------------------------

CHAR_COLORS = {
    "red":    ((216, 40, 0), (255, 120, 100)),
    "green":  ((0, 152, 56), (120, 224, 144)),
    "blue":   ((32, 96, 224), (120, 176, 255)),
    "yellow": ((216, 168, 0), (255, 224, 120)),
}

SKIN = (252, 188, 132)
HAIR = (96, 56, 8)
BLACK = (16, 16, 16)
WHITE = (248, 248, 248)
OVERALL = (24, 60, 168)

THEMES = {
    "grass":  {"ground": (200, 112, 48), "grass": (0, 168, 68), "sky": (104, 168, 248),
               "block": (228, 152, 72), "bg": (0, 120, 48)},
    "cave":   {"ground": (60, 88, 168), "grass": (100, 136, 216), "sky": (8, 8, 24),
               "block": (92, 120, 200), "bg": (28, 40, 80)},
    "desert": {"ground": (224, 176, 88), "grass": (240, 208, 120), "sky": (248, 216, 144),
               "block": (232, 188, 104), "bg": (200, 144, 72)},
    "ice":    {"ground": (120, 176, 232), "grass": (224, 240, 255), "sky": (168, 208, 248),
               "block": (152, 200, 244), "bg": (96, 144, 208)},
    "castle": {"ground": (112, 112, 120), "grass": (144, 144, 152), "sky": (16, 8, 16),
               "block": (136, 136, 144), "bg": (56, 48, 56)},
}

# --- Grid builder -------------------------------------------------------------


def build(grid, palette):
    h = len(grid)
    w = max(len(r) for r in grid)
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    for y, row in enumerate(grid):
        for x, ch in enumerate(row):
            if ch != ".":
                surf.set_at((x, y), palette[ch])
    return surf


# --- Hero ---------------------------------------------------------------------

HERO_STAND = [
    "....CCCCCC......",
    "...CCCCCCCCC....",
    "...HHSSSSKS.....",
    "..HSHSSSSKSS....",
    "..HSHHSSSKSSS...",
    "..HHSSSSKKKK....",
    "....SSSSSSS.....",
    "...CCCOOCCC.....",
    "..CCCCOOCCCC....",
    ".SSCCOOOOCCSS...",
    ".SSCOOOOOOCSS...",
    ".SS.OOOOOO.SS...",
    "....OOOOOO......",
    "...OOO..OOO.....",
    "..KKKK..KKKK....",
    ".KKKKK..KKKKK...",
]

HERO_WALK = [
    "....CCCCCC......",
    "...CCCCCCCCC....",
    "...HHSSSSKS.....",
    "..HSHSSSSKSS....",
    "..HSHHSSSKSSS...",
    "..HHSSSSKKKK....",
    "....SSSSSSS.....",
    "...CCCOOCCCSS...",
    "..CCCCOOCCCSS...",
    ".SSCCOOOOCC.....",
    ".SSCOOOOOOC.....",
    "....OOOOOOO.....",
    "...OOOO.OOOO....",
    "..OOO.....OOO...",
    ".KKKK......KKK..",
    "KKKKK......KKKK.",
]

HERO_JUMP = [
    "....CCCCCC..SS..",
    "...CCCCCCCCCSS..",
    "...HHSSSSKS.S...",
    "..HSHSSSSKSC....",
    "..HSHHSSSKSC....",
    "..HHSSSSKKKK....",
    "..S.SSSSSSS.....",
    ".SSCCCOOCCC.....",
    ".SSCCCOOCCCC....",
    "..CCCOOOOCCC....",
    "...COOOOOOC.....",
    "....OOOOOO......",
    "...OOOOOOOO.....",
    "..OOKKK.OOOO....",
    "..KKKKK..KKKK...",
    "..........KKKK..",
]


def _make_big(grid):
    """Stretch a 16-row hero into a ~28-row 'super' form."""
    return grid[0:7] + grid[7:12] + grid[7:12] + grid[11:13] + grid[13:]


def hero_frames(color_name, fire=False):
    """Returns {'small': [stand, walk, jump], 'big': [...]} surfaces."""
    main, _light = CHAR_COLORS[color_name]
    if fire:
        pal = {"C": WHITE, "O": main, "S": SKIN, "H": HAIR, "K": BLACK}
    else:
        pal = {"C": main, "O": OVERALL, "S": SKIN, "H": HAIR, "K": BLACK}
    small = [build(g, pal) for g in (HERO_STAND, HERO_WALK, HERO_JUMP)]
    big = [build(_make_big(g), pal) for g in (HERO_STAND, HERO_WALK, HERO_JUMP)]
    return {"small": small, "big": big}


# --- Enemies --------------------------------------------------------------------

GRUB_1 = [
    "................",
    "................",
    "................",
    "................",
    "................",
    ".....BBBBBB.....",
    "...BBBBBBBBBB...",
    "..BBWKBBBBKWBB..",
    ".BBBWKBBBBKWBBB.",
    ".BBBBBBBBBBBBBB.",
    ".BBBBBBBBBBBBBB.",
    "..CCCCCCCCCCCC..",
    "...CCCCCCCCCC...",
    "..KKKK....KKKK..",
    ".KKKKK....KKKKK.",
    "................",
]
GRUB_2 = GRUB_1[:13] + ["...KKKK..KKKK...", "...KKKK..KKKK...", "................"]
GRUB_SQUASH = ["................"] * 11 + [
    "...BBBBBBBBBB...",
    ".BBBBBBBBBBBBBB.",
    ".BWKBBBBBBBBKWB.",
    ".KKKKKKKKKKKKKK.",
    "................",
]

SHELL_WALK_1 = [
    "................",
    "................",
    "................",
    "......GGG.......",
    ".....GWKGG......",
    ".....GWKGG......",
    ".....GGGGG......",
    "...SSSSSSSS.....",
    "..SSYYYYYYSS....",
    ".SSYYGGGGYYSS...",
    ".SYYGGGGGGYYS...",
    ".SYYGGGGGGYYS...",
    "..SYYGGGGYYS....",
    "...SSSSSSSS.....",
    "...GG....GG.....",
    "..GGG....GGG....",
]
SHELL_WALK_2 = SHELL_WALK_1[:14] + ["....GG..GG......", "....GG..GG......"]
SHELL_IDLE = ["................"] * 6 + [
    "....SSSSSSSS....",
    "..SSYYYYYYYYSS..",
    ".SSYYGGGGGGYYSS.",
    ".SYYGGGGGGGGYYS.",
    ".SYYGGGGGGGGYYS.",
    ".SSYYGGGGGGYYSS.",
    "..SSYYYYYYYYSS..",
    "....SSSSSSSS....",
    "................",
    "................",
]

SPINY_1 = [
    "................",
    "................",
    "................",
    "................",
    "..W....WW....W..",
    "..KW..WKKW..WK..",
    "...KWWKKKKWWK...",
    "...RKKRRRRKKR...",
    "..RRRRRRRRRRRR..",
    ".RRWKRRRRRRKWRR.",
    ".RRKKRRRRRRKKRR.",
    ".RRRRRRRRRRRRRR.",
    "..RRRRRRRRRRRR..",
    "..YYYY....YYYY..",
    ".YYYYY....YYYYY.",
    "................",
]
SPINY_2 = SPINY_1[:13] + ["...YYYY..YYYY...", "...YYYY..YYYY...", "................"]

FLIT_1 = [
    "................",
    "..WW........WW..",
    ".WWWW......WWWW.",
    ".WWWWW....WWWWW.",
    "..WWWWBBBBWWWW..",
    "....BBBBBBBB....",
    "...BBWKBBKWBB...",
    "...BBWKBBKWBB...",
    "...BBBBBBBBBB...",
    "....BBKKKKBB....",
    ".....BBBBBB.....",
    "................",
    "................",
    "................",
    "................",
    "................",
]
FLIT_2 = ["................", "................",
          "..WW........WW..", ".WWWWW....WWWWW."] + FLIT_1[4:11] + ["................"] * 5

PLANT_OPEN = [
    "....RRR..RRR....",
    "...RWWRRRRRWR...",
    "...RWRRRRRRRR...",
    "....RRRRRRRR....",
    "....RRWWWWRR....",
    "....RRRRRRRR....",
    "...RRRRRRRRRR...",
    "..RRRRRRRRRRRR..",
    "..RRWRRRRRRWRR..",
    "..RRRRRRRRRRRR..",
    "...RRRRRRRRRR...",
    "......GGG.......",
    ".....GGGGG......",
    "......GGG.......",
    "......GGG.......",
    "......GGG.......",
]
PLANT_CLOSED = ["................"] * 4 + [
    "....RRRRRRRR....",
    "...RRWWRRWWRR...",
    "..RRRRRRRRRRRR..",
    "..RRWRRRRRRWRR..",
    "..RRRRRRRRRRRR..",
    "...RRRRRRRRRR...",
    "....RRRRRRRR....",
] + PLANT_OPEN[11:]

BOSS = [
    "......YY..YY..YY......",
    "......YYYYYYYYYY......",
    ".......GGGGGGGG.......",
    "......GGWWKGGWWK......",
    "......GGWWKGGWWK......",
    ".......GGGGGGGG.......",
    ".......GGKKKKGG.......",
    "....SSSSSSSSSSSSSS....",
    "..SSDDDDDDDDDDDDDDSS..",
    ".SSDDGGGGGGGGGGGGDDSS.",
    ".SDDGGGGGGGGGGGGGGDDS.",
    ".SDDGGGGWWGGWWGGGGDDS.",
    ".SDDGGGGGGGGGGGGGGDDS.",
    ".SSDDGGGGGGGGGGGGDDSS.",
    "..SSDDDDDDDDDDDDDDSS..",
    "....SSSSSSSSSSSSSS....",
    "...GGG..GGGG...GGG....",
    "..GGGG..GGGG...GGGG...",
]

ENEMY_PAL = {
    "B": (172, 108, 40), "C": (228, 176, 112), "K": BLACK, "W": WHITE,
    "G": (0, 168, 68), "S": (248, 216, 120), "Y": (252, 224, 88),
    "R": (216, 40, 0), "D": (0, 112, 44),
}

# --- Items ----------------------------------------------------------------------

COIN_FRAMES_SRC = [
    ["....YYYYYY......", "...YYYYYYYY.....", "..YYWWYYYYYY....", "..YYWYYYYYYY....",
     "..YYWYYYYYYY....", "..YYWYYYYYYY....", "..YYWYYYYYYY....", "..YYWYYYYYYY....",
     "..YYWYYYYYYY....", "..YYWWYYYYYY....", "...YYYYYYYY.....", "....YYYYYY......"],
    ["......YYYY......", ".....YYYYYY.....", ".....YWWYYY.....", ".....YWYYYY.....",
     ".....YWYYYY.....", ".....YWYYYY.....", ".....YWYYYY.....", ".....YWYYYY.....",
     ".....YWYYYY.....", ".....YWWYYY.....", ".....YYYYYY.....", "......YYYY......"],
    [".......YY.......", ".......YY.......", ".......WY.......", ".......WY.......",
     ".......WY.......", ".......WY.......", ".......WY.......", ".......WY.......",
     ".......WY.......", ".......WY.......", ".......YY.......", ".......YY......."],
]

MUSHROOM = [
    "................",
    ".....RRRRRR.....",
    "...RRWWRRRRRR...",
    "..RRWWRRRRRRRR..",
    "..RWWRRRWWRRRR..",
    ".RRWRRRWWWWRRRR.",
    ".RRRRRRWWWWRRWR.",
    ".RRRRRRRWWRRWWR.",
    ".RRRRRRRRRRRWWR.",
    "..WWWWWWWWWWWW..",
    "...WWKWWWWKWW...",
    "...WWKWWWWKWW...",
    "...WWWWWWWWWW...",
    "....WWWWWWWW....",
    "................",
    "................",
]

FLOWER = [
    "................",
    "....RRR..RRR....",
    "...RYYR..RYYR...",
    "...RYWYRRYWYR...",
    "...RYYYYYYYYR...",
    "....RYYWWYYR....",
    "....RYYWWYYR....",
    "...RYYYYYYYYR...",
    "...RYWYRRYWYR...",
    "...RYYR..RYYR...",
    "....RRR..RRR....",
    "......GGG.......",
    "...G..GGG..G....",
    "...GG.GGG.GG....",
    "....GGGGGGG.....",
    "......GGG.......",
]

ONEUP = [r.replace("R", "G") for r in MUSHROOM]

FIREBALL = [
    "....OO..",
    "..OOYYO.",
    ".OYYWYO.",
    ".OYWWYO.",
    ".OYYYYO.",
    "..OOOO..",
]

ITEM_PAL = {
    "Y": (252, 224, 88), "W": WHITE, "R": (216, 40, 0), "G": (0, 168, 68),
    "K": BLACK, "O": (255, 120, 20),
}


# --- Sprite bank ------------------------------------------------------------------

class Sprites:
    """Builds every surface once; access via attributes."""

    def __init__(self):
        ep, ip = ENEMY_PAL, ITEM_PAL
        self.heroes = {}          # (color, fire) -> {'small': [...], 'big': [...]}
        for color in CHAR_COLORS:
            self.heroes[(color, False)] = hero_frames(color, False)
            self.heroes[(color, True)] = hero_frames(color, True)
        self.grub = [build(GRUB_1, ep), build(GRUB_2, ep)]
        self.grub_squash = build(GRUB_SQUASH, ep)
        self.shell_walk = [build(SHELL_WALK_1, ep), build(SHELL_WALK_2, ep)]
        self.shell = build(SHELL_IDLE, ep)
        self.spiny = [build(SPINY_1, ep), build(SPINY_2, ep)]
        self.flit = [build(FLIT_1, ep), build(FLIT_2, ep)]
        self.plant = [build(PLANT_OPEN, ep), build(PLANT_CLOSED, ep)]
        self.boss = build(BOSS, ep)
        self.coin = [build(g, ip) for g in COIN_FRAMES_SRC]
        self.coin.append(pygame.transform.flip(self.coin[1], True, False))
        self.mushroom = build(MUSHROOM, ip)
        self.flower = build(FLOWER, ip)
        self.oneup = build(ONEUP, ip)
        self.fireball = build(FIREBALL, ip)
        self.spike_ball = self._spike_ball()
        self.tiles = {theme: self._build_tiles(THEMES[theme]) for theme in THEMES}

    # -- tiles --

    def _build_tiles(self, th):
        t = {}
        t["ground"] = self._ground(th["ground"], th["grass"])
        t["dirt"] = self._dirt(th["ground"])
        t["brick"] = self._brick(th["block"])
        t["solid"] = self._solid(th["block"])
        t["qblock"] = self._qblock(False)
        t["qblock2"] = self._qblock(True)
        t["used"] = self._used()
        t["platform"] = self._platform(th["block"])
        t["pipe_tl"], t["pipe_tr"], t["pipe_l"], t["pipe_r"] = self._pipe()
        t["spike"] = self._spike()
        t["lava"], t["lava2"] = self._lava()
        t["pole"] = self._pole()
        t["flag"] = self._flag()
        t["checkpoint"] = self._checkpoint()
        t["bridge"] = self._bridge()
        return t

    @staticmethod
    def _dark(c, f=0.6):
        return tuple(int(v * f) for v in c)

    @staticmethod
    def _light(c, f=1.35):
        return tuple(min(255, int(v * f)) for v in c)

    def _ground(self, ground, grass):
        s = pygame.Surface((TILE, TILE))
        s.fill(ground)
        pygame.draw.rect(s, grass, (0, 0, TILE, 5))
        pygame.draw.rect(s, self._light(grass), (0, 0, TILE, 2))
        for x in (2, 7, 12):
            pygame.draw.rect(s, self._light(grass, 1.15), (x, 3, 2, 3))
        pygame.draw.rect(s, self._dark(ground), (3, 9, 3, 3))
        pygame.draw.rect(s, self._dark(ground), (10, 12, 3, 3))
        pygame.draw.line(s, self._dark(ground), (0, TILE - 1), (TILE, TILE - 1))
        return s

    def _dirt(self, ground):
        s = pygame.Surface((TILE, TILE))
        s.fill(self._dark(ground, 0.8))
        for x, y in ((2, 3), (9, 6), (4, 11), (12, 13), (7, 1)):
            pygame.draw.rect(s, self._dark(ground, 0.6), (x, y, 3, 2))
        return s

    def _brick(self, block):
        s = pygame.Surface((TILE, TILE))
        s.fill(block)
        m = self._dark(block, 0.45)
        for y in (0, 8):
            pygame.draw.line(s, m, (0, y + 7), (TILE, y + 7))
        pygame.draw.line(s, m, (7, 0), (7, 7))
        pygame.draw.line(s, m, (3, 8), (3, 15))
        pygame.draw.line(s, m, (11, 8), (11, 15))
        pygame.draw.line(s, self._light(block), (0, 0), (TILE, 0))
        return s

    def _solid(self, block):
        s = pygame.Surface((TILE, TILE))
        s.fill(block)
        pygame.draw.rect(s, self._light(block), (0, 0, TILE, 2))
        pygame.draw.rect(s, self._light(block), (0, 0, 2, TILE))
        pygame.draw.rect(s, self._dark(block, 0.5), (0, TILE - 2, TILE, 2))
        pygame.draw.rect(s, self._dark(block, 0.5), (TILE - 2, 0, 2, TILE))
        return s

    def _qblock(self, dim):
        c = (216, 160, 32) if dim else (252, 188, 60)
        s = pygame.Surface((TILE, TILE))
        s.fill(c)
        pygame.draw.rect(s, self._light(c), (0, 0, TILE, 2))
        pygame.draw.rect(s, self._dark(c, 0.5), (0, TILE - 2, TILE, 2))
        pygame.draw.rect(s, self._dark(c, 0.5), (TILE - 2, 0, 2, TILE))
        q = WHITE if not dim else (232, 208, 140)
        # hand-drawn '?'
        pygame.draw.rect(s, q, (5, 3, 6, 2))
        pygame.draw.rect(s, q, (9, 5, 2, 3))
        pygame.draw.rect(s, q, (7, 7, 3, 2))
        pygame.draw.rect(s, q, (7, 11, 2, 2))
        for x, y in ((3, 3), (3, 12), (12, 3), (12, 12)):
            s.set_at((x, y), BLACK)
        return s

    def _used(self):
        c = (168, 120, 72)
        s = self._solid(c)
        for x, y in ((3, 3), (3, 12), (12, 3), (12, 12)):
            s.set_at((x, y), BLACK)
        return s

    def _platform(self, block):
        s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        c = self._light(block, 1.1)
        pygame.draw.rect(s, c, (0, 0, TILE, 6))
        pygame.draw.rect(s, self._light(block, 1.3), (0, 0, TILE, 2))
        pygame.draw.rect(s, self._dark(block, 0.6), (0, 4, TILE, 2))
        for x in (2, 13):
            pygame.draw.rect(s, self._dark(block, 0.6), (x, 2, 1, 2))
        return s

    def _pipe(self):
        g, gl, gd = (0, 168, 68), (152, 248, 152), (0, 100, 40)
        tl = pygame.Surface((TILE, TILE))
        tl.fill(g)
        pygame.draw.rect(tl, gl, (2, 0, 3, TILE))
        pygame.draw.rect(tl, gd, (0, 0, 1, TILE))
        pygame.draw.rect(tl, gd, (0, TILE - 2, TILE, 2))
        pygame.draw.rect(tl, gl, (0, 0, TILE, 2))
        tr = pygame.transform.flip(tl, True, False)
        bl = pygame.Surface((TILE, TILE))
        bl.fill(g)
        pygame.draw.rect(bl, gl, (4, 0, 3, TILE))
        pygame.draw.rect(bl, gd, (1, 0, 1, TILE))
        br = pygame.transform.flip(bl, True, False)
        return tl, tr, bl, br

    def _spike(self):
        s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        c, cl = (160, 160, 176), (216, 216, 232)
        for i, x in enumerate((0, 8)):
            pygame.draw.polygon(s, c, [(x, TILE), (x + 8, TILE), (x + 4, 4)])
            pygame.draw.line(s, cl, (x + 4, 4), (x, TILE))
        return s

    def _lava(self):
        frames = []
        for k in range(2):
            s = pygame.Surface((TILE, TILE))
            s.fill((224, 80, 0))
            pygame.draw.rect(s, (255, 160, 32), (0, 0, TILE, 3))
            for i, x in enumerate((1, 6, 11)):
                y = 5 + ((i + k) % 2) * 4
                pygame.draw.rect(s, (255, 160, 32), (x, y, 3, 2))
            frames.append(s)
        return frames

    def _pole(self):
        s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        pygame.draw.rect(s, (0, 168, 68), (7, 0, 3, TILE))
        pygame.draw.rect(s, (152, 248, 152), (7, 0, 1, TILE))
        return s

    def _flag(self):
        s = self._pole()
        pygame.draw.circle(s, (252, 224, 88), (8, 3), 3)
        pygame.draw.polygon(s, (216, 40, 0), [(7, 4), (7, 12), (0, 8)])
        return s

    def _checkpoint(self):
        s = pygame.Surface((TILE, TILE * 2), pygame.SRCALPHA)
        pygame.draw.rect(s, (200, 200, 208), (7, 0, 2, TILE * 2))
        pygame.draw.polygon(s, (120, 120, 128), [(9, 2), (9, 9), (15, 5)])
        return s

    def _bridge(self):
        s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
        c = (200, 112, 48)
        pygame.draw.rect(s, c, (0, 0, TILE, 6))
        for x in range(0, TILE, 4):
            pygame.draw.line(s, self._dark(c, 0.55), (x, 0), (x, 5))
        pygame.draw.rect(s, self._light(c), (0, 0, TILE, 1))
        return s

    def _spike_ball(self):
        s = pygame.Surface((10, 10), pygame.SRCALPHA)
        pygame.draw.circle(s, (160, 160, 176), (5, 5), 4)
        for dx, dy in ((0, -5), (0, 5), (-5, 0), (5, 0), (-4, -4), (4, 4), (-4, 4), (4, -4)):
            pygame.draw.line(s, (216, 216, 232), (5, 5), (5 + dx, 5 + dy))
        return s
