"""Players, enemies, items and projectiles."""
import math

import pygame

from .constants import (
    TILE, GRAVITY, MAX_FALL, JUMP_VEL, JUMP_CUT, JUMP_HOLD_GRAV, COYOTE_TIME,
    JUMP_BUFFER, WALK_SPEED, RUN_SPEED, ACCEL, AIR_ACCEL, FRICTION, ICE_FRICTION,
    STOMP_BOUNCE, STOMP_BOUNCE_HELD, SMALL_W, SMALL_H, BIG_W, BIG_H, HURT_INVULN,
    SPAWN_INVULN, CHARACTERS, GRUB_SPEED, SHELL_WALK_SPEED, SHELL_SLIDE_SPEED,
    SPINY_SPEED, FLIT_SPEED, FLIT_AMP, PLANT_PERIOD, FIREBALL_SPEED,
    FIREBALL_BOUNCE, START_LIVES, HOPPER_JUMP, HOPPER_SPEED, HOPPER_WAIT,
    DOZER_SPEED, CANNON_SPEED, SPRING_VEL,
)


class Entity:
    def __init__(self, x, y, w, h):
        self.x, self.y = float(x), float(y)
        self.w, self.h = w, h
        self.vx = self.vy = 0.0
        self.alive = True

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    @property
    def cx(self):
        return self.x + self.w / 2


def move_collide(ent, level, dt, oneway=True, platforms=()):
    """Move ent with tile collision. Returns dict with on_ground / hit_wall /
    bumped (list of head-bumped tiles) / on_platform (Platform or None)."""
    res = {"on_ground": False, "hit_wall": False, "bumped": [], "on_platform": None}

    # X axis
    ent.x += ent.vx * dt
    r = ent.rect
    hits = level.rect_hits(r, lambda c: c in level_solid())
    for tx, ty, c in hits:
        trect = pygame.Rect(tx * TILE, ty * TILE, TILE, TILE)
        if r.colliderect(trect):
            if ent.vx > 0:
                ent.x = trect.left - ent.w
            elif ent.vx < 0:
                ent.x = trect.right
            res["hit_wall"] = True
            r = ent.rect

    # Y axis
    old_bottom = ent.rect.bottom
    ent.y += ent.vy * dt
    r = ent.rect
    hits = level.rect_hits(r, lambda c: c in level_solid())
    for tx, ty, c in hits:
        trect = pygame.Rect(tx * TILE, ty * TILE, TILE, TILE)
        if r.colliderect(trect):
            if ent.vy > 0:
                ent.y = trect.top - ent.h
                ent.vy = 0
                res["on_ground"] = True
            elif ent.vy < 0:
                ent.y = trect.bottom
                ent.vy = 0
                res["bumped"].append((tx, ty, c))
            r = ent.rect
    # one-way platforms: only when falling and previous bottom was above the top
    if oneway and ent.vy > 0:
        r = ent.rect
        for tx, ty, c in level.rect_hits(r, lambda c: c == "-"):
            top = ty * TILE
            if old_bottom <= top + 4 and r.bottom > top:
                ent.y = top - ent.h
                ent.vy = 0
                res["on_ground"] = True
    # moving platforms
    if ent.vy >= 0:
        r = ent.rect
        for p in platforms:
            pr = p.rect
            if (r.colliderect(pr) or (r.bottom == pr.top and r.right > pr.left
                                      and r.left < pr.right)) and old_bottom <= pr.top + 6:
                ent.y = pr.top - ent.h
                ent.vy = 0
                res["on_ground"] = True
                res["on_platform"] = p
    # ground probe: sub-pixel gravity oscillation must not flicker on_ground
    # (feet hover <1px above the floor on alternate frames otherwise)
    if not res["on_ground"] and ent.vy >= 0:
        probe = ent.rect.move(0, 1)
        if level.rect_hits(probe, lambda c: c in level_solid()):
            res["on_ground"] = True
        elif oneway:
            bottom = ent.rect.bottom
            for tx, ty, c in level.rect_hits(probe, lambda c: c == "-"):
                if bottom <= ty * TILE + 4:
                    res["on_ground"] = True
                    break
    return res


