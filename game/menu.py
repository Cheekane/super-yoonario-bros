"""Menu scenes: title, character select, level select, join & lobbies."""
import time

import pygame

from .constants import VIEW_W, VIEW_H, CHARACTERS, MAX_PLAYERS, NET_PORT
from .sprites import CHAR_COLORS, THEMES
from .levels import LEVELS
from .hud import text, box
from . import net


class Scene:
    def __init__(self, app):
        self.app = app

    def update(self, dt, events):
        pass

    def draw(self, surf):
        pass


def menu_nav(events, index, count):
    """Up/down navigation; returns (index, confirmed, backed)."""
    confirmed = backed = False
    for e in events:
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_UP, pygame.K_w):
                index = (index - 1) % count
            elif e.key in (pygame.K_DOWN, pygame.K_s):
                index = (index + 1) % count
            elif e.key in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE):
                confirmed = True
            elif e.key == pygame.K_ESCAPE:
                backed = True
    return index, confirmed, backed


def draw_sky(surf, app):
    surf.fill(THEMES["grass"]["sky"])
    tiles = app.sprites.tiles["grass"]
    for x in range(0, VIEW_W, 16):
        surf.blit(tiles["ground"], (x, VIEW_H - 16))
        surf.blit(tiles["dirt"], (x, VIEW_H))


