"""JSON save file: level progress, best scores, settings."""
import json
import os

SAVE_DIR = os.path.join(os.path.expanduser("~"), ".yoonario")
SAVE_PATH = os.path.join(SAVE_DIR, "save.json")

DEFAULT = {
    "unlocked": 1,               # number of levels playable (1 = only 1-1)
    "best": {},                  # level_id(str) -> {"score": int, "coins": int}
    "player_name": "Player",
    "character": 0,
    "map_pos": 0,
    "sfx_volume": 0.8,
    "music_volume": 0.5,
    "last_host_ip": "",
}


class Save:
    def __init__(self):
        self.data = dict(DEFAULT)
        self.load()

    def load(self):
        try:
            with open(SAVE_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            for k, v in loaded.items():
                if k in DEFAULT:
                    self.data[k] = v
        except (OSError, ValueError):
            pass

    def write(self):
        try:
            os.makedirs(SAVE_DIR, exist_ok=True)
            with open(SAVE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except OSError:
            pass

    def record_clear(self, level_id, score, coins, total_levels):
        key = str(level_id)
        best = self.data["best"].get(key, {"score": 0, "coins": 0})
        best["score"] = max(best["score"], score)
        best["coins"] = max(best["coins"], coins)
        self.data["best"][key] = best
        if level_id + 1 >= self.data["unlocked"]:
            self.data["unlocked"] = min(total_levels, level_id + 2)
        self.write()

    def __getitem__(self, k):
        return self.data[k]

    def __setitem__(self, k, v):
        self.data[k] = v