_SOLID_CACHE = None


def level_solid():
    global _SOLID_CACHE
    if _SOLID_CACHE is None:
        from .level import SOLID
        _SOLID_CACHE = SOLID
    return _SOLID_CACHE


# ================================ PLAYER =====================================

class Player(Entity):
    def __init__(self, pid, char_idx, name, x=0, y=0):
        super().__init__(x, y, SMALL_W, SMALL_H)
        self.pid = pid
        self.char = char_idx
        self.name = name
        self.stats = CHARACTERS[char_idx]
        self.form = "small"                 # small | big | fire
        self.facing = 1
        self.on_ground = False
        self.coyote = 0.0
        self.jump_buf = 0.0
        self.jumping = False
        self.invuln = SPAWN_INVULN
        self.dead = False
        self.respawn_t = 0.0
        self.anim_t = 0.0
        self.fire_cd = 0.0
        self.local = True
        self.score = 0
        self.coins = 0
        self.lives = START_LIVES
        self.checkpoint = None              # (x, y) respawn point
        self.finished = False
        self.platform = None
        # remote interpolation
        self.net_buf = []                   # [(t, statedict)]

    # -- geometry --

    def set_form(self, form):
        if form == self.form:
            return
        bottom = self.y + self.h
        self.form = form
        self.h = SMALL_H if form == "small" else BIG_H
        self.y = bottom - self.h

    # -- simulation (local player only) --

    def update(self, inp, level, dt, world):
        if self.dead:
            self.vy = min(self.vy + GRAVITY * dt, MAX_FALL)
            self.y += self.vy * dt
            return
        st = self.stats
        run = inp.get("run")
        target = (RUN_SPEED if run else WALK_SPEED) * st["speed"]
        ax = (ACCEL if self.on_ground else AIR_ACCEL) * st["accel"]
        move = (1 if inp.get("right") else 0) - (1 if inp.get("left") else 0)
        if move:
            self.facing = move
            if self.vx * move < target:
                self.vx = min(target, self.vx + ax * dt) if move > 0 else \
                    max(-target, self.vx - ax * dt)
        else:
            fr = (ICE_FRICTION if level.ice else FRICTION) if self.on_ground else FRICTION * 0.4
            if self.vx > 0:
                self.vx = max(0.0, self.vx - fr * dt)
            elif self.vx < 0:
                self.vx = min(0.0, self.vx + fr * dt)

        # jumping
        self.coyote = COYOTE_TIME if self.on_ground else max(0.0, self.coyote - dt)
        self.jump_buf = JUMP_BUFFER if inp.get("jump_pressed") else max(0.0, self.jump_buf - dt)
        if self.jump_buf > 0 and self.coyote > 0:
            speed_boost = 1.0 + 0.08 * abs(self.vx) / RUN_SPEED
            self.vy = JUMP_VEL * st["jump"] * speed_boost
            self.jumping = True
            self.coyote = self.jump_buf = 0.0
            world.sfx_local(self, "jump")
        if self.jumping and not inp.get("jump") and self.vy < 0:
            self.vy *= JUMP_CUT
            self.jumping = False

        # gravity (lighter while rising with jump held)
        g = GRAVITY * st["grav"]
        if self.vy < 0 and inp.get("jump"):
            g *= JUMP_HOLD_GRAV
        self.vy = min(self.vy + g * dt, MAX_FALL)

        # ride platform
        if self.platform and self.on_ground:
            self.x += self.platform.vx * dt
            self.y += self.platform.vy * dt

        res = move_collide(self, level, dt, platforms=world.platforms)
        self.on_ground = res["on_ground"]
        self.platform = res["on_platform"]
        if self.on_ground:
            self.jumping = False
            # springboard: launch high (hold jump to go even higher)
            under = level.tile(int(self.cx // TILE), int((self.y + self.h + 2) // TILE))
            if under == "J":
                self.vy = SPRING_VEL * self.stats["jump"]
                self.jumping = False        # spring bounce can't be jump-cut
                self.on_ground = False
                world.sfx_local(self, "spring")
        if res["bumped"] and self.vy == 0:
            # pick the tile most aligned with player's center
            best = min(res["bumped"], key=lambda t: abs((t[0] + 0.5) * TILE - self.cx))
            world.bump_tile(best[0], best[1], self)

        # fireballs
        self.fire_cd = max(0.0, self.fire_cd - dt)
        if inp.get("fire_pressed") and self.form == "fire" and self.fire_cd == 0:
            world.spawn_fireball(self)
            self.fire_cd = 0.35

        self.invuln = max(0.0, self.invuln - dt)
        self.anim_t += dt * (0.5 + abs(self.vx) / WALK_SPEED)

    def damage(self, world):
        if self.invuln > 0 or self.dead:
            return
        if self.form == "fire":
            self.set_form("big")
            self.invuln = HURT_INVULN
            world.sfx_local(self, "hurt")
        elif self.form == "big":
            self.set_form("small")
            self.invuln = HURT_INVULN
            world.sfx_local(self, "hurt")
        else:
            self.kill(world)

    def kill(self, world):
        if self.dead:
            return
        self.lives -= 1
        self.dead = True
        self.vy = -300.0
        self.vx = 0.0
        self.respawn_t = 0.0
        world.sfx_local(self, "die")
        world.on_player_death(self)

    # -- networking --

    def get_state(self):
        return {"pid": self.pid, "x": round(self.x, 1), "y": round(self.y, 1),
                "vx": round(self.vx, 1), "f": self.facing, "form": self.form,
                "d": int(self.dead), "i": int(self.invuln > 0),
                "c": self.char, "n": self.name, "g": int(self.on_ground),
                "sc": self.score, "co": self.coins, "li": self.lives}

    def push_remote_state(self, t, st):
        self.net_buf.append((t, st))
        if len(self.net_buf) > 20:
            self.net_buf.pop(0)

    def interpolate(self, render_t):
        buf = self.net_buf
        if not buf:
            return
        if len(buf) == 1 or render_t <= buf[0][0]:
            st = buf[0][1]
        elif render_t >= buf[-1][0]:
            st = buf[-1][1]
        else:
            st = None
            for i in range(len(buf) - 1):
                t0, s0 = buf[i]
                t1, s1 = buf[i + 1]
                if t0 <= render_t <= t1:
                    k = (render_t - t0) / max(1e-6, t1 - t0)
                    self.x = s0["x"] + (s1["x"] - s0["x"]) * k
                    self.y = s0["y"] + (s1["y"] - s0["y"]) * k
                    st = s1
                    break
            if st is None:
                st = buf[-1][1]
        if st is buf[0][1] or st is buf[-1][1]:
            self.x, self.y = st["x"], st["y"]
        self.facing = st["f"]
        self.vx = st.get("vx", 0)
        new_form = st["form"]
        if new_form != self.form:
            self.set_form(new_form)
        self.dead = bool(st["d"])
        self.invuln = 1.0 if st["i"] else 0.0
        self.char = st["c"]
        self.stats = CHARACTERS[self.char]
        self.name = st["n"]
        self.on_ground = bool(st.get("g", 1))
        self.score = st.get("sc", self.score)
        self.coins = st.get("co", self.coins)
        self.lives = st.get("li", self.lives)
        self.anim_t += 1 / 60 * (0.5 + abs(self.vx) / WALK_SPEED)


# ================================ ENEMIES ====================================

class Enemy(Entity):
    kind = "enemy"
    stompable = True

    def __init__(self, eid, x, y, w, h):
        super().__init__(x, y, w, h)
        self.eid = eid
        self.dir = -1
        self.anim_t = 0.0
        self.squash_t = 0.0                 # >0: playing death anim
        self.flip_dead = False              # knocked off screen (fireball/shell)
        self.net_buf = []

    def hurts_on_touch(self):
        return True

    def update(self, level, dt, world):
        self.anim_t += dt
        if self.squash_t > 0:
            self.squash_t -= dt
            if self.squash_t <= 0:
                self.alive = False
            return
        if self.flip_dead:
            self.vy = min(self.vy + GRAVITY * dt, MAX_FALL)
            self.y += self.vy * dt
            self.x += self.vx * dt
            if self.y > level.pixel_h + 64:
                self.alive = False
            return
        self.tick(level, dt, world)

    def tick(self, level, dt, world):
        pass

    def stomp(self, world):
        """Player bounced on head. Return True if the stomp was lethal."""
        self.squash_t = 0.4
        return True

    def fire_kill(self, world):
        self.flip_dead = True
        self.vy = -220.0
        self.vx = 60.0 * -self.dir

    def get_state(self):
        return [self.eid, self.kind, round(self.x, 1), round(self.y, 1),
                self.dir, int(self.squash_t > 0), int(self.flip_dead), self.extra()]

    def extra(self):
        return 0

    def apply_state(self, st):
        _, _, x, y, d, squash, flip, extra = st
        self.dir = d
        if squash and self.squash_t <= 0:
            self.squash_t = 0.4
        if flip and not self.flip_dead:
            self.flip_dead = True
            self.vy = -220.0
        if not self.flip_dead:
            self.x, self.y = x, y
        self.set_extra(extra)

    def set_extra(self, extra):
        pass


class Walker(Enemy):
    """Shared logic: walk along ground, turn at walls."""
    speed = GRUB_SPEED

    def tick(self, level, dt, world):
        self.vx = self.speed * self.dir
        self.vy = min(self.vy + GRAVITY * dt, MAX_FALL)
        res = move_collide(self, level, dt, oneway=True)
        if res["hit_wall"]:
            self.dir *= -1
        if self.y > level.pixel_h + 64:
            self.alive = False


class Grub(Walker):
    kind = "grub"
    speed = GRUB_SPEED

    def __init__(self, eid, x, y):
        super().__init__(eid, x, y, 13, 11)


class Spiny(Walker):
    kind = "spiny"
    speed = SPINY_SPEED
    stompable = False

    def __init__(self, eid, x, y):
        super().__init__(eid, x, y, 13, 12)


class Shell(Enemy):
    kind = "shell"

    def __init__(self, eid, x, y):
        super().__init__(eid, x, y, 13, 13)
        self.state = "walk"                 # walk | idle | slide
        self.wake_t = 0.0

    def hurts_on_touch(self):
        return self.state in ("walk", "slide")

    def tick(self, level, dt, world):
        if self.state == "walk":
            self.vx = SHELL_WALK_SPEED * self.dir
        elif self.state == "slide":
            self.vx = SHELL_SLIDE_SPEED * self.dir
        else:
            self.vx = 0
            self.wake_t += dt
            if self.wake_t > 6.0:
                self.state = "walk"
                self.wake_t = 0.0
        self.vy = min(self.vy + GRAVITY * dt, MAX_FALL)
        res = move_collide(self, level, dt, oneway=True)
        if res["hit_wall"]:
            self.dir *= -1
            if self.state == "slide":
                world.sfx_at(self, "bump")
        if self.state == "slide":
            world.shell_hits(self)
        if self.y > level.pixel_h + 64:
            self.alive = False

    def stomp(self, world):
        if self.state == "walk":
            self.state = "idle"
            self.wake_t = 0.0
        elif self.state == "slide":
            self.state = "idle"
            self.wake_t = 0.0
        else:
            return self.kick_from(None, world)
        return True

    def kick_from(self, player, world):
        self.state = "slide"
        if player is not None:
            self.dir = 1 if player.cx < self.cx else -1
        world.sfx_at(self, "kick")
        return True

    def extra(self):
        return {"walk": 0, "idle": 1, "slide": 2}[self.state]

    def set_extra(self, extra):
        self.state = ("walk", "idle", "slide")[extra]


class Flit(Enemy):
    kind = "flit"

    def __init__(self, eid, x, y):
        super().__init__(eid, x, y, 13, 10)
        self.anchor_x = x
        self.anchor_y = y
        self.t = 0.0
        self.dive = 0.0                     # 0..1 swoop toward players below

    def tick(self, level, dt, world):
        self.t += dt
        target = world.nearest_player_pos(self.cx, self.y)
        want = 0.0
        if target and abs(target[0] - self.cx) < 56 and target[1] > self.y:
            want = 1.0                      # player underneath: swoop down
        self.dive += (want - self.dive) * min(1.0, 2.5 * dt)
        self.x = self.anchor_x + math.sin(self.t * 0.9) * 40
        self.y = self.anchor_y + math.sin(self.t * 2.2) * FLIT_AMP \
            + self.dive * 44
        self.dir = 1 if math.cos(self.t * 0.9) > 0 else -1

    def extra(self):
        return round(self.dive, 2)

    def set_extra(self, extra):
        if isinstance(extra, (int, float)):
            self.dive = extra


class Plant(Enemy):
    kind = "plant"
    stompable = False

    def __init__(self, eid, tx, ty):
        # anchored to the center of a 2-wide pipe top
        super().__init__(eid, (tx + 1) * TILE - 6, ty * TILE, 12, 16)
        self.base_y = ty * TILE
        self.t = eid % 3 * 0.9              # desync cycles between plants
        self.out = 0.0                      # 0 hidden .. 1 fully out

    def hurts_on_touch(self):
        return self.out > 0.3

    def tick(self, level, dt, world):
        self.t = (self.t + dt) % PLANT_PERIOD
        k = self.t / PLANT_PERIOD
        if k < 0.25:
            self.out = k / 0.25
        elif k < 0.6:
            self.out = 1.0
        elif k < 0.85:
            self.out = 1.0 - (k - 0.6) / 0.25
        else:
            self.out = 0.0
        self.y = self.base_y - 18 * self.out + 2
        self.h = max(2, int(18 * self.out))

    def extra(self):
        return round(self.out, 2)

    def set_extra(self, extra):
        self.out = extra
        self.y = self.base_y - 18 * self.out + 2
        self.h = max(2, int(18 * self.out))


class Dozer(Walker):
    """Smart walker: turns at ledges instead of marching off them."""
    kind = "dozer"
    speed = DOZER_SPEED

    def __init__(self, eid, x, y):
        super().__init__(eid, x, y, 13, 11)

    def tick(self, level, dt, world):
        if self.vy == 0:                    # grounded: probe the ledge ahead
            front = self.cx + (self.w / 2 + 2) * self.dir
            ftx = int(front // TILE)
            fty = int((self.y + self.h + 4) // TILE)
            if not level.is_solid(ftx, fty) and not level.is_oneway(ftx, fty):
                self.dir *= -1
        super().tick(level, dt, world)


class Hopper(Enemy):
    """Frog that waits, then leaps toward the nearest player."""
    kind = "hopper"

    def __init__(self, eid, x, y):
        super().__init__(eid, x, y, 13, 12)
        self.wait = HOPPER_WAIT * (1 + (eid % 3) * 0.3)
        self.grounded = True

    def tick(self, level, dt, world):
        if self.grounded:
            self.vx = 0
            self.wait -= dt
            if self.wait <= 0:
                target = world.nearest_player_x(self.cx)
                if target is not None:
                    self.dir = 1 if target > self.cx else -1
                self.vy = HOPPER_JUMP
                self.vx = HOPPER_SPEED * self.dir
                self.grounded = False
                self.wait = HOPPER_WAIT
        self.vy = min(self.vy + GRAVITY * dt, MAX_FALL)
        res = move_collide(self, level, dt, oneway=True)
        if res["hit_wall"]:
            self.dir *= -1
            self.vx = HOPPER_SPEED * self.dir
        if res["on_ground"] and not self.grounded and self.vy >= 0:
            self.grounded = True
        if self.y > level.pixel_h + 64:
            self.alive = False

    def extra(self):
        return int(self.grounded)

    def set_extra(self, extra):
        if isinstance(extra, int):
            self.grounded = bool(extra)


class CannonBall(Enemy):
    """Slow projectile fired by turret blocks; stompable in mid-air."""
    kind = "cball"

    def __init__(self, eid, x, y):
        super().__init__(eid, x, y, 10, 7)
        self.life = 9.0

    def tick(self, level, dt, world):
        self.life -= dt
        self.x += CANNON_SPEED * self.dir * dt
        if self.life <= 0 or self.x < -32 or self.x > level.pixel_w + 32:
            self.alive = False

    def stomp(self, world):
        self.squash_t = 0.25
        return True


class Boss(Enemy):
    kind = "boss"

    ACTIVATION_RANGE = 176                  # px; sleeps until a player is close

    def __init__(self, eid, x, y, hp):
        super().__init__(eid, x, y, 20, 17)
        self.hp = hp
        self.max_hp = hp
        self.home_x, self.home_y = x, y     # arena anchor
        self.hurt_t = 0.0
        self.jump_t = 1.2
        self.throw_t = 2.5
        self.fire_hits = 0

    def hurts_on_touch(self):
        return True

    def tick(self, level, dt, world):
        self.hurt_t = max(0.0, self.hurt_t - dt)
        target = world.nearest_player_x(self.cx)
        active = target is not None and abs(target - self.cx) < self.ACTIVATION_RANGE
        if active:
            self.dir = 1 if target > self.cx else -1
            speed = 30 + 14 * (self.max_hp - self.hp)
            self.vx = speed * self.dir if self.hurt_t <= 0 else 0
            self.jump_t -= dt
            if self.jump_t <= 0 and self.vy == 0:
                self.vy = -260.0
                self.jump_t = 1.2 + (self.eid % 3) * 0.3
            self.throw_t -= dt
            if self.throw_t <= 0:
                world.boss_throw(self)
                self.throw_t = 2.8 - 0.4 * (self.max_hp - self.hp)
        else:
            self.vx = 0                     # wait in the arena
        # never walk off the arena ledge
        if self.vy == 0 and self.vx != 0:
            front = self.cx + (self.w / 2 + 3) * (1 if self.vx > 0 else -1)
            if not level.is_solid(int(front // TILE),
                                  int((self.y + self.h + 4) // TILE)):
                self.vx = 0
        self.vy = min(self.vy + GRAVITY * dt, MAX_FALL)
        move_collide(self, level, dt, oneway=False)
        # stay near home even if a jump drifts; recover if somehow dropped out
        self.x = max(self.home_x - 84, min(self.x, self.home_x + 84))
        if self.y > level.pixel_h:
            self.x, self.y, self.vy = self.home_x, self.home_y, 0.0

    def stomp(self, world):
        if self.hurt_t > 0:
            return False
        self.hp -= 1
        self.hurt_t = 1.0
        world.sfx_at(self, "boss_hit")
        if self.hp <= 0:
            world.on_boss_dead(self)
            self.flip_dead = True
            self.vy = -260.0
        return True

    def fire_kill(self, world):
        self.fire_hits += 1
        if self.fire_hits >= 4:
            self.fire_hits = 0
            self.stomp(world)
        else:
            world.sfx_at(self, "bump")

    def extra(self):
        return [self.hp, round(self.hurt_t, 2)]

    def set_extra(self, extra):
        self.hp, self.hurt_t = extra


ENEMY_CLASSES = {"grub": Grub, "shell": Shell, "spiny": Spiny,
                 "flit": Flit, "plant": Plant, "boss": Boss,
                 "dozer": Dozer, "hopper": Hopper, "cball": CannonBall}


def make_enemy(kind, eid, tx, ty, boss_hp=3):
    if kind == "plant":
        return Plant(eid, tx, ty)
    if kind == "boss":
        return Boss(eid, tx * TILE - 2, (ty - 1) * TILE, boss_hp)
    cls = ENEMY_CLASSES[kind]
    e = cls(eid, tx * TILE + 1, ty * TILE)
    e.y = (ty + 1) * TILE - e.h
    return e


def enemy_from_state(st):
    eid, kind = st[0], st[1]
    if kind == "plant":
        e = Plant(eid, 0, 0)
        out = st[7]
        e.base_y = st[3] + 18 * out - 2     # reconstruct pipe-top anchor
    elif kind == "boss":
        e = Boss(eid, st[2], st[3], st[7][0])
    else:
        e = ENEMY_CLASSES[kind](eid, st[2], st[3])
    e.apply_state(st)
    return e


# ================================ ITEMS ======================================

class Item(Entity):
    kind = "item"
    itype = "?"

    def __init__(self, iid, x, y, w=13, h=13):
        super().__init__(x, y, w, h)
        self.iid = iid
        self.emerge = 0.0                   # rising-out-of-block animation

    def update(self, level, dt, world):
        if self.emerge > 0:
            self.emerge -= dt
            self.y -= 20 * dt
            return
        self.tick(level, dt, world)

    def tick(self, level, dt, world):
        pass

    def get_state(self):
        return [self.iid, self.itype, round(self.x, 1), round(self.y, 1)]


class Mushroom(Item):
    itype = "mushroom"
    speed = 55.0

    def __init__(self, iid, x, y):
        super().__init__(iid, x, y)
        self.dir = 1

    def tick(self, level, dt, world):
        self.vx = self.speed * self.dir
        self.vy = min(self.vy + GRAVITY * dt, MAX_FALL)
        res = move_collide(self, level, dt)
        if res["hit_wall"]:
            self.dir *= -1
        if self.y > level.pixel_h + 64:
            self.alive = False


class OneUp(Mushroom):
    itype = "oneup"
    speed = 75.0


class Flower(Item):
    itype = "flower"

    def tick(self, level, dt, world):
        self.vy = min(self.vy + GRAVITY * dt, MAX_FALL)
        move_collide(self, level, dt)


ITEM_CLASSES = {"mushroom": Mushroom, "oneup": OneUp, "flower": Flower}


class Fireball(Entity):
    def __init__(self, fid, pid, x, y, direction):
        super().__init__(x, y, 6, 6)
        self.fid = fid
        self.pid = pid
        self.vx = FIREBALL_SPEED * direction
        self.vy = 60.0
        self.life = 2.0

    def update(self, level, dt, world):
        self.life -= dt
        if self.life <= 0:
            self.alive = False
            return
        self.vy = min(self.vy + GRAVITY * 0.8 * dt, MAX_FALL)
        res = move_collide(self, level, dt, oneway=False)
        if res["on_ground"]:
            self.vy = FIREBALL_BOUNCE
        if res["hit_wall"]:
            self.alive = False
        if self.y > level.pixel_h + 32:
            self.alive = False


class SpikeBall(Entity):
    """Boss projectile."""

    def __init__(self, sid, x, y, vx, vy):
        super().__init__(x, y, 9, 9)
        self.sid = sid
        self.vx, self.vy = vx, vy
        self.life = 5.0

    def update(self, level, dt, world):
        self.life -= dt
        self.vy = min(self.vy + GRAVITY * 0.6 * dt, MAX_FALL)
        self.x += self.vx * dt
        self.y += self.vy * dt
        if self.life <= 0 or self.y > level.pixel_h + 32:
            self.alive = False


class Coin(Entity):
    """Static level coin, id = (tx, ty)."""

    def __init__(self, tx, ty):
        super().__init__(tx * TILE + 2, ty * TILE + 2, 12, 12)
        self.cid = (tx, ty)


class Particle:
    """Client-local visual effect: brick shards, score popups, coin pops."""

    def __init__(self, x, y, vx, vy, kind="shard", text="", life=0.8):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.kind = kind
        self.text = text
        self.life = life
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        if self.kind == "shard" or self.kind == "coinpop":
            self.vy += GRAVITY * 0.8 * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        return self.t < self.life