class TitleScene(Scene):
    OPTIONS = ["Single Player", "Host Multiplayer", "Join Multiplayer", "Quit"]

    def __init__(self, app):
        super().__init__(app)
        self.index = 0
        app.audio.play_music("menu")

    def update(self, dt, events):
        self.index, ok, back = menu_nav(events, self.index, len(self.OPTIONS))
        if ok:
            self.app.audio.play("confirm")
            if self.index == 0:
                self.app.switch(CharSelectScene(self.app, "sp"))
            elif self.index == 1:
                self.app.switch(CharSelectScene(self.app, "host"))
            elif self.index == 2:
                self.app.switch(CharSelectScene(self.app, "join"))
            else:
                self.app.running = False
        if back:
            self.app.running = False

    def draw(self, surf):
        draw_sky(surf, self.app)
        text(surf, "SUPER", VIEW_W // 2, 30, (255, 224, 88), 16, center=True)
        text(surf, "YOONARIO BROS", VIEW_W // 2, 48, (255, 80, 60), 22, center=True)
        text(surf, "4-player online co-op", VIEW_W // 2, 76, (255, 255, 255), 8,
             center=True)
        for i, opt in enumerate(self.OPTIONS):
            sel = i == self.index
            color = (255, 224, 88) if sel else (255, 255, 255)
            text(surf, ("> " if sel else "") + opt, VIEW_W // 2, 110 + i * 16,
                 color, 10, center=True)
        text(surf, "arrows: move   Z/space: select   esc: back", VIEW_W // 2,
             VIEW_H - 36, (220, 220, 240), 8, center=True)


class CharSelectScene(Scene):
    def __init__(self, app, mode):
        super().__init__(app)
        self.mode = mode                    # sp | host | join
        self.index = app.save["character"]
        self.name = app.save["player_name"]

    def update(self, dt, events):
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key in (pygame.K_LEFT, pygame.K_a):
                    self.index = (self.index - 1) % 4
                    self.app.audio.play("select")
                elif e.key in (pygame.K_RIGHT, pygame.K_d):
                    self.index = (self.index + 1) % 4
                    self.app.audio.play("select")
                elif e.key == pygame.K_BACKSPACE:
                    self.name = self.name[:-1]
                elif e.key == pygame.K_ESCAPE:
                    self.app.switch(TitleScene(self.app))
                    return
                elif e.key == pygame.K_RETURN:
                    self._confirm()
                    return
                elif e.unicode and e.unicode.isprintable() and \
                        len(self.name) < 10:
                    self.name += e.unicode

    def _confirm(self):
        if not self.name.strip():
            self.name = "Player"
        self.app.save["character"] = self.index
        self.app.save["player_name"] = self.name.strip()
        self.app.save.write()
        self.app.audio.play("confirm")
        if self.mode == "sp":
            self.app.switch(LevelSelectScene(self.app))
        elif self.mode == "host":
            self.app.switch(HostLobbyScene(self.app))
        else:
            self.app.switch(JoinScene(self.app))

    def draw(self, surf):
        draw_sky(surf, self.app)
        text(surf, "CHOOSE YOUR HERO", VIEW_W // 2, 20, (255, 255, 255), 12,
             center=True)
        for i, ch in enumerate(CHARACTERS):
            x = 48 + i * 60
            sel = i == self.index
            if sel:
                box(surf, x - 20, 50, 44, 70, (40, 40, 90))
            frames = self.app.sprites.heroes[(ch["color"], False)]["big"]
            img = frames[0]
            surf.blit(img, (x - img.get_width() // 2 + 2, 60))
            col = CHAR_COLORS[ch["color"]][1] if sel else (200, 200, 200)
            text(surf, ch["name"], x + 2, 96, col, 8, center=True)
            if sel:
                desc = {"Yoonario": "All-around hero",
                        "Luna": "Highest jumper",
                        "Dash": "Fastest runner",
                        "Pip": "Floaty and light"}[ch["name"]]
                text(surf, desc, VIEW_W // 2, 130, (255, 224, 88), 8, center=True)
        text(surf, f"Name: {self.name}_", VIEW_W // 2, 156, (255, 255, 255), 10,
             center=True)
        text(surf, "type to edit name - left/right: pick - enter: confirm",
             VIEW_W // 2, VIEW_H - 36, (220, 220, 240), 8, center=True)


class LevelSelectScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.index = min(app.save["unlocked"], len(LEVELS)) - 1
        app.audio.play_music("menu")

    def update(self, dt, events):
        unlocked = self.app.save["unlocked"]
        self.index, ok, back = menu_nav(events, self.index, unlocked)
        if ok:
            self.app.audio.play("confirm")
            from .app import GameScene
            self.app.switch(GameScene(self.app, "sp", self.index))
        if back:
            self.app.switch(TitleScene(self.app))

    def draw(self, surf):
        draw_sky(surf, self.app)
        text(surf, "SELECT LEVEL", VIEW_W // 2, 12, (255, 255, 255), 12, center=True)
        unlocked = self.app.save["unlocked"]
        top = max(0, self.index - 5)
        for row, i in enumerate(range(top, min(len(LEVELS), top + 8))):
            lv = LEVELS[i]
            y = 34 + row * 20
            locked = i >= unlocked
            sel = i == self.index
            col = (120, 120, 130) if locked else \
                (255, 224, 88) if sel else (255, 255, 255)
            label = f"{lv['world']}-{lv['index']} {lv['name']}"
            if locked:
                label += "  [locked]"
            text(surf, ("> " if sel else "  ") + label, 40, y, col, 9)
            best = self.app.save["best"].get(str(i))
            if best and not locked:
                text(surf, f"best {best['score']}", 230, y, (160, 255, 160), 7)
        text(surf, "enter: play   esc: back", VIEW_W // 2, VIEW_H - 22,
             (220, 220, 240), 8, center=True)


class JoinScene(Scene):
    def __init__(self, app):
        super().__init__(app)
        self.ip = app.save["last_host_ip"]
        self.status = ""
        self.client = None
        self.join_sent = 0.0

    def update(self, dt, events):
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    if self.client:
                        self.client.close()
                    self.app.switch(TitleScene(self.app))
                    return
                if self.client:
                    continue
                if e.key == pygame.K_BACKSPACE:
                    self.ip = self.ip[:-1]
                elif e.key == pygame.K_RETURN and self.ip.strip():
                    self._connect()
                elif e.unicode and (e.unicode.isdigit() or e.unicode in ".:"):
                    if len(self.ip) < 21:
                        self.ip += e.unicode
        if self.client:
            for msg in self.client.poll():
                if msg["t"] == "welcome":
                    self.app.save["last_host_ip"] = self.ip.strip()
                    self.app.save.write()
                    self.app.switch(ClientLobbyScene(self.app, self.client))
                    return
                if msg["t"] == "reject":
                    self.status = f"Rejected: {msg.get('why', '?')}"
                    self.client.close()
                    self.client = None
            if self.client and time.time() - self.join_sent > 1.0:
                self.join_sent = time.time()
                self.client.join(self.app.save["player_name"],
                                 self.app.save["character"])
                if self.client.timed_out:
                    self.status = "No response from host."
                    self.client.close()
                    self.client = None

    def _connect(self):
        ip = self.ip.strip()
        port = NET_PORT
        if ":" in ip:
            ip, _, p = ip.partition(":")
            port = int(p) if p.isdigit() else NET_PORT
        try:
            self.client = net.Client(ip, port)
        except OSError:
            self.status = "Invalid address."
            return
        self.client.join(self.app.save["player_name"], self.app.save["character"])
        self.join_sent = time.time()
        self.status = "Connecting..."

    def draw(self, surf):
        draw_sky(surf, self.app)
        text(surf, "JOIN GAME", VIEW_W // 2, 30, (255, 255, 255), 14, center=True)
        text(surf, "Host address:", VIEW_W // 2, 80, (255, 255, 255), 9, center=True)
        box(surf, VIEW_W // 2 - 80, 96, 160, 18)
        text(surf, self.ip + ("_" if not self.client else ""), VIEW_W // 2, 100,
             (255, 224, 88), 10, center=True)
        if self.status:
            text(surf, self.status, VIEW_W // 2, 130, (255, 160, 160), 8, center=True)
        text(surf, "same wifi: use the host's LAN IP shown on their screen",
             VIEW_W // 2, VIEW_H - 52, (220, 220, 240), 8, center=True)
        text(surf, "over internet: host forwards UDP port, or use Tailscale",
             VIEW_W // 2, VIEW_H - 40, (220, 220, 240), 8, center=True)
        text(surf, "enter: connect   esc: back", VIEW_W // 2, VIEW_H - 24,
             (220, 220, 240), 8, center=True)


class HostLobbyScene(Scene):
    def __init__(self, app, host=None):
        super().__init__(app)
        try:
            self.host = host or net.Host()
            self.error = None
        except OSError as exc:
            self.host = None
            self.error = f"Cannot open port: {exc}"
        self.level = min(app.save["unlocked"], len(LEVELS)) - 1
        self.ip = net.local_ip()
        self._last_bcast = 0.0
        if self.host:
            self.host.start_port_forward()
        app.audio.play_music("menu")

    def lobby_players(self):
        players = [{"pid": 0, "name": self.app.save["player_name"],
                    "char": self.app.save["character"]}]
        for peer in self.host.peers.values():
            players.append({"pid": peer["pid"], "name": peer["name"],
                            "char": peer["char"]})
        return sorted(players, key=lambda p: p["pid"])

    def update(self, dt, events):
        if self.error:
            for e in events:
                if e.type == pygame.KEYDOWN:
                    self.app.switch(TitleScene(self.app))
            return
        unlocked = self.app.save["unlocked"]
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.host.close()
                    self.app.switch(TitleScene(self.app))
                    return
                elif e.key in (pygame.K_UP, pygame.K_w):
                    self.level = (self.level - 1) % unlocked
                    self.app.audio.play("select")
                elif e.key in (pygame.K_DOWN, pygame.K_s):
                    self.level = (self.level + 1) % unlocked
                    self.app.audio.play("select")
                elif e.key == pygame.K_RETURN:
                    self.app.audio.play("confirm")
                    from .app import GameScene
                    self.app.switch(GameScene(self.app, "host", self.level,
                                              host=self.host))
                    return
        for pid, msg in self.host.poll():
            if msg.get("t") == "char":
                addr = self.host.by_pid.get(pid)
                if addr:
                    self.host.peers[addr]["char"] = msg.get("char", 0) % 4
        now = time.time()
        if now - self._last_bcast > 0.2:
            self._last_bcast = now
            self.host.send_all({"t": "lobby", "players": self.lobby_players(),
                                "level": self.level, "ingame": 0})

    def draw(self, surf):
        draw_sky(surf, self.app)
        if self.error:
            text(surf, self.error, VIEW_W // 2, 100, (255, 120, 120), 9, center=True)
            text(surf, "press any key", VIEW_W // 2, 130, (255, 255, 255), 8,
                 center=True)
            return
        text(surf, "HOSTING GAME", VIEW_W // 2, 10, (255, 255, 255), 12, center=True)
        text(surf, f"Same wifi: {self.ip}:{self.host.port}", VIEW_W // 2, 26,
             (160, 255, 160), 8, center=True)
        up = self.host.upnp
        if up is None or up.status == "working":
            text(surf, "Internet: checking your router...", VIEW_W // 2, 37,
                 (200, 200, 220), 8, center=True)
        elif up.status == "ok":
            text(surf, f"Internet: {up.external_ip}:{self.host.port}",
                 VIEW_W // 2, 37, (160, 255, 160), 8, center=True)
        else:
            text(surf, f"Internet: auto-setup failed ({up.message})",
                 VIEW_W // 2, 37, (255, 190, 120), 7, center=True)
        draw_player_slots(surf, self.app, self.lobby_players())
        lv = LEVELS[self.level]
        text(surf, f"Level: {lv['world']}-{lv['index']} {lv['name']}",
             VIEW_W // 2, 150, (255, 224, 88), 9, center=True)
        text(surf, "up/down: level   enter: start   esc: cancel",
             VIEW_W // 2, VIEW_H - 24, (220, 220, 240), 8, center=True)


class ClientLobbyScene(Scene):
    def __init__(self, app, client):
        super().__init__(app)
        self.client = client
        self.players = []
        self.level = 0
        self.char = app.save["character"]
        app.audio.play_music("menu")

    def update(self, dt, events):
        for e in events:
            if e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    self.client.close()
                    self.app.switch(TitleScene(self.app))
                    return
                elif e.key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                    delta = -1 if e.key in (pygame.K_LEFT, pygame.K_a) else 1
                    self.char = (self.char + delta) % 4
                    self.app.save["character"] = self.char
                    self.client.send({"t": "char", "char": self.char})
                    self.app.audio.play("select")
        for msg in self.client.poll():
            t = msg.get("t")
            if t == "lobby":
                self.players = msg["players"]
                self.level = msg["level"]
            elif t == "snap":
                from .app import GameScene
                self.app.switch(GameScene(self.app, "client", msg["lv"],
                                          client=self.client, first_snap=msg))
                return
            elif t == "end":
                self.client.close()
                self.app.switch(TitleScene(self.app))
                return
        if self.client.timed_out:
            self.client.close()
            self.app.switch(TitleScene(self.app))

    def draw(self, surf):
        draw_sky(surf, self.app)
        text(surf, "LOBBY", VIEW_W // 2, 12, (255, 255, 255), 12, center=True)
        text(surf, f"ping {int(self.client.rtt * 1000)}ms", VIEW_W - 56, 12,
             (160, 255, 160), 7)
        draw_player_slots(surf, self.app, self.players, my_pid=self.client.pid,
                          my_char=self.char)
        if self.players:
            lv = LEVELS[self.level]
            text(surf, f"Level: {lv['world']}-{lv['index']} {lv['name']}",
                 VIEW_W // 2, 150, (255, 224, 88), 9, center=True)
        text(surf, "waiting for host to start...", VIEW_W // 2, 170,
             (200, 200, 220), 8, center=True)
        text(surf, "left/right: character   esc: leave", VIEW_W // 2,
             VIEW_H - 24, (220, 220, 240), 8, center=True)


def draw_player_slots(surf, app, players, my_pid=None, my_char=None):
    for i in range(MAX_PLAYERS):
        x = 30 + i * 70
        box(surf, x, 50, 56, 84, (30, 30, 60))
        if i < len(players):
            p = dict(players[i])
            if my_pid is not None and p["pid"] == my_pid and my_char is not None:
                p["char"] = my_char
            ch = CHARACTERS[p["char"] % 4]
            frames = app.sprites.heroes[(ch["color"], False)]["big"]
            surf.blit(frames[0], (x + 20, 62))
            text(surf, p["name"], x + 28, 100, (255, 255, 255), 7, center=True)
            text(surf, ch["name"], x + 28, 112, CHAR_COLORS[ch["color"]][1], 7,
                 center=True)
            if p["pid"] == 0:
                text(surf, "HOST", x + 28, 122, (255, 224, 88), 7, center=True)
        else:
            text(surf, "open", x + 28, 88, (120, 120, 140), 7, center=True)
