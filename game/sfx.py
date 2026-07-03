"""Procedurally synthesized chiptune sound effects and music.

Everything is generated at startup from square/triangle/noise primitives,
so the game ships with zero audio asset files.
"""
import random
import array

import pygame

SAMPLE_RATE = 22050
_AMP = 12000


def _samples(duration):
    return int(SAMPLE_RATE * duration)


def square(freq_fn, duration, volume=1.0, duty=0.5, decay=0.0):
    """Square wave. freq_fn may be a constant or f(t)->Hz."""
    if not callable(freq_fn):
        f0 = freq_fn
        freq_fn = lambda t: f0
    n = _samples(duration)
    buf = array.array("h", bytes(2 * n))
    phase = 0.0
    for i in range(n):
        t = i / SAMPLE_RATE
        phase += freq_fn(t) / SAMPLE_RATE
        v = volume * (1.0 - decay * t / duration)
        buf[i] = int(_AMP * v) if (phase % 1.0) < duty else -int(_AMP * v)
    return buf


def triangle(freq, duration, volume=1.0):
    n = _samples(duration)
    buf = array.array("h", bytes(2 * n))
    for i in range(n):
        t = i / SAMPLE_RATE
        p = (t * freq) % 1.0
        v = 4 * p - 1 if p < 0.5 else 3 - 4 * p
        buf[i] = int(_AMP * volume * v)
    return buf


def noise(duration, volume=1.0, decay=1.0, low=False):
    n = _samples(duration)
    buf = array.array("h", bytes(2 * n))
    val = 0
    for i in range(n):
        if not low or i % 4 == 0:
            val = random.randint(-_AMP, _AMP)
        env = 1.0 - decay * (i / n)
        buf[i] = int(val * volume * max(0.0, env))
    return buf


def silence(duration):
    return array.array("h", bytes(2 * _samples(duration)))


def concat(*bufs):
    out = array.array("h")
    for b in bufs:
        out.extend(b)
    return out


def mix(*bufs):
    n = max(len(b) for b in bufs)
    out = array.array("h", bytes(2 * n))
    for b in bufs:
        for i, s in enumerate(b):
            v = out[i] + s
            out[i] = max(-32767, min(32767, v))
    return out


def envelope(buf, attack=0.005, release=0.02):
    """Soften clicks at buffer edges."""
    na = min(len(buf), _samples(attack))
    nr = min(len(buf), _samples(release))
    for i in range(na):
        buf[i] = int(buf[i] * i / na)
    for i in range(nr):
        j = len(buf) - 1 - i
        buf[j] = int(buf[j] * i / nr)
    return buf


def sound(buf):
    return pygame.mixer.Sound(buffer=envelope(buf).tobytes())


# --- Note helpers -----------------------------------------------------------

_NOTE_INDEX = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def note_freq(name):
    """'E5' / 'F#4' / 'Bb3' -> frequency in Hz."""
    letter, rest = name[0], name[1:]
    semitone = _NOTE_INDEX[letter]
    if rest.startswith("#"):
        semitone += 1
        rest = rest[1:]
    elif rest.startswith("b"):
        semitone -= 1
        rest = rest[1:]
    octave = int(rest)
    midi = 12 * (octave + 1) + semitone
    return 440.0 * (2 ** ((midi - 69) / 12))


def jingle(notes, note_dur=0.09, volume=0.5, duty=0.5):
    """notes: list of note names ('.' = rest) or (name, beats) tuples."""
    parts = []
    for item in notes:
        name, beats = item if isinstance(item, tuple) else (item, 1)
        dur = note_dur * beats
        if name == ".":
            parts.append(silence(dur))
        else:
            parts.append(envelope(square(note_freq(name), dur, volume, duty=duty, decay=0.6)))
    return concat(*parts)


def melody_track(pattern, beat, volume, duty=0.5):
    """Tracker string: tokens separated by spaces. 'E5' plays, '-' holds
    the previous note, '.' is a rest. Each token is one beat."""
    tokens = pattern.split()
    parts = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == ".":
            parts.append(silence(beat))
            i += 1
            continue
        beats = 1
        j = i + 1
        while j < len(tokens) and tokens[j] == "-":
            beats += 1
            j += 1
        parts.append(envelope(square(note_freq(tok), beat * beats, volume, duty=duty, decay=0.35)))
        i = j
    return concat(*parts)


