"""HUD, text rendering and simple menu drawing helpers."""
import pygame

from .constants import VIEW_W, VIEW_H, CHARACTERS
from .sprites import CHAR_COLORS

_fonts = {}


def font(size=8):
    if size not in _fonts:
        _fonts[size] = pygame.font.Font(None, size + 4)
    return _fonts[size]


def text(surf, s, x, y, color=(255, 255, 255), size=8, center=False, shadow=True):
    img = font(size).render(s, False, color)
    r = img.get_rect()
    if center:
        r.midtop = (x, y)
    else:
        r.topleft = (x, y)
    if shadow:
        sh = font(size).render(s, False, (0, 0, 0))
        surf.blit(sh, (r.x + 1, r.y + 1))
    surf.blit(img, r)
    return r


def tiny_text(surf, s, x, y, color):
    text(surf, s, x, y, color, size=6)


def draw_hud(surf, world, net_info=None, sprites=None):
    me = world.local_player
    if not me:
        return
    lv = world.level.info
    text(surf, f"{me.name}", 6, 4, CHAR_COLORS[CHARACTERS[me.char]['color']][1], 8)
    text(surf, f"SCORE {me.score:06d}", 6, 14, (255, 255, 255), 8)
    if sprites:
        surf.blit(sprites.coin[0], (92, 11))
        text(surf, f"x{me.coins:02d}", 106, 14, (255, 224, 88), 8)
        icon = sprites.heroes[(CHARACTERS[me.char]["color"], False)]["small"][0]
        surf.blit(pygame.transform.scale(icon, (12, 12)), (136, 12))
        text(surf, f"x{me.lives}", 150, 14, (255, 255, 255), 8)
    else:
        text(surf, f"coins x{me.coins:02d}  lives x{me.lives}", 92, 14,
             (255, 224, 88), 8)
    text(surf, f"{lv['world']}-{lv['index']} {lv['name']}", VIEW_W // 2, 4,
         (255, 255, 255), 8, center=True)
    text(surf, f"TIME {int(world.time_left):03d}", VIEW_W - 64, 4, (255, 255, 255), 8)
    if net_info:
        text(surf, net_info, VIEW_W - 64, 14, (160, 255, 160), 7)
    # other players' status line
    y = 24
    for p in world.players.values():
        if p.pid == me.pid:
            continue
        col = CHAR_COLORS[CHARACTERS[p.char]["color"]][1]
        status = "DEAD" if p.dead else ""
        text(surf, f"{p.name} {p.score} {status}", 6, y, col, 7)
        y += 8

    if me.dead:
        if world.spectating(me):
            text(surf, "Out of lives - spectating", VIEW_W // 2,
                 VIEW_H // 2 - 20, (255, 120, 120), 10, center=True)
        else:
            text(surf, "Respawning...", VIEW_W // 2, VIEW_H // 2 - 20,
                 (255, 120, 120), 10, center=True)

    if world.cleared:
        box(surf, VIEW_W // 2 - 70, VIEW_H // 2 - 26, 140, 44)
        text(surf, "COURSE CLEAR!", VIEW_W // 2, VIEW_H // 2 - 18,
             (255, 224, 88), 12, center=True)
        who = world.players.get(world.clear_pid)
        if who:
            text(surf, f"{who.name} reached the goal!", VIEW_W // 2,
                 VIEW_H // 2 - 2, (255, 255, 255), 8, center=True)


def box(surf, x, y, w, h, color=(0, 0, 40), border=(255, 255, 255)):
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill((*color, 210))
    surf.blit(s, (x, y))
    pygame.draw.rect(surf, border, (x, y, w, h), 1)
