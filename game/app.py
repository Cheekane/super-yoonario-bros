"""Application shell: main loop, the in-game scene for all roles, victory."""
import time

import pygame

from .constants import (
    VIEW_W, VIEW_H, FPS, DT, SNAP_RATE, PSTATE_RATE, INTERP_DELAY,
)
from .levels import LEVELS
from .sprites import Sprites
from .sfx import Audio
from .save import Save
from .world import World
from . import render
from .hud import draw_hud, text, box
from .menu import Scene, TitleScene, menu_nav, draw_sky


JUMP_KEYS = (pygame.K_z, pygame.K_SPACE, pygame.K_UP, pygame.K_w)
RUN_KEYS = (pygame.K_x, pygame.K_LSHIFT, pygame.K_RSHIFT)


class GameScene(Scene):
    def __init__(self, app, role, level_id, host=None, client=None,
                 first_snap=None):
        super().__init__(app)
        self.role = role                    # sp | host | client
        self.level_id = level_id
        self.host = host
        self.client = client
        self.world = World(level_id, app.audio, app.sprites,
                           authority=(role != "client"))
        pid = client.pid if role == "client" else 0
        self.world.add_player(pid, app.save["character"],
                              app.save["player_name"], local=True)
        if first_snap:
            self.world.apply_snapshot(first_snap, time.time())
        self.paused = False
        self.pause_index = 0
        self.ready_t = 1.2                  # "READY?" banner time
        self._send_t = 0.0
        self._recorded = False
        app.audio.play_music(LEVELS[level_id]["music"])

    # ------------------------------------------------------------- update

    def update(self, dt, events):
        keys = pygame.key.get_pressed()
        inp = {
            "left": keys[pygame.K_LEFT] or keys[pygame.K_a],
            "right": keys[pygame.K_RIGHT] or keys[pygame.K_d],
            "run": any(keys[k] for k in RUN_KEYS),
            "jump": any(keys[k] for k in JUMP_KEYS),
            "jump_pressed": False,
            "fire_pressed": False,
        }
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key in JUMP_KEYS and not self.paused:
                    inp["jump_pressed"] = True
                elif e.key in RUN_KEYS and not self.paused:
                    inp["fire_pressed"] = True
                elif e.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                    self.paused = not self.paused
                    self.pause_index = 0
                    self.app.audio.play("pause")
                elif e.key == pygame.K_MINUS:
                    self.app.audio.set_music_volume(self.app.audio.music_volume - 0.1)
                elif e.key == pygame.K_EQUALS:
                    self.app.audio.set_music_volume(self.app.audio.music_volume + 0.1)
        if self.paused:
            if self._update_pause(events):
                return
            if self.role == "sp":
                inp = {}
            else:
                inp = {k: False for k in inp}
        if self.ready_t > 0:
            self.ready_t -= dt

        sim_paused = self.paused and self.role == "sp"
        if not sim_paused:
            self.world.set_jump_held(inp.get("jump", False))
            self.world.update(dt, inp)
            now = time.time()
            for p in self.world.players.values():
                if not p.local:
                    p.interpolate(now - INTERP_DELAY)

        if self.role == "host":
            self._host_net()
        elif self.role == "client":
            if self._client_net():
                return

        if self.world.cleared and not self._recorded:
            self._recorded = True
            me = self.world.local_player
            if me:
                self.app.save.record_clear(self.level_id, me.score, me.coins,
                                           len(LEVELS))
        if self.world.cleared and self.world.clear_t > 4.5:
            self._advance()

    def _update_pause(self, events):
        opts = ["Resume", "Restart Level", "Quit to Title"] if self.role == "sp" \
            else ["Resume", "Leave Game"]
        self.pause_index, ok, back = menu_nav(events, self.pause_index, len(opts))
        if back:
            self.paused = False
        if not ok:
            return False
        choice = opts[self.pause_index]
        if choice == "Resume":
            self.paused = False
        elif choice == "Restart Level":
            self.app.switch(GameScene(self.app, "sp", self.level_id))
            return True
        else:
            self._leave()
            return True
        return False

    def _leave(self):
        if self.host:
            self.host.close()
        if self.client:
            self.client.close()
        self.app.audio.stop_music()
        self.app.switch(TitleScene(self.app))

    def _advance(self):
        nxt = self.level_id + 1
        if self.role == "sp":
            if nxt >= len(LEVELS):
                self.app.switch(VictoryScene(self.app))
            else:
                self.app.switch(GameScene(self.app, "sp", nxt))
        elif self.role == "host":
            if nxt >= len(LEVELS):
                from .menu import HostLobbyScene
                self.app.switch(HostLobbyScene(self.app, host=self.host))
            else:
                self.app.switch(GameScene(self.app, "host", nxt, host=self.host))
        # client: waits for the host's snapshots to carry the new level id

    # ------------------------------------------------------------- net

    def _host_net(self):
        w = self.world
        now = time.time()
        for pid, msg in self.host.poll():
            t = msg.get("t")
            if t == "pstate":
                w.apply_pstate(pid, msg, now)
            elif t == "char":
                pass
            else:
                w.apply_claim(pid, msg)
        # drop players whose peer vanished
        live = set(self.host.player_ids())
        for pid in list(w.players):
            if pid not in live:
                del w.players[pid]
                w.remote_fireballs.pop(pid, None)
        if now - self._send_t >= 1.0 / SNAP_RATE:
            self._send_t = now
            snap = w.snapshot()
            snap["lv"] = self.level_id
            self.host.send_all(snap)

    def _client_net(self):
        """Returns True if we switched scenes."""
        w = self.world
        now = time.time()
        for msg in self.client.poll():
            t = msg.get("t")
            if t == "snap":
                if msg["lv"] != self.level_id:
                    self.app.switch(GameScene(self.app, "client", msg["lv"],
                                              client=self.client, first_snap=msg))
                    return True
                w.apply_snapshot(msg, now)
            elif t == "lobby":
                from .menu import ClientLobbyScene
                self.app.switch(ClientLobbyScene(self.app, self.client))
                return True
            elif t == "end":
                self._leave()
                return True
        if self.client.timed_out:
            self._leave()
            return True
        # send claims immediately (latency-sensitive), player state at fixed rate
        for claim in w.outbox:
            self.client.send(claim)
        w.outbox.clear()
        if now - self._send_t >= 1.0 / PSTATE_RATE:
            self._send_t = now
            ps = w.local_pstate()
            if ps:
                self.client.send(ps)
        return False

    # ------------------------------------------------------------- draw

    def draw(self, surf):
        render.draw_world(surf, self.world, self.app.sprites)
        net_info = None
        if self.role == "client":
            net_info = f"ping {int(self.client.rtt * 1000)}ms"
        elif self.role == "host":
            net_info = f"host {len(self.world.players)}p"
        draw_hud(surf, self.world, net_info, self.app.sprites)
        if self.ready_t > 0:
            text(surf, "READY?", VIEW_W // 2, VIEW_H // 2 - 30,
                 (255, 224, 88), 16, center=True)
        if self.paused:
            box(surf, VIEW_W // 2 - 60, 80, 120, 80)
            text(surf, "PAUSED", VIEW_W // 2, 88, (255, 255, 255), 12, center=True)
            opts = ["Resume", "Restart Level", "Quit to Title"] \
                if self.role == "sp" else ["Resume", "Leave Game"]
            for i, o in enumerate(opts):
                sel = i == self.pause_index
                col = (255, 224, 88) if sel else (255, 255, 255)
                text(surf, ("> " if sel else "") + o, VIEW_W // 2, 108 + i * 14,
                     col, 8, center=True)
            text(surf, "-/= music volume", VIEW_W // 2, 150, (200, 200, 220), 7,
                 center=True)


class VictoryScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        app.audio.play_music("menu")
        app.audio.play("clear")

    def update(self, dt, events):
        for e in events:
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN,
                                                      pygame.K_ESCAPE,
                                                      pygame.K_z):
                self.app.switch(TitleScene(self.app))

    def draw(self, surf):
        draw_sky(surf, self.app)
        text(surf, "CONGRATULATIONS!", VIEW_W // 2, 60, (255, 224, 88), 16,
             center=True)
        text(surf, "You conquered all three worlds", VIEW_W // 2, 90,
             (255, 255, 255), 10, center=True)
        text(surf, "and toppled King Snap!", VIEW_W // 2, 104,
             (255, 255, 255), 10, center=True)
        for i, color in enumerate(("red", "green", "blue", "yellow")):
            frames = self.app.sprites.heroes[(color, False)]["big"]
            surf.blit(frames[0], (VIEW_W // 2 - 60 + i * 30, 130))
        text(surf, "press enter", VIEW_W // 2, 190, (200, 200, 220), 8,
             center=True)


class App:
    def __init__(self):
        pygame.mixer.pre_init(22050, -16, 1, 512)
        pygame.init()
        pygame.display.set_caption("Super Yoonario Bros")
        self.screen = pygame.display.set_mode(
            (VIEW_W, VIEW_H), pygame.SCALED | pygame.RESIZABLE)
        self.surface = self.screen
        self.clock = pygame.time.Clock()
        self.save = Save()
        self.audio = Audio()
        self.audio.sfx_volume = self.save["sfx_volume"]
        self.audio.music_volume = self.save["music_volume"]
        self.sprites = Sprites()
        self.scene = TitleScene(self)
        self.running = True

    def switch(self, scene):
        self.scene = scene

    def run(self):
        while self.running:
            self.clock.tick(FPS)
            events = pygame.event.get()
            for e in events:
                if e.type == pygame.QUIT:
                    self.running = False
            self.scene.update(DT, events)
            self.scene.draw(self.surface)
            pygame.display.flip()
        # persist volume settings on exit
        self.save["sfx_volume"] = self.audio.sfx_volume
        self.save["music_volume"] = self.audio.music_volume
        self.save.write()
        scene = self.scene
        if isinstance(scene, GameScene):
            if scene.host:
                scene.host.close()
            if scene.client:
                scene.client.close()
        pygame.quit()
