"""Game world simulation.

Authority model (for low latency):
- Each client is authoritative over its OWN player and fireballs: zero input lag.
- The host is authoritative over the world: enemies, items, blocks, coins,
  boss, timer, level-clear.
- Clients apply world effects optimistically (stomps, bumps, coin grabs) and
  send claims; the host validates and rebroadcasts the authoritative result.
In single-player / on the host, authority=True and claims resolve instantly.
"""
import math

import pygame

from .constants import (
    TILE, VIEW_W, VIEW_H, STOMP_BOUNCE, STOMP_BOUNCE_HELD, RESPAWN_DELAY,
    SPAWN_INVULN, SCORE_COIN, SCORE_STOMP, SCORE_FIREBALL_KILL, SCORE_POWERUP,
    SCORE_1UP, SCORE_FLAG_BASE, SCORE_BOSS, LEVEL_TIME, SCORE_KICK,
    COINS_PER_LIFE, CANNON_COOLDOWN, CANNON_RANGE, FIREBAR_SPEED,
    FIREBAR_FLAMES,
)
import math as _math
from .level import Level
from .entities import (
    Player, Coin, Fireball, SpikeBall, Particle, Shell, Boss, Plant, Spiny,
    make_enemy, enemy_from_state, ITEM_CLASSES, Item,
)


class Camera:
    def __init__(self, level):
        self.x = 0.0
        self.y = 0.0
        self.level = level

    def follow(self, target, dt):
        tx = target.cx - VIEW_W / 2
        ty = target.y + target.h / 2 - VIEW_H / 2
        k = min(1.0, 8.0 * dt)
        self.x += (tx - self.x) * k
        self.y += (ty - self.y) * k
        self.x = max(0.0, min(self.x, self.level.pixel_w - VIEW_W))
        self.y = max(0.0, min(self.y, self.level.pixel_h - VIEW_H))


