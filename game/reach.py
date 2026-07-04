"""Level reachability checker.

Models the player's jump envelope (derived from the physics constants:
~4 tiles of jump height, ~7 tiles of horizontal reach) and BFS-explores the
standing positions of a level. Used by the tests to prove that the goal,
checkpoints and power-ups of every level can actually be reached — an
impossible jump fails the build instead of shipping.
"""
from collections import deque

from .constants import TILE
from .level import Level, SOLID

MAX_UP = 4          # tiles of reliable jump height
MAX_DX_FLAT = 6     # horizontal tiles clearable on a flat jump (conservative)
MAX_DX = 8          # absolute cap (running jump with drop)


def jump_ok(dx, dy):
    """Can the player move dx tiles horizontally, dy tiles vertically
    (dy < 0 = up) in a single jump/fall? Conservative envelope."""
    adx = abs(dx)
    if dy < 0:                                   # rising
        if -dy > MAX_UP:
            return False
        return adx <= MAX_DX_FLAT - (-dy)        # height costs distance
    # flat or dropping: falling farther grants a little more glide
    return adx <= min(MAX_DX, MAX_DX_FLAT + dy // 3)


class Reach:
    def __init__(self, level_id):
        self.level = Level(level_id)
        self.standing = self._standing_tiles()
        self.reached = self._bfs()

    # -- standing positions --

    def _standable_support(self, tx, ty):
        c = self.level.tile(tx, ty)
        return c in SOLID or c == "-"

    def _clear(self, tx, ty):
        """Tile is passable air for the player's body (not solid/hazard)."""
        c = self.level.tile(tx, ty)
        return c not in SOLID and c not in "^L"

    def _standing_tiles(self):
        lv = self.level
        out = set()
        for ty in range(lv.h):
            for tx in range(lv.w):
                if (self._clear(tx, ty) and self._clear(tx, ty - 1)
                        and self._standable_support(tx, ty + 1)):
                    out.add((tx, ty))
        # moving platforms count as standable across their travel range
        for axis, tx, ty in lv.platform_spawns:
            ox, oy = tx * TILE - TILE, ty * TILE
            if axis == "h":
                x0 = (ox - 56) // TILE
                x1 = (ox + 56 + 3 * TILE) // TILE
                for x in range(x0, x1 + 1):
                    out.add((x, oy // TILE - 1))
            else:
                y0 = (oy - 44) // TILE
                y1 = (oy + 44) // TILE
                for k in range(3):
                    for y in range(y0, y1 + 1):
                        out.add((tx - 1 + k, y - 1))
        return out

    # -- reachability --

    def _spawn_tile(self):
        sx, sy = self.level.spawn
        tx, ty = sx // TILE, sy // TILE
        while ty < self.level.h and (tx, ty) not in self.standing:
            ty += 1
        return (tx, ty)

    def _headroom(self, x, y, tiles):
        """Clear space above the player's head at (x, y) for a jump arc.
        The player is 2 tiles tall, so the head is at y-1; check above it."""
        for k in range(2, tiles + 2):
            if not self._clear(x, y - k):
                return False
        return True

    def _move_ok(self, x, y, dx, dy):
        if not jump_ok(dx, dy):
            return False
        adx = abs(dx)
        if dy < 0:                          # rising: need room to jump up
            return self._headroom(x, y, -dy + 1)
        if adx >= 2:                        # long flat/drop jumps still arc up
            return self._headroom(x, y, 2 if adx <= 4 else 3)
        return True                         # plain walking / stepping down

    SPRING_UP = 5       # tiles of lift from a springboard (without holding jump)

    def _bfs(self):
        start = self._spawn_tile()
        seen = {start}
        q = deque([start])
        standing = self.standing
        while q:
            x, y = q.popleft()
            spring = self.level.tile(x, y + 1) == "J"
            max_up = self.SPRING_UP if spring else MAX_UP
            for dx in range(-MAX_DX, MAX_DX + 1):
                for dy in range(-max_up, self.level.h):
                    t = (x + dx, y + dy)
                    if t in seen or t not in standing:
                        continue
                    if spring and dy < -MAX_UP:
                        ok = abs(dx) <= 4 and self._headroom(x, y, -dy + 1)
                    else:
                        ok = self._move_ok(x, y, dx, dy)
                    if ok:
                        seen.add(t)
                        q.append(t)
        return seen

    def can_reach_near(self, tx, ty, dx=1, up=MAX_UP, down=2):
        """Some reached standing tile within a small window of (tx, ty)."""
        for x in range(tx - dx, tx + dx + 1):
            for y in range(ty - down, ty + up + 1):
                if (x, y) in self.reached:
                    return True
        return False

    # -- checks --

    def problems(self):
        lv = self.level
        out = []
        # goal
        if lv.flag:
            fx, _, fbot = lv.flag
            if not self.can_reach_near(fx, fbot, dx=1, up=lv.h, down=0):
                out.append("flag unreachable")
        if lv.boss_spawn:
            bx, by = lv.boss_spawn
            if not self.can_reach_near(bx, by, dx=6, up=6, down=8):
                out.append("boss arena unreachable")
        # checkpoints
        for tx, ty in lv.checkpoints:
            if not self.can_reach_near(tx, ty, dx=1, up=2, down=2):
                out.append(f"checkpoint at ({tx},{ty}) unreachable")
        # power-up / 1-up / coin blocks must be bumpable from below
        for ty in range(lv.h):
            for tx in range(lv.w):
                if lv.tile(tx, ty) in "?MU":
                    if not any((tx, ty + k) in self.reached for k in (1, 2, 3, 4)):
                        out.append(f"block '{lv.tile(tx, ty)}' at ({tx},{ty}) "
                                   "can't be bumped")
        # loose coins: within collection range of a reached tile
        missing = []
        for tx, ty in lv.coin_spawns:
            near = any((x, y) in self.reached
                       for x in range(tx - 3, tx + 4)
                       for y in range(ty - 1, ty + MAX_UP + 2))
            if not near:
                missing.append((tx, ty))
        if missing:
            out.append(f"{len(missing)} coins unreachable: {missing[:6]}")
        return out


def validate_all():
    from .levels import LEVELS
    problems = {}
    for i, lv in enumerate(LEVELS):
        p = Reach(i).problems()
        if p:
            problems[lv["name"]] = p
    return problems
