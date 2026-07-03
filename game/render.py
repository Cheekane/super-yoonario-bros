"""World rendering: parallax backgrounds and all entity drawing."""
import pygame

from .constants import TILE, VIEW_W, VIEW_H, CHARACTERS
from .sprites import THEMES
from .entities import Shell, Boss, Plant, Grub, Spiny, Flit


_bg_cache = {}


def _background(theme):
    """Pre-rendered parallax layer for a theme (tiles horizontally)."""
    if theme in _bg_cache:
        return _bg_cache[theme]
    th = THEMES[theme]
    w = 256
    surf = pygame.Surface((w, VIEW_H), pygame.SRCALPHA)
    if theme == "castle":
        for i in range(6):
            x = (i * 47) % w
            pygame.draw.rect(surf, (44, 36, 44), (x, 60 + (i % 3) * 40, 10, 16))
    elif theme == "cave":
        for i in range(10):
            x = (i * 29) % w
            y = 30 + (i * 53) % 150
            pygame.draw.circle(surf, (40, 56, 104), (x, y), 2)
    else:
        hill = th["bg"]
        for i in range(3):
            cx = 40 + i * 90
            pygame.draw.circle(surf, hill, (cx, VIEW_H + 30), 70)
        cloud = (255, 255, 255) if theme != "desert" else (255, 244, 220)
        for i in range(3):
            cx, cy = 30 + i * 85, 40 + (i * 37) % 50
            for dx, r in ((-10, 7), (0, 10), (12, 7)):
                pygame.draw.circle(surf, cloud, (cx + dx, cy), r)
    _bg_cache[theme] = surf
    return surf


def draw_world(surf, world, sprites):
    level = world.level
    cam = world.camera
    theme = level.theme
    surf.fill(THEMES[theme]["sky"])
    bg = _background(theme)
    off = int(cam.x * 0.4) % bg.get_width()
    for x in range(-off, VIEW_W, bg.get_width()):
        surf.blit(bg, (x, 0))

    level.draw(surf, sprites, cam.x, cam.y, world.t)
    cx, cy = int(cam.x), int(cam.y)

    for pl in world.platforms:
        img = sprites.tiles[theme]["platform"]
        for i in range(3):
            surf.blit(img, (int(pl.x) - cx + i * TILE, int(pl.y) - cy))

    frame = int(world.t * 6) % 4
    for coin in world.coins.values():
        surf.blit(sprites.coin[frame], (coin.rect.x - cx - 2, coin.rect.y - cy - 2))

    for it in world.items:
        img = {"mushroom": sprites.mushroom, "flower": sprites.flower,
               "oneup": sprites.oneup}[it.itype]
        r = it.rect
        surf.blit(img, (r.x - 1 - cx, r.bottom - 16 - cy))

    for e in world.enemies:
        draw_enemy(surf, e, sprites, cx, cy, world.t)

    for sb in world.spikeballs:
        surf.blit(sprites.spike_ball, (int(sb.x) - cx, int(sb.y) - cy))

    for fb in world.fireballs:
        surf.blit(sprites.fireball, (int(fb.x) - cx - 1, int(fb.y) - cy))
    for fbs in world.remote_fireballs.values():
        for x, y in fbs:
            surf.blit(sprites.fireball, (int(x) - cx - 1, int(y) - cy))

    for p in world.players.values():
        draw_player(surf, p, sprites, cx, cy, world)

    for pt in world.particles:
        draw_particle(surf, pt, sprites, cx, cy)


def draw_enemy(surf, e, sprites, cx, cy, t):
    f = int(e.anim_t * 5) % 2
    r = e.rect
    if isinstance(e, Grub):
        img = sprites.grub_squash if e.squash_t > 0 else sprites.grub[f]
    elif isinstance(e, Shell):
        img = sprites.shell if e.state != "walk" else sprites.shell_walk[f]
        if e.state == "slide":
            img = sprites.shell
    elif isinstance(e, Spiny):
        img = sprites.spiny[f]
    elif isinstance(e, Flit):
        img = sprites.flit[f]
    elif isinstance(e, Plant):
        img = sprites.plant[0 if int(e.anim_t * 3) % 2 else 1]
        # clip to how far it has emerged
        vis = int(16 * min(1.0, e.out + 0.1))
        if vis <= 0:
            return
        area = pygame.Rect(0, 0, 16, vis)
        surf.blit(img, (r.centerx - 8 - cx, int(e.y) - cy), area)
        return
    elif isinstance(e, Boss):
        img = sprites.boss
        if e.hurt_t > 0 and int(t * 12) % 2:
            return
        surf.blit(pygame.transform.flip(img, e.dir > 0, e.flip_dead),
                  (r.centerx - 11 - cx, r.bottom - 18 - cy))
        return
    else:
        return
    flip_v = e.flip_dead
    if e.dir > 0 or flip_v:
        img = pygame.transform.flip(img, e.dir > 0, flip_v)
    surf.blit(img, (r.centerx - 8 - cx, r.bottom - 16 - cy))


def draw_player(surf, p, sprites, cx, cy, world):
    if p.invuln > 0 and int(world.t * 14) % 2 and not p.dead:
        return
    color = CHARACTERS[p.char]["color"]
    frames = sprites.heroes[(color, p.form == "fire")]
    fset = frames["small" if p.form == "small" else "big"]
    if p.dead:
        img = fset[2]
        img = pygame.transform.flip(img, False, True)
    elif not p.on_ground:
        img = fset[2]
    elif abs(p.vx) > 8:
        img = fset[int(p.anim_t * 8) % 2]
    else:
        img = fset[0]
    if p.facing < 0 and not p.dead:
        img = pygame.transform.flip(img, True, False)
    r = p.rect
    surf.blit(img, (r.centerx - 8 - cx, r.bottom - img.get_height() - cy))


def draw_particle(surf, pt, sprites, cx, cy):
    x, y = int(pt.x) - cx, int(pt.y) - cy
    if pt.kind == "shard":
        pygame.draw.rect(surf, (200, 112, 48), (x, y, 4, 4))
    elif pt.kind == "coinpop":
        surf.blit(sprites.coin[int(pt.t * 12) % 4], (x, y))
    elif pt.kind == "score":
        from .hud import tiny_text
        tiny_text(surf, pt.text, x, y, (255, 255, 255))