class World:
    def __init__(self, level_id, audio, sprites, authority=True):
        self.level = Level(level_id)
        self.audio = audio
        self.sprites = sprites
        self.authority = authority
        self.players = {}                   # pid -> Player
        self.local_pid = 0
        self.enemies = []
        self.items = []
        self.coins = {}                     # cid -> Coin
        self.fireballs = []                 # local player's fireballs
        self.remote_fireballs = {}          # pid -> [[x,y],...] render-only
        self.spikeballs = []
        self.platforms = []
        self.particles = []
        self.t = 0.0
        self.time_left = float(LEVEL_TIME)
        self.cleared = False
        self.clear_t = 0.0
        self.clear_pid = None
        self.camera = Camera(self.level)
        self.outbox = []                    # client -> host claims
        self.events = []                    # host -> clients events [seq, type, data]
        self.ev_seq = 0
        self.applied_ev = 0                 # client: last applied event seq
        self._next_eid = 0
        self._next_iid = 0
        self._next_fid = 0
        self._turret_cd = {t: CANNON_COOLDOWN * 0.5 for t in self.level.turrets}
        self._populate()

    # ---------------------------------------------------------------- setup

    def _populate(self):
        for tx, ty in self.level.coin_spawns:
            self.coins[(tx, ty)] = Coin(tx, ty)
        for axis, tx, ty in self.level.platform_spawns:
            self.platforms.append(MovingPlatform(axis, tx, ty))
        if self.authority:
            for kind, tx, ty in self.level.enemy_spawns:
                self.enemies.append(make_enemy(kind, self._eid(), tx, ty))
            if self.level.boss_spawn:
                tx, ty = self.level.boss_spawn
                self.enemies.append(make_enemy("boss", self._eid(), tx, ty,
                                               self.level.boss_hp))

    def _eid(self):
        self._next_eid += 1
        return self._next_eid

    def add_player(self, pid, char_idx, name, local):
        p = Player(pid, char_idx, name)
        sx, sy = self.level.spawn
        p.x, p.y = sx + pid * 14, sy
        p.local = local
        self.players[pid] = p
        if local:
            self.local_pid = pid
        return p

    @property
    def local_player(self):
        return self.players.get(self.local_pid)

    # ---------------------------------------------------------------- update

    def update(self, dt, inp):
        self.t += dt
        if self.authority and not self.cleared:
            self.time_left = max(0.0, self.time_left - dt)
        for pl in self.platforms:
            pl.update(self.t)

        me = self.local_player
        if me:
            if self.cleared:
                inp = {"right": me.x < self.clear_walk_target(),
                       "jump": False, "run": False}
            me.update(inp, self.level, dt, self)
            if not me.dead:
                self.player_world_collisions(me)
            else:
                me.respawn_t += dt
                if me.respawn_t > RESPAWN_DELAY and not self.cleared \
                        and me.lives > 0:
                    self.respawn(me)
            for fb in self.fireballs:
                fb.update(self.level, dt, self)
                if fb.alive:
                    self.fireball_hits(fb)
            self.fireballs = [f for f in self.fireballs if f.alive]

        if self.authority:
            for e in self.enemies:
                e.update(self.level, dt, self)
            self.enemies = [e for e in self.enemies if e.alive]
            for it in self.items:
                it.update(self.level, dt, self)
            self.items = [i for i in self.items if i.alive]
            for sb in self.spikeballs:
                sb.update(self.level, dt, self)
            self.spikeballs = [s for s in self.spikeballs if s.alive]
        else:
            # cosmetic animation for ghosts (positions come from snapshots)
            for e in self.enemies:
                e.anim_t += dt
                if e.squash_t > 0:
                    e.squash_t -= dt
                if e.flip_dead:
                    e.update(self.level, dt, self)
            self.enemies = [e for e in self.enemies if e.alive]

        if self.authority and not self.cleared:
            self.update_turrets(dt)

        if me and not me.dead and not self.cleared:
            self.player_enemy_collisions(me)
            self.player_item_collisions(me)
            self.check_flag(me)
            self.firebar_collisions(me)

        self.particles = [p for p in self.particles if p.update(dt)]
        if self.cleared:
            self.clear_t += dt
        if me:
            target = me
            if self.spectating(me):         # out of lives: watch a teammate
                for p in self.players.values():
                    if not p.dead:
                        target = p
                        break
            self.camera.follow(target, dt)

    def spectating(self, p):
        return p.dead and p.lives <= 0

    def local_out(self):
        """Local player is out of lives (past the respawn grace)."""
        me = self.local_player
        return bool(me and self.spectating(me) and me.respawn_t > RESPAWN_DELAY)

    def all_out(self):
        """Every player in the session is out of lives."""
        return all(self.spectating(p) for p in self.players.values())

    # ------------------------------------------------------- player collisions

    def player_world_collisions(self, p):
        r = p.rect
        # hazards
        if self.level.rect_hits(r.inflate(-4, -2), lambda c: c == "^"):
            p.damage(self)
        if self.level.rect_hits(r, lambda c: c == "L"):
            p.kill(self)
        if p.y > self.level.pixel_h + 24:
            p.kill(self)
        # coins
        for cid, coin in list(self.coins.items()):
            if r.colliderect(coin.rect):
                self.collect_coin(p, cid)
        # checkpoints
        for tx, ty in self.level.checkpoints:
            cp = (tx * TILE, (ty - 1) * TILE)
            if p.checkpoint != cp and abs(p.cx - (tx * TILE + 8)) < 10:
                p.checkpoint = cp
                self.audio.play("checkpoint")
        # spikeballs
        for sb in self.spikeballs:
            if r.colliderect(sb.rect):
                p.damage(self)

    def player_enemy_collisions(self, p):
        if p.invuln > 0:
            return
        r = p.rect
        for e in self.enemies:
            if not e.alive or e.squash_t > 0 or e.flip_dead:
                continue
            er = e.rect
            if not r.colliderect(er):
                continue
            falling_on = p.vy > 40 and (r.bottom - er.top) < er.h * 0.6 + 6
            if falling_on and e.stompable:
                self.do_stomp(p, e)
            elif isinstance(e, Shell) and e.state == "idle":
                self.do_kick(p, e)
            elif isinstance(e, Boss) and falling_on:
                self.do_stomp(p, e)
            elif e.hurts_on_touch():
                p.damage(self)

    def do_stomp(self, p, e):
        held = p.local and self._jump_held
        p.vy = STOMP_BOUNCE_HELD if held else STOMP_BOUNCE
        p.y = e.rect.top - p.h
        self.audio.play("stomp")
        p.score += SCORE_STOMP
        self.add_score_pop(e.cx, e.y, SCORE_STOMP)
        if self.authority:
            e.stomp(self)
        else:
            if not isinstance(e, (Shell, Boss)):
                e.squash_t = 0.4            # optimistic
            self.outbox.append({"t": "stomp", "eid": e.eid})

    def do_kick(self, p, e):
        if self.authority:
            e.kick_from(p, self)
        else:
            e.state = "slide"
            e.dir = 1 if p.cx < e.cx else -1
            self.outbox.append({"t": "kick", "eid": e.eid,
                                "dir": e.dir})
        p.score += SCORE_KICK

    def player_item_collisions(self, p):
        r = p.rect
        for it in self.items:
            if it.alive and it.emerge <= 0 and r.colliderect(it.rect):
                self.apply_item(p, it.itype)
                it.alive = False
                if self.authority:
                    self.broadcast_event("sfx", {"n": "powerup", "x": it.x})
                else:
                    self.outbox.append({"t": "item", "iid": it.iid})

    def apply_item(self, p, itype):
        if itype == "mushroom":
            if p.form == "small":
                p.set_form("big")
            self.audio.play("powerup")
            p.score += SCORE_POWERUP
        elif itype == "flower":
            p.set_form("fire" if p.form != "small" else "big")
            self.audio.play("powerup")
            p.score += SCORE_POWERUP
        elif itype == "oneup":
            p.lives += 1
            self.audio.play("oneup")
            p.score += SCORE_1UP
        self.add_score_pop(p.cx, p.y, SCORE_POWERUP)

    def fireball_hits(self, fb):
        r = fb.rect
        for e in self.enemies:
            if not e.alive or e.squash_t > 0 or e.flip_dead:
                continue
            if isinstance(e, Plant) and e.out < 0.2:
                continue
            if r.colliderect(e.rect):
                fb.alive = False
                self.audio.play("kick")
                me = self.local_player
                if me:
                    me.score += SCORE_FIREBALL_KILL
                self.add_score_pop(e.cx, e.y, SCORE_FIREBALL_KILL)
                if self.authority:
                    e.fire_kill(self)
                else:
                    if not isinstance(e, Boss):
                        e.flip_dead = True
                        e.vy = -220.0       # optimistic
                    self.outbox.append({"t": "fbkill", "eid": e.eid})
                return

    def check_flag(self, p):
        if self.cleared or not self.level.flag:
            return
        tx, ty_top, ty_bot = self.level.flag
        pole = pygame.Rect(tx * TILE + 4, ty_top * TILE, 8, (ty_bot - ty_top + 1) * TILE)
        if p.rect.colliderect(pole):
            bonus = SCORE_FLAG_BASE + int(self.time_left) * 10
            p.score += bonus
            if self.authority:
                self.trigger_clear(p.pid)
            else:
                self.outbox.append({"t": "flag"})
                self.trigger_clear(p.pid)   # optimistic; host confirms

    def trigger_clear(self, pid):
        if self.cleared:
            return
        self.cleared = True
        self.clear_t = 0.0
        self.clear_pid = pid
        self.audio.play("clear")
        if self.authority:
            self.broadcast_event("clear", {"pid": pid})

    def clear_walk_target(self):
        if self.level.flag:
            return (self.level.flag[0] + 4) * TILE
        me = self.local_player
        return me.x + 40 if me else 0

    # ---------------------------------------------------------- world services

    _jump_held = False

    def set_jump_held(self, held):
        self._jump_held = held

    def sfx_local(self, player, name):
        if player.local:
            self.audio.play(name)
        elif self.on_screen(player.x):
            self.audio.play(name)

    def sfx_at(self, ent, name):
        if self.on_screen(ent.x):
            self.audio.play(name)
        if self.authority:
            self.broadcast_event("sfx", {"n": name, "x": ent.x})

    def on_screen(self, x):
        return self.camera.x - 64 < x < self.camera.x + VIEW_W + 64

    def broadcast_event(self, etype, data):
        self.ev_seq += 1
        self.events.append([self.ev_seq, etype, data])
        if len(self.events) > 60:
            self.events.pop(0)

    def bump_tile(self, tx, ty, player):
        code = self.level.tile(tx, ty)
        if code not in "B?MU":
            if code in "X=[]{}#b":
                self.audio.play("bump")
            return
        if self.authority:
            self.resolve_bump(tx, ty, player)
        else:
            # optimistic: show the result instantly, host confirms via diffs
            if code == "B" and player.form != "small":
                self.level.grid[ty][tx] = "."
                self.audio.play("break")
                self.add_shards(tx, ty)
            elif code == "B":
                self.audio.play("bump")
            else:
                self.level.grid[ty][tx] = "#"
                self.audio.play("coin" if code == "?" else "sprout")
                if code == "?":
                    self.add_coin(player)
                    self.add_coin_pop(tx, ty, player)
            self.outbox.append({"t": "bump", "tx": tx, "ty": ty})
        self.bounce_enemies_above(tx, ty)

    def resolve_bump(self, tx, ty, player):
        code = self.level.tile(tx, ty)
        if code == "B":
            if player.form != "small":
                self.level.set_tile(tx, ty, ".")
                self.audio.play("break")
                self.add_shards(tx, ty)
                self.broadcast_event("sfx", {"n": "break", "x": tx * TILE})
                player.score += 50
            else:
                self.audio.play("bump")
        elif code == "?":
            self.level.set_tile(tx, ty, "#")
            self.audio.play("coin")
            self.add_coin(player)
            self.add_coin_pop(tx, ty, player)
            self.broadcast_event("coinpop", {"tx": tx, "ty": ty, "pid": player.pid})
        elif code in "MU":
            self.level.set_tile(tx, ty, "#")
            self.audio.play("sprout")
            self.broadcast_event("sfx", {"n": "sprout", "x": tx * TILE})
            if code == "U":
                itype = "oneup"
            else:
                itype = "flower" if player.form != "small" else "mushroom"
            self._next_iid += 1
            item = ITEM_CLASSES[itype](self._next_iid, tx * TILE + 1, ty * TILE - 2)
            item.emerge = 0.7
            self.items.append(item)

    def bounce_enemies_above(self, tx, ty):
        if not self.authority:
            return
        zone = pygame.Rect(tx * TILE, (ty - 1) * TILE, TILE, TILE)
        for e in self.enemies:
            if e.alive and e.rect.colliderect(zone):
                e.fire_kill(self)

    def add_coin(self, p):
        p.coins += 1
        p.score += SCORE_COIN
        if p.coins >= COINS_PER_LIFE:
            p.coins -= COINS_PER_LIFE
            p.lives += 1
            self.audio.play("oneup")
            self.add_score_pop(p.cx, p.y - 8, "1UP")

    def collect_coin(self, p, cid):
        if cid not in self.coins:
            return
        del self.coins[cid]
        self.add_coin(p)
        self.audio.play("coin")
        if not self.authority:
            self.outbox.append({"t": "coin", "cid": list(cid)})

    def spawn_fireball(self, p):
        self._next_fid += 1
        fb = Fireball(self._next_fid, p.pid, p.cx + p.facing * 6,
                      p.y + 6, p.facing)
        self.fireballs.append(fb)
        self.audio.play("fireball")

    def shell_hits(self, shell):
        """Sliding shell kills enemies it touches (host only)."""
        r = shell.rect
        for e in self.enemies:
            if e is shell or not e.alive or e.squash_t > 0 or e.flip_dead:
                continue
            if isinstance(e, Boss):
                continue
            if r.colliderect(e.rect):
                e.fire_kill(self)
                self.sfx_at(e, "kick")

    def update_turrets(self, dt):
        for (tx, ty), cd in list(self._turret_cd.items()):
            cd -= dt
            if cd <= 0:
                cx, cy = tx * TILE + 8, ty * TILE + 6
                target = self.nearest_player_x(cx)
                if target is not None and 24 < abs(target - cx) < CANNON_RANGE:
                    d = 1 if target > cx else -1
                    self._next_eid += 1
                    from .entities import CannonBall
                    ball = CannonBall(self._next_eid, cx + d * 12, cy)
                    ball.dir = d
                    self.enemies.append(ball)
                    self.sfx_at(ball, "cannon")
                    cd = CANNON_COOLDOWN
            self._turret_cd[(tx, ty)] = cd

    def firebar_points(self, tx, ty):
        """Flame positions for the bar at (tx,ty) — pure function of world
        time, so host and clients always agree with zero network traffic."""
        cx, cy = tx * TILE + 8, ty * TILE + 8
        ang = self.t * FIREBAR_SPEED + (tx * 0.7 + ty * 1.3)
        return [(cx + _math.cos(ang) * (8 + i * 8),
                 cy + _math.sin(ang) * (8 + i * 8))
                for i in range(FIREBAR_FLAMES)]

    def firebar_collisions(self, p):
        if p.invuln > 0:
            return
        r = p.rect.inflate(2, 2)
        for tx, ty in self.level.firebars:
            if abs(tx * TILE - p.cx) > 80:
                continue
            for fx, fy in self.firebar_points(tx, ty):
                if r.collidepoint(fx, fy):
                    p.damage(self)
                    return

    def nearest_player_pos(self, x, y):
        best, dist = None, 1e9
        for p in self.players.values():
            if not p.dead:
                d = abs(p.cx - x) + abs(p.y - y)
                if d < dist:
                    best, dist = (p.cx, p.y), d
        return best

    def nearest_player_x(self, x):
        best, dist = None, 1e9
        for p in self.players.values():
            if not p.dead:
                d = abs(p.cx - x)
                if d < dist:
                    best, dist = p.cx, d
        return best

    def boss_throw(self, boss):
        if not self.authority:
            return
        self.sfx_at(boss, "throw")
        tx = self.nearest_player_x(boss.cx)
        d = 1 if (tx or boss.cx) >= boss.cx else -1
        for vx, vy in ((70 * d, -220), (110 * d, -180)):
            self._next_fid += 1
            self.spikeballs.append(SpikeBall(self._next_fid, boss.cx, boss.y,
                                             vx, vy))

    def on_boss_dead(self, boss):
        self.audio.play("boss_die")
        me = self.local_player
        if me:
            me.score += SCORE_BOSS
        if self.authority:
            self.broadcast_event("sfx", {"n": "boss_die", "x": boss.x})
            self.trigger_clear(self.local_pid)

    def on_player_death(self, p):
        pass

    def respawn(self, p):
        p.dead = False
        p.respawn_t = 0.0
        p.set_form("small")
        p.vx = p.vy = 0.0
        p.invuln = SPAWN_INVULN
        # multiplayer: rejoin at the nearest living teammate
        anchor = None
        for other in self.players.values():
            if other.pid != p.pid and not other.dead:
                anchor = other
                break
        if anchor:
            p.x, p.y = anchor.x, anchor.y - 24
        elif p.checkpoint:
            p.x, p.y = p.checkpoint
        else:
            p.x, p.y = self.level.spawn
        self.audio.play("respawn")

    # ------------------------------------------------------------- particles

    def add_shards(self, tx, ty):
        cx, cy = tx * TILE + 8, ty * TILE + 8
        for vx, vy in ((-60, -220), (60, -220), (-40, -120), (40, -120)):
            self.particles.append(Particle(cx, cy, vx, vy, "shard", life=1.0))

    def add_coin_pop(self, tx, ty, player):
        self.particles.append(Particle(tx * TILE + 4, ty * TILE - 12, 0, -160,
                                       "coinpop", life=0.45))

    def add_score_pop(self, x, y, score):
        self.particles.append(Particle(x, y - 8, 0, -30, "score",
                                       str(score), life=0.8))


    # ============================== NETWORKING ==============================

    def snapshot(self):
        """Host: authoritative world snapshot."""
        return {
            "t": "snap",
            "time": round(self.t, 3),
            "tl": int(self.time_left),
            "pl": {str(p.pid): p.get_state() for p in self.players.values()},
            "en": [e.get_state() for e in self.enemies],
            "it": [i.get_state() for i in self.items],
            "sb": [[s.sid, round(s.x, 1), round(s.y, 1)] for s in self.spikeballs],
            "fb": self._all_fireballs(),
            "cg": [list(c) for c in self._coins_gone()],
            "td": self.level.diff_list(),
            "ev": self.events[-30:],
            "cl": int(self.cleared),
            "cp": self.clear_pid if self.clear_pid is not None else -1,
        }

    def _coins_gone(self):
        return [cid for cid in self.level.coin_spawns if cid not in self.coins]

    def _all_fireballs(self):
        out = {str(self.local_pid): [[round(f.x, 1), round(f.y, 1)]
                                     for f in self.fireballs]}
        for pid, fbs in self.remote_fireballs.items():
            out[str(pid)] = fbs
        return out

    def apply_snapshot(self, snap, recv_time):
        """Client: reconcile with host's authoritative state."""
        self.time_left = snap["tl"]
        # keep world clock in sync so deterministic platforms match the host
        drift = snap["time"] - self.t
        if abs(drift) > 0.5:
            self.t = snap["time"]
        else:
            self.t += drift * 0.2
        # remote players
        for pid_s, st in snap["pl"].items():
            pid = int(pid_s)
            if pid == self.local_pid:
                continue
            if pid not in self.players:
                p = self.add_player(pid, st["c"], st["n"], local=False)
            p = self.players[pid]
            p.push_remote_state(recv_time, st)
        # drop players not in snapshot
        for pid in list(self.players):
            if pid != self.local_pid and str(pid) not in snap["pl"]:
                del self.players[pid]
        # enemies: reconcile by eid
        have = {e.eid: e for e in self.enemies}
        seen = set()
        for st in snap["en"]:
            eid = st[0]
            seen.add(eid)
            if eid in have:
                have[eid].apply_state(st)
            else:
                self.enemies.append(enemy_from_state(st))
        for e in self.enemies:
            if e.eid not in seen and not e.flip_dead and e.squash_t <= 0:
                e.alive = False
        self.enemies = [e for e in self.enemies if e.alive]
        # items
        have_i = {i.iid: i for i in self.items}
        seen_i = set()
        for st in snap["it"]:
            iid, itype, x, y = st
            seen_i.add(iid)
            if iid in have_i:
                have_i[iid].x, have_i[iid].y = x, y
            else:
                it = ITEM_CLASSES[itype](iid, x, y)
                self.items.append(it)
        self.items = [i for i in self.items if i.iid in seen_i]
        # spikeballs (dumb ghosts)
        self.spikeballs = [SpikeBall(sid, x, y, 0, 0) for sid, x, y in snap["sb"]]
        for s in self.spikeballs:
            s.vy = 0
        # remote fireballs
        self.remote_fireballs = {int(k): v for k, v in snap["fb"].items()
                                 if int(k) != self.local_pid}
        # coins gone
        for cid in snap["cg"]:
            self.coins.pop(tuple(cid), None)
        # tile diffs
        self.level.apply_diffs(snap["td"])
        # events
        for seq, etype, data in snap["ev"]:
            if seq <= self.applied_ev:
                continue
            self.applied_ev = seq
            self.apply_event(etype, data)
        # clear state
        if snap["cl"] and not self.cleared:
            self.trigger_clear(snap["cp"])

    def apply_event(self, etype, data):
        if etype == "sfx":
            if self.on_screen(data["x"]):
                self.audio.play(data["n"])
        elif etype == "coinpop":
            if data.get("pid") != self.local_pid:
                self.add_coin_pop(data["tx"], data["ty"], None)
        elif etype == "clear":
            self.trigger_clear(data.get("pid"))

    def apply_claim(self, pid, msg):
        """Host: validate and apply a claim from client `pid`."""
        p = self.players.get(pid)
        if p is None:
            return
        t = msg["t"]
        if t == "stomp" or t == "fbkill":
            for e in self.enemies:
                if e.eid == msg["eid"] and e.alive and not e.flip_dead \
                        and e.squash_t <= 0:
                    if t == "stomp":
                        e.stomp(self)
                        self.sfx_at(e, "stomp")
                    else:
                        e.fire_kill(self)
                    break
        elif t == "kick":
            for e in self.enemies:
                if e.eid == msg["eid"] and isinstance(e, Shell):
                    e.state = "slide"
                    e.dir = msg.get("dir", 1)
                    self.sfx_at(e, "kick")
                    break
        elif t == "bump":
            self.resolve_bump(msg["tx"], msg["ty"], p)
            self.bounce_enemies_above(msg["tx"], msg["ty"])
        elif t == "coin":
            cid = tuple(msg["cid"])
            if cid in self.coins:
                del self.coins[cid]
        elif t == "item":
            for it in self.items:
                if it.iid == msg["iid"]:
                    it.alive = False
                    break
        elif t == "flag":
            self.trigger_clear(pid)

    def local_pstate(self):
        """Client: own player + fireballs, sent to host."""
        me = self.local_player
        if not me:
            return None
        return {"t": "pstate", "st": me.get_state(),
                "fb": [[round(f.x, 1), round(f.y, 1)] for f in self.fireballs]}

    def apply_pstate(self, pid, msg, recv_time):
        """Host: record a client's player state."""
        st = msg["st"]
        if pid not in self.players:
            self.add_player(pid, st["c"], st["n"], local=False)
        self.players[pid].push_remote_state(recv_time, st)
        self.remote_fireballs[pid] = msg.get("fb", [])


class MovingPlatform:
    """Deterministic platform: position is a pure function of world time,
    so it needs no network sync and predicts perfectly on every client."""
    W, H = 3 * TILE, 8

    def __init__(self, axis, tx, ty):
        self.axis = axis
        self.ox = tx * TILE - TILE
        self.oy = ty * TILE
        self.range = 56 if axis == "h" else 44
        self.period = 4.0
        self.phase = (tx * 0.7 + ty * 1.3) % self.period
        self.x, self.y = self.ox, self.oy
        self.vx = self.vy = 0.0

    def update(self, t):
        k = math.sin((t / self.period + self.phase) * 2 * math.pi)
        dk = math.cos((t / self.period + self.phase) * 2 * math.pi) \
            * 2 * math.pi / self.period
        if self.axis == "h":
            nx = self.ox + k * self.range
            self.vx, self.vy = dk * self.range, 0.0
            self.x, self.y = nx, self.oy
        else:
            ny = self.oy + k * self.range
            self.vx, self.vy = 0.0, dk * self.range
            self.x, self.y = self.ox, ny

    @property
    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.W, self.H)