# --- Public API -------------------------------------------------------------

class Audio:
    """Owns all generated sounds and music. Create once after mixer init."""

    def __init__(self):
        self.enabled = True
        try:
            pygame.mixer.get_init() or pygame.mixer.init(SAMPLE_RATE, -16, 1, 512)
        except pygame.error:
            self.enabled = False
        self.sfx_volume = 0.8
        self.music_volume = 0.5
        self.sfx = {}
        self.music = {}
        self._music_channel = None
        self._current_music = None
        if self.enabled:
            self._build_sfx()
            self._build_music()
            self._music_channel = pygame.mixer.Channel(0)

    # -- generation --

    def _build_sfx(self):
        s = self.sfx
        s["jump"] = sound(square(lambda t: 240 + 900 * t, 0.16, 0.5, decay=0.7))
        s["stomp"] = sound(mix(noise(0.09, 0.5, decay=1.0, low=True),
                               square(lambda t: 220 - 900 * t, 0.09, 0.3)))
        s["coin"] = sound(concat(square(note_freq("B5"), 0.06, 0.45),
                                 square(note_freq("E6"), 0.20, 0.45, decay=0.9)))
        s["bump"] = sound(square(lambda t: 110 - 300 * t, 0.08, 0.5))
        s["break"] = sound(noise(0.18, 0.55, decay=1.0))
        s["sprout"] = sound(square(lambda t: 300 + 500 * t, 0.30, 0.4))
        s["powerup"] = sound(jingle(["C5", "E5", "G5", "C6", "E6", "G6"], 0.055, 0.5))
        s["oneup"] = sound(jingle(["E5", "G5", "E6", "C6", "D6", "G6"], 0.09, 0.5))
        s["hurt"] = sound(square(lambda t: 500 - 1400 * t, 0.25, 0.5))
        s["die"] = sound(jingle([("B4", 1), ("F5", 1), (".", 1), ("F5", 1),
                                 ("F5", 1.5), ("E5", 1.5), ("D5", 1.5),
                                 ("C5", 1), ("E4", 1), ("G3", 2)], 0.11, 0.5))
        s["fireball"] = sound(mix(square(lambda t: 700 - 2000 * t, 0.09, 0.35),
                                  noise(0.07, 0.25, decay=1.0)))
        s["kick"] = sound(square(lambda t: 380 + 500 * t, 0.08, 0.5))
        s["skid"] = sound(noise(0.10, 0.2, decay=1.0, low=True))
        s["flag"] = sound(jingle(["G4", "C5", "E5", "G5", "C6", "E6", ("G6", 3),
                                  ("E6", 3)], 0.09, 0.5))
        s["clear"] = sound(jingle(["G4", "C5", "E5", "G5", ("C6", 2), ".",
                                   "A4", "C5", "E5", "A5", ("D6", 2), ".",
                                   "B4", "D5", "F#5", "B5", ("E6", 4)], 0.085, 0.5))
        s["pause"] = sound(jingle(["E6", "C6", "E6", "C6"], 0.06, 0.4))
        s["select"] = sound(square(note_freq("A5"), 0.06, 0.4))
        s["confirm"] = sound(jingle(["C5", "G5"], 0.07, 0.45))
        s["boss_hit"] = sound(mix(square(lambda t: 200 - 400 * t, 0.20, 0.5),
                                  noise(0.20, 0.4, decay=1.0)))
        s["boss_die"] = sound(concat(noise(0.4, 0.6, decay=1.0),
                                     jingle(["C5", "E5", "G5", "C6", ("G6", 3)], 0.1, 0.5)))
        s["respawn"] = sound(square(lambda t: 200 + 600 * t, 0.2, 0.35))
        s["checkpoint"] = sound(jingle(["C6", "E6", "G6"], 0.07, 0.45))
        s["throw"] = sound(square(lambda t: 500 - 800 * t, 0.10, 0.4))

    def _build_music(self):
        b = 0.145  # beat length (s) ~ 103 bpm eighth notes

        def track(mel, bass, duty=0.5):
            m = melody_track(mel, b, 0.30, duty=duty)
            bs = melody_track(bass, b, 0.22, duty=0.5)
            return sound(mix(m, bs))

        # Overworld: bouncy major tune (original composition)
        self.music["grass"] = track(
            "E5 . G5 . A5 - G5 . E5 . C5 - . . D5 . "
            "E5 . G5 . A5 - C6 . B5 . G5 - . . . . "
            "F5 . A5 . C6 - A5 . G5 . E5 - . . C5 . "
            "D5 . F5 . E5 - D5 . C5 - - - . . . . ",
            "C3 . G3 . C3 . G3 . A2 . E3 . A2 . E3 . "
            "C3 . G3 . C3 . G3 . G2 . D3 . G2 . D3 . "
            "F2 . C3 . F2 . C3 . C3 . G3 . C3 . G3 . "
            "G2 . D3 . G2 . D3 . C3 . G3 . C3 - . . ")
        # Desert: snake-charmer-ish harmonic minor
        self.music["desert"] = track(
            "A4 . C5 . E5 - D5 . C5 . B4 - . . E4 . "
            "A4 . C5 . E5 - G5 . F5 . E5 - . . . . "
            "F5 . E5 . D5 - C5 . B4 . G#4 - . . E4 . "
            "A4 - B4 - C5 - B4 - A4 - - - . . . . ",
            "A2 . E3 . A2 . E3 . A2 . E3 . A2 . E3 . "
            "A2 . E3 . A2 . E3 . F2 . C3 . F2 . C3 . "
            "D3 . A3 . D3 . A3 . E3 . B3 . E3 . B3 . "
            "A2 . E3 . A2 . E3 . A2 . E3 . A2 - . . ", duty=0.35)
        # Ice: gentle waltz-y melody
        self.music["ice"] = track(
            "G5 - E5 . C5 - . . A5 - G5 . E5 - . . "
            "F5 - D5 . B4 - . . G5 - E5 . C5 - . . "
            "E5 . F5 . G5 - A5 . B5 . C6 - . . G5 . "
            "A5 - F5 . D5 - B4 . C5 - - - . . . . ",
            "C3 . . E3 G3 . C3 . . E3 G3 . F2 . . A2 "
            "C3 . G2 . . B2 D3 . C3 . . E3 G3 . C3 . "
            "C3 . . E3 G3 . F2 . . A2 C3 . G2 . . B2 "
            "D3 . G2 . . B2 D3 . C3 . . E3 C3 - . . ", duty=0.25)
        # Castle: tense chromatic
        self.music["castle"] = track(
            "C5 . C5 . Eb5 - C5 . Ab4 - G4 - . . . . "
            "C5 . C5 . E5 - C5 . A4 - G4 - . . . . "
            "Db5 . Db5 . F5 - Db5 . C5 - B4 - . . . . "
            "C5 - G4 - Eb5 - D5 - C5 - - - . . . . ",
            "C3 . C3 . C3 . C3 . Ab2 . Ab2 . G2 . G2 . "
            "C3 . C3 . C3 . C3 . A2 . A2 . G2 . G2 . "
            "Db3 . Db3 . Db3 . Db3 . C3 . C3 . B2 . B2 . "
            "C3 . G2 . C3 . G2 . C3 . G2 . C3 - . . ", duty=0.35)
        # Menu: short calm loop
        self.music["menu"] = track(
            "C5 - E5 - G5 - E5 - A5 - G5 - E5 - C5 - "
            "D5 - F5 - A5 - F5 - G5 - - - . . . . ",
            "C3 . . . G3 . . . A2 . . . E3 . . . "
            "F2 . . . C3 . . . G2 . . . G2 . . . ", duty=0.25)

    # -- playback --

    def play(self, name):
        if self.enabled and name in self.sfx:
            snd = self.sfx[name]
            snd.set_volume(self.sfx_volume)
            snd.play()

    def play_music(self, name):
        if not self.enabled:
            return
        if name == self._current_music:
            return
        self._current_music = name
        self._music_channel.stop()
        if name and name in self.music:
            snd = self.music[name]
            snd.set_volume(self.music_volume)
            self._music_channel.play(snd, loops=-1)

    def stop_music(self):
        if self.enabled:
            self._current_music = None
            self._music_channel.stop()

    def set_music_volume(self, v):
        self.music_volume = max(0.0, min(1.0, v))
        if self.enabled and self._current_music:
            self.music[self._current_music].set_volume(self.music_volume)
