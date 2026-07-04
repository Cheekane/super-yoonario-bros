# Super Yoonario Bros

A 4-player online co-op platformer in the spirit of classic side-scrolling
Mario games. Run and jump through 3 worlds and 12 levels, stomp enemies,
grab power-ups, and topple King Snap — alone or with up to three friends,
each playing on their own computer.

Everything — pixel art, levels, sound effects, and music — is generated
procedurally in code. There are no asset files.

## Download

Grab the latest build for your OS from the
[Releases page](https://github.com/Cheekane/super-yoonario-bros/releases) —
a macOS app (Apple Silicon) and a Windows .exe, no Python required.
Release builds are produced automatically by GitHub Actions on every version
tag (`git tag v1.x && git push --tags`).

## Quick start (from source)

Requires Python 3.10+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

## Controls

| Action | Keys |
|---|---|
| Move | Arrow keys or A/D |
| Jump (hold for higher) | Z, Space, Up, or W |
| Run / throw fireball | X or Shift |
| Pause | Esc or Enter |
| Music volume | - / = |

## Playing together

One player hosts, up to three join. Everyone picks a character in the lobby;
the host picks the level and starts.

The host's lobby shows two **game codes** (short codes that encode the
address — no IPs to dictate):

- **Wifi code:** for friends on the same network.
- **Internet code:** for friends anywhere — the game automatically forwards
  the port on the host's router (UPnP) while hosting and removes the mapping
  after. If the router has UPnP disabled or the ISP uses CGNAT, the lobby
  says so; fall back to forwarding UDP `26501` manually or using
  [Tailscale](https://tailscale.com). Raw `ip:port` still works on the Join
  screen too.

If someone dies they respawn after a couple of seconds next to a living
teammate. The level is cleared when *any* player reaches the flag (or defeats
the boss). Players can drop in from the lobby and drop out at any time.

## The game

**Characters** (pick your playstyle):

- **Yoonario** — the all-around hero
- **Luna** — jumps highest, accelerates gently
- **Dash** — fastest on the ground, a little slippery
- **Pip** — light and floaty, falls slowly

**Worlds:** an overworld map connects Green Hills (1-1 Rolling Meadow, 1-2
Dewdrop Cave, 1-3 Treetop Hop, 1-4 Snapjaw Keep), Sandy Dunes (Dune Dash,
Oasis Pipes, Sky Ruins, Sunbaked Citadel), and Frostpeak (Slippery Slopes,
Crystal Cavern, Blizzard Heights, King Snap's Fortress) — walk between
unlocked levels and press enter to play. Each world ends in a castle boss
fight; world 3 has ice physics. Levels have mid-way checkpoints, ?-blocks
with coins and power-ups (mushroom → fire flower), breakable bricks, moving
platforms, and a time bonus at the flag.

**Lives:** you start with 5. Deaths cost one; 1-Up blocks and every 100
coins grant one. Out of lives in single player means game over (back to the
map); in multiplayer you spectate until the team clears the level — and if
the whole team is out, the level restarts for everyone.

Every level is verified by `game/reach.py`, which models the jump physics
(height, distance, ceilings) and proves the goal, checkpoints, power-ups
and coins are reachable. `tests/smoke_test.py` fails if a level regresses.

**Enemies:** Grubs (stomp them), Shellbacks (stomp, then kick the shell),
Spinies (fireball only!), Flits (flying), Chomp Plants (in pipes), and
King Snap, who takes more stomps in each world.

Levels are plain ASCII maps in `game/levels.py` — open it and you can read
(or edit!) every level like a picture. The legend is at the top of the file.

## Saving

Progress (unlocked levels, best scores), your name/character, and volume
settings save automatically to `~/.yoonario/save.json`. Level clears also
count in multiplayer — everyone in the session gets the unlock.

## How the netcode stays low-latency

- **Your own character is simulated locally** — zero input lag, always.
- The host is authoritative over the shared world (enemies, items, blocks,
  the timer). Clients apply effects optimistically (a stomped Grub squashes
  instantly) and send a claim the host validates.
- Plain **UDP** — a lost packet never blocks anything, because snapshots are
  idempotent full-state and your own movement doesn't depend on the network.
- Remote players are drawn ~100 ms in the past and interpolated between
  snapshots, so they move smoothly even with jitter.
- Moving platforms are a pure function of the (synced) world clock — they
  use zero bandwidth and are always exactly where you predict.
- Snapshots are ~0.7 KB at 30 Hz — fine on any connection.

## Distributing to friends

Friends can just install Python and run the two commands above. To hand them
a double-clickable app instead:

```bash
.venv/bin/pip install pyinstaller
.venv/bin/pyinstaller --onefile --windowed --name yoonario main.py
```

The result lands in `dist/`. Build on each OS you want to support
(macOS/Windows/Linux).

## Development

```bash
.venv/bin/python tests/smoke_test.py    # levels, sim, netcode loopback
.venv/bin/python tests/screenshots.py   # renders menus/levels to tests/shots/
```
