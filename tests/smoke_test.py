"""Headless smoke test: levels, world sim, and a host+client net session."""
import os
import sys
import time

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame
pygame.mixer.pre_init(22050, -16, 1, 512)
pygame.init()
pygame.display.set_mode((320, 240))

from game import levels
from game.constants import DT
from game.sprites import Sprites
from game.sfx import Audio
from game.world import World
from game import render, net

failures = []


def check(name, cond, detail=""):
    status = "ok" if cond else "FAIL"
    print(f"[{status}] {name} {detail}")
    if not cond:
        failures.append(name)


# 1. Level data validation
problems = levels.validate()
for p in problems:
    print("   level problem:", p)
check("levels validate", not problems, f"({len(levels.LEVELS)} levels)")

# 2. Sprites + audio build
sprites = Sprites()
audio = Audio()
check("sprites built", len(sprites.tiles) == 5)
check("audio built", not audio.enabled or len(audio.sfx) > 15)

# 3. Parse every level and simulate a single-player world for 5 seconds
surf = pygame.Surface((320, 240))
for lid in range(len(levels.LEVELS)):
    w = World(lid, audio, sprites, authority=True)
    w.add_player(0, 0, "Tester", local=True)
    inp = {"right": True, "run": True, "jump": False}
    for frame in range(300):
        if frame % 45 == 0:
            inp["jump_pressed"] = True
            inp["jump"] = True
        else:
            inp["jump_pressed"] = False
            inp["jump"] = frame % 45 < 20
        w.update(DT, inp)
        if frame % 60 == 0:
            render.draw_world(surf, w, sprites)
    me = w.local_player
    name = levels.LEVELS[lid]["name"]
    check(f"sim {name}", me.x > 30 or me.dead is False,
          f"x={me.x:.0f} enemies={len(w.enemies)} coins={len(w.coins)}")

# 4. Flag / boss present and reachable geometry sanity
for lid, lv in enumerate(levels.LEVELS):
    w = World(lid, audio, sprites, authority=True)
    if lv["boss_hp"]:
        check(f"boss in {lv['name']}",
              any(e.kind == "boss" for e in w.enemies))
    else:
        check(f"flag in {lv['name']}", w.level.flag is not None)

# 5. Networking loopback: host + one client exchange state
host = net.Host(port=26599)
client = net.Client("127.0.0.1", port=26599)
client.join("Remote", 1)
time.sleep(0.05)
host.poll()
time.sleep(0.05)
msgs = client.poll()
check("client welcomed", client.pid == 1, f"pid={client.pid}")

hw = World(0, audio, sprites, authority=True)
hw.add_player(0, 0, "HostP", local=True)
cw = World(0, audio, sprites, authority=False)
cw.add_player(1, 1, "Remote", local=True)

# client walks right and sends pstates; host snapshots back
for i in range(30):
    cw.update(DT, {"right": True})
    ps = cw.local_pstate()
    client.send(ps)
    time.sleep(0.002)
    for pid, msg in host.poll():
        if msg.get("t") == "pstate":
            hw.apply_pstate(pid, msg, time.time())
    hw.update(DT, {})
    snap = hw.snapshot()
    snap["lv"] = 0
    host.send_all(snap)
    time.sleep(0.002)
    for msg in client.poll():
        if msg.get("t") == "snap":
            cw.apply_snapshot(msg, time.time())

check("host sees remote player", 1 in hw.players,
      f"players={list(hw.players)}")
check("client mirrors host world", len(cw.enemies) == len(hw.enemies),
      f"client={len(cw.enemies)} host={len(hw.enemies)}")
hp = hw.players.get(1)
check("remote player moved", hp is not None and hp.net_buf and
      hp.net_buf[-1][1]["x"] > cw.level.spawn[0],
      f"x={hp.net_buf[-1][1]['x'] if hp and hp.net_buf else '?'}")

# claim round-trip: client stomps first enemy
if hw.enemies:
    target = hw.enemies[0]
    client.send({"t": "stomp", "eid": target.eid})
    time.sleep(0.02)
    for pid, msg in host.poll():
        if msg.get("t") not in ("pstate", "ping"):
            hw.apply_claim(pid, msg)
    check("stomp claim applied", target.squash_t > 0 or target.flip_dead)

client.close()
host.close()

# 6. UPnP parsing (offline: fixture XML, no real router involved)
from game import upnp

FIXTURE = """<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
 <device><deviceList><device><serviceList>
  <service>
   <serviceType>urn:schemas-upnp-org:service:WANIPConnection:1</serviceType>
   <controlURL>/ctl/IPConn</controlURL>
  </service>
 </serviceList></device></deviceList></device>
</root>"""
stype, ctl = upnp.parse_control_url(FIXTURE, "http://192.168.1.1:5000/desc.xml")
check("upnp parse control url",
      stype == "urn:schemas-upnp-org:service:WANIPConnection:1"
      and ctl == "http://192.168.1.1:5000/ctl/IPConn", ctl or "")
body = upnp.soap_body(stype, "AddPortMapping",
                      [("NewExternalPort", 26501), ("NewProtocol", "UDP")])
check("upnp soap body",
      "<NewExternalPort>26501</NewExternalPort>" in body
      and 'xmlns:u="urn:schemas-upnp-org:service:WANIPConnection:1"' in body)

# 7. Snapshot size sanity (single UDP datagram, ideally < MTU)
big = net.encode(snap)
check("snapshot size", len(big) < 1400, f"{len(big)} bytes")

print()
if failures:
    print("FAILURES:", failures)
    sys.exit(1)
print("All smoke tests passed.")
