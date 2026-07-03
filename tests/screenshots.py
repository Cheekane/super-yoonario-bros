"""Capture screenshots of menus and levels for visual inspection."""
import os
import sys

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pygame
pygame.mixer.pre_init(22050, -16, 1, 512)
pygame.init()
pygame.display.set_mode((320, 240))

from game.constants import DT, VIEW_W, VIEW_H
from game.app import App, GameScene
from game.menu import TitleScene, CharSelectScene, LevelSelectScene, HostLobbyScene

OUT = os.path.join(os.path.dirname(__file__), "shots")
os.makedirs(OUT, exist_ok=True)

app = App.__new__(App)
from game.save import Save
from game.sfx import Audio
from game.sprites import Sprites
app.save = Save()
app.audio = Audio()
app.sprites = Sprites()
app.running = True
app.switch = lambda s: None

surf = pygame.Surface((VIEW_W, VIEW_H))


def shot(scene, name, frames=1, inp=None):
    for _ in range(frames):
        scene.update(DT, [])
    scene.draw(surf)
    path = os.path.join(OUT, f"{name}.png")
    pygame.image.save(pygame.transform.scale(surf, (VIEW_W * 2, VIEW_H * 2)), path)
    print("saved", path)


shot(TitleScene(app), "01_title")
shot(CharSelectScene(app, "sp"), "02_charselect")
app.save["unlocked"] = 12
shot(LevelSelectScene(app), "03_levelselect")

for lid, tag in ((0, "04_level_1_1"), (3, "05_castle_boss"),
                 (4, "06_desert"), (8, "07_ice"), (2, "08_athletic")):
    gs = GameScene(app, "sp", lid)
    inp = {"right": True, "run": True, "jump": False}
    keys = {}
    # walk into the level a bit so the shot shows real content
    for f in range(150):
        gs.world.set_jump_held(False)
        gs.world.update(DT, {"right": True,
                             "jump_pressed": f % 50 == 0, "jump": f % 50 < 18})
    gs.ready_t = 0
    from game import render
    from game.hud import draw_hud
    render.draw_world(surf, gs.world, app.sprites)
    draw_hud(surf, gs.world)
    path = os.path.join(OUT, f"{tag}.png")
    pygame.image.save(pygame.transform.scale(surf, (VIEW_W * 2, VIEW_H * 2)), path)
    print("saved", path)

print("done")
