#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ÇAYCIK: BOSS SAVAŞI
===================
1930'lar çizgi film tarzında, Cuphead'den esinlenen 2D boss savaşı.
Tek dosya - sadece Python standart kütüphanesi (tkinter). Kurulum gerektirmez.

KONTROLLER
  Sol/Sağ veya A/D   : koş
  Space / Z          : zıpla (havada basılı tut = daha yüksek)
  Havada PEMBE nesneye tekrar zıpla : PARRY (EX kartı kazanırsın)
  X / J              : ateş (basılı tut)  - Yukarı/W ile yukarı nişan
  Shift / C          : atılma (dash) - atılırken dokunulmazsın
  Q / E              : EX atışı (1 kart harcar)
  R / Tab / fare tekerleği : silah değiştir (Çay Topu, Saçma, Takipçi)
  Esc                : duraklat        F11 : tam ekran
  FARE MODU (Ayarlar > Kontroller): imleç yönüne nişan, sol tık ateş, sağ tık EX

Tüm tuşlar, tam ekran, çözünürlük ve zorluk AYARLAR menüsünden değiştirilebilir.

İlerleme ve notlar, oyunun yanındaki "caycik_kayit.json" dosyasına kaydedilir.
"""
import tkinter as tk
import random
import math
import json
import os
import io
import wave
import struct
import sys
import subprocess
import tempfile
import shutil
import atexit
import threading
from array import array
import time

W, H = 960, 540
GROUND = 452
GRAV = 0.85

INK = "#1b1209"
CREAM = "#f7e8c0"
WHITE = "#fffaf0"
GOLD = "#f2b632"
RED = "#c8372d"
PINK = "#ff6fb5"
FONT = "Georgia"

SAVE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "caycik_kayit.json")

LEFT = ("left", "a")
RIGHT = ("right", "d")
UPK = ("up", "w")
DOWNK = ("down", "s")
JUMP = ("space", "z", "k")
SHOOT = ("x", "j")
DASH = ("shift_l", "shift_r", "c", "l")
EXK = ("q", "e", "v")
OKK = ("return", "space", "z")
BACKK = ("escape",)

NORM = {"shift_r": "shift_l", "control_r": "control_l", "alt_r": "alt_l"}
KEYNAMES = {"left": "←", "right": "→", "up": "↑", "down": "↓", "space": "BOŞLUK",
            "shift_l": "SHIFT", "control_l": "CTRL", "alt_l": "ALT", "return": "ENTER",
            "tab": "TAB", "caps_lock": "CAPS", "backspace": "⌫", "delete": "DEL"}
DEFAULT_BINDS = dict(left=["left", "a"], right=["right", "d"], up=["up", "w"], jump=["space", "z"],
                     shoot=["x", "j"], dash=["shift_l", "c"], ex=["q", "e"], weapon=["r", "tab"])
ACTIONS = [("left", "Sola git"), ("right", "Sağa git"), ("up", "Yukarı nişan (klavye)"),
           ("jump", "Zıpla / Parry"), ("shoot", "Ateş"), ("dash", "Atılma (Dash)"),
           ("ex", "EX atışı"), ("weapon", "Silah değiştir")]
WEAPONS = [
    dict(name="ÇAY TOPU", col="#ffffff", kind="pea", cd=5, dmg=1.0),
    dict(name="SAÇMA", col="#ffb347", kind="spread", cd=16, dmg=0.7),
    dict(name="TAKİPÇİ", col="#7ad0ff", kind="homing", cd=7, dmg=0.55),
]
KEYACTS = set(a for a, _ in ACTIONS)
DEFAULT_SETTINGS = dict(fullscreen=False, res=0, grain=True, shake=True, sound=True, music=True,
                        weapon=0, aim="keyboard", diff=[1, 1, 1])
RES = [(960, 540), (1280, 720), (1600, 900), (1920, 1080)]
DIFF = [
    dict(name="KOLAY", hp=5, bhp=0.7, bt=0.82, shot=0.9, cap=79, col="#6fd04a",
         info="KOLAY: 5 can · boss %30 daha zayıf ve yavaş · en yüksek not B"),
    dict(name="NORMAL", hp=3, bhp=1.0, bt=1.0, shot=1.0, col=GOLD,
         info="NORMAL: 3 can · standart savaş"),
    dict(name="ZOR", hp=2, bhp=1.3, bt=1.15, shot=1.1, bonus=5, col="#ff5a4a",
         info="ZOR: 2 can · boss %30 daha dayanıklı ve hızlı · +5 puan"),
]


# ----------------------------------------------------------------- yardımcılar
def hx(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5))


def mix(a, b, t):
    a, b = hx(a), hx(b)
    return "#%02x%02x%02x" % tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def clamp(v, a, b):
    return max(a, min(b, v))


def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    l = dx * dx + dy * dy
    t = 0 if l == 0 else clamp(((px - x1) * dx + (py - y1) * dy) / l, 0, 1)
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def keyname(k):
    return "—" if not k else KEYNAMES.get(k, k.upper())


def star_pts(cx, cy, r1, r2, n, rot):
    pts = []
    for i in range(n * 2):
        a = rot + i * math.pi / n
        r = r1 if i % 2 == 0 else r2
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts


# ----------------------------------------------------------------------- ses
class Cv:
    """Tuvali ölçekleyen ince sarmalayıcı: oyun mantıksal 960x540 koordinatlarında çizer,
    gerçek tuvale (çözünürlüğe göre) ölçeklenmiş olarak aktarır."""

    def __init__(s, r):
        s.r = r
        s.S = 1.0

    def _co(s, a):
        if len(a) == 1 and isinstance(a[0], (list, tuple)):
            a = a[0]
        return [v * s.S for v in a]

    def _kw(s, k):
        S = s.S
        if "width" in k:
            k["width"] = k["width"] * S
        if "dash" in k:
            k["dash"] = tuple(max(1, int(d * S)) for d in k["dash"])
        if "font" in k:
            f = k["font"]
            k["font"] = (f[0], max(6, int(round(f[1] * S)))) + tuple(f[2:])
        return k

    def create_rectangle(s, *a, **k):
        return s.r.create_rectangle(*s._co(a), **s._kw(k))

    def create_oval(s, *a, **k):
        return s.r.create_oval(*s._co(a), **s._kw(k))

    def create_polygon(s, *a, **k):
        return s.r.create_polygon(*s._co(a), **s._kw(k))

    def create_line(s, *a, **k):
        return s.r.create_line(*s._co(a), **s._kw(k))

    def create_text(s, *a, **k):
        return s.r.create_text(*s._co(a), **s._kw(k))

    def move(s, tag, dx, dy):
        s.r.move(tag, dx * s.S, dy * s.S)

    def __getattr__(s, n):
        return getattr(s.r, n)


class Sfx:
    """Ses sistemi. Müzik ve efektler kodla üretilir (dosya gerekmez).
    Windows: winmm/MCI, macOS: afplay, Linux: paplay/aplay/play. Hiçbiri yoksa oyun sessiz çalışır.
    Sessiz başlatmak için: CAYCIK_SESSIZ=1 ortam değişkeni."""
    SR = 22050
    MIN = {"shoot": 0.14, "hit": 0.07, "land": 0.12, "coin": 0.05}

    def __init__(s):
        s.on = True
        s.music_on = True
        s.ok = False
        s.backend = None
        s.dir = None
        s.sfx = {}
        s.tracks = {}
        s.opened = set()
        s.cnt = {}
        s.last = {}
        s.want = None
        s.cur = None
        s.proc = None
        s.procs = []
        s.n = 0
        s.mci = None
        s.ct = None
        if os.environ.get("CAYCIK_SESSIZ"):
            return
        try:
            s.dir = tempfile.mkdtemp(prefix="caycik_")
            atexit.register(s.close)
            if os.name == "nt":
                import ctypes
                s.ct = ctypes
                s.mci = ctypes.windll.winmm.mciSendStringW
                s.backend = "mci"
            elif sys.platform == "darwin" and shutil.which("afplay"):
                s.backend = ["afplay"]
            else:
                for cmd in (["paplay"], ["aplay", "-q"], ["play", "-q"]):
                    if shutil.which(cmd[0]):
                        s.backend = cmd
                        break
            if s.backend:
                s.make_sfx()
                s.ok = True
                threading.Thread(target=s.make_music, daemon=True).start()
        except Exception:
            s.ok = False

    # ---- sentez
    def synth(s, parts, slow=False):
        sr = s.SR
        total = max(p[5] + p[3] for p in parts)
        buf = [0.0] * int(total * sr + 2)
        rnd = random.random
        for typ, f0, f1, d, vol, st in parts:
            n = int(d * sr)
            o = int(st * sr)
            ph = 0.0
            for i in range(n):
                k = i / n
                ph += (f0 + (f1 - f0) * k) / sr
                ph -= int(ph)
                if typ == "sq":
                    v = 1.0 if ph < 0.5 else -1.0
                elif typ == "tri":
                    v = 4 * abs(ph - 0.5) - 1
                elif typ == "saw":
                    v = 2 * ph - 1
                elif typ == "sin":
                    v = math.sin(ph * 6.2832)
                else:
                    v = rnd() * 2 - 1
                env = (1 - k) ** 1.4
                if i < 60:
                    env *= i / 60.0
                buf[o + i] += v * vol * env
            if slow:
                time.sleep(0.0004)
        return buf

    def write(s, name, buf, norm=None):
        m = max(1e-6, max(abs(x) for x in buf))
        if norm:
            g = norm / m
        else:
            g = 0.9 / m if m > 0.9 else 1.0
        arr = array("h", [int(clamp(x * g, -1, 1) * 32000) for x in buf])
        path = os.path.join(s.dir, name + ".wav")
        w = wave.open(path, "wb")
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(s.SR)
        w.writeframes(arr.tobytes())
        w.close()
        return path

    def make_sfx(s):
        S = {
            "blip": [("sq", 880, 880, 0.04, 0.3, 0)],
            "ok": [("sq", 660, 990, 0.1, 0.3, 0)],
            "shoot": [("sq", 1000, 320, 0.05, 0.22, 0), ("noise", 0, 0, 0.03, 0.12, 0)],
            "hit": [("noise", 0, 0, 0.05, 0.25, 0), ("tri", 260, 120, 0.06, 0.3, 0)],
            "hurt": [("saw", 320, 70, 0.32, 0.5, 0), ("noise", 0, 0, 0.2, 0.3, 0)],
            "parry": [("sin", 1200, 2000, 0.15, 0.45, 0), ("sin", 1800, 2600, 0.15, 0.4, 0.05)],
            "dash": [("noise", 0, 0, 0.13, 0.3, 0), ("tri", 500, 200, 0.1, 0.2, 0)],
            "jump": [("sq", 300, 640, 0.1, 0.22, 0)],
            "land": [("noise", 0, 0, 0.05, 0.2, 0), ("tri", 140, 80, 0.06, 0.3, 0)],
            "coin": [("sq", 1320, 1320, 0.06, 0.25, 0), ("sq", 1980, 1980, 0.16, 0.25, 0.06)],
            "boom": [("noise", 0, 0, 0.35, 0.5, 0), ("tri", 140, 40, 0.35, 0.5, 0)],
            "ko": [("saw", 420, 60, 0.9, 0.5, 0), ("noise", 0, 0, 0.6, 0.4, 0), ("tri", 200, 40, 0.9, 0.5, 0)],
            "go": [("sq", 440, 440, 0.09, 0.3, 0), ("sq", 554, 554, 0.09, 0.3, 0.08),
                   ("sq", 660, 660, 0.2, 0.3, 0.16)],
            "weapon": [("sq", 700, 700, 0.04, 0.25, 0), ("sq", 1000, 1000, 0.06, 0.25, 0.05)],
        }
        for k, parts in S.items():
            s.sfx[k] = s.write(k, s.synth(parts))
        if s.backend == "mci":
            for k, pth in s.sfx.items():
                for i in range(3):
                    s.mcmd('open "%s" type waveaudio alias %s%d' % (pth, k, i))

    def compose(s, name):
        sr = s.SR
        rnd = random.Random({"menu": 7, "boss": 13, "run": 29}[name])
        if name == "menu":
            bpm, key, minor = 118, 0, False
            prog = [(0, "M"), (9, "m"), (5, "M"), (7, "7"), (0, "M"), (4, "7"), (9, "m"), (7, "7"),
                    (5, "M"), (7, "7"), (0, "M"), (7, "7")]
        elif name == "boss":
            bpm, key, minor = 148, 9, True
            prog = [(9, "m"), (9, "m"), (5, "M"), (4, "7"), (9, "m"), (2, "m"), (4, "7"), (9, "m"),
                    (5, "M"), (7, "M"), (4, "7"), (4, "7")]
        else:
            bpm, key, minor = 138, 7, False
            prog = [(7, "M"), (4, "m"), (0, "M"), (2, "7"), (7, "M"), (11, "7"), (4, "m"), (2, "7"),
                    (0, "M"), (2, "7"), (7, "M"), (2, "7")]
        beat = 60.0 / bpm
        swing = beat * 0.14
        Q = {"M": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10)}
        pent = (0, 3, 5, 7, 10) if minor else (0, 2, 4, 7, 9)

        def fq(m):
            return 440.0 * 2 ** ((m - 69) / 12.0)
        sc = [72 + key + 12 * o + p for o in (0, 1) for p in pent]
        mi = 4
        bar = 4 * beat
        parts = []
        for b, (root, q) in enumerate(prog):
            t0 = b * bar
            iv = Q[q]
            rb = 36 + root
            seq = [0, iv[1], iv[2], iv[1]] if name != "boss" else [0, 0, iv[2], iv[1]]
            for i in range(4):
                parts.append(("tri", fq(rb + seq[i]), fq(rb + seq[i]), beat * 0.85, 0.55, t0 + i * beat))
            for i in (1, 3):
                for v in iv:
                    f_ = fq(60 + root + v)
                    parts.append(("sq", f_, f_, beat * 0.3, 0.07, t0 + i * beat))
            for e in range(8):
                if rnd.random() < 0.72:
                    on = t0 + e * beat / 2 + (swing if e % 2 else 0)
                    mi = clamp(mi + rnd.choice([-2, -1, -1, 0, 1, 1, 2]), 0, len(sc) - 1)
                    d = beat / 2 * (1.7 if rnd.random() < 0.3 else 0.85)
                    f_ = fq(sc[mi])
                    parts.append(("saw" if name == "boss" else "sq", f_, f_, d, 0.15, on))
            for i in range(4):
                tb = t0 + i * beat
                if i in (0, 2):
                    parts.append(("tri", 150, 45, 0.12, 0.7, tb))
                else:
                    parts.append(("noise", 0, 0, 0.1, 0.22, tb))
            if name == "boss" and b % 2 == 1:
                parts.append(("tri", 150, 45, 0.1, 0.6, t0 + 2.5 * beat))
            for e in range(8):
                th = t0 + e * beat / 2 + (swing if e % 2 else 0)
                parts.append(("noise", 0, 0, 0.03, 0.09 if e % 2 else 0.06, th))
        buf = s.synth(parts, True)
        n = int(len(prog) * bar * sr)
        return buf[:n]

    def make_music(s):
        try:
            for name in ("menu", "boss", "run"):
                s.tracks[name] = s.write("mus_" + name, s.compose(name), norm=0.42)
        except Exception:
            pass

    # ---- çalma
    def mcmd(s, cmd, buf=False):
        try:
            if buf:
                b = s.ct.create_unicode_buffer(64)
                s.mci(cmd, b, 64, 0)
                return b.value
            s.mci(cmd, None, 0, 0)
        except Exception:
            pass
        return ""

    def play(s, k):
        if not (s.ok and s.on) or k not in s.sfx:
            return
        now = time.perf_counter()
        if now - s.last.get(k, 0) < s.MIN.get(k, 0.04):
            return
        s.last[k] = now
        try:
            if s.backend == "mci":
                i = s.cnt.get(k, 0) % 3
                s.cnt[k] = i + 1
                s.mcmd("play %s%d from 0" % (k, i))
            else:
                s.procs = [p for p in s.procs if p.poll() is None]
                if len(s.procs) < 6 and k != "shoot":
                    s.procs.append(subprocess.Popen(s.backend + [s.sfx[k]], stdout=subprocess.DEVNULL,
                                                    stderr=subprocess.DEVNULL))
        except Exception:
            pass

    def set_music(s, track):
        s.want = track

    def stop_music(s):
        try:
            if s.cur:
                if s.backend == "mci":
                    s.mcmd("stop mus_%s" % s.cur)
                elif s.proc is not None:
                    s.proc.terminate()
        except Exception:
            pass
        s.proc = None
        s.cur = None

    def start_music(s, name):
        pth = s.tracks[name]
        if s.backend == "mci":
            if name not in s.opened:
                s.mcmd('open "%s" type waveaudio alias mus_%s' % (pth, name))
                s.opened.add(name)
            s.mcmd("play mus_%s from 0" % name)
        else:
            s.proc = subprocess.Popen(s.backend + [pth], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        s.cur = name

    def tick(s):
        if not s.ok:
            return
        s.n += 1
        want = s.want if s.music_on else None
        try:
            if want != s.cur:
                s.stop_music()
                if want and want in s.tracks:
                    s.start_music(want)
            elif s.cur and s.n % 30 == 0:
                if s.backend == "mci":
                    if s.mcmd("status mus_%s mode" % s.cur, True) == "stopped":
                        s.mcmd("play mus_%s from 0" % s.cur)
                elif s.proc is not None and s.proc.poll() is not None:
                    s.start_music(s.cur)
        except Exception:
            pass

    def close(s):
        try:
            s.stop_music()
            if s.backend == "mci":
                s.mcmd("close all")
            for p in s.procs:
                p.terminate()
        except Exception:
            pass
        try:
            if s.dir:
                shutil.rmtree(s.dir, ignore_errors=True)
        except Exception:
            pass


# -------------------------------------------------------------------- oyuncu
class Bullet:
    def __init__(s, x, y, vx, vy, ex=False, dmg=1.0, life=999, kind="pea", col="#ffffff"):
        s.x, s.y, s.vx, s.vy = x, y, vx, vy
        s.ex = ex
        s.kind = kind
        s.col = col
        s.dmg = dmg
        s.life = life
        s.r = 18 if ex else (5 if kind != "pea" else 6)
        s.age = 0
        s.dead = False
        s.hit = False
        s.hits = set()


class Player:
    def __init__(s):
        s.x = 170.0
        s.y = float(GROUND)
        s.vx = s.vy = 0.0
        s.face = 1
        s.on = True
        s.coy = 0
        s.hp = 3
        s.maxhp = 3
        s.inv = 0
        s.hurt = 0
        s.dash = 0
        s.dd = 1
        s.dcd = 0
        s.cd = 0
        s.mz = 0
        s.card = 0.0
        s.weapon = 0
        s.land = 0
        s.parries = 0
        s.jh = False
        s.t = 0

    def box(s):
        return (s.x - 13, s.y - 54, s.x + 13, s.y - 3)

    def aimvec(s, g):
        if g.mouse_mode and g.state == "fight":
            dx, dy = g.mx - (s.x - g.camx), g.my - (s.y - 36)
            d = math.hypot(dx, dy) or 1.0
            return (dx / d, dy / d)
        up = g.act("up")
        mv = g.act("left") or g.act("right")
        if up and mv:
            return (s.face * 0.7071, -0.7071)
        if up:
            return (0.0, -1.0)
        return (float(s.face), 0.0)

    def update(s, g):
        s.t += 1
        for a in ("inv", "hurt", "dcd", "cd", "mz", "land"):
            v = getattr(s, a)
            if v > 0:
                setattr(s, a, v - 1)
        if s.hp <= 0:
            return
        l = g.act("left")
        r = g.act("right")
        locked = s.hurt > 14
        if s.dash > 0:
            s.dash -= 1
            s.vx = s.dd * 14.5
            s.vy = 0
            if s.t % 2 == 0:
                g.dust(s.x - s.dd * 10, s.y - 4, 1)
        else:
            tgt = ((1 if r else 0) - (1 if l else 0)) * 5.5
            if locked:
                tgt = 0
            s.vx += (tgt - s.vx) * (0.42 if s.on else 0.24)
            if not locked:
                if r and not l:
                    s.face = 1
                elif l and not r:
                    s.face = -1
            if g.actp("dash") and s.dcd <= 0 and not locked:
                s.dash = 12
                s.dcd = 38
                s.dd = s.face
                g.sfx.play("dash")
                g.dust(s.x, s.y - 4, 5)
        if g.mouse_mode and s.dash == 0 and not locked:
            s.face = 1 if g.mx >= s.x - g.camx else -1
        jp = g.actp("jump")
        if jp and not locked:
            if s.on or s.coy > 0:
                s.vy = -16.8
                s.on = False
                s.coy = 0
                s.jh = True
                g.dust(s.x, s.y, 5)
                g.sfx.play("jump")
            else:
                g.try_parry()
        if s.jh and not g.act("jump"):
            s.jh = False
            if s.vy < -6:
                s.vy *= 0.45
        if s.dash == 0:
            s.vy = min(s.vy + GRAV, 17.0)
        lo, hi = g.xrange()
        s.x = clamp(s.x + s.vx, lo, hi)
        oy = s.y
        s.y += s.vy
        was = s.on
        s.on = False
        if s.vy >= 0:
            for (x1, x2, top) in g.plats:
                if x1 - 8 <= s.x <= x2 + 8 and oy <= top + 2 and s.y >= top:
                    s.y = float(top)
                    s.vy = 0
                    s.on = True
            if s.y >= GROUND and oy <= GROUND + 2 and g.ground_at(s.x):
                s.y = float(GROUND)
                s.vy = 0
                s.on = True
        if s.on:
            s.coy = 6
            if not was:
                g.dust(s.x, s.y, 6)
                s.land = 7
                g.sfx.play("land")
        else:
            s.coy = max(0, s.coy - 1)
        # ateş
        can = g.intro <= 60 and not locked and s.dash == 0 and g.ko == 0
        if can and g.actp("weapon"):
            g.next_weapon(1)
        if can and g.shooting() and s.cd <= 0:
            wp = WEAPONS[s.weapon]
            s.cd = wp["cd"]
            ax, ay = s.aimvec(g)
            base = math.atan2(ay, ax)
            mx_, my_ = s.x + ax * 30, s.y - 36 + ay * 26
            if wp["kind"] == "spread":
                for kk in range(-2, 3):
                    a = base + kk * 0.17 + random.uniform(-0.03, 0.03)
                    g.bul.append(Bullet(mx_, my_, math.cos(a) * 17, math.sin(a) * 17, False,
                                        wp["dmg"], 20, "spread", wp["col"]))
            elif wp["kind"] == "homing":
                a = base + random.uniform(-0.3, 0.3)
                g.bul.append(Bullet(mx_, my_, math.cos(a) * 11, math.sin(a) * 11, False,
                                    wp["dmg"], 110, "homing", wp["col"]))
            else:
                a = base + random.uniform(-0.03, 0.03)
                g.bul.append(Bullet(mx_, my_, math.cos(a) * 18, math.sin(a) * 18, False,
                                    wp["dmg"], 999, "pea", wp["col"]))
            s.mz = 4
            g.sfx.play("shoot")
        if can and g.ex_pressed() and s.card >= 1:
            s.card -= 1
            ax, ay = s.aimvec(g)
            g.bul.append(Bullet(s.x + ax * 30, s.y - 36 + ay * 26, ax * 13, ay * 13, True))
            s.mz = 8
            g.shake = 6
            g.burst(s.x + ax * 30, s.y - 36, GOLD, 10, 5)
            g.ring(s.x + ax * 30, s.y - 36, GOLD, 50, 16)
            g.sfx.play("boom")


# --------------------------------------------------------------- düşman mermisi
class Shot:
    def __init__(s, kind, x, y, vx=0.0, vy=0.0, r=12, pink=False, g=0.0, hp=0,
                 hh=40, sp=0.0, ph=0.0, life=700, skin=""):
        s.skin = skin
        s.kind, s.x, s.y, s.vx, s.vy = kind, x, y, vx, vy
        s.r, s.pink, s.g, s.hp, s.hh, s.sp, s.ph, s.life = r, pink, g, hp, hh, sp, ph, life
        s.t = 0
        s.dead = False
        s.ang = math.atan2(vy, vx) if (vx or vy) else 0.0
        s.flash = 0
        s.spin = random.uniform(0, 6)

    def update(s, G):
        s.t += 1
        k = s.kind
        if k == "carrot":
            if s.t < 200:
                p = G.p
                want = math.atan2(p.y - 30 - s.y, p.x - s.x)
                d = (want - s.ang + math.pi) % (2 * math.pi) - math.pi
                s.ang += clamp(d, -0.045, 0.045)
            s.vx = math.cos(s.ang) * s.sp
            s.vy = math.sin(s.ang) * s.sp
        elif k == "fly":
            s.vx = math.sin(s.t * 0.07 + s.ph) * 2.6
        elif k == "gear":
            if s.y >= GROUND - s.r and s.vy >= 0:
                s.y = GROUND - s.r
                s.vy = -8.5
            s.spin -= 0.2
        elif k in ("card", "star"):
            s.spin += 0.22
        elif k == "roll":
            s.spin -= 0.15
        elif k == "bee":
            s.vy = math.sin(s.t * 0.12 + s.ph) * 2.6
        s.vy += s.g
        s.x += s.vx
        s.y += s.vy
        if k == "bomb" and s.y >= GROUND - s.r:
            s.dead = True
            G.bomb_boom(s)
        if s.skin in ("honey", "snow") and s.vy > 0 and s.y >= GROUND - s.r:
            s.dead = True
            G.burst(s.x, GROUND - 6, "#ffffff" if s.skin == "snow" else GOLD, 8, 4)
        if k == "ice" and s.y >= GROUND - 10:
            s.dead = True
            G.burst(s.x, GROUND - 6, "#bfeaff", 8, 4)
        if s.flash > 0:
            s.flash -= 1
        if s.t > s.life or s.x < G.camx - 90 or s.x > G.camx + W + 90 or s.y > H + 90 or s.y < -140:
            s.dead = True


def hits_player(sh, p):
    if sh.kind == "wave":
        return abs(sh.x - p.x) < sh.r + 10 and p.y > GROUND - sh.hh
    bx1, by1, bx2, by2 = p.box()
    cx = clamp(sh.x, bx1, bx2)
    cy = clamp(sh.y, by1, by2)
    return math.hypot(sh.x - cx, sh.y - cy) < sh.r * 0.8


# -------------------------------------------------------------------- bosslar
class Base:
    def pick(s, opts):
        o = [x for x in opts if x != s.last] or opts
        s.last = random.choice(o)
        return s.last

    def hurt(s, d):
        s.hp = max(0, s.hp - d)
        s.flash = 2


class Frog(Base):
    name = "KURBAĞA KRAL"
    maxhp = 250

    def __init__(s, g):
        s.g = g
        s.hp = s.maxhp
        s.x = 770.0
        s.y = float(GROUND)
        s.vx = s.vy = 0.0
        s.st = "idle"
        s.tm = 60
        s.t = 0
        s.flash = 0
        s.ph = 1
        s.face = -1
        s.n = 0
        s.sq = 1.0
        s.mouth = 0
        s.last = ""
        s.dead = False

    def boxes(s):
        return [(s.x - 70, s.y - 165, s.x + 70, s.y - 8)]

    def update(s):
        g = s.g
        p = g.p
        s.t += 1
        s.flash = max(0, s.flash - 1)
        s.mouth = max(0, s.mouth - 1)
        if s.st not in ("air",):
            s.face = -1 if p.x < s.x else 1
        if s.ph == 1 and s.hp <= s.maxhp * 0.5:
            s.ph = 2
            s.st = "roar"
            s.tm = 70
            g.shake = 12
        st = s.st
        if st == "idle":
            s.sq = 1 + 0.03 * math.sin(s.t * 0.12)
            s.tm -= 1
            if s.tm <= 0:
                a = s.pick(["spit", "jump"] + (["flies"] if s.ph == 2 else []))
                s.st = a + "_w"
                s.tm = 26
                s.n = 0
        elif st == "roar":
            s.sq = 1.1 + 0.05 * math.sin(s.t)
            s.mouth = 2
            s.tm -= 1
            if s.tm <= 0:
                s.st = "idle"
                s.tm = 30
        elif st == "spit_w":
            s.sq = 0.9
            s.tm -= 1
            if s.tm <= 0:
                s.st = "spit"
                s.tm = 0
        elif st == "spit":
            s.tm -= 1
            if s.tm <= 0:
                total = 3 if s.ph == 1 else 5
                mx = s.x + s.face * 66
                my = s.y - 100
                ang = math.atan2(p.y - 30 - my, p.x - mx) + random.uniform(-0.12, 0.12)
                sp = 5.6 if s.ph == 1 else 6.6
                pink = (s.n == total - 1) or (s.ph == 2 and s.n == 1)
                g.shots.append(Shot("ball", mx, my, math.cos(ang) * sp, math.sin(ang) * sp,
                                    r=14, pink=pink))
                s.mouth = 10
                s.n += 1
                s.tm = 18 if s.ph == 1 else 13
                s.sq = 1.08
                if s.n >= total:
                    s.st = "idle"
                    s.tm = 55 if s.ph == 1 else 38
        elif st == "jump_w":
            s.sq = 0.78
            s.tm -= 1
            if s.tm <= 0:
                s.st = "air"
                s.vy = -23.0
                T = 2 * 23.0 / 0.9
                tx = random.uniform(170, 330) if s.x > 480 else random.uniform(640, 790)
                s.vx = (tx - s.x) / T
        elif st == "air":
            s.vy += 0.9
            s.x += s.vx
            s.y += s.vy
            s.sq = 1.18 if s.vy < 0 else 1.05
            if s.y >= GROUND:
                s.y = float(GROUND)
                s.vy = 0
                s.vx = 0
                s.st = "land"
                s.tm = 34
                g.shake = 12
                g.dust(s.x, GROUND, 10)
                sp = 6.5 if s.ph == 1 else 7.8
                for d in (-1, 1):
                    g.shots.append(Shot("wave", s.x + d * 60, GROUND - 2, d * sp, 0, r=16, hh=40))
            elif s.vy > 0:
                bx = s.boxes()[0]
                px1, py1, px2, py2 = p.box()
                if px1 < bx[2] and px2 > bx[0] and py1 < bx[3] and py2 > bx[1]:
                    g.hurt_player()
        elif st == "land":
            s.sq = 0.8 + 0.2 * (1 - s.tm / 34.0)
            s.tm -= 1
            if s.tm <= 0:
                s.st = "idle"
                s.tm = 40 if s.ph == 1 else 26
        elif st == "flies_w":
            s.mouth = 2
            s.sq = 1.1
            s.tm -= 1
            if s.tm <= 0:
                s.st = "flies"
                s.tm = 0
        elif st == "flies":
            s.tm -= 1
            if s.tm <= 0:
                g.shots.append(Shot("fly", random.uniform(80, 880), -20, 0, 2.4, r=13,
                                    pink=(s.n % 3 == 2), ph=random.uniform(0, 6), life=500))
                s.n += 1
                s.tm = 16
                if s.n >= 7:
                    s.st = "idle"
                    s.tm = 45

    def draw(s, g, ox=0):
        p = g.p
        x = s.x + ox
        y = s.y
        sq = s.sq
        fl = s.flash > 0

        def C(c):
            return "#ffffff" if fl else c
        green, dk, belly = C("#69b043"), C("#3d7a2b"), C("#e4f09a")
        g.ov(x, GROUND + 5, 92, 9, mix(g.gcol, INK, .5), 0, "")
        g.ov(x - 62, y - 20 * sq, 34, 22 * sq, dk)
        g.ov(x + 62, y - 20 * sq, 34, 22 * sq, dk)
        g.ov(x, y - 72 * sq, 82, 72 * sq, green)
        g.ov(x, y - 52 * sq, 56, 46 * sq, belly, 2)
        for d in (-1, 1):
            g.ov(x + d * 60, y - 8, 36, 13, green)
            g.ov(x + d * 40, y - 60 * sq, 17, 26 * sq, dk, 2)
        for d in (-1, 1):
            ex = x + d * 38
            ey = y - 146 * sq
            g.ov(ex, ey, 28, 28, green)
            g.ov(ex, ey, 21, 21, C("#fffbe8"), 2)
            dx = p.x - ex
            dy = (p.y - 30) - ey
            dd = math.hypot(dx, dy) or 1
            g.ov(ex + dx / dd * 8, ey + dy / dd * 8, 9, 11, INK, 0, "")
            lid = 4 if s.ph == 1 else 12
            g.pl([(ex + d * 30, ey - 34), (ex - d * 30, ey - 34), (ex - d * 30, ey - lid - 2),
                  (ex + d * 30, ey - lid - 18)], green, 3)
        my = y - 92 * sq
        if s.mouth > 0:
            g.ov(x, my + 6, 50, 24, "#7a1f1f")
            g.ov(x, my + 18, 28, 9, PINK, 0, "")
        else:
            g.ln([(x - 54, my - 6), (x, my + 12), (x + 54, my - 6)], 6, INK, True)
        cy = y - 184 * sq
        g.pl([(x - 26, cy + 8), (x - 26, cy - 20), (x - 13, cy - 6), (x, cy - 26),
              (x + 13, cy - 6), (x + 26, cy - 20), (x + 26, cy + 8)], C(GOLD))
        g.ov(x, cy - 2, 5, 5, C(RED), 2)
        for wx, wy in ((-50, -100), (-62, -70), (55, -105), (64, -64)):
            g.ov(x + wx, y + wy * sq, 6, 5, dk, 2)


class Mage(Base):
    name = "SİHİRBAZ TAVŞAN"
    maxhp = 320

    def __init__(s, g):
        s.g = g
        s.hp = s.maxhp
        s.bx, s.by = 760.0, 250.0
        s.x, s.y = s.bx, s.by
        s.st = "idle"
        s.tm = 70
        s.t = 0
        s.flash = 0
        s.ph = 1
        s.n = 0
        s.vol = 0
        s.last = ""
        s.dead = False
        s.vis = 1.0
        s.puff = 0

    def boxes(s):
        if s.vis < 0.5:
            return []
        return [(s.x - 62, s.y - 110, s.x + 62, s.y + 105)]

    def fan(s):
        g = s.g
        p = g.p
        n = 5 if s.ph == 1 else 7
        sp = 6.2 if s.ph == 1 else 7.0
        spread = 1.0 if s.ph == 1 else 1.3
        a0 = math.atan2(p.y - 30 - s.y, p.x - s.x) + random.uniform(-0.15, 0.15)
        pk = random.randrange(n) if random.random() < 0.75 else -1
        for i in range(n):
            a = a0 - spread / 2 + spread * i / (n - 1)
            g.shots.append(Shot("card", s.x - 20, s.y, math.cos(a) * sp, math.sin(a) * sp,
                                r=12, pink=(i == pk)))

    def update(s):
        g = s.g
        p = g.p
        s.t += 1
        s.flash = max(0, s.flash - 1)
        s.y = s.by + math.sin(s.t * 0.06) * 16
        s.x = s.bx + math.sin(s.t * 0.031) * 18
        if s.ph == 1 and s.hp <= s.maxhp * 0.5:
            s.ph = 2
            g.shake = 10
            s.st = "idle"
            s.tm = 40
            g.burst(s.x, s.y, PINK, 24, 6)
        st = s.st
        if st == "idle":
            s.tm -= 1
            if s.tm <= 0:
                a = s.pick(["cards", "carrots", "tele"] + (["stars"] if s.ph == 2 else []))
                s.st = a + "_w"
                s.tm = 26
                s.n = 0
                if a == "cards":
                    s.vol = 2 if s.ph == 1 else 3
        elif st == "cards_w":
            s.tm -= 1
            if s.tm <= 0:
                s.st = "cards"
                s.tm = 0
        elif st == "cards":
            s.tm -= 1
            if s.tm <= 0:
                if s.vol <= 0:
                    s.st = "idle"
                    s.tm = 55 if s.ph == 1 else 38
                else:
                    s.fan()
                    s.vol -= 1
                    s.tm = 44
        elif st == "carrots_w":
            s.tm -= 1
            if s.tm <= 0:
                s.st = "carrots"
        elif st == "carrots":
            n = 2 if s.ph == 1 else 3
            pk = random.randrange(n)
            for i in range(n):
                a = math.atan2(p.y - 30 - s.y, p.x - s.x) + (i - (n - 1) / 2.0) * 0.7
                sp = 4.4 + 0.7 * (s.ph - 1)
                g.shots.append(Shot("carrot", s.x - 30, s.y + 10, math.cos(a) * 3, math.sin(a) * 3,
                                    r=15, pink=(i == pk and random.random() < 0.7), hp=3, sp=sp))
            s.st = "idle"
            s.tm = 85
        elif st == "tele_w":
            s.tm -= 1
            if s.tm <= 0:
                s.st = "vanish"
                s.tm = 22
                g.burst(s.x, s.y, "#e9dcff", 14, 4)
        elif st == "vanish":
            s.vis = s.tm / 22.0
            s.tm -= 1
            if s.tm <= 0:
                spots = [(800, 260), (170, 250), (480, 190)]
                spots = [q for q in spots if abs(q[0] - s.bx) > 60]
                s.bx, s.by = random.choice(spots)
                s.st = "appear"
                s.tm = 22
        elif st == "appear":
            s.vis = 1 - s.tm / 22.0
            s.tm -= 1
            if s.tm <= 0:
                s.vis = 1.0
                s.st = "cards_w"
                s.tm = 10
                s.vol = 1
                g.burst(s.bx, s.by, "#e9dcff", 14, 4)
        elif st == "stars_w":
            s.tm -= 1
            if s.tm <= 0:
                s.st = "stars"
                s.tm = 0
                s.n = 0
        elif st == "stars":
            s.tm -= 1
            if s.tm <= 0:
                if s.n >= 3:
                    s.st = "idle"
                    s.tm = 55
                else:
                    gi = random.randint(1, 8)
                    pk = random.choice([i for i in range(10) if abs(i - gi) > 1])
                    for i in range(10):
                        if abs(i - gi) <= 1:
                            continue
                        g.shots.append(Shot("star", 48 + i * (W - 96) / 9.0, -20, 0, 4.2, r=16,
                                            pink=(i == pk), life=300))
                    s.n += 1
                    s.tm = 70

    def draw(s, g, ox=0):
        p = g.p
        if s.vis < 0.06:
            return
        x = s.x + ox
        y = s.y
        fl = s.flash > 0

        def C(c):
            return "#ffffff" if fl else c
        sc = 0.55 + 0.45 * s.vis
        g.ov(x, GROUND + 5, 60 * sc, 8, mix(g.gcol, INK, .5), 0, "")
        g.pl([(x - 60 * sc, y + 10), (x + 60 * sc, y + 10), (x + 92 * sc, y + 140 * sc),
              (x - 92 * sc, y + 140 * sc)], C("#7a35b5"), 3, True)
        g.ov(x, y + 55 * sc, 48 * sc, 62 * sc, C("#241532"))
        g.ov(x, y + 55 * sc, 22 * sc, 42 * sc, C("#fff6e0"), 2)
        sw = math.sin(s.t * 0.12) * 6
        g.limb((x - 36 * sc, y + 44), (x - 80 * sc, y + 20 + sw), 6)
        g.ov(x - 82 * sc, y + 18 + sw, 10, 10, WHITE)
        g.limb((x + 36 * sc, y + 44), (x + 78 * sc, y + 64 - sw), -6)
        g.ov(x + 80 * sc, y + 66 - sw, 10, 10, WHITE)
        for d in (-1, 1):
            e = [(x + d * 14, y - 30), (x + d * 22, y - 118 * sc - 6), (x + d * 46, y - 112 * sc),
                 (x + d * 36, y - 30)]
            g.pl(e, C(WHITE), 3, True)
            g.pl([(x + d * 20, y - 36), (x + d * 27, y - 100 * sc), (x + d * 38, y - 96 * sc),
                  (x + d * 31, y - 36)], C("#ffb3d1"), 0, True, "")
        g.ov(x, y - 6, 42 * sc, 38 * sc, C(WHITE))
        g.rc(x - 27, y - 84, x + 27, y - 40, C("#1b1b22"))
        g.rc(x - 27, y - 58, x + 27, y - 46, C(RED), 2)
        g.ov(x, y - 41, 42, 8, C("#1b1b22"))
        if s.st in ("cards_w", "carrots_w", "stars_w", "tele_w"):
            g.pl(star_pts(x, y - 98, 12, 5, 4, s.t * 0.2), GOLD, 2)
        for d in (-1, 1):
            ex = x + d * 15
            ey = y - 10
            g.ov(ex, ey, 9, 11, WHITE, 2)
            dx = p.x - ex
            dy = (p.y - 30) - ey
            dd = math.hypot(dx, dy) or 1
            g.ov(ex + dx / dd * 3, ey + dy / dd * 3, 4, 6, INK, 0, "")
            g.ln([(ex - d * 12, ey - 17 + (4 if s.ph == 2 else 0)), (ex + d * 8, ey - 10)], 4, INK)
        g.ov(x, y + 3, 6, 4, C(PINK), 2)
        g.rc(x - 6, y + 9, x + 6, y + 21, WHITE, 2)
        g.ln([(x, y + 9), (x, y + 21)], 1, INK)
        for d in (-1, 1):
            g.ln([(x + d * 10, y + 4), (x + d * 38, y), ], 2, INK)
            g.ln([(x + d * 10, y + 8), (x + d * 38, y + 12)], 2, INK)


class Clock(Base):
    name = "ZAMAN EFENDİSİ"
    maxhp = 420
    cx = 745.0
    cy = 225.0
    L = 520

    def __init__(s, g):
        s.g = g
        s.hp = s.maxhp
        s.st = "idle"
        s.tm = 80
        s.t = 0
        s.flash = 0
        s.ph = 1
        s.n = 0
        s.last = ""
        s.dead = False
        s.beams = []
        s.live = False
        s.a0 = 0.0
        s.dr = 1
        s.el = 0
        s.om = 0.034
        s.hand = 0.0

    def boxes(s):
        return [(s.cx - 100, s.cy - 100, s.cx + 100, s.cy + 100)]

    def ring(s):
        g = s.g
        n = 16 if s.ph == 1 else 22
        off = random.uniform(0, math.tau)
        sp = 3.8 if s.ph == 1 else 4.5
        pk = set(random.sample(range(n), 2))
        for i in range(n):
            a = off + i * math.tau / n
            g.shots.append(Shot("ball", s.cx, s.cy, math.cos(a) * sp, math.sin(a) * sp,
                                r=10, pink=(i in pk), life=400))

    def update(s):
        g = s.g
        p = g.p
        s.t += 1
        s.flash = max(0, s.flash - 1)
        s.hand += 0.03
        if s.ph == 1 and s.hp <= s.maxhp * 0.5:
            s.ph = 2
            s.st = "idle"
            s.tm = 50
            s.beams = []
            s.live = False
            g.shake = 12
            s.ring()
        st = s.st
        if st == "idle":
            s.tm -= 1
            if s.tm <= 0:
                a = s.pick(["ring", "sweep", "gear"] + (["bomb"] if s.ph == 2 else []))
                s.st = a + "_w"
                s.tm = 36
                s.n = 0
                if a == "sweep":
                    s.dr = random.choice((-1, 1))
                    ang = math.atan2(p.y - 30 - s.cy, p.x - s.cx)
                    s.a0 = ang - s.dr * 1.1
                    s.om = 0.034 if s.ph == 1 else 0.040
                    s.live = False
                    s.beams = [s.a0] + ([s.a0 + math.pi] if s.ph == 2 else [])
                    s.tm = 50
        elif st == "ring_w":
            s.tm -= 1
            if s.tm <= 0:
                s.st = "ring"
                s.tm = 0
        elif st == "ring":
            s.tm -= 1
            if s.tm <= 0:
                if s.n >= (2 if s.ph == 1 else 3):
                    s.st = "idle"
                    s.tm = 60
                else:
                    s.ring()
                    s.n += 1
                    s.tm = 44
        elif st == "sweep_w":
            s.tm -= 1
            if s.tm <= 0:
                s.st = "sweep"
                s.el = 0
                s.live = True
                s.tm = 150
        elif st == "sweep":
            s.el += 1
            a = s.a0 + s.dr * s.el * s.om
            s.beams = [a] + ([a + math.pi] if s.ph == 2 else [])
            for b in s.beams:
                d = seg_dist(p.x, p.y - 28, s.cx, s.cy, s.cx + s.L * math.cos(b),
                             s.cy + s.L * math.sin(b))
                if d < 20:
                    g.hurt_player()
            s.tm -= 1
            if s.tm <= 0:
                s.beams = []
                s.live = False
                s.st = "idle"
                s.tm = 60
        elif st == "gear_w":
            s.tm -= 1
            if s.tm <= 0:
                s.st = "gear"
                s.tm = 0
        elif st == "gear":
            s.tm -= 1
            if s.tm <= 0:
                total = 2 if s.ph == 1 else 3
                g.shots.append(Shot("gear", W + 30, GROUND - 28, -5.4 if s.ph == 1 else -6.4, 0,
                                    r=28, g=0.5, pink=(s.n == 1), life=500))
                s.n += 1
                s.tm = 55
                if s.n >= total:
                    s.st = "idle"
                    s.tm = 80
        elif st == "bomb_w":
            s.tm -= 1
            if s.tm <= 0:
                s.st = "bomb"
                s.tm = 0
        elif st == "bomb":
            s.tm -= 1
            if s.tm <= 0:
                x = clamp(p.x + random.uniform(-150, 150), 40, 920)
                g.shots.append(Shot("bomb", x, -24, 0, 2.5, r=17, g=0.22, life=300))
                s.n += 1
                s.tm = 24
                if s.n >= 4:
                    s.st = "idle"
                    s.tm = 75

    def draw(s, g, ox=0):
        p = g.p
        cx = s.cx + ox
        cy = s.cy + math.sin(s.t * 0.05) * 5
        fl = s.flash > 0

        def C(c):
            return "#ffffff" if fl else c
        gold = C("#e8b43a")
        g.ov(cx, GROUND + 5, 90, 9, mix(g.gcol, INK, .5), 0, "")
        for d in (-1, 1):
            g.ln([(cx + d * 40, cy + 100), (cx + d * 55, GROUND - 16)], 14, INK)
            g.ln([(cx + d * 40, cy + 100), (cx + d * 55, GROUND - 16)], 8, CREAM)
            g.ov(cx + d * 62, GROUND - 8, 24, 11, "#8a4a22")
        ring_ = math.sin(s.t * 0.9) * 0.2 if s.st.endswith("_w") else 0
        for d in (-1, 1):
            bxp = cx + d * 70
            byp = cy - 100
            g.ln([(cx + d * 40, cy - 90), (bxp, byp)], 8, INK)
            g.ov(bxp + d * ring_ * 30, byp - 8, 28, 20, C("#d9d9e8"))
            g.ov(bxp + d * ring_ * 30, byp - 8, 10, 7, INK, 0, "")
        g.ov(cx, cy, 118, 118, gold, 5)
        g.ov(cx, cy, 96, 96, C(CREAM), 3)
        for i in range(12):
            a = i * math.pi / 6
            g.ln([(cx + math.cos(a) * 80, cy + math.sin(a) * 80),
                  (cx + math.cos(a) * 92, cy + math.sin(a) * 92)], 4, INK)
        for d in (-1, 1):
            ex = cx + d * 30
            ey = cy - 20
            g.ov(ex, ey, 14, 20, INK, 0, "")
            dx = p.x - ex
            dy = (p.y - 30) - ey
            dd = math.hypot(dx, dy) or 1
            g.ov(ex + dx / dd * 4, ey + dy / dd * 6, 6, 8, "#ffffff", 0, "")
            g.ln([(ex - d * 18, ey - 28), (ex + d * 14, ey - 18)], 5, INK)
        g.pl([(cx - 36, cy + 28), (cx, cy + 46), (cx + 36, cy + 28), (cx + 30, cy + 22),
              (cx, cy + 32), (cx - 30, cy + 22)], INK, 3, True)
        for i in range(-2, 3):
            g.rc(cx + i * 11 - 4, cy + 28, cx + i * 11 + 4, cy + 36, WHITE, 1)
        if not s.beams:
            for ln_, ang, w in ((50, s.hand, 6), (34, s.hand / 12.0, 8)):
                g.ln([(cx, cy), (cx + math.cos(ang) * ln_, cy + math.sin(ang) * ln_)], w, INK)
        for a in s.beams:
            tx = cx + s.L * math.cos(a)
            ty = cy + s.L * math.sin(a)
            if not s.live:
                if (s.t // 4) % 2 == 0:
                    g.c.create_line(cx, cy, tx, ty, fill=RED, width=3, dash=(10, 10), tags="d")
                    g.tx(clamp(cx + 150 * math.cos(a), 30, W - 30),
                         clamp(cy + 150 * math.sin(a), 60, H - 80), "!", 30, RED)
            else:
                nx, ny = -math.sin(a), math.cos(a)
                g.pl([(cx + nx * 12, cy + ny * 12), (tx, ty), (cx - nx * 12, cy - ny * 12)],
                     C(GOLD), 4)
                g.ln([(cx, cy), (cx + (tx - cx) * 0.9, cy + (ty - cy) * 0.9)], 3, WHITE)


# --------------------------------------------------------------------- bölümler
class Snowman(Base):
    name = "KAR ADAM KRAL"
    maxhp = 300

    def __init__(s, g):
        s.g = g
        s.hp = s.maxhp
        s.x = 780.0
        s.y = float(GROUND)
        s.st = "idle"
        s.tm = 70
        s.t = 0
        s.flash = 0
        s.ph = 1
        s.n = 0
        s.last = ""
        s.dead = False
        s.face = -1
        s.sq = 1.0

    def boxes(s):
        return [(s.x - 72, s.y - 255, s.x + 72, s.y - 6)]

    def update(s):
        g = s.g
        p = g.p
        s.t += 1
        s.flash = max(0, s.flash - 1)
        s.face = -1 if p.x < s.x else 1
        s.sq = 1 + 0.025 * math.sin(s.t * 0.1)
        if s.ph == 1 and s.hp <= s.maxhp * 0.5:
            s.ph = 2
            s.st = "roar"
            s.tm = 60
            g.shake = 12
        st = s.st
        if st == "idle":
            s.tm -= 1
            if s.tm <= 0:
                a = s.pick(["balls", "roll", "ice"])
                s.st = a + "_w"
                s.tm = 28
                s.n = 0
        elif st == "roar":
            s.tm -= 1
            if s.tm <= 0:
                s.st = "idle"
                s.tm = 35
        elif st in ("balls_w", "roll_w", "ice_w"):
            s.tm -= 1
            if s.tm <= 0:
                s.st = st[:-2]
                s.tm = 0
        elif st == "balls":
            s.tm -= 1
            if s.tm <= 0:
                total = 3 if s.ph == 1 else 5
                mx, my = s.x - 50, s.y - 215
                T = random.uniform(55, 75)
                tx = p.x + random.uniform(-50, 50)
                vx = (tx - mx) / T
                vy = (p.y - 30 - my) / T - 0.5 * 0.28 * T
                g.shots.append(Shot("ball", mx, my, vx, vy, r=15, g=0.28,
                                    pink=(s.n == total - 1), skin="snow", life=300))
                s.n += 1
                s.tm = 24 if s.ph == 1 else 16
                if s.n >= total:
                    s.st = "idle"
                    s.tm = 60 if s.ph == 1 else 42
        elif st == "roll":
            s.tm -= 1
            if s.tm <= 0:
                cnt = 1 if s.ph == 1 else 2
                g.shots.append(Shot("roll", s.x - 60, GROUND - 34, -(5.2 if s.ph == 1 else 6.4), 0,
                                    r=34, life=400))
                s.n += 1
                s.tm = 60
                if s.n >= cnt:
                    s.st = "idle"
                    s.tm = 80 if s.ph == 1 else 55
        elif st == "ice":
            s.tm -= 1
            if s.tm <= 0:
                total = 6 if s.ph == 1 else 9
                if s.n == 0:
                    x = p.x + random.uniform(-40, 40)
                else:
                    x = clamp(p.x + random.uniform(-170, 170), 30, 930)
                g.shots.append(Shot("ice", x, -30, 0, 3.0, r=12, g=0.18, life=300))
                s.n += 1
                s.tm = 15 if s.ph == 1 else 11
                if s.n >= total:
                    s.st = "idle"
                    s.tm = 55

    def draw(s, g, ox=0):
        x = s.x + ox
        y = s.y
        fl = s.flash > 0

        def C(c):
            return "#ffffff" if fl else c
        wh = C("#f4fbff")
        sq = s.sq
        f = s.face
        g.ov(x, GROUND + 5, 95, 9, mix(g.gcol, INK, .5), 0, "")
        g.ov(x, y - 62 * sq, 82, 62 * sq, wh)
        g.ov(x, y - 150 * sq, 58, 52 * sq, wh)
        g.ov(x, y - 226 * sq, 44, 40 * sq, wh)
        for yy in (-172, -150, -128):
            g.ov(x, y + yy * sq, 6, 6, INK, 0, "")
        cast = s.st in ("balls_w", "balls", "ice_w", "ice")
        lift = -60 if cast else 28
        ay = y - 160 * sq
        for d in (-1, 1):
            tip = (x + d * 122, ay + lift)
            g.ln([(x + d * 52, ay), tip], 9, INK)
            g.ln([(x + d * 52, ay), tip], 5, "#7a4a22")
            g.ln([(tip[0] - d * 18, tip[1] + (lift * -0.25)), (tip[0] + d * 12, tip[1] - 14)], 4, "#7a4a22")
        g.pl([(x - 48, y - 192 * sq), (x + 48, y - 192 * sq), (x + 44, y - 172 * sq), (x - 44, y - 172 * sq)],
             C(RED), 3, True)
        g.pl([(x + 20, y - 176 * sq), (x + 44, y - 176 * sq), (x + 52, y - 120 * sq), (x + 30, y - 126 * sq)],
             C(RED), 3, True)
        hy = y - 230 * sq
        for d in (-1, 1):
            g.ov(x + d * 16, hy, 6, 7, INK, 0, "")
            g.ln([(x + d * 26, hy - 14), (x + d * 8, hy - 8)], 4, INK)
        g.pl([(x + f * 2, hy + 6), (x + f * 2, hy + 16), (x + f * 44, hy + 12)], C("#ff8c1a"), 3)
        for k in range(5):
            g.ov(x - 16 + k * 8, hy + 28 + (k - 2) ** 2 * 1.4, 3, 3, INK, 0, "")
        g.ov(x, y - 262 * sq, 46, 9, C("#2d3a8a"))
        g.rc(x - 31, y - 298 * sq, x + 31, y - 262 * sq, C("#2d3a8a"))
        g.rc(x - 31, y - 276 * sq, x + 31, y - 266 * sq, C(GOLD), 2)


class Bee(Base):
    name = "KRAL ARI"
    maxhp = 300

    def __init__(s, g):
        s.g = g
        s.hp = s.maxhp
        s.bx, s.by = 760.0, 210.0
        s.x, s.y = s.bx, s.by
        s.st = "idle"
        s.tm = 70
        s.t = 0
        s.flash = 0
        s.ph = 1
        s.n = 0
        s.last = ""
        s.dead = False
        s.ty = 300.0
        s.vx = 0.0

    def boxes(s):
        return [(s.x - 70, s.y - 60, s.x + 70, s.y + 60)]

    def update(s):
        g = s.g
        p = g.p
        s.t += 1
        s.flash = max(0, s.flash - 1)
        if s.ph == 1 and s.hp <= s.maxhp * 0.5:
            s.ph = 2
            g.shake = 10
            g.burst(s.x, s.y, GOLD, 24, 6)
            if s.st in ("dive_w", "dive", "ret"):
                s.st = "ret"
                s.x = 1120.0
            else:
                s.st = "idle"
                s.tm = 40
        st = s.st
        if st in ("idle", "honey_w", "honey", "swarm_w", "swarm"):
            s.y = s.by + math.sin(s.t * 0.06) * 18
            s.x = s.bx + math.sin(s.t * 0.04) * 20
        if st == "idle":
            s.tm -= 1
            if s.tm <= 0:
                a = s.pick(["honey", "swarm", "dive"])
                s.n = 0
                if a == "dive":
                    s.st = "dive_w"
                    s.tm = 44
                else:
                    s.st = a + "_w"
                    s.tm = 26
        elif st in ("honey_w", "swarm_w"):
            s.tm -= 1
            if s.tm <= 0:
                s.st = st[:-2]
                s.tm = 0
        elif st == "honey":
            s.tm -= 1
            if s.tm <= 0:
                total = 5 if s.ph == 1 else 7
                g.shots.append(Shot("ball", s.x - 20, s.y + 25, random.uniform(-6.5, -1.2),
                                    random.uniform(-7, -2), r=15, g=0.26, skin="honey",
                                    pink=(s.n == 2), life=300))
                s.n += 1
                s.tm = 12
                if s.n >= total:
                    s.st = "idle"
                    s.tm = 60 if s.ph == 1 else 40
        elif st == "swarm":
            s.tm -= 1
            if s.tm <= 0:
                total = 6 if s.ph == 1 else 8
                g.shots.append(Shot("bee", s.x - 30, s.y + random.uniform(-30, 60),
                                    -(3.4 if s.ph == 1 else 4.2), 0, r=12, ph=random.uniform(0, 6),
                                    pink=(s.n % 4 == 3), life=400))
                s.n += 1
                s.tm = 14
                if s.n >= total:
                    s.st = "idle"
                    s.tm = 55
        elif st == "dive_w":
            s.tm -= 1
            s.x += (900 - s.x) * 0.12
            s.ty = clamp(p.y - 40, 130, GROUND - 45)
            s.y += (s.ty - s.y) * 0.12
            if s.tm <= 0:
                s.st = "dive"
                s.vx = -17.0
                s.n += 1
        elif st == "dive":
            s.x += s.vx
            s.y = s.ty
            bx = s.boxes()[0]
            pb = p.box()
            if pb[0] < bx[2] and pb[2] > bx[0] and pb[1] < bx[3] and pb[3] > bx[1]:
                g.hurt_player()
            if s.x < -140:
                s.st = "ret"
                s.x = 1120.0
                s.y = s.by
        elif st == "ret":
            s.x += (s.bx - s.x) * 0.07
            s.y += (s.by - s.y) * 0.1
            if abs(s.x - s.bx) < 8:
                s.x, s.y = s.bx, s.by
                if s.n < (1 if s.ph == 1 else 2):
                    s.st = "dive_w"
                    s.tm = 36
                else:
                    s.st = "idle"
                    s.tm = 60 if s.ph == 1 else 40

    def draw(s, g, ox=0):
        p = g.p
        x = s.x + ox
        y = s.y
        fl = s.flash > 0

        def C(c):
            return "#ffffff" if fl else c
        g.ov(x, GROUND + 5, max(20, 70 - (GROUND - y) * 0.12), 7, mix(g.gcol, INK, .5), 0, "")
        if s.st == "dive_w" and (s.t // 4) % 2 == 0:
            g.c.create_line(0, s.ty, W, s.ty, fill=RED, width=3, dash=(12, 10), tags="d")
            g.tx(W - 40, s.ty - 18, "!", 30, RED)
        wing = abs(math.sin(s.t * 0.8)) * 14 + 12
        g.ov(x + 5, y - 64, 38, wing, C("#e6f6ff"), 3)
        g.ov(x + 45, y - 58, 28, wing * 0.8, C("#e6f6ff"), 3)
        g.ov(x, y, 66, 52, C(GOLD))
        for dx in (-8, 16, 40):
            k = math.sqrt(max(0.05, 1 - (dx / 66.0) ** 2))
            g.ov(x + dx, y, 7, 50 * k, INK, 0, "")
        g.ov(x - 58, y - 6, 36, 34, C(GOLD))
        ex, ey = x - 66, y - 14
        g.ov(ex, ey, 11, 13, WHITE, 2)
        dx = p.x - ex
        dy = (p.y - 30) - ey
        dd = math.hypot(dx, dy) or 1
        g.ov(ex + dx / dd * 4, ey + dy / dd * 4, 4, 6, INK, 0, "")
        g.ln([(ex - 14, ey - 18), (ex + 10, ey - 8)], 4, INK)
        g.ln([(x - 80, y + 12), (x - 66, y + 20), (x - 52, y + 12)], 4, INK, True)
        g.ln([(x - 70, y - 36), (x - 84, y - 66)], 4, INK)
        g.ov(x - 86, y - 68, 5, 5, INK, 0, "")
        g.pl([(x - 76, y - 36), (x - 76, y - 52), (x - 66, y - 44), (x - 58, y - 56), (x - 50, y - 44),
              (x - 42, y - 52), (x - 42, y - 36)], C(GOLD), 3)
        g.pl([(x + 62, y - 9), (x + 104, y), (x + 62, y + 9)], C("#2b2b33"), 3)


class RGEnemy:
    """Koş & ateş bölümlerindeki düşmanlar."""

    def __init__(s, kind, x, y, x1=None, x2=None, hp=2, col="#c0552e"):
        s.kind = kind
        s.x = float(x)
        s.y = float(y)
        s.y0 = float(y)
        s.x1 = x1 if x1 is not None else x - 100
        s.x2 = x2 if x2 is not None else x + 100
        s.hp = hp
        s.t = random.randint(0, 60)
        s.vx = -1.4 if kind == "walker" else 0.0
        s.vy = 0.0
        s.face = -1
        s.dead = False
        s.flash = 0
        s.cd = random.randint(30, 90)
        s.col = col

    def box(s):
        if s.kind == "bat":
            return (s.x - 20, s.y - 16, s.x + 20, s.y + 16)
        if s.kind == "turret":
            return (s.x - 26, s.y - 44, s.x + 26, s.y)
        return (s.x - 18, s.y - 42, s.x + 18, s.y)

    def update(s, G):
        s.t += 1
        if s.flash > 0:
            s.flash -= 1
        p = G.p
        k = s.kind
        if k == "walker":
            s.x += s.vx
            if s.x < s.x1:
                s.x = s.x1
                s.vx = abs(s.vx)
            elif s.x > s.x2:
                s.x = s.x2
                s.vx = -abs(s.vx)
            s.face = 1 if s.vx > 0 else -1
        elif k == "hopper":
            if s.y < s.y0 - 0.5 or s.vy < 0:
                s.vy += 0.8
                s.y += s.vy
                s.x = clamp(s.x + s.vx, s.x1, s.x2)
                if s.y >= s.y0 and s.vy > 0:
                    s.y = s.y0
                    s.vy = 0
                    s.vx = 0
                    s.cd = 55 + random.randint(0, 40)
            else:
                s.cd -= 1
                s.face = 1 if p.x > s.x else -1
                if s.cd <= 0 and abs(p.x - s.x) < 480:
                    s.vy = -13.5
                    s.vx = s.face * 3.2
                    s.y -= 1
        elif k == "bat":
            s.x -= 2.6
            s.y = s.y0 + math.sin(s.t * 0.08) * 45
            if s.x < G.camx - 160:
                s.dead = True
        elif k == "turret":
            s.cd -= 1
            if s.cd <= 0 and G.camx + 30 <= s.x <= G.camx + W - 30:
                s.cd = int(110 / G.dif["bt"])
                mx, my = s.x, s.y - 30
                a = math.atan2(p.y - 30 - my, p.x - mx)
                sp = 4.6 * G.dif["shot"]
                G.shots.append(Shot("ball", mx, my, math.cos(a) * sp, math.sin(a) * sp, r=11,
                                    pink=(random.random() < 0.22), life=300))


def gen_rg(cfg, hpm=1.0):
    """Koş & ateş bölümü dünyasını (tohuma göre, her seferinde aynı) üretir."""
    rnd = random.Random(cfg["seed"])
    L = cfg["len"]
    dens = cfg.get("dens", 1.0)
    segs, plats, movers, ens, coins, orbs = [], [], [], [], [], []
    ecol = cfg.get("ecol", "#c0552e")
    seg0 = [0.0]

    def E(kind, x, y, x1=None, x2=None, hp=2):
        ens.append(RGEnemy(kind, x, y, x1, x2, max(1, int(round(hp * hpm))), ecol))

    def pit(x, gap):
        segs.append((seg0[0], x))
        seg0[0] = x + gap

    cx = 760.0
    last = ""
    allt = ["flat", "pit", "stairs", "gauntlet", "mover", "tower", "pit2"]
    while cx < L - 1100:
        t = rnd.choice([a for a in allt if a != last])
        last = t
        if t == "flat":
            w = rnd.uniform(640, 900)
            n = max(1, int(round(rnd.randint(2, 4) * dens)))
            for i in range(n):
                x = cx + 80 + (w - 160) * (i + rnd.random() * 0.6) / n
                k = rnd.choice(["walker", "walker", "hopper", "turret"])
                if k == "walker":
                    E("walker", x, GROUND, x - 110, x + 110, 2)
                elif k == "hopper":
                    E("hopper", x, GROUND, x - 140, x + 140, 3)
                else:
                    E("turret", x, GROUND, hp=5)
            cx += w
        elif t == "pit":
            gap = rnd.uniform(250, 300)
            gx = cx + 260
            E("walker", cx + 120, GROUND, cx + 20, cx + 220, 2)
            pit(gx, gap)
            plats.append((gx + gap / 2 - 45, gx + gap / 2 + 45, GROUND - 38))
            orbs.append((gx + gap * 0.3, GROUND - 175))
            if len(coins) < 5 and rnd.random() < 0.7:
                coins.append((gx + gap / 2, GROUND - 105))
            E("bat", gx + gap + 380, GROUND - 150)
            cx = gx + gap + 220
        elif t == "stairs":
            xs = cx + 120
            plats += [(xs, xs + 130, GROUND - 100), (xs + 230, xs + 360, GROUND - 180),
                      (xs + 470, xs + 600, GROUND - 100)]
            E("walker", xs + 65, GROUND - 100, xs + 15, xs + 115, 2)
            E("walker", xs + 295, GROUND - 180, xs + 245, xs + 345, 2)
            if len(coins) < 5:
                coins.append((xs + 295, GROUND - 245))
            E("hopper", xs + 360, GROUND, xs + 200, xs + 520, 3)
            E("bat", cx + 680, GROUND - 200)
            cx += 800
        elif t == "gauntlet":
            for i in range(int(3 * dens) + 1):
                E("bat", cx + 300 + i * 170, GROUND - rnd.choice([70, 110, 150]))
            E("turret", cx + 620, GROUND, hp=5)
            E("hopper", cx + 240, GROUND, cx + 100, cx + 380, 3)
            cx += 800
        elif t == "mover":
            gap = 400.0
            gx = cx + 220
            pit(gx, gap)
            movers.append(dict(bx=gx + gap / 2, y=GROUND - 28, w=110, amp=115, spd=0.032,
                               ph=rnd.uniform(0, 6), x1=0.0, dx=0.0))
            orbs.append((gx + gap / 2, GROUND - 190))
            if len(coins) < 5:
                coins.append((gx + gap / 2 + 80, GROUND - 120))
            E("bat", gx + gap + 300, GROUND - 120)
            cx = gx + gap + 240
        elif t == "tower":
            xs = cx + 160
            plats += [(xs, xs + 110, GROUND - 100), (xs + 170, xs + 280, GROUND - 195),
                      (xs + 30, xs + 140, GROUND - 290)]
            E("walker", xs + 55, GROUND - 100, xs + 10, xs + 100, 2)
            if len(coins) < 5:
                coins.append((xs + 85, GROUND - 335))
            E("bat", cx + 560, GROUND - 160)
            E("turret", cx + 440, GROUND, hp=5)
            cx += 700
        elif t == "pit2":
            x0 = cx + 200
            gap = 230.0
            pit(x0, gap)
            plats.append((x0 + gap / 2 - 40, x0 + gap / 2 + 40, GROUND - 30))
            isl0 = x0 + gap
            E("hopper", isl0 + 110, GROUND, isl0 + 30, isl0 + 190, 3)
            x1 = isl0 + 220
            pit(x1, gap)
            plats.append((x1 + gap / 2 - 40, x1 + gap / 2 + 40, GROUND - 50))
            orbs.append((x1 + gap / 2, GROUND - 190))
            if len(coins) < 5:
                coins.append((x1 + gap / 2, GROUND - 115))
            cx = x1 + gap + 200
    E("walker", L - 760, GROUND, L - 860, L - 660, 2)
    E("hopper", L - 520, GROUND, L - 640, L - 400, 3)
    E("turret", L - 360, GROUND, hp=5)
    segs.append((seg0[0], float(L)))
    xs_ = []
    for a, b in segs:
        if b - a > 400:
            xs_.append((a, b))
    while len(coins) < 5:
        a, b = rnd.choice(xs_)
        coins.append((rnd.uniform(a + 150, b - 150), GROUND - 75))
    coins = coins[:5]
    return dict(segs=segs, plats=plats, movers=movers, ens=ens, coins=coins, orbs=orbs,
                goal=L - 200.0, len=float(L))


def _rg(name, sub, theme, sky, ray, ground, far, near, pit, ecol, length, seed, par, stars, dens=1.0):
    return dict(name=name, sub=sub, kind="rg", theme=theme, sky=sky, ray=ray, ground=ground,
                far=far, near=near, pit=pit, ecol=ecol, len=length, seed=seed, par=par,
                stars=stars, dens=dens, plats=[])


LEVELS = [
    dict(name="KURBAĞA KRAL", sub="Bataklıkta Kavga", cls=Frog, theme="swamp",
         sky=("#fbe08a", "#f08f45"), ray="#fff0b0", ground="#6f9a3a", plats=[], par=75, stars=1),
    _rg("BATAKLIK KOŞUSU", "Koş, zıpla, ateş et!", "swamp", ("#fbe08a", "#f08f45"), "#fff0b0",
        "#6f9a3a", "#8dbb50", "#4e8a35", "#3c6a8a", "#c0552e", 6000, 11, 80, 1, 0.9),
    _rg("SONBAHAR ORMANI", "Düşen yapraklar, dikenli dostlar", "forest", ("#f7c97a", "#d9733a"),
        "#ffe2a8", "#8a5a2a", "#c9843a", "#7a3a1f", "#5a3a22", "#a33a2a", 6800, 23, 90, 1, 1.0),
    dict(name="SİHİRBAZ TAVŞAN", sub="Şapkadan Çıkan Bela", cls=Mage, theme="stage",
         sky=("#4b2a7a", "#c25a8a"), ray="#7a4aa8", ground="#8a4a2a",
         plats=[(120, 300, 350), (660, 840, 350)], par=95, stars=2),
    _rg("SİRK ÇATILARI", "Gösteri başlıyor", "circus", ("#6a3a9a", "#f08a9a"), "#a06ac8",
        "#b0392e", "#8a4aa8", "#e8c050", "#2a1a3a", "#e8c050", 7200, 37, 100, 2, 1.1),
    _rg("KARLI ZİRVE", "Buz gibi bir macera", "snow", ("#bfe6ff", "#f2fbff"), "#ffffff",
        "#dfeefa", "#a8cce6", "#2f6f58", "#6ab4e6", "#4a6ab8", 7400, 41, 105, 2, 1.1),
    dict(name="KAR ADAM KRAL", sub="Soğuk Karşılama", cls=Snowman, theme="snow",
         sky=("#a8d8f2", "#f4fbff"), ray="#ffffff", ground="#e8f2fa", plats=[(380, 560, 340)],
         par=100, stars=2),
    _rg("YANARDAĞ YOLU", "Zemin kızgın, kan kaynıyor", "lava", ("#4a1a1a", "#e0602a"), "#8a2a1a",
        "#4a3a3a", "#7a2a22", "#a8402a", "#ff7a2a", "#6a5a5a", 7600, 53, 110, 3, 1.2),
    _rg("DİŞLİ FABRİKASI", "Çarklar durmuyor", "tower", ("#17424a", "#3e8a7a"), "#2c6a68",
        "#5a4a3a", "#2b6a66", "#3c8a82", "#102a30", "#d8a02a", 8000, 67, 120, 3, 1.2),
    dict(name="KRAL ARI", sub="Bal Kokusu", cls=Bee, theme="meadow",
         sky=("#8fd8ff", "#fff3b0"), ray="#ffffff", ground="#79b844",
         plats=[(120, 300, 350), (660, 840, 350)], par=105, stars=3),
    _rg("BULUT PATİKASI", "Yer yok, sadece bulut", "sky", ("#7ad0ff", "#e8f8ff"), "#ffffff",
        "#f4f8ff", "#b8e0f8", "#98c8ec", "#4aa0e0", "#e8708a", 8400, 79, 125, 3, 1.2),
    dict(name="ZAMAN EFENDİSİ", sub="Vakit Daralıyor", cls=Clock, theme="tower",
         sky=("#17424a", "#3e8a7a"), ray="#2c6a68", ground="#5a4a3a",
         plats=[(90, 250, 360), (400, 560, 305)], par=120, stars=3),
]

MENU_CFG = dict(theme="menu", sky=("#f7d77a", "#ee9446"), ray="#ffe9a0", ground="#7b4d2b", plats=[])
GRADE_RANK = {"": 0, "D": 1, "C": 2, "B": 3, "A": 4, "S": 5}

HOWTO = [
    "Boss savaşları + KOŞ & ATEŞ bölümleri: sona ulaş, altınları topla!",
    "",
    "Varsayılan tuşlar (AYARLAR > KONTROLLER'den değiştirilebilir):",
    "A/D veya ← →  ...  koş          Space / Z  ...  zıpla (basılı = yüksek)",
    "X / J  ...  ateş (basılı tut),  ↑ / W ile yukarı nişan",
    "Shift / C  ...  atılma: atılırken hiçbir şey sana zarar veremez",
    "Q / E  ...  EX atışı (1 kart harcar, çok güçlü)",
    "FARE MODU: imleç yönüne nişan al, sol tık ateş, sağ tık EX",
    "",
    "PARRY: Havadayken PEMBE bir nesneye / pembe küreye tekrar zıpla!",
    "Her parry sana 1 EX kartı kazandırır. Çukura düşersen 1 can kaybedersin.",
    "R / fare tekerleği: silah değiştir (Çay Topu · Saçma · Takipçi)",
    "Hızlı bitir, az hasar al, çok parry yap = daha yüksek not.   F11: tam ekran",
]


# ------------------------------------------------------------------------ oyun
class Game:
    def __init__(s, root):
        s.root = root
        root.title("ÇAYCIK: Boss Savaşı")
        root.resizable(False, False)
        root.configure(bg=INK)
        s.save = s.load()
        s.settings = s.save["settings"]
        s.binds = s.settings["binds"]
        s.cv = tk.Canvas(root, width=W, height=H, highlightthickness=0, bg=INK)
        s.cv.pack(expand=True)
        s.c = Cv(s.cv)
        s.keys = set()
        s.pressed = set()
        s.rel = {}
        s.mx = s.my = 0.0
        s.mb = set()
        s.mpress = set()
        s.cap = None
        s.msg = ""
        s.msgt = 0
        s.stab = 0
        s.sidx = 0
        s.sslot = 0
        s.set_back = "menu"
        s.cur = ""
        root.bind("<KeyPress>", s.kd)
        root.bind("<KeyRelease>", s.ku)
        root.bind("<FocusOut>", lambda e: (s.keys.clear(), s.mb.clear()))
        s.cv.bind("<Motion>", s.on_motion)
        s.cv.bind("<MouseWheel>", lambda e: s.on_wheel(1 if e.delta > 0 else -1))
        s.cv.bind("<Button-4>", lambda e: s.on_wheel(-1))
        s.cv.bind("<Button-5>", lambda e: s.on_wheel(1))
        for nb in (1, 2, 3):
            bb = 1 if nb == 1 else 3
            s.cv.bind("<ButtonPress-%d>" % nb, lambda e, bb=bb: s.on_mouse(e, bb, True))
            s.cv.bind("<ButtonRelease-%d>" % nb, lambda e, bb=bb: s.on_mouse(e, bb, False))
        s.sfx = Sfx()
        s.sfx.on = bool(s.settings["sound"])
        s.sfx.music_on = bool(s.settings["music"])
        s.state = "menu"
        s.sel = 0
        s.lsel = 0
        s.psel = 0
        s.dsel = 0
        s.t = 0
        s.iris = None
        s.iris_c = (W / 2, H / 2)
        s.p = Player()
        s.boss = None
        s.shots, s.bul, s.parts, s.pops = [], [], [], []
        s.plats = []
        s.cfg = MENU_CFG
        s.gcol = MENU_CFG["ground"]
        s.bgkey = None
        s.bgoff = (0, 0)
        s.intro = 0
        s.ko = 0
        s.ft = 0
        s.shake = 0
        s.hitstop = 0
        s.dying = 0
        s.lv = 0
        s.rt = 0
        s.res = {}
        s.quit = False
        s.rings = []
        s.wheel = 0
        s.mode = "boss"
        s.camx = 0.0
        s.fin = 0
        s.rg = None
        s.coin_list = []
        s.orbs = []
        s.got = 0
        s.ncoin = 0
        s.safe = (110.0, float(GROUND))
        s.bacc = 0.0
        s.dif = DIFF[1]
        s.acc = 0.0
        s.last = time.perf_counter()
        s.apply_display()
        s.loop()

    # ------------------------------------------------------------ giriş / kayıt
    def kd(s, e):
        k = e.keysym.lower()
        k = NORM.get(k, k)
        if k in s.rel:
            try:
                s.root.after_cancel(s.rel.pop(k))
            except Exception:
                s.rel.pop(k, None)
        if k == "f11":
            if k not in s.keys:
                s.keys.add(k)
                s.toggle_fullscreen()
            return
        if s.state == "settings" and s.cap is not None:
            s.capture(k)
            return
        if k not in s.keys:
            s.keys.add(k)
            s.pressed.add(k)

    def ku(s, e):
        k = e.keysym.lower()
        k = NORM.get(k, k)
        if k in s.rel:
            return
        s.rel[k] = s.root.after(25, lambda k=k: s.drop(k))

    def drop(s, k):
        s.keys.discard(k)
        s.rel.pop(k, None)

    def held(s, *n):
        return any(k in s.keys for k in n)

    # ---- ayarlanabilir tuşlar / fare
    @property
    def mouse_mode(s):
        return s.settings["aim"] == "mouse"

    def act(s, name):
        return any(k and k in s.keys for k in s.binds[name])

    def actp(s, name):
        return any(k and k in s.pressed for k in s.binds[name])

    def shooting(s):
        return s.act("shoot") or (s.mouse_mode and 1 in s.mb)

    def ex_pressed(s):
        return s.actp("ex") or (s.mouse_mode and 3 in s.mpress)

    def on_wheel(s, d):
        s.wheel = d

    def ring(s, x, y, col, maxr=60, life=18):
        s.rings.append([x, y, col, life, life, maxr])

    def next_weapon(s, d=1):
        p = s.p
        p.weapon = (p.weapon + d) % len(WEAPONS)
        s.settings["weapon"] = p.weapon
        wp = WEAPONS[p.weapon]
        s.pop(p.x, p.y - 80, wp["name"], wp["col"])
        s.sfx.play("weapon")

    def steer(s, bl):
        if bl.kind != "homing":
            return
        best = None
        bd = 1e9
        if s.mode == "rg" and s.rg:
            for e in s.rg["ens"]:
                if e.dead or abs(e.x - s.camx - W / 2) > W * 0.6:
                    continue
                d = math.hypot(e.x - bl.x, e.y - 20 - bl.y)
                if d < bd:
                    bd = d
                    best = (e.x, e.y - 20)
        elif s.boss is not None and not s.boss.dead and s.intro <= 30:
            bx = s.boss.boxes()
            if bx:
                best = ((bx[0][0] + bx[0][2]) / 2.0, (bx[0][1] + bx[0][3]) / 2.0)
        if best:
            want = math.atan2(best[1] - bl.y, best[0] - bl.x)
            cur = math.atan2(bl.vy, bl.vx)
            d = (want - cur + math.pi) % (2 * math.pi) - math.pi
            cur += clamp(d, -0.13, 0.13)
            sp = math.hypot(bl.vx, bl.vy)
            bl.vx, bl.vy = math.cos(cur) * sp, math.sin(cur) * sp

    def on_motion(s, e):
        s.mx = e.x / s.c.S
        s.my = e.y / s.c.S

    def on_mouse(s, e, b, down):
        s.on_motion(e)
        if down:
            s.mb.add(b)
            s.mpress.add(b)
        else:
            s.mb.discard(b)

    def flash(s, text):
        s.msg = text
        s.msgt = 150

    def persist(s):
        s.save["settings"] = s.settings
        s.store()

    def hint(s):
        def b(n):
            return keyname(s.binds[n][0] or s.binds[n][1])
        shoot = "SOL TIK" if s.mouse_mode else b("shoot")
        ex = "SAĞ TIK" if s.mouse_mode else b("ex")
        return "Koş: %s/%s   Zıpla: %s   Ateş: %s   Atıl: %s   EX: %s" % (
            b("left"), b("right"), b("jump"), shoot, b("dash"), ex)

    def capture(s, k):
        name, slot = s.cap
        s.cap = None
        b = s.binds
        if k == "escape":
            return
        if k in ("delete", "backspace"):
            if b[name][1 - slot]:
                b[name][slot] = ""
                s.persist()
            else:
                s.flash("Her eylemde en az bir tuş kalmalı")
            return
        if k in ("p", "return", "f11"):
            s.flash("Bu tuş sistem için ayrılmış")
            return
        old = b[name][slot]
        if old == k:
            return
        for a, lst in b.items():
            for i, kk in enumerate(lst):
                if kk == k and not (a == name and i == slot):
                    if old == "" and not any(lst[j] for j in range(2) if j != i):
                        s.flash("Bu tuş başka bir eylemin tek tuşu")
                        return
                    lst[i] = old
        b[name][slot] = k
        s.sfx.play("ok")
        s.persist()

    def toggle_fullscreen(s):
        s.settings["fullscreen"] = not s.settings["fullscreen"]
        s.apply_display()
        s.persist()

    def apply_display(s):
        st = s.settings
        r = s.root
        try:
            r.attributes("-fullscreen", bool(st["fullscreen"]))
        except tk.TclError:
            pass
        try:
            r.update_idletasks()
        except tk.TclError:
            pass
        try:
            sw, sh = int(r.winfo_screenwidth()), int(r.winfo_screenheight())
        except Exception:
            sw, sh = 1920, 1080
        if st["fullscreen"]:
            S = min(sw / float(W), sh / float(H))
        else:
            S = RES[clamp(st["res"], 0, len(RES) - 1)][0] / float(W)
            S = min(S, (sw - 40) / float(W), (sh - 120) / float(H))
        S = max(0.5, S)
        s.c.S = S
        s.cv.config(width=int(W * S), height=int(H * S))
        if not st["fullscreen"]:
            try:
                r.geometry("")
            except tk.TclError:
                pass
        s.bgkey = None
        s.bgoff = (0, 0)

    def hit(s, *n):
        return any(k in s.pressed for k in n)

    def load(s):
        d = {}
        try:
            with open(SAVE, "r", encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            d = {}
        d.setdefault("unlocked", 1)
        d.setdefault("grades", {})
        d.setdefault("times", {})
        if d.get("ver") != 2:
            d["unlocked"] = 1
            d["grades"] = {}
            d["times"] = {}
            d["coins"] = {}
            d["ver"] = 2
        d.setdefault("coins", {})
        if not isinstance(d.get("settings"), dict):
            d["settings"] = {}
        st = d["settings"]
        for k, v in DEFAULT_SETTINGS.items():
            if k not in st:
                st[k] = list(v) if isinstance(v, list) else v
        if not isinstance(st["diff"], list):
            st["diff"] = []
        st["diff"] = (list(st["diff"]) + [1] * len(LEVELS))[:len(LEVELS)]
        st["diff"] = [clamp(int(x), 0, 2) if isinstance(x, int) else 1 for x in st["diff"]]
        if not isinstance(st.get("binds"), dict):
            st["binds"] = {}
        for a, v in DEFAULT_BINDS.items():
            b = st["binds"].get(a)
            if not (isinstance(b, list) and len(b) == 2):
                st["binds"][a] = list(v)
        return d

    def store(s):
        try:
            with open(SAVE, "w", encoding="utf-8") as f:
                json.dump(s.save, f)
        except Exception:
            pass

    # ---------------------------------------------------------------- geçişler
    def go(s, cb, center=None):
        if s.iris is None:
            s.iris = [0, 0, cb]
            s.iris_c = center or (W / 2, H / 2)

    def set_state(s, st):
        s.state = st
        s.sel = 0 if st == "menu" else s.sel
        s.rt = 0

    def xrange(s):
        if s.mode == "rg" and s.rg:
            return (s.camx + 20, s.rg["len"] - 20)
        return (20, W - 20)

    def ground_at(s, x):
        if s.mode != "rg" or not s.rg:
            return True
        for a, b in s.rg["segs"]:
            if a - 6 <= x <= b + 6:
                return True
        return False

    def solid(s, p):
        if abs(p.y - GROUND) < 1.5 and s.ground_at(p.x - 30) and s.ground_at(p.x + 30):
            return True
        for (x1, x2, top) in s.rg["plats"]:
            if abs(p.y - top) < 1.5 and x1 + 25 <= p.x <= x2 - 25:
                return True
        return False

    def setup_rg(s):
        w = gen_rg(s.cfg, s.dif["bhp"])
        s.rg = w
        s.plats = list(w["plats"])
        s.coin_list = [[x, y, False] for (x, y) in w["coins"]]
        s.orbs = [[x, y, False] for (x, y) in w["orbs"]]
        s.ncoin = len(s.coin_list)
        s.got = 0
        s.p.x = 110.0
        s.safe = (110.0, float(GROUND))

    def start_level(s, i):
        s.lv = i
        s.cfg = LEVELS[i]
        s.mode = s.cfg.get("kind", "boss")
        s.p = Player()
        s.dif = DIFF[clamp(s.settings["diff"][i], 0, 2)]
        s.p.hp = s.p.maxhp = s.dif["hp"]
        s.bacc = 0.0
        s.shots, s.bul, s.parts, s.pops = [], [], [], []
        s.plats = s.cfg["plats"]
        s.camx = 0.0
        s.fin = 0
        s.rings = []
        s.p.weapon = clamp(int(s.settings.get("weapon", 0)), 0, len(WEAPONS) - 1)
        s.orbs = []
        s.coin_list = []
        s.got = s.ncoin = 0
        if s.mode == "rg":
            s.boss = None
            s.setup_rg()
        else:
            s.boss = s.cfg["cls"](s)
            s.boss.maxhp = int(s.boss.maxhp * s.dif["bhp"])
            s.boss.hp = s.boss.maxhp
        s.intro = 170
        s.ft = 0
        s.ko = 0
        s.shake = 0
        s.hitstop = 0
        s.dying = 0
        s.build_bg(("lv", i), s.cfg)
        s.state = "fight"
        s.sfx.play("go")

    def to_menu(s):
        s.mode = "boss"
        s.camx = 0.0
        s.state = "menu"
        s.sel = 0
        s.p = Player()
        s.plats = []
        s.shots, s.bul, s.parts, s.pops = [], [], [], []

    # ------------------------------------------------------------------- efekt
    def dust(s, x, y, n=5):
        for _ in range(n):
            s.parts.append([x + random.uniform(-8, 8), y - 2, random.uniform(-1.5, 1.5),
                            random.uniform(-1.2, -0.2), 18, 18, "#efe3c4", random.uniform(4, 7), 2])

    def burst(s, x, y, col, n=12, sp=5.0):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(1, sp)
            s.parts.append([x, y, math.cos(a) * v, math.sin(a) * v - 1, random.randint(16, 32),
                            32, col, random.uniform(3, 6), random.choice((0, 0, 1))])

    def pop(s, x, y, text, col):
        s.pops.append([x, y, text, 45, col])

    def bomb_boom(s, sh):
        s.burst(sh.x, GROUND - 10, "#ffb347", 18, 6)
        s.shake = 6
        for d in (-1, 1):
            s.shots.append(Shot("wave", sh.x + d * 20, GROUND - 2, d * 5.5, 0, r=12, hh=24, life=200))

    def try_parry(s):
        p = s.p
        for o in s.orbs:
            if not o[2] and math.hypot(o[0] - p.x, o[1] - (p.y - 30)) < 46:
                o[2] = True
                p.card = min(5.0, p.card + 1)
                p.parries += 1
                p.vy = -13.0
                p.jh = False
                s.hitstop = 5
                s.burst(o[0], o[1], PINK, 18, 6)
                s.ring(o[0], o[1], PINK, 60)
                s.pop(p.x, p.y - 70, "PARRY!", PINK)
                s.sfx.play("parry")
                return
        for sh in s.shots:
            if sh.pink and not sh.dead and math.hypot(sh.x - p.x, sh.y - (p.y - 30)) < sh.r + 38:
                sh.dead = True
                p.card = min(5.0, p.card + 1)
                p.parries += 1
                p.vy = -13.0
                p.jh = False
                s.hitstop = 5
                s.burst(sh.x, sh.y, PINK, 18, 6)
                s.ring(sh.x, sh.y, PINK, 60)
                s.pop(p.x, p.y - 70, "PARRY!", PINK)
                s.sfx.play("parry")
                return

    def hurt_player(s):
        p = s.p
        if p.inv > 0 or p.dash > 0 or p.hp <= 0 or s.ko > 0 or s.fin > 0 or s.intro > 30:
            return False
        p.hp -= 1
        p.inv = 110
        p.hurt = 26
        p.vy = -9.0
        p.vx = -p.face * 4.0
        p.on = False
        s.shake = 14
        s.hitstop = 6
        s.burst(p.x, p.y - 30, "#ffffff", 16, 6)
        s.ring(p.x, p.y - 30, "#ffffff", 55, 14)
        s.sfx.play("hurt")
        if p.hp <= 0:
            s.dying = 1
            s.pop(p.x, p.y - 80, "ÖLDÜN!", RED)
        return True

    # ----------------------------------------------------------------- güncelle
    def update(s):
        s.t += 1
        if s.msgt > 0:
            s.msgt -= 1
        st0 = s.state
        if st0 in ("fight", "pause"):
            tr = "run" if s.mode == "rg" else "boss"
            if s.ko > 0 or s.fin > 0 or s.dying > 0:
                tr = None
        elif st0 == "dead":
            tr = None
        else:
            tr = "menu"
        s.sfx.set_music(tr)
        s.sfx.tick()
        if s.wheel:
            if st0 == "fight" and s.intro <= 60 and s.p.hp > 0:
                s.next_weapon(s.wheel)
            s.wheel = 0
        if s.iris:
            it = s.iris
            it[1] += 1
            if it[0] == 0 and it[1] >= 22:
                it[2]()
                it[0] = 1
                it[1] = 0
            elif it[0] == 1 and it[1] >= 22:
                s.iris = None
            s.pressed.clear()
            s.mpress.clear()
            return
        st = s.state
        if st == "menu":
            s.upd_menu()
        elif st == "select":
            s.upd_select()
        elif st == "howto":
            if s.hit(*OKK, *BACKK):
                s.sfx.play("blip")
                s.go(lambda: s.set_state("menu"))
        elif st == "settings":
            s.upd_settings()
        elif st == "fight":
            s.upd_fight()
        elif st == "pause":
            s.upd_pause()
        elif st == "result":
            s.rt += 1
            if s.rt > 90 and s.res.get("grade") in ("S", "A") and s.rt % 3 == 0:
                s.parts.append([random.uniform(0, W), -10, random.uniform(-1, 1), random.uniform(1, 3),
                                200, 200, random.choice((GOLD, PINK, "#7ad0ff", RED, "#9be36b")),
                                random.uniform(4, 8), 3])
            s.upd_parts()
            if s.rt > 100 and s.hit("return", "space", "z"):
                s.sfx.play("ok")
                s.go(s.after_result)
        elif st == "dead":
            s.rt += 1
            if s.hit("up", "w", "down", "s"):
                s.dsel = 1 - s.dsel
                s.sfx.play("blip")
            if s.rt > 20 and s.hit(*OKK):
                s.sfx.play("ok")
                if s.dsel == 0:
                    s.go(lambda: s.start_level(s.lv))
                else:
                    s.go(s.to_menu)
        elif st == "ending":
            s.rt += 1
            if s.rt % 4 == 0:
                s.parts.append([random.uniform(0, W), -10, random.uniform(-1, 1), random.uniform(1, 3),
                                200, 200, random.choice((GOLD, PINK, "#7ad0ff", RED, "#9be36b")),
                                random.uniform(4, 8), 3])
            s.upd_parts()
            if s.rt > 90 and s.hit(*OKK):
                s.go(s.to_menu)
        s.pressed.clear()
        s.mpress.clear()

    def upd_menu(s):
        n = 5
        if s.hit(*UPK):
            s.sel = (s.sel - 1) % n
            s.sfx.play("blip")
        if s.hit(*DOWNK):
            s.sel = (s.sel + 1) % n
            s.sfx.play("blip")
        if s.hit(*OKK):
            s.sfx.play("ok")
            if s.sel == 0:
                i = min(s.save["unlocked"], len(LEVELS)) - 1
                s.go(lambda: s.start_level(i))
            elif s.sel == 1:
                s.go(lambda: s.set_state("select"))
            elif s.sel == 2:
                s.go(lambda: s.open_settings("menu"))
            elif s.sel == 3:
                s.go(lambda: s.set_state("howto"))
            else:
                s.quit = True
                s.root.destroy()

    def upd_select(s):
        n = len(LEVELS)
        if s.hit(*LEFT):
            s.lsel = (s.lsel - 1) % n
            s.sfx.play("blip")
        if s.hit(*RIGHT):
            s.lsel = (s.lsel + 1) % n
            s.sfx.play("blip")
        if s.hit(*UPK) or s.hit(*DOWNK):
            dd = s.settings["diff"]
            dd[s.lsel] = (dd[s.lsel] + (1 if s.hit(*DOWNK) else -1)) % 3
            s.persist()
            s.sfx.play("blip")
        if s.hit(*BACKK):
            s.go(lambda: s.set_state("menu"))
        elif s.hit(*OKK):
            if s.lsel < s.save["unlocked"]:
                s.sfx.play("ok")
                i = s.lsel
                s.go(lambda: s.start_level(i))
            else:
                s.sfx.play("hurt")

    def open_settings(s, back):
        s.set_back = back
        s.state = "settings"
        s.stab = 0
        s.sidx = 0
        s.sslot = 0
        s.cap = None

    def leave_settings(s):
        s.sfx.play("blip")
        if s.set_back == "pause":
            s.state = "pause"
        else:
            s.go(lambda: s.set_state("menu"))

    def set_items(s):
        if s.stab == 0:
            return [("fullscreen", "Tam ekran (F11)"), ("res", "Çözünürlük"),
                    ("grain", "Film greni efekti"), ("shake", "Ekran sarsıntısı")]
        if s.stab == 1:
            return [("aim", "Nişan / ateş modu")] + list(ACTIONS) + [("reset", "Varsayılan tuşlara dön")]
        return [("diff", "Zorluk (tüm bölümler)"), ("music", "Müzik"), ("sound", "Ses efektleri")]

    def setting_val(s, name):
        st = s.settings
        onoff = lambda v: "AÇIK" if v else "KAPALI"
        if name == "fullscreen":
            return onoff(st["fullscreen"])
        if name == "res":
            if st["fullscreen"]:
                return "OTOMATİK"
            r = RES[clamp(st["res"], 0, len(RES) - 1)]
            return "%d x %d" % r
        if name in ("grain", "shake", "sound", "music"):
            return onoff(st[name])
        if name == "aim":
            return "FARE (imleç)" if st["aim"] == "mouse" else "KLAVYE"
        if name == "diff":
            d = st["diff"]
            return DIFF[d[0]]["name"] if all(x == d[0] for x in d) else "ÖZEL (bölüme göre)"
        if name == "reset":
            return "Enter ile sıfırla"
        return ""

    def setting_act(s, name, d, enter):
        st = s.settings
        if name == "fullscreen":
            st["fullscreen"] = not st["fullscreen"]
            s.apply_display()
        elif name == "res":
            if st["fullscreen"]:
                s.flash("Tam ekranda çözünürlük otomatik ayarlanır")
                return
            st["res"] = (st["res"] + d) % len(RES)
            s.apply_display()
        elif name in ("grain", "shake", "sound", "music"):
            st[name] = not st[name]
            if name == "sound":
                s.sfx.on = bool(st["sound"])
            elif name == "music":
                s.sfx.music_on = bool(st["music"])
        elif name == "aim":
            st["aim"] = "mouse" if st["aim"] == "keyboard" else "keyboard"
        elif name == "diff":
            dd = st["diff"]
            nv = (dd[0] + d) % 3 if all(x == dd[0] for x in dd) else 1
            st["diff"] = [nv] * len(LEVELS)
        elif name == "reset":
            if not enter:
                return
            for a, v in DEFAULT_BINDS.items():
                s.binds[a] = list(v)
            s.flash("Tuşlar varsayılana döndü")
        elif name in KEYACTS:
            if enter:
                s.cap = (name, s.sslot)
                return
            s.sslot = 1 if d > 0 else 0
            s.sfx.play("blip")
            return
        s.sfx.play("blip")
        s.persist()

    def upd_settings(s):
        if s.cap is not None:
            return
        if s.hit("escape"):
            s.leave_settings()
            return
        if s.hit("q"):
            s.stab = (s.stab - 1) % 3
            s.sidx = 0
            s.sfx.play("blip")
        if s.hit("e", "tab"):
            s.stab = (s.stab + 1) % 3
            s.sidx = 0
            s.sfx.play("blip")
        items = s.set_items()
        s.sidx = clamp(s.sidx, 0, len(items) - 1)
        if s.hit(*UPK):
            s.sidx = (s.sidx - 1) % len(items)
            s.sfx.play("blip")
        if s.hit(*DOWNK):
            s.sidx = (s.sidx + 1) % len(items)
            s.sfx.play("blip")
        d = 0
        if s.hit(*LEFT):
            d = -1
        if s.hit(*RIGHT):
            d = 1
        ok = s.hit(*OKK)
        if d or ok:
            s.setting_act(items[s.sidx][0], d if d else 1, bool(ok and not d))

    def upd_pause(s):
        if s.hit("up", "w", "down", "s"):
            s.psel = (s.psel + (1 if s.hit("down", "s") else -1)) % 4
            s.sfx.play("blip")
        if s.hit("escape", "p"):
            s.state = "fight"
        elif s.hit(*OKK):
            if s.psel == 0:
                s.state = "fight"
            elif s.psel == 1:
                s.go(lambda: s.start_level(s.lv))
            elif s.psel == 2:
                s.open_settings("pause")
            else:
                s.go(s.to_menu)

    def upd_parts(s):
        for r_ in s.rings:
            r_[3] -= 1
        s.rings = [r_ for r_ in s.rings if r_[3] > 0]
        for q in s.parts:
            q[0] += q[2]
            q[1] += q[3]
            if q[8] in (0, 1, 3):
                q[3] += 0.22
            else:
                q[2] *= 0.92
                q[3] *= 0.92
            q[4] -= 1
        s.parts = [q for q in s.parts if q[4] > 0]
        for q in s.pops:
            q[1] -= 0.8
            q[3] -= 1
        s.pops = [q for q in s.pops if q[3] > 0]

    def fall_respawn(s):
        p = s.p
        p.hp -= 1
        s.shake = 12
        s.sfx.play("hurt")
        if p.hp <= 0:
            s.dying = 1
            p.x = clamp(p.x, s.camx + 40, s.camx + W - 40)
            p.y = H - 100.0
            p.vx = p.vy = 0.0
            s.pop(p.x, p.y - 80, "ÖLDÜN!", RED)
        else:
            p.x = max(s.safe[0] - 10, s.camx + 40)
            p.y = s.safe[1]
            p.vx = p.vy = 0.0
            p.on = True
            p.inv = 120
            s.burst(p.x, p.y - 30, "#ffffff", 14, 5)

    def upd_rg(s):
        if s.hit("escape", "p"):
            s.state = "pause"
            s.psel = 0
            return
        if s.hitstop > 0:
            s.hitstop -= 1
            return
        if s.shake > 0:
            s.shake -= 1
        p = s.p
        w = s.rg
        if s.intro > 0:
            s.intro -= 1
        active = s.intro <= 30
        s.plats = list(w["plats"])
        for m in w["movers"]:
            ox = m["x1"]
            m["x1"] = m["bx"] + math.sin(s.t * m["spd"] + m["ph"]) * m["amp"] - m["w"] / 2
            m["dx"] = (m["x1"] - ox) if ox else 0.0
            s.plats.append((m["x1"], m["x1"] + m["w"], m["y"]))
        p.update(s)
        for m in w["movers"]:
            if p.on and abs(p.y - m["y"]) < 1.5 and m["x1"] - 8 <= p.x <= m["x1"] + m["w"] + 8:
                p.x += m["dx"]
        tgt = clamp(p.x - 380, 0, w["len"] - W)
        if tgt > s.camx:
            s.camx = tgt
        if p.on and p.hp > 0 and p.dash == 0 and s.solid(p):
            s.safe = (p.x, p.y)
        if p.y > H + 70 and p.hp > 0 and s.fin == 0:
            s.fall_respawn()
        pb = p.box()
        if active and s.fin == 0:
            for e in w["ens"]:
                if e.dead or e.x < s.camx - 200 or e.x > s.camx + W + 160:
                    continue
                e.update(s)
                if e.dead:
                    continue
                b = e.box()
                if pb[0] < b[2] and pb[2] > b[0] and pb[1] < b[3] and pb[3] > b[1]:
                    s.hurt_player()
        for sh in s.shots:
            sh.update(s)
            if not sh.dead and hits_player(sh, p):
                if s.hurt_player():
                    sh.dead = True
        s.shots = [x for x in s.shots if not x.dead]
        for cn in s.coin_list:
            if not cn[2] and p.hp > 0 and math.hypot(cn[0] - p.x, cn[1] - (p.y - 30)) < 34:
                cn[2] = True
                s.got += 1
                s.burst(cn[0], cn[1], GOLD, 10, 4)
                s.pop(cn[0], cn[1] - 24, "ALTIN!", GOLD)
                s.sfx.play("coin")
        for bl in s.bul:
            s.steer(bl)
            bl.x += bl.vx
            bl.y += bl.vy
            bl.age += 1
            if bl.age > bl.life:
                bl.dead = True
                continue
            if bl.x < s.camx - 40 or bl.x > s.camx + W + 40 or bl.y < -60 or bl.y > H + 60:
                bl.dead = True
                continue
            if not active:
                continue
            for e in w["ens"]:
                if e.dead or id(e) in bl.hits:
                    continue
                b = e.box()
                if b[0] - bl.r <= bl.x <= b[2] + bl.r and b[1] - bl.r <= bl.y <= b[3] + bl.r:
                    if bl.ex:
                        bl.hits.add(id(e))
                        dmg = 8
                    else:
                        bl.dead = True
                        dmg = bl.dmg
                        p.card = min(5.0, p.card + 0.03 * bl.dmg)
                        s.sfx.play("hit")
                    e.hp -= dmg
                    e.flash = 3
                    s.burst(bl.x, bl.y, "#fff2b0", 3, 3)
                    if e.hp <= 0:
                        e.dead = True
                        s.burst(e.x, e.y - 20, e.col, 16, 5)
                        s.ring(e.x, e.y - 20, "#ffffff", 40, 14)
                        s.sfx.play("boom")
                    if not bl.ex:
                        break
        s.bul = [x for x in s.bul if not x.dead]
        s.upd_parts()
        if p.hp > 0 and active and s.fin == 0:
            s.ft += 1
        if s.fin == 0 and p.hp > 0 and p.x >= w["goal"]:
            s.fin = 1
            s.shots = []
            s.shake = 10
            s.sfx.play("ko")
            for rr in (50, 100, 160):
                s.ring(p.x, p.y - 30, GOLD, rr, 30)
        if s.fin > 0:
            s.fin += 1
            if s.fin == 120:
                s.go(s.show_result, (clamp(p.x - s.camx, 0, W), clamp(p.y - 30, 0, H)))
        if s.dying > 0:
            s.dying += 1
            if s.dying == 110:
                s.go(s.show_dead, (clamp(p.x - s.camx, 0, W), clamp(p.y - 30, 0, H)))

    def upd_fight(s):
        if s.mode == "rg":
            s.upd_rg()
            return
        if s.hit("escape", "p"):
            s.state = "pause"
            s.psel = 0
            return
        if s.hitstop > 0:
            s.hitstop -= 1
            return
        if 0 < s.ko < 70 and s.t % 2 == 0:
            return
        if s.shake > 0:
            s.shake -= 1
        p = s.p
        if s.intro > 0:
            s.intro -= 1
        b = s.boss
        p.update(s)
        if s.intro <= 30 and not b.dead:
            n0 = len(s.shots)
            s.bacc += s.dif["bt"]
            while s.bacc >= 1 and not b.dead:
                s.bacc -= 1
                b.update()
            sm = s.dif["shot"]
            if sm != 1:
                for sh in s.shots[n0:]:
                    sh.vx *= sm
                    sh.vy *= sm
                    sh.sp *= sm
            if p.hp > 0:
                s.ft += 1
        for sh in s.shots:
            sh.update(s)
            if not sh.dead and hits_player(sh, p):
                if s.hurt_player() and sh.kind not in ("wave", "gear", "roll"):
                    sh.dead = True
        s.shots = [x for x in s.shots if not x.dead]
        for bl in s.bul:
            s.steer(bl)
            bl.x += bl.vx
            bl.y += bl.vy
            bl.age += 1
            if bl.age > bl.life:
                bl.dead = True
                continue
            if bl.x < -40 or bl.x > W + 40 or bl.y < -40 or bl.y > H + 40:
                bl.dead = True
                continue
            if s.intro > 30 or b.dead:
                continue
            for sh in s.shots:
                if sh.hp > 0 and not bl.dead and not sh.dead and \
                        math.hypot(sh.x - bl.x, sh.y - bl.y) < sh.r + bl.r:
                    if not bl.ex:
                        bl.dead = True
                    sh.hp -= 3 if bl.ex else bl.dmg
                    sh.flash = 3
                    s.burst(bl.x, bl.y, "#fff2b0", 3, 3)
                    if sh.hp <= 0:
                        sh.dead = True
                        s.burst(sh.x, sh.y, "#ff9a3c", 14, 5)
            if bl.dead:
                continue
            for (x1, y1, x2, y2) in b.boxes():
                if x1 - bl.r <= bl.x <= x2 + bl.r and y1 - bl.r <= bl.y <= y2 + bl.r:
                    if bl.ex:
                        if not bl.hit:
                            bl.hit = True
                            b.hurt(12)
                            s.burst(bl.x, bl.y, GOLD, 16, 6)
                            s.shake = 5
                    else:
                        bl.dead = True
                        b.hurt(bl.dmg)
                        p.card = min(5.0, p.card + 0.035 * bl.dmg)
                        s.sfx.play("hit")
                        s.burst(bl.x, bl.y, "#fff2b0", 3, 3)
                    break
        s.bul = [x for x in s.bul if not x.dead]
        for pu in s.pops:
            pass
        s.upd_parts()
        if b.hp <= 0 and s.ko == 0 and p.hp > 0:
            s.ko = 1
            b.dead = True
            s.shots = []
            s.shake = 16
            s.sfx.play("ko")
            bb = b.boxes() or [(600, 100, 800, 300)]
            for rr in (60, 110, 170):
                s.ring((bb[0][0] + bb[0][2]) / 2.0, (bb[0][1] + bb[0][3]) / 2.0, "#ffffff", rr, 30)
        if s.ko > 0:
            s.ko += 1
            if s.ko % 4 == 0:
                bx = b.boxes()[0] if b.boxes() else (600, 100, 800, 300)
                s.burst(random.uniform(bx[0], bx[2]), random.uniform(bx[1], bx[3]),
                        random.choice((GOLD, RED, "#ffffff")), 10, 6)
            if s.ko == 165:
                s.go(s.show_result, (p.x, p.y - 30))
        if s.dying > 0:
            s.dying += 1
            if s.dying == 110:
                s.go(s.show_dead, (p.x, p.y - 30))

    def show_result(s):
        p = s.p
        t = s.ft / 60.0
        par = LEVELS[s.lv]["par"]
        score = 100 - max(0, t - par) * 0.6 - (1 - p.hp / float(p.maxhp)) * 36 + min(p.parries, 6) * 3
        score = score + s.dif.get("bonus", 0)
        if s.mode == "rg":
            score += s.got * 3 - 10
        score = clamp(score, 0, s.dif.get("cap", 100))
        g = "S" if score >= 92 else "A" if score >= 80 else "B" if score >= 68 else \
            "C" if score >= 52 else "D"
        s.res = dict(time=t, hp=p.hp, maxhp=p.maxhp, parries=p.parries, grade=g, diff=s.dif["name"],
                     coins=((s.got, s.ncoin) if s.mode == "rg" else None))
        s.save["unlocked"] = max(s.save["unlocked"], min(len(LEVELS), s.lv + 2))
        k = str(s.lv)
        if GRADE_RANK[g] > GRADE_RANK.get(s.save["grades"].get(k, ""), 0):
            s.save["grades"][k] = g
        bt = s.save["times"].get(k)
        if bt is None or t < bt:
            s.save["times"][k] = round(t, 1)
        if s.mode == "rg":
            cd = s.save.setdefault("coins", {})
            cd[k] = max(cd.get(k, 0), s.got)
        s.store()
        s.state = "result"
        s.rt = 0
        s.parts = []

    def show_dead(s):
        s.save["deaths"] = s.save.get("deaths", 0) + 1
        s.store()
        s.state = "dead"
        s.rt = 0
        s.dsel = 0
        s.parts = []

    def after_result(s):
        if s.lv + 1 < len(LEVELS):
            s.start_level(s.lv + 1)
        else:
            s.mode = "boss"
            s.camx = 0.0
            s.state = "ending"
            s.rt = 0
            s.parts = []

    # ------------------------------------------------------------- çizim araçları
    def ov(s, x, y, rx, ry, fill, w=3, out=INK):
        if w == 0:
            out = ""
        return s.c.create_oval(x - rx, y - ry, x + rx, y + ry, fill=fill, outline=out,
                               width=max(w, 1), tags="d")

    def rc(s, x1, y1, x2, y2, fill, w=3, out=INK):
        if w == 0:
            out = ""
        return s.c.create_rectangle(x1, y1, x2, y2, fill=fill, outline=out, width=max(w, 1), tags="d")

    def pl(s, pts, fill, w=3, smooth=False, out=INK):
        flat = [v for q in pts for v in q]
        if w == 0:
            out = ""
        return s.c.create_polygon(flat, fill=fill, outline=out, width=max(w, 1), smooth=smooth, tags="d")

    def ln(s, pts, w, fill, smooth=False):
        flat = [v for q in pts for v in q]
        return s.c.create_line(flat, width=w, fill=fill, capstyle="round", joinstyle="round",
                               smooth=smooth, tags="d")

    def limb(s, a, b, bend=0):
        mid = ((a[0] + b[0]) / 2 + bend, (a[1] + b[1]) / 2)
        s.ln([a, mid, b], 9, INK, True)
        s.ln([a, mid, b], 5, CREAM, True)

    def tx(s, x, y, t, size=20, fill=CREAM, anchor="center", ow=2, out=INK):
        f = (FONT, size, "bold")
        if ow:
            offs = ((-ow, 0), (ow, 0), (0, -ow), (0, ow))
            if ow >= 3:
                offs += ((-ow, -ow), (ow, ow), (-ow, ow), (ow, -ow))
            for dx, dy in offs:
                s.c.create_text(x + dx, y + dy, text=t, font=f, fill=out, anchor=anchor, tags="d")
        s.c.create_text(x, y, text=t, font=f, fill=fill, anchor=anchor, tags="d")

    def panel(s, x1, y1, x2, y2, fill=CREAM):
        s.rc(x1 + 6, y1 + 7, x2 + 6, y2 + 7, INK, 0, "")
        s.rc(x1, y1, x2, y2, fill, 4)
        s.rc(x1 + 8, y1 + 8, x2 - 8, y2 - 8, "", 2)

    def floor_y(s, p):
        base = GROUND
        for (x1, x2, y) in s.plats:
            if x1 - 8 <= p.x <= x2 + 8 and p.y <= y + 2:
                base = min(base, y)
        return base

    # ------------------------------------------------------------------ arka plan
    def build_bg(s, key, cfg):
        if s.bgkey == key:
            return
        s.bgkey = key
        s.gcol = cfg["ground"]
        c = s.c
        c.delete("bg")
        s.bgoff = (0, 0)
        top, bot = cfg["sky"]
        bands = 32
        for i in range(bands):
            c.create_rectangle(-40, -40 + i * (H + 80) / bands, W + 40, -40 + (i + 1) * (H + 80) / bands + 2,
                               fill=mix(top, bot, i / (bands - 1.0)), outline="", tags=("bg", "sky"))
        if cfg.get("kind") == "rg":
            return
        th = cfg["theme"]
        if th == "snow":
            s.th_snow()
        elif th == "meadow":
            s.th_meadow()
        elif th == "swamp":
            s.th_swamp()
        elif th == "stage":
            s.th_stage()
        elif th == "tower":
            s.th_tower()
        else:
            s.th_menu()
        # zemin
        gc = cfg["ground"]
        c.create_rectangle(-40, GROUND, W + 40, H + 40, fill=gc, outline="", tags="bg")
        for i in range(-1, 14):
            if i % 2 == 0:
                c.create_polygon(i * 80, GROUND, i * 80 + 80, GROUND, i * 80 + 110, H + 40, i * 80 - 30, H + 40,
                                 fill=mix(gc, "#ffffff", 0.12), outline="", tags="bg")
        c.create_line(-40, GROUND, W + 40, GROUND, fill=INK, width=5, tags="bg")
        c.create_rectangle(-40, GROUND + 5, W + 40, GROUND + 14, fill=mix(gc, "#ffffff", 0.3),
                           outline="", tags="bg")
        for (x1, x2, y) in cfg["plats"]:
            c.create_rectangle(x1 + 8, y + 16, x2 - 8, y + 30, fill=mix(INK, "#8a5a2a", .5), outline=INK,
                               width=3, tags="bg")
            c.create_rectangle(x1, y, x2, y + 18, fill="#c98a45", outline=INK, width=4, tags="bg")
            c.create_line(x1 + 6, y + 5, x2 - 6, y + 5, fill="#e9b678", width=3, tags="bg")
            for xx in range(int(x1) + 30, int(x2) - 10, 40):
                c.create_line(xx, y + 4, xx, y + 16, fill=INK, width=2, tags="bg")

    def th_swamp(s):
        c = s.c
        for cx, r, col in ((140, 220, "#8dbb50"), (520, 290, "#7aa944"), (900, 240, "#8dbb50")):
            c.create_oval(cx - r, GROUND - 100, cx + r, GROUND + 260, fill=col, outline=INK, width=3,
                          tags=("bg", "hills"))
        for x, h in ((60, 300), (905, 340), (430, 170)):
            c.create_rectangle(x - 14, GROUND - h, x + 14, GROUND, fill="#6b4a2a", outline=INK, width=3, tags="bg")
            for dx, dy, r in ((-40, 0, 62), (36, -10, 66), (0, -46, 72)):
                c.create_oval(x + dx - r, GROUND - h + dy - r, x + dx + r, GROUND - h + dy + r,
                              fill="#4e8a35", outline=INK, width=3, tags="bg")
            for k in range(-3, 4):
                c.create_line(x + k * 22, GROUND - h + 40, x + k * 22 + 4, GROUND - h + 90 + (k % 2) * 25,
                              fill="#b9d98a", width=3, tags="bg")
        for x in range(30, 940, 95):
            hh = 60 + (x * 7) % 40
            c.create_line(x, GROUND, x, GROUND - hh, fill=INK, width=6, tags="bg")
            c.create_line(x, GROUND, x, GROUND - hh, fill="#5b7d2a", width=3, tags="bg")
            c.create_oval(x - 7, GROUND - hh - 24, x + 7, GROUND - hh + 4, fill="#7a4a22", outline=INK,
                          width=3, tags="bg")

    def th_stage(s):
        c = s.c
        for x0 in (250, 480, 710):
            c.create_polygon(x0, -10, x0 + 60, -10, x0 + 200, GROUND, x0 - 200, GROUND,
                             fill="#c98ab0", outline="", tags=("bg", "hills"))
        for i in range(24):
            sx = (i * 137) % W
            sy = (i * 71) % 260 + 30
            c.create_polygon([v for q in star_pts(sx, sy, 7, 3, 4, 0.3) for v in q], fill="#ffe9a0",
                             outline="", tags="bg")
        for side in (0, 1):
            if side == 0:
                pts = [-40, -40, 170, -40, 120, GROUND, -40, GROUND]
            else:
                pts = [W + 40, -40, W - 170, -40, W - 120, GROUND, W + 40, GROUND]
            c.create_polygon(pts, fill="#a3222d", outline=INK, width=4, tags="bg")
            for k in range(1, 5):
                xx = (k * 30) if side == 0 else W - k * 30
                c.create_line(xx, -10, xx - 12 + (0 if side == 0 else 24), GROUND, fill="#7c1620", width=5, tags="bg")
        for i in range(-1, 13):
            c.create_oval(i * 90 - 10, -30, i * 90 + 80, 50, fill="#a3222d", outline=INK, width=4, tags="bg")
            c.create_oval(i * 90 + 25, 28, i * 90 + 45, 44, fill=GOLD, outline=INK, width=2, tags="bg")

    def th_tower(s):
        c = s.c
        for cx, cy, r, n in ((130, 150, 150, 12), (860, 420, 190, 14), (480, 90, 100, 10)):
            pts = star_pts(cx, cy, r, r * 0.82, n, 0.2)
            c.create_polygon([v for q in pts for v in q], fill="#2b6a66", outline=INK, width=3,
                             tags=("bg", "hills"))
            c.create_oval(cx - r * .55, cy - r * .55, cx + r * .55, cy + r * .55, fill="#3c8a82", outline=INK,
                          width=3, tags="bg")
            c.create_oval(cx - r * .15, cy - r * .15, cx + r * .15, cy + r * .15, fill=INK, outline="", tags="bg")
        for x in (60, 300, 600, 900):
            c.create_rectangle(x - 34, 190, x + 34, GROUND, fill="#9ad8c4", outline=INK, width=4, tags="bg")
            c.create_oval(x - 34, 156, x + 34, 224, fill="#9ad8c4", outline=INK, width=4, tags="bg")
            c.create_line(x, 160, x, GROUND, fill=INK, width=3, tags="bg")
            c.create_line(x - 34, 330, x + 34, 330, fill=INK, width=3, tags="bg")

    def th_snow(s):
        c = s.c
        for cx, r, col in ((160, 240, "#cfe6f5"), (560, 300, "#bfdcee"), (920, 250, "#cfe6f5")):
            c.create_oval(cx - r, GROUND - 110, cx + r, GROUND + 260, fill=col, outline=INK, width=3,
                          tags=("bg", "hills"))
        for x, h in ((70, 230), (880, 260), (470, 150)):
            c.create_rectangle(x - 9, GROUND - h + 130, x + 9, GROUND, fill="#6b4a2a", outline=INK,
                               width=3, tags="bg")
            for k in range(3):
                wd = 70 - k * 16
                yy = GROUND - h + k * 62
                c.create_polygon(x, yy - 70, x - wd, yy + 30, x + wd, yy + 30, fill="#2f6f58",
                                 outline=INK, width=3, tags="bg")
                c.create_polygon(x, yy - 70, x - wd * .45, yy - 24, x + wd * .45, yy - 24, fill="#f4fbff",
                                 outline="", tags="bg")

    def th_meadow(s):
        c = s.c
        for cx, r, col in ((120, 230, "#9fd668"), (500, 300, "#8ccb58"), (900, 240, "#9fd668")):
            c.create_oval(cx - r, GROUND - 100, cx + r, GROUND + 260, fill=col, outline=INK, width=3,
                          tags=("bg", "hills"))
        for i, x in enumerate(range(40, 940, 70)):
            hh = 40 + (x * 7) % 35
            c.create_line(x, GROUND, x, GROUND - hh, fill=INK, width=6, tags="bg")
            c.create_line(x, GROUND, x, GROUND - hh, fill="#4a8a2a", width=3, tags="bg")
            col = ("#ff6fb5", "#ffffff", "#ffd23a", "#ff8a5a")[i % 4]
            c.create_oval(x - 12, GROUND - hh - 12, x + 12, GROUND - hh + 12, fill=col, outline=INK,
                          width=3, tags="bg")
            c.create_oval(x - 4, GROUND - hh - 4, x + 4, GROUND - hh + 4, fill="#ffe9a0", outline="", tags="bg")
        for cx, cy in ((200, 110), (620, 80), (860, 150)):
            for dx, rr in ((-34, 28), (0, 38), (34, 28)):
                c.create_oval(cx + dx - rr, cy - rr * .7, cx + dx + rr, cy + rr * .7, fill="#ffffff",
                              outline=INK, width=3, tags="bg")

    def th_menu(s):
        c = s.c
        for cx, r, col in ((100, 260, "#e08a3a"), (520, 330, "#d27a2f"), (940, 280, "#e08a3a")):
            c.create_oval(cx - r, GROUND - 120, cx + r, GROUND + 300, fill=col, outline=INK, width=3,
                          tags=("bg", "hills"))

    # ------------------------------------------------------------------- çizim
    def rays(s, cx, cy, col, n=18, spd=0.004):
        R = 1300
        for i in range(n):
            a = i * math.tau / n + s.t * spd
            b = a + math.pi / n
            s.c.create_polygon(cx, cy, cx + R * math.cos(a), cy + R * math.sin(a),
                               cx + R * math.cos(b), cy + R * math.sin(b),
                               fill=col, outline="", tags=("d", "rays"))
        try:
            s.c.tag_lower("rays", "hills")
        except tk.TclError:
            pass

    def draw(s):
        c = s.c
        c.delete("d")
        st = s.state
        if st in ("fight", "pause"):
            s.draw_fight()
        else:
            s.build_bg("menu", MENU_CFG)
            s.camx = 0.0
            if s.bgoff != (0, 0):
                c.move("bg", -s.bgoff[0], -s.bgoff[1])
                s.bgoff = (0, 0)
            s.rays(W / 2, 300, MENU_CFG["ray"])
            getattr(s, "dr_" + st)()
        s.film()
        s.draw_iris()
        want = "none" if (st == "fight" and s.mouse_mode) else "arrow"
        if want != s.cur:
            s.cur = want
            try:
                s.cv.config(cursor=want)
            except tk.TclError:
                s.cv.config(cursor="crosshair")

    def film(s):
        c = s.c
        if s.settings["grain"]:
            for _ in range(22):
                x = random.randint(0, W)
                y = random.randint(0, H)
                c.create_rectangle(x, y, x + 2, y + 2, fill="#3a2a14", outline="", tags="d")
            if random.random() < 0.12:
                x = random.randint(20, W - 20)
                c.create_line(x, 0, x + random.randint(-4, 4), H, fill="#e8d9b0", width=1, tags="d")
        R_, wd_ = 506, 100
        c.create_oval(W / 2 - R_ - wd_ / 2, H / 2 - R_ - wd_ / 2, W / 2 + R_ + wd_ / 2, H / 2 + R_ + wd_ / 2,
                      outline=INK, width=wd_, tags="d")
        c.create_rectangle(0, 0, W, H, outline=INK, width=14, tags="d")
        c.create_rectangle(10, 10, W - 10, H - 10, outline=mix(INK, CREAM, .25), width=2, tags="d")

    def draw_iris(s):
        it = s.iris
        if not it:
            return
        R = 640
        k = it[1] / 22.0
        k = clamp(k, 0, 1)
        r = R * (1 - k) ** 1.5 if it[0] == 0 else R * k ** 1.5
        cx, cy = s.iris_c
        c = s.c
        if r < 2:
            c.create_rectangle(0, 0, W, H, fill=INK, outline="", tags="d")
            return
        wd = r * 0.5 + 8
        c.create_oval(cx - r - wd / 2, cy - r - wd / 2, cx + r + wd / 2, cy + r + wd / 2,
                      outline=INK, width=wd, tags="d")
        c.create_rectangle(-10, -10, W + 10, cy - r, fill=INK, outline="", tags="d")
        c.create_rectangle(-10, cy + r, W + 10, H + 10, fill=INK, outline="", tags="d")
        c.create_rectangle(-10, cy - r, cx - r, cy + r, fill=INK, outline="", tags="d")
        c.create_rectangle(cx + r, cy - r, W + 10, cy + r, fill=INK, outline="", tags="d")

    # ---- shot çizimi
    def draw_shot(s, sh):
        k = sh.kind
        x, y, r = sh.x - s.camx, sh.y, sh.r
        pk = sh.pink
        col = PINK if pk else {"snow": "#eaf6ff", "honey": "#ffbe2e"}.get(sh.skin, "#ff5a2c")
        core = "#ffffff" if pk else "#ffe9a8"
        if sh.flash > 0:
            col = "#ffffff"
        if k == "ball":
            pu = 1 + 0.12 * math.sin(s.t * 0.4) if pk else 1
            s.ov(x, y, r * pu, r * pu, col)
            s.ov(x, y, r * 0.5, r * 0.5, core, 0)
        elif k == "fly":
            wg = abs(math.sin(s.t * 0.5)) * 8 + 4
            wc = PINK if pk else "#ffffff"
            s.ov(x - 9, y - 7, 8, wg, wc, 2)
            s.ov(x + 9, y - 7, 8, wg, wc, 2)
            s.ov(x, y, 8, 11, INK)
            s.ov(x - 3, y - 3, 2, 2, RED, 0)
            s.ov(x + 3, y - 3, 2, 2, RED, 0)
        elif k == "card":
            a = sh.spin
            pts = []
            for dx, dy in ((-9, -13), (9, -13), (9, 13), (-9, 13)):
                pts.append((x + dx * math.cos(a) - dy * math.sin(a), y + dx * math.sin(a) + dy * math.cos(a)))
            s.pl(pts, PINK if pk else WHITE)
            s.ov(x, y, 4, 4, "#ffffff" if pk else RED, 0)
        elif k == "carrot":
            a = sh.ang
            nx, ny = -math.sin(a), math.cos(a)
            tip = (x + math.cos(a) * 22, y + math.sin(a) * 22)
            bk = (x - math.cos(a) * 14, y - math.sin(a) * 14)
            for sgn in (-1, 1):
                s.ln([bk, (bk[0] - math.cos(a) * 14 + nx * sgn * 8, bk[1] - math.sin(a) * 14 + ny * sgn * 8)],
                     5, "#4fa83a")
            c1 = PINK if pk else "#ff8c1a"
            if sh.flash > 0:
                c1 = "#ffffff"
            s.pl([tip, (bk[0] + nx * 10, bk[1] + ny * 10), (bk[0] - nx * 10, bk[1] - ny * 10)], c1)
        elif k == "star":
            s.pl(star_pts(x, y, r, r * 0.45, 5, sh.spin), PINK if pk else GOLD)
        elif k == "wave":
            hh = sh.hh
            s.ov(x, GROUND - hh * 0.5, sh.r, hh * 0.5, "#fff3b0")
            s.ov(x, GROUND - hh * 0.4, sh.r * 0.5, hh * 0.28, "#ffffff", 0)
        elif k == "gear":
            s.pl(star_pts(x, y, r, r * 0.78, 8, sh.spin), PINK if pk else "#d8a02a")
            s.ov(x, y, r * 0.55, r * 0.55, "#fff0c0" if pk else "#f2c85c", 3)
            s.ov(x, y, r * 0.2, r * 0.2, INK, 0)
        elif k == "bomb":
            s.ov(x, y, r, r, "#2b2b33")
            s.ov(x - 5, y - 5, 4, 4, "#8a8a99", 0)
            s.ln([(x + 4, y - r + 2), (x + 10, y - r - 8)], 3, "#a06a2a")
            s.ov(x + 11, y - r - 10, 4, 4, "#ffd23a", 0)
        elif k == "roll":
            s.ov(x, y, r, r, "#f4fbff")
            for i in range(3):
                a = sh.spin + i * 2.1
                s.ov(x + math.cos(a) * r * 0.5, y + math.sin(a) * r * 0.5, 5, 5, "#cfe6f0", 2)
        elif k == "ice":
            s.pl([(x - 8, y - 18), (x + 8, y - 18), (x, y + 20)], "#bfeaff", 3)
            s.ln([(x - 2, y - 12), (x, y + 6)], 2, "#ffffff")
        elif k == "bee":
            wg = abs(math.sin(s.t * 0.6)) * 6 + 3
            s.ov(x + 2, y - 9, 6, wg, PINK if pk else "#ffffff", 2)
            s.ov(x, y, 10, 8, GOLD)
            s.ln([(x - 3, y - 7), (x - 3, y + 7)], 3, INK)
            s.ln([(x + 3, y - 7), (x + 3, y + 7)], 3, INK)
            s.pl([(x + 9, y - 2), (x + 16, y), (x + 9, y + 2)], INK, 2)

    def draw_parts(s):
        for x, y, col, l, ml, mr in s.rings:
            k = 1 - l / float(ml)
            r_ = mr * (0.25 + 0.75 * k)
            s.ov(x - s.camx, y, r_, r_, "", 6, INK)
            s.ov(x - s.camx, y, r_, r_, "", 3, col)
        for q in s.parts:
            x, y, vx, vy, l, ml, col, sz, k = q
            x -= s.camx
            r = max(0.6, sz * l / ml)
            if k == 0:
                s.ov(x, y, r, r, col, 2)
            elif k == 1:
                s.pl(star_pts(x, y, r * 1.8, r * 0.7, 4, l * 0.2), col, 2)
            elif k == 2:
                s.ov(x, y, r * 1.5, r * 1.1, col, 0)
            else:
                s.rc(x - r, y - r * 0.6, x + r, y + r * 0.6, col, 1)
        for x, y, t, l, col in s.pops:
            s.tx(x - s.camx, y, t, 20, col)

    # ---- oyuncu çizimi
    def draw_player(s, p, ox=0, ghost=False):
        f = p.face
        x = p.x + ox
        y = p.y
        if ghost:
            gy = y - s.dying * 1.4
            s.ov(x, gy - 78, 17, 6, GOLD, 3)
            s.pl([(x - 13, gy - 60), (x + 13, gy - 60), (x + 15, gy - 51), (x + 12, gy - 39), (x + 7, gy - 31),
                  (x - 7, gy - 31), (x - 12, gy - 39), (x - 15, gy - 51)], "#e6f6fa", 3, True)
            s.ov(x - 5, gy - 50, 3, 5, INK, 0)
            s.ov(x + 5, gy - 50, 3, 5, INK, 0)
            for d in (-1, 1):
                s.ov(x + d * 24, gy - 42, 10, 16, WHITE, 3)
            return
        if p.inv > 0 and (s.t // 3) % 2:
            return
        base = s.floor_y(p)
        if base < GROUND or s.ground_at(p.x):
            s.ov(x, base + 3, 18, 5, mix(s.gcol, INK, .5), 0)
        if p.dash > 0:
            for i in range(3):
                s.ov(x - f * (14 + i * 18), y - 30, 18 - i * 4, 10 - i * 2, mix(WHITE, s.gcol, i * .25), 2)
            s.ov(x, y - 30, 24, 15, "#f4fbff")
            s.ov(x + f * 6, y - 32, 5, 7, INK, 0)
            s.ov(x + f * 8, y - 31, 7, 5, RED, 0)
            return
        run = p.on and abs(p.vx) > 1.2
        ph = s.t * 0.38
        if run:
            bob = abs(math.sin(ph)) * 3
        elif p.on:
            bob = math.sin(s.t * 0.1) * 1.5
        else:
            bob = 0
        hipy = y - 24 - bob + (p.land * 0.6 if p.land > 0 else 0)
        if run:
            f1 = (x + math.sin(ph) * 13, y - 3 - max(0, math.cos(ph)) * 7)
            f2 = (x - math.sin(ph) * 13, y - 3 - max(0, -math.cos(ph)) * 7)
        elif not p.on:
            f1 = (x + 7 * f, y - 10)
            f2 = (x - 6 * f, y - (4 if p.vy > 0 else 15))
        else:
            f1 = (x - 8, y - 3)
            f2 = (x + 8, y - 3)
        for ft in (f1, f2):
            s.limb((x, hipy), ft, 4 * f)
            s.ov(ft[0] + f * 4, ft[1] - 1, 9, 5, "#7a3a18")
        s.ov(x, hipy - 2, 11, 9, RED)
        s.ov(x, hipy - 14, 8, 10, CREAM)
        sh_y = hipy - 18
        ax, ay = p.aimvec(s) if s.state == "fight" else (f, 0)
        shooting = s.state == "fight" and s.shooting() and s.intro <= 60
        if shooting or p.mz > 0:
            hand = (x + ax * 22, sh_y + 4 + ay * 20)
        else:
            hand = (x + f * 12, sh_y + 12 + math.sin(s.t * 0.2) * 2)
        s.limb((x, sh_y), hand, 3)
        s.ov(hand[0], hand[1], 6, 6, WHITE)
        h2 = (x - f * 12 + (math.sin(ph) * 8 if run else 0), sh_y + 14)
        s.limb((x, sh_y), h2, -3)
        s.ov(h2[0], h2[1], 6, 6, WHITE)
        hx_, hy_ = x + f * 2, hipy - 38
        if not p.on:
            hy_ -= 2
        s.ln([(hx_ - 4, hy_ + 2), (hx_ - 10, hy_ - 22)], 7, INK)
        s.ln([(hx_ - 4, hy_ + 2), (hx_ - 10, hy_ - 22)], 3, RED)
        glass = [(hx_ - 13, hy_ - 15), (hx_ + 13, hy_ - 15), (hx_ + 15, hy_ - 6), (hx_ + 12, hy_ + 6),
                 (hx_ + 7, hy_ + 14), (hx_ - 7, hy_ + 14), (hx_ - 12, hy_ + 6), (hx_ - 15, hy_ - 6)]
        s.pl(glass, "#e6f6fa", 0, True, "")
        s.pl([(hx_ - 14, hy_ - 4), (hx_ + 14, hy_ - 4), (hx_ + 12, hy_ + 6), (hx_ + 7, hy_ + 14),
              (hx_ - 7, hy_ + 14), (hx_ - 12, hy_ + 6)], "#c4501a", 0, True, "")
        s.pl(glass, "", 3, True)
        s.ln([(hx_ - 11, hy_ - 12), (hx_ + 11, hy_ - 12)], 2, "#ffffff")
        for kk in (0, 1):
            wx = hx_ + 2 + kk * 7
            s.ln([(wx, hy_ - 17), (wx + math.sin(s.t * 0.15 + kk * 2) * 4, hy_ - 25),
                  (wx + math.sin(s.t * 0.15 + kk * 2 + 1.5) * 4, hy_ - 33)], 2, "#ffffff", True)
        blink = (s.t % 200) < 6 and p.hurt <= 0
        for d in (-4, 6):
            if blink:
                s.ln([(hx_ + d + f * 2 - 3, hy_ - 1), (hx_ + d + f * 2 + 3, hy_ - 1)], 2, INK)
            else:
                s.ov(hx_ + d + f * 2, hy_ - 1, 3, 5, INK, 0)
                s.ov(hx_ + d + f * 2 + 1, hy_ - 3, 1, 1, "#ffffff", 0)
        if p.mz > 0 or p.hurt > 0:
            s.ov(hx_ + f * 5, hy_ + 7, 3, 3, INK, 0)
        else:
            s.ln([(hx_ + f * 2 - 2, hy_ + 7), (hx_ + f * 2 + 3, hy_ + 7)], 2, INK)
        if p.mz > 0:
            mx = hand[0] + ax * 14
            my = hand[1] + ay * 14
            s.pl(star_pts(mx, my, 10, 4, 4, s.t), GOLD, 2)

    def draw_clouds(s, cam, col):
        for k in range(5):
            x = (k * 230 + s.t * (0.15 + 0.05 * (k % 3)) - cam * 0.1) % (W + 240) - 120
            y = 60 + (k * 41) % 80
            sc = 0.7 + (k % 3) * 0.22
            for dx, rr in ((-36, 28), (0, 38), (36, 28), (64, 20)):
                s.ov(x + dx * sc, y, rr * sc, rr * 0.62 * sc, col, 3)

    def sky_clouds(s, cfg, cam=0.0):
        th = cfg["theme"]
        if th in ("swamp", "meadow", "snow", "sky", "forest"):
            s.draw_clouds(cam, mix(cfg["sky"][0], "#ffffff", .65))
        elif th == "lava":
            s.draw_clouds(cam, mix(cfg["sky"][0], INK, .3))

    def draw_ambient(s, th, cam=0.0):
        t = s.t
        if th == "swamp":
            for k in range(14):
                x = (k * 71 + math.sin(t * 0.01 + k) * 60 - cam * 0.6) % W
                y = 120 + (k * 37) % 260 + math.sin(t * 0.03 + k * 2) * 18
                pu = 0.6 + 0.4 * math.sin(t * 0.08 + k)
                s.ov(x, y, 4 + 4 * pu, 4 + 4 * pu, "#fff0a0", 0, "")
                s.ov(x, y, 2, 2, "#ffffff", 0, "")
        elif th == "forest":
            for k in range(18):
                x = (k * 59 - t * 0.7 + math.sin(t * 0.03 + k) * 30 - cam * 0.5) % W
                y = (k * 43 + t * (0.9 + (k % 3) * 0.3)) % H
                a = t * 0.05 + k
                col = ("#e0702a", "#c8372d", "#f2b632")[k % 3]
                s.pl([(x + math.cos(a) * 6, y), (x, y + 4), (x - math.cos(a) * 6, y), (x, y - 4)], col, 1)
        elif th == "snow":
            for k in range(30):
                fx = (k * 131 - t * (0.6 + (k % 3) * 0.4) - cam * 0.5) % W
                fy = (k * 57 + t * (1.2 + (k % 4) * 0.3)) % H
                s.ov(fx, fy, 2.5, 2.5, WHITE, 0)
        elif th == "lava":
            for k in range(24):
                fx = (k * 97 - cam * 0.4 + math.sin(t * 0.05 + k) * 20) % W
                fy = H - ((k * 61 + t * (1 + k % 3)) % H)
                s.ov(fx, fy, 2.5, 2.5, "#ffb347", 0)
        elif th == "circus":
            for k in range(22):
                x = (k * 47 + math.sin(t * 0.02 + k) * 25 - cam * 0.3) % W
                y = (k * 61 + t * (0.8 + (k % 4) * 0.3)) % H
                col = (RED, GOLD, "#7ad0ff", PINK, "#9be36b")[k % 5]
                s.rc(x, y, x + 6, y + 4, col, 1)
        elif th == "stage":
            for k in range(16):
                x = (k * 83 + 40) % W
                y = 30 + (k * 29) % 250
                r = 3 + 3 * abs(math.sin(t * 0.07 + k))
                s.pl(star_pts(x, y, r * 1.6, r * 0.6, 4, 0.4), "#ffe9a0", 0, False, "")
        elif th == "tower":
            for k in range(16):
                x = (k * 73 + math.sin(t * 0.04 + k) * 12) % W
                y = H - ((k * 53 + t * (0.8 + (k % 3) * 0.4)) % H)
                s.ov(x, y, 2, 2, "#ffcf6a", 0, "")
        elif th == "meadow":
            for k in range(14):
                x = (k * 71 - t * 0.5 + math.sin(t * 0.04 + k) * 25) % W
                y = (k * 37 + t * 0.6 + math.sin(k) * 30) % H
                s.ov(x, y, 4, 2.5, PINK, 0, "")
            for k in range(2):
                bx = (200 + k * 420 + t * 0.9 + math.sin(t * 0.05 + k) * 40) % W
                by = 300 + math.sin(t * 0.07 + k * 3) * 50
                wing = abs(math.sin(t * 0.4)) * 7 + 2
                s.ov(bx - 4, by, wing, 5, "#ff9a3c", 2)
                s.ov(bx + 4, by, wing, 5, "#ff9a3c", 2)
        elif th == "sky":
            for k in range(8):
                x = (k * 131 - t * (4 + k % 3) - cam * 0.8) % (W + 200) - 100
                y = 60 + (k * 57) % 360
                s.ln([(x, y), (x + 60, y)], 2, "#ffffff")

    def draw_boss_scene(s):
        s.sky_clouds(s.cfg, 0.0)
        s.draw_ambient(s.cfg["theme"], 0.0)
        b = s.boss
        ox = 0
        if s.intro > 40:
            ox = (s.intro - 40) * 9
        bshake = random.randint(-4, 4) if s.ko > 0 and s.ko < 150 else 0
        b.draw(s, ox + bshake)
        for sh in s.shots:
            s.draw_shot(sh)
        s.draw_player(s.p, 0, ghost=s.p.hp <= 0)

    def draw_bullets(s):
        cx = s.camx
        for bl in s.bul:
            x = bl.x - cx
            if bl.ex:
                s.ov(x, bl.y, 20, 16, GOLD, 3)
                s.ov(x, bl.y, 10, 8, "#ffffff", 0)
                s.pl(star_pts(x, bl.y, 26, 12, 6, s.t * 0.3), "", 2, False, GOLD)
            elif bl.kind == "spread":
                s.ov(x, bl.y, 5, 5, bl.col, 2)
            elif bl.kind == "homing":
                s.ov(x - bl.vx * 0.7, bl.y - bl.vy * 0.7, 3, 3, bl.col, 0)
                s.ov(x, bl.y, 5, 5, bl.col, 2)
                s.ov(x, bl.y, 2, 2, "#ffffff", 0)
            else:
                s.ov(x, bl.y, 7, 5, WHITE, 2)

    def draw_plat(s, x1, x2, top, col, bolts=False):
        s.rc(x1 + 8, top + 16, x2 - 8, top + 30, mix(INK, col, .5), 3)
        s.rc(x1, top, x2, top + 18, col, 4)
        s.ln([(x1 + 6, top + 5), (x2 - 6, top + 5)], 3, mix(col, "#ffffff", .45))
        for xx in range(int(x1) + 30, int(x2) - 10, 40):
            s.ln([(xx, top + 4), (xx, top + 16)], 2, INK)
        if bolts:
            s.ov(x1 + 8, top + 9, 3, 3, INK, 0)
            s.ov(x2 - 8, top + 9, 3, 3, INK, 0)

    def rg_prop(s, th, x, y, i, col):
        if th == "swamp":
            s.rc(x - 10, y - 150, x + 10, y, "#6b4a2a", 3)
            s.ov(x, y - 170, 52, 46, col, 3)
            s.ov(x - 30, y - 140, 34, 28, col, 3)
        elif th in ("forest", "snow"):
            s.rc(x - 8, y - 40, x + 8, y, "#6b4a2a", 3)
            for k in range(3):
                wd = 62 - k * 14
                yy = y - 40 - k * 52
                s.pl([(x, yy - 80), (x - wd, yy), (x + wd, yy)], col, 3)
                if th == "snow":
                    s.pl([(x, yy - 80), (x - wd * .42, yy - 34), (x + wd * .42, yy - 34)], "#f4fbff", 0, False, "")
        elif th == "circus":
            s.pl([(x - 80, y), (x + 80, y), (x, y - 140)], col, 4)
            s.pl([(x - 26, y), (x + 26, y), (x, y - 140)], "#fff3d0", 0, False, "")
            s.ln([(x, y - 140), (x, y - 175)], 4, INK)
            s.pl([(x, y - 175), (x + 28, y - 166), (x, y - 156)], RED, 3)
        elif th == "lava":
            s.pl([(x - 120, y), (x + 120, y), (x + 34, y - 180), (x - 34, y - 180)], col, 4)
            s.ov(x, y - 180, 34, 10, "#ff9a2a", 3)
            s.ln([(x - 8, y - 176), (x - 30, y - 90), (x - 18, y - 10)], 4, "#ff7a2a")
        elif th == "tower":
            s.rc(x - 24, y - 190, x + 24, y, col, 3)
            s.ov(x, y - 190, 24, 16, col, 3)
            rot = s.t * 0.01 * (1 if i % 2 else -1)
            s.pl(star_pts(x, y - 110, 44, 36, 8, rot), mix(col, "#ffffff", .15), 3)
            s.ov(x, y - 110, 12, 12, INK, 0, "")
        elif th == "sky":
            yy = y - 230 - (i % 3) * 45
            for dx, rr in ((-34, 30), (0, 40), (34, 30)):
                s.ov(x + dx, yy, rr, rr * 0.7, col, 3)

    def rg_parallax(s, cfg, cam):
        far, near, th = cfg["far"], cfg["near"], cfg["theme"]
        s.sky_clouds(cfg, cam)
        sp = 300.0
        off = cam * 0.2
        i0 = int(off // sp)
        for i in range(i0 - 1, i0 + 5):
            cx = i * sp - off + 150
            h = 90 + ((i * 37) % 70)
            s.ov(cx, GROUND + 40, 190, h + 40, far, 3)
        sp2 = 330.0
        off2 = cam * 0.5
        i0 = int(off2 // sp2)
        for i in range(i0 - 1, i0 + 5):
            bx = i * sp2 - off2 + 80 + ((i * 53) % 120)
            s.rg_prop(th, bx, GROUND, i, near)
        s.draw_ambient(th, cam)

    def rg_ground(s, cfg, cam):
        gc = cfg["ground"]
        pit = cfg["pit"]
        s.rc(-10, GROUND + 30, W + 10, H + 10, pit, 0, "")
        off = (-cam * 0.6) % 40
        for i in range(-1, W // 40 + 2):
            s.ov(i * 40 + off, GROUND + 30, 24, 8, mix(pit, "#ffffff", .25), 2)
        for (a, b) in s.rg["segs"]:
            if b < cam - 10 or a > cam + W + 10:
                continue
            x1 = max(a - cam, -20)
            x2 = min(b - cam, W + 20)
            s.pl([(x1, GROUND), (x2, GROUND), (x2, H + 20), (x1, H + 20)], gc, 4)
            s.rc(x1, GROUND + 4, x2, GROUND + 14, mix(gc, "#ffffff", .3), 0, "")
            for k in range(int(max(a, cam) // 80), int(min(b, cam + W) // 80) + 1):
                xx = k * 80 - cam
                if x1 + 4 < xx < x2 - 4:
                    s.ln([(xx, GROUND + 14), (xx - 18, H)], 2, mix(gc, INK, .25))

    def draw_goal(s, x):
        if x < -150 or x > W + 150:
            return
        s.ln([(x, GROUND), (x, GROUND - 210)], 10, INK)
        s.ln([(x, GROUND), (x, GROUND - 210)], 5, CREAM)
        s.pl([(x, GROUND - 210), (x + 100, GROUND - 184), (x, GROUND - 158)], RED, 4)
        s.ov(x, GROUND - 214, 8, 8, GOLD, 3)
        s.tx(x + 36, GROUND - 184, "BİTİŞ", 12, CREAM, ow=2)

    def draw_enemy(s, e):
        x = e.x - s.camx
        y = e.y
        col = "#ffffff" if e.flash > 0 else e.col
        dk = mix(col, INK, 0.35)
        k = e.kind
        f = e.face
        if k == "walker":
            ph = e.t * 0.3
            for d in (-1, 1):
                s.ov(x + d * 8 + math.sin(ph * d) * 6, y - 4, 10, 5, "#3a2a1a")
            s.ov(x, y - 24, 18, 22, col)
            s.ov(x, y - 14, 12, 12, mix(col, "#ffffff", .35), 0, "")
            s.ov(x + f * 6, y - 30, 7, 8, WHITE, 2)
            s.ov(x + f * 8, y - 30, 3, 4, INK, 0)
            s.ln([(x - f * 2, y - 40), (x + f * 15, y - 34)], 4, INK)
            s.pl([(x - 10, y - 42), (x, y - 58), (x + 10, y - 42)], dk, 3)
        elif k == "hopper":
            air = e.y < e.y0 - 1
            sq = 1.18 if air else (0.84 if e.cd < 12 else 1.0)
            s.ov(x, y - 22 * sq, 22 * (2 - sq), 22 * sq, col)
            s.ov(x + f * 7, y - 28 * sq, 7, 8, WHITE, 2)
            s.ov(x + f * 9, y - 28 * sq, 3, 4, INK, 0)
            s.ov(x - f * 5, y - 28 * sq, 5, 6, WHITE, 2)
            s.ln([(x - 12, y - 42 * sq), (x + 14, y - 36 * sq)], 4, INK)
            for d in (-1, 1):
                s.ov(x + d * 12, y - 3, 9, 4, dk)
        elif k == "bat":
            wing = math.sin(e.t * 0.4) * 16
            for d in (-1, 1):
                s.pl([(x + d * 6, y - 4), (x + d * 38, y - 14 + wing), (x + d * 30, y + 8),
                      (x + d * 14, y + 4)], dk, 3)
            s.ov(x, y, 15, 13, col)
            s.pl([(x - 11, y - 8), (x - 8, y - 22), (x - 2, y - 11)], col, 3)
            s.pl([(x + 11, y - 8), (x + 8, y - 22), (x + 2, y - 11)], col, 3)
            for d in (-1, 1):
                s.ov(x + d * 5, y - 2, 4, 5, WHITE, 2)
            s.ln([(x - 10, y - 8), (x - 2, y - 4)], 3, INK)
            s.ln([(x + 10, y - 8), (x + 2, y - 4)], 3, INK)
        elif k == "turret":
            s.rc(x - 26, y - 20, x + 26, y, "#6a6a78", 4)
            s.ov(x, y - 22, 19, 16, col)
            a = math.atan2(s.p.y - 30 - (y - 30), s.p.x - e.x)
            tx_, ty_ = x + math.cos(a) * 30, y - 30 + math.sin(a) * 30
            s.ln([(x, y - 30), (tx_, ty_)], 13, INK)
            s.ln([(x, y - 30), (tx_, ty_)], 8, "#8a8a98")
            s.ov(x, y - 30, 10, 10, dk, 3)

    def draw_rg_scene(s):
        cfg = s.cfg
        cam = s.camx
        w = s.rg
        s.rg_parallax(cfg, cam)
        s.rg_ground(cfg, cam)
        for (x1, x2, top) in w["plats"]:
            if x2 < cam - 20 or x1 > cam + W + 20:
                continue
            s.draw_plat(x1 - cam, x2 - cam, top, "#c98a45")
        for m in w["movers"]:
            if m["x1"] + m["w"] < cam - 20 or m["x1"] > cam + W + 20:
                continue
            s.draw_plat(m["x1"] - cam, m["x1"] + m["w"] - cam, m["y"], "#9aa6b8", True)
        s.draw_goal(w["goal"] - cam)
        for cn in s.coin_list:
            if not cn[2] and -30 < cn[0] - cam < W + 30:
                yy = cn[1] + math.sin(s.t * 0.1 + cn[0]) * 3
                s.ov(cn[0] - cam, yy, 12, 12, GOLD, 3)
                s.ov(cn[0] - cam, yy, 6, 6, "#ffe9a0", 2)
        for o in s.orbs:
            if not o[2] and -30 < o[0] - cam < W + 30:
                pu = 1 + 0.12 * math.sin(s.t * 0.2)
                s.ov(o[0] - cam, o[1], 16 * pu, 16 * pu, PINK, 3)
                s.ov(o[0] - cam, o[1], 7, 7, "#ffffff", 0, "")
        for e in w["ens"]:
            if not e.dead and cam - 100 < e.x < cam + W + 100:
                s.draw_enemy(e)
        for sh in s.shots:
            s.draw_shot(sh)
        s.draw_player(s.p, -cam, ghost=s.p.hp <= 0)

    def draw_fight(s):
        c = s.c
        cfg = s.cfg
        s.build_bg(("lv", s.lv), cfg)
        s.rays(W * 0.75, 200, cfg["ray"], 16, 0.003)
        if s.mode == "rg":
            s.draw_rg_scene()
        else:
            s.draw_boss_scene()
        s.draw_bullets()
        s.draw_parts()
        s.draw_hud()
        s.draw_banners()
        sx = sy = 0
        if s.shake > 0 and s.settings["shake"]:
            sx = random.randint(-s.shake, s.shake) // 2
            sy = random.randint(-s.shake, s.shake) // 2
        c.move("d", sx, sy)
        c.move("bg", sx - s.bgoff[0], sy - s.bgoff[1])
        s.bgoff = (sx, sy)
        if s.state == "fight" and s.mouse_mode:
            mx, my = s.mx, s.my
            s.ov(mx, my, 14, 14, "", 5, INK)
            s.ov(mx, my, 14, 14, "", 2, CREAM)
            for ddx, ddy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                s.ln([(mx + ddx * 7, my + ddy * 7), (mx + ddx * 22, my + ddy * 22)], 5, INK)
                s.ln([(mx + ddx * 8, my + ddy * 8), (mx + ddx * 21, my + ddy * 21)], 2, CREAM)
        if s.state == "pause":
            s.panel(300, 120, 660, 420)
            s.tx(480, 165, "DURAKLATILDI", 26, INK, ow=0)
            for i, lab in enumerate(("DEVAM", "YENİDEN BAŞLA", "AYARLAR", "ANA MENÜ")):
                y = 225 + i * 52
                if i == s.psel:
                    s.rc(330, y - 20, 630, y + 20, GOLD, 3)
                s.tx(480, y, lab, 20, INK, ow=0)

    def draw_hud(s):
        p = s.p
        b = s.boss
        s.panel(14, H - 58, 96, H - 16)
        col = RED if (p.hp <= 1 and (s.t // 10) % 2 == 0) else INK
        s.tx(55, H - 37, "HP %d" % max(0, p.hp), 20, col, ow=0)
        for i in range(5):
            x = 112 + i * 27
            fr = clamp(p.card - i, 0, 1)
            s.rc(x, H - 58, x + 21, H - 16, WHITE, 3)
            if fr > 0:
                s.rc(x + 2, H - 16 - 2 - fr * 38, x + 19, H - 18, GOLD if fr < 1 else "#ffd95a", 0, "")
                if fr >= 1:
                    s.pl(star_pts(x + 10.5, H - 37, 7, 3, 4, s.t * 0.05), INK, 1)
            s.rc(x, H - 58, x + 21, H - 16, "", 3)
        wp = WEAPONS[p.weapon]
        s.panel(256, H - 58, 408, H - 16)
        s.ov(274, H - 37, 8, 8, wp["col"], 3)
        s.tx(290, H - 37, wp["name"], 14, INK, "w", 0)
        bw = 440
        x0 = W / 2 - bw / 2
        s.rc(x0 - 3, 20, x0 + bw + 3, 40, INK, 0, "")
        if s.mode == "rg":
            frac = clamp(p.x / float(s.rg["len"] - 200), 0, 1)
            s.rc(x0, 23, x0 + bw, 37, "#1a3a5a", 0, "")
            if frac > 0:
                s.rc(x0, 23, x0 + bw * frac, 37, "#4fa8e8", 0, "")
            s.rc(x0 - 3, 20, x0 + bw + 3, 40, "", 3, CREAM)
            s.ov(x0 + bw * frac, 30, 9, 9, GOLD, 3)
            s.tx(W / 2, 55, s.cfg["name"], 14, CREAM, ow=2)
            s.tx(W - 22, 32, "ALTIN %d/%d" % (s.got, s.ncoin), 15, GOLD, "e", 2)
        else:
            frac = clamp(b.hp / b.maxhp, 0, 1)
            s.rc(x0, 23, x0 + bw, 37, "#5a2a1a", 0, "")
            if frac > 0:
                s.rc(x0, 23, x0 + bw * frac, 37, RED if b.ph == 1 else "#ff7a2c", 0, "")
            s.rc(x0 - 3, 20, x0 + bw + 3, 40, "", 3, CREAM)
            s.tx(W / 2, 55, b.name, 14, CREAM, ow=2)

    def draw_titlecard(s):
        t = 170 - s.intro
        if t < 20:
            k = 1 - (1 - t / 20.0) ** 2
        elif s.intro < 100:
            k = clamp((s.intro - 70) / 30.0, 0, 1)
        else:
            k = 1.0
        ox = (k - 1) * 1100
        y = 118
        s.pl([(60 + ox, y - 46), (900 + ox, y - 46), (932 + ox, y), (900 + ox, y + 46), (60 + ox, y + 46),
              (28 + ox, y)], CREAM, 5)
        s.pl([(72 + ox, y - 36), (888 + ox, y - 36), (910 + ox, y), (888 + ox, y + 36), (72 + ox, y + 36),
              (50 + ox, y)], "", 2, False, RED)
        kind = "BOSS SAVAŞI" if s.mode != "rg" else "KOŞ & ATEŞ"
        s.tx(480 + ox, y - 24, "BÖLÜM %d  ·  %s" % (s.lv + 1, kind), 13, RED, ow=0)
        s.tx(480 + ox, y + 4, s.cfg["name"], 32, INK, ow=0)
        s.tx(480 + ox, y + 30, s.cfg["sub"], 13, "#7a5a2a", ow=0)

    def draw_banners(s):
        if 0 < s.ko < 5 or 0 < s.fin < 4:
            s.rc(-20, -20, W + 20, H + 20, "#ffffff", 0, "")
        if s.intro > 70:
            s.draw_titlecard()
        if s.fin > 0 and s.fin < 120:
            k = min(1.0, s.fin / 14.0)
            s.tx(W / 2, H / 2 - 40, "BİTTİ!", int(40 + 80 * k), GOLD, ow=4)
        elif s.ko > 0 and s.ko < 150:
            k = min(1.0, s.ko / 14.0)
            s.tx(W / 2, H / 2 - 40, "K.O.!", int(40 + 90 * k), GOLD, ow=4)
        elif s.intro > 0:
            if s.intro > 60:
                yy = H / 2 - 30 - max(0, s.intro - 150) * 8
                s.tx(W / 2, yy, "HAZIR MISIN?", 56, CREAM, ow=4)
                s.tx(W / 2, H - 100, s.hint(), 14, CREAM, ow=2)
            else:
                s.tx(W / 2, H / 2 - 30, ("DÖVÜŞ!" if s.mode != "rg" else "KOŞ!"), 90 - int((60 - s.intro) * 0.5), GOLD, ow=4)

    # ---- ekranlar
    def dr_menu(s):
        t = s.t
        s.draw_clouds(0, "#fff3c8")
        s.draw_ambient("circus", 0)
        p = s.p
        ph = t * 0.02
        p.x = 210 + 120 * math.sin(ph)
        p.vx = 5.5 * math.cos(ph)
        p.face = 1 if p.vx >= 0 else -1
        p.on = True
        p.inv = 0
        p.hp = 3
        p.dash = 0
        p.mz = 0
        p.hurt = 0
        p.y = float(GROUND)
        if not hasattr(s, "menu_bosses"):
            s.menu_bosses = [Frog(s), Mage(s), Snowman(s), Bee(s)]
        idx = (t // 360) % len(s.menu_bosses)
        loc = t % 360
        ox = max(0, 40 - loc) * 20 + max(0, loc - 320) * 20
        b = s.menu_bosses[idx]
        b.t = t
        b.flash = 0
        b.face = -1
        b.vis = 1.0
        if isinstance(b, Frog):
            b.x, b.y, b.sq = 790.0, float(GROUND), 1 + 0.03 * math.sin(t * 0.12)
            b.mouth = 2 if (t % 240) < 18 else 0
        elif isinstance(b, Mage):
            b.x, b.y = 780.0, 250 + math.sin(t * 0.06) * 16
        elif isinstance(b, Snowman):
            b.x, b.y, b.sq = 790.0, float(GROUND), 1 + 0.025 * math.sin(t * 0.1)
        else:
            b.x, b.y = 780.0, 230 + math.sin(t * 0.06) * 18
        b.draw(s, ox)
        s.draw_player(p)
        word = "ÇAYCIK"
        for i, ch in enumerate(word):
            bx = W / 2 - 3 * 66 + 33 + i * 66
            by = 100 + math.sin(t * 0.07 + i * 0.8) * 8
            s.tx(bx + 5, by + 6, ch, 84, RED, ow=0)
            s.tx(bx, by, ch, 84, CREAM, ow=4)
        for k in range(6):
            a = t * 0.03 + k * 1.05
            sx = W / 2 + math.cos(a) * (250 + k * 6)
            sy = 100 + math.sin(a * 1.3) * 60
            s.pl(star_pts(sx, sy, 8 + 4 * math.sin(t * 0.1 + k), 3, 4, t * 0.05), GOLD, 2)
        s.pl([(W / 2 - 150, 150), (W / 2 + 150, 150), (W / 2 + 170, 172), (W / 2 + 150, 194),
              (W / 2 - 150, 194), (W / 2 - 170, 172)], GOLD, 4)
        s.tx(W / 2, 172, "BOSS SAVAŞI", 22, INK, ow=0)
        for i, lab in enumerate(("BAŞLA", "BÖLÜM SEÇ", "AYARLAR", "NASIL OYNANIR", "ÇIKIŞ")):
            y = 236 + i * 46
            if i == s.sel:
                pu = 1 + 0.04 * math.sin(t * 0.2)
                wd = 170 * pu
                s.pl([(W / 2 - wd, y - 20), (W / 2 + wd, y - 20), (W / 2 + wd + 16, y), (W / 2 + wd, y + 20),
                      (W / 2 - wd, y + 20), (W / 2 - wd - 16, y)], GOLD, 4)
                gx, gy = W / 2 - wd + 22, y
                s.pl([(gx - 9, gy - 10), (gx + 9, gy - 10), (gx + 8, gy + 2), (gx + 4, gy + 9),
                      (gx - 4, gy + 9), (gx - 8, gy + 2)], "#c4501a", 3, True)
                s.tx(W / 2, y, lab, 22, INK, ow=0)
            else:
                s.tx(W / 2, y, lab, 22, CREAM, ow=3)
        done = max(0, s.save["unlocked"] - 1)
        coins = sum(s.save.get("coins", {}).values())
        s.tx(W / 2, H - 62, "Tamamlanan: %d/%d   ·   Altın: %d   ·   Ölüm: %d" % (
            done, len(LEVELS), coins, s.save.get("deaths", 0)), 13, CREAM, ow=2)
        s.tx(W / 2, H - 34, "↑ ↓ seç      Enter / Space onayla      F11 tam ekran", 13, CREAM, ow=2)

    def mfrog(s):
        return None

    def dr_settings(s):
        st = s.settings
        s.panel(70, 24, 890, 514)
        s.tx(W / 2, 60, "AYARLAR", 32, INK, ow=0)
        for i, t in enumerate(("GÖRÜNTÜ", "KONTROLLER", "OYUN")):
            x1 = 120 + i * 255
            s.rc(x1, 88, x1 + 235, 122, GOLD if i == s.stab else "#d9c79a", 3)
            s.tx(x1 + 117, 105, t, 15, INK, ow=0)
        items = s.set_items()
        s.sidx = clamp(s.sidx, 0, len(items) - 1)
        step = 30 if s.stab == 1 else 46
        for i, (name, label) in enumerate(items):
            y = 156 + i * step
            sel = i == s.sidx
            if sel:
                s.rc(100, y - 15, 860, y + 15, "#f5d77a", 2)
            s.tx(120, y, label, 15, INK, "w", 0)
            if name in KEYACTS:
                for sl in (0, 1):
                    bx = 540 + sl * 160
                    on = sel and sl == s.sslot
                    s.rc(bx, y - 13, bx + 145, y + 13, GOLD if on else WHITE, 3 if on else 2)
                    if s.cap == (name, sl):
                        txt = "BİR TUŞA BAS..."
                    else:
                        txt = keyname(s.binds[name][sl])
                    s.tx(bx + 72, y, txt, 13, RED if s.cap == (name, sl) else INK, ow=0)
            else:
                v = s.setting_val(name)
                if sel and name != "reset":
                    v = "◄  %s  ►" % v
                s.tx(700, y, v, 15, RED if sel else INK, ow=0)
        if s.stab == 0:
            s.tx(W / 2, 380, "F11 ile oyunun her yerinde tam ekran açılıp kapanır.", 13, INK, ow=0)
            s.tx(W / 2, 404, "Pencere modunda çözünürlük anında uygulanır, tam ekranda oyun ekrana sığdırılır.",
                 13, INK, ow=0)
        elif s.stab == 1:
            if s.mouse_mode:
                s.tx(W / 2, 462, "FARE: imleç yönüne nişan · SOL TIK ateş · SAĞ TIK EX", 13, RED, ow=0)
            else:
                s.tx(W / 2, 462, "KLAVYE: yukarı tuşu ile yukarı / çapraz nişan · Del: slotu temizle", 13, INK, ow=0)
            s.tx(W / 2, 482, "Her eylem için 2 tuş atayabilirsin (← → ile slot seç, Enter ile ata)", 12, INK, ow=0)
        else:
            for i, dd in enumerate(DIFF):
                s.tx(120, 290 + i * 30, dd["info"], 14, INK, "w", 0)
            s.tx(120, 400, "Her bölümün zorluğunu BÖLÜM SEÇ ekranında ↑ ↓ ile ayrı ayrı da değiştirebilirsin.",
                 13, RED, "w", 0)
        if s.msgt > 0:
            s.tx(W / 2, 445, s.msg, 14, RED, ow=0)
        if s.stab != 1:
            s.tx(W / 2, 492, "↑ ↓ seç    ← → değiştir    Q / E sekme    Esc geri", 12, INK, ow=0)
        else:
            s.tx(W / 2, 500, "↑ ↓ seç   ← → slot / değer   Enter ata   Q / E sekme   Esc geri", 12, INK, ow=0)

    def dr_howto(s):
        s.panel(110, 60, 850, 480)
        s.tx(W / 2, 100, "NASIL OYNANIR", 30, INK, ow=0)
        for i, t in enumerate(HOWTO):
            s.tx(135, 140 + i * 25, t, 14, INK, "w", 0)
        s.tx(W / 2, 462, "Enter: geri", 13, RED, ow=0)

    def node_pos(s, i):
        row, col = divmod(i, 4)
        if row % 2 == 1:
            col = 3 - col
        return (150 + col * 220, 125 + row * 100)

    def dr_select(s):
        n = len(LEVELS)
        s.tx(W / 2, 34, "BÖLÜM SEÇ", 30, CREAM, ow=4)
        s.tx(W / 2, 68, "← → bölüm      ↑ ↓ zorluk      Enter başla      Esc geri", 13, CREAM, ow=2)
        pos = [s.node_pos(i) for i in range(n)]
        for i in range(n - 1):
            lk = (i + 1) >= s.save["unlocked"]
            s.ln([pos[i], pos[i + 1]], 14, INK)
            s.ln([pos[i], pos[i + 1]], 8, "#8a8372" if lk else CREAM)
        for i, lv in enumerate(LEVELS):
            x, y = pos[i]
            lock = i >= s.save["unlocked"]
            sel = i == s.lsel
            boss = lv.get("kind", "boss") == "boss"
            r = 31 if boss else 25
            by = y + (math.sin(s.t * 0.15) * 4 if sel else 0)
            if sel:
                s.ov(x, by, r + 10, r + 10, "", 5, GOLD)
            s.ov(x, by, r, r, "#8a8372" if lock else (RED if boss else CREAM), 4)
            if lock:
                s.rc(x - 9, by - 3, x + 9, by + 11, "#444444", 2)
                s.ln([(x - 5, by - 3), (x - 5, by - 10), (x + 5, by - 10), (x + 5, by - 3)], 4, INK)
            elif boss:
                s.pl(star_pts(x, by, r * 0.7, r * 0.3, 5, -math.pi / 2), GOLD, 2)
                s.tx(x, by + r + 13, str(i + 1), 12, CREAM, ow=2)
            else:
                s.tx(x, by, str(i + 1), 20, INK, ow=0)
            g = s.save["grades"].get(str(i))
            if g and not lock:
                s.ov(x + r * 0.85, by - r * 0.85, 11, 11, GOLD, 2)
                s.tx(x + r * 0.85, by - r * 0.85, g, 12, INK, ow=0)
        i = s.lsel
        lv = LEVELS[i]
        lock = i >= s.save["unlocked"]
        boss = lv.get("kind", "boss") == "boss"
        s.panel(60, 372, 900, 512)
        if lock:
            s.tx(W / 2, 442, "KİLİTLİ - önce önceki bölümü bitir", 20, INK, ow=0)
            return
        s.tx(90, 408, "%d. %s" % (i + 1, lv["name"]), 22, INK, "w", 0)
        s.tx(90, 438, lv["sub"], 14, RED, "w", 0)
        tag = "BOSS SAVAŞI" if boss else "KOŞ & ATEŞ"
        s.tx(90, 470, tag + "    " + "★" * lv["stars"] + "☆" * (3 - lv["stars"]), 14, INK, "w", 0)
        dd = DIFF[clamp(s.settings["diff"][i], 0, 2)]
        s.tx(520, 408, "◄ %s ►" % dd["name"], 20, dd["col"], "center", 2)
        tm = s.save["times"].get(str(i))
        s.tx(520, 442, ("en iyi süre: %.1f sn" % tm) if tm else "henüz bitmedi", 13, INK, ow=0)
        if not boss:
            s.tx(520, 470, "Altın: %d / 5" % s.save.get("coins", {}).get(str(i), 0), 13, "#a8741a", ow=0)
        g = s.save["grades"].get(str(i))
        if g:
            s.ov(800, 442, 36, 36, GOLD, 5)
            s.tx(800, 442, g, 40, INK, ow=0)

    def dr_result(s):
        r = s.res
        s.panel(190, 50, 770, 490)
        s.tx(W / 2, 100, "SONUÇ", 38, INK, ow=0)
        tt = r["time"] * clamp((s.rt - 20) / 50.0, 0, 1)
        lines = [("Süre", "%d:%04.1f" % (int(tt // 60), tt % 60)),
                 ("Kalan can", "%d / %d" % (r["hp"], r["maxhp"])),
                 ("Parry", str(r["parries"])),
                 ("Zorluk", r["diff"])]
        if r.get("coins"):
            lines.insert(3, ("Altın", "%d / %d" % r["coins"]))
        step = 38 if len(lines) > 4 else 46
        for i, (a, b) in enumerate(lines):
            if s.rt > 20 + i * 18:
                y = 165 + i * step
                s.tx(250, y, a, 22, INK, "w", 0)
                s.tx(710, y, b, 22, RED, "e", 0)
                s.ln([(250, y + 20), (710, y + 20)], 2, "#b9a97d")
        if s.rt > 90:
            k = min(1.0, (s.rt - 90) / 10.0)
            s.ov(W / 2, 395, 54 * k + 4, 54 * k + 4, GOLD, 5)
            s.tx(W / 2, 395, r["grade"], int(70 * k) + 4, INK, ow=0)
        if s.rt > 100 and (s.t // 25) % 2 == 0:
            txt = "Enter: sonraki bölüm" if s.lv + 1 < len(LEVELS) else "Enter: devam"
            s.tx(W / 2, 470, txt, 17, RED, ow=0)
        s.draw_parts()

    def dr_dead(s):
        s.panel(200, 80, 760, 460)
        s.tx(W / 2, 135, "ÖLDÜN!", 50, RED, ow=0)
        if s.mode == "rg":
            nm = s.cfg["name"]
            frac = clamp(s.p.x / float(s.rg["len"] - 200), 0, 1)
            bar = "#4fa8e8"
            lab = "Bölümün %%%d kadarını geçtin" % int(frac * 100)
        else:
            b = s.boss
            nm = b.name
            frac = clamp(b.hp / b.maxhp, 0, 1)
            bar = RED
            lab = "Boss'un kalan canı: %%%d" % int(frac * 100)
        s.tx(W / 2, 200, nm, 20, INK, ow=0)
        s.rc(260, 230, 700, 256, "#5a2a1a", 3)
        s.rc(262, 232, 262 + 436 * frac, 254, bar, 0, "")
        s.tx(W / 2, 285, lab, 15, INK, ow=0)
        for i, lab in enumerate(("TEKRAR DENE", "ANA MENÜ")):
            y = 345 + i * 50
            if i == s.dsel:
                s.rc(300, y - 20, 660, y + 20, GOLD, 3)
            s.tx(W / 2, y, lab, 20, INK, ow=0)

    def dr_ending(s):
        s.tx(W / 2, 150, "TEBRİKLER!", 70, CREAM, ow=5)
        s.tx(W / 2, 235, "Tüm bosslar yenildi.", 24, GOLD, ow=3)
        s.tx(W / 2, 285, "Bardak artık huzur içinde çayını yudumlayabilir.", 18, CREAM, ow=2)
        s.p.x, s.p.face = W / 2, 1
        s.p.y = GROUND
        s.p.hp = 3
        s.p.inv = 0
        s.draw_player(s.p)
        s.draw_parts()
        if s.rt > 90 and (s.t // 25) % 2 == 0:
            s.tx(W / 2, 400, "Enter: ana menü", 18, CREAM, ow=3)

    # --------------------------------------------------------------- döngü
    def loop(s):
        now = time.perf_counter()
        dt = min(now - s.last, 0.1)
        s.acc += dt
        s.last = now
        n = 0
        try:
            # Keep both simulation and rendering on the 60 Hz game tick.
            while s.acc >= 1 / 60.0 and n < 4:
                s.acc -= 1 / 60.0
                s.update()
                n += 1
                if s.quit:
                    return
            if n:
                s.draw()
            # Schedule close to 60 callbacks per second on supported devices.
            s.root.after(16, s.loop)
        except tk.TclError:
            return


def main():
    root = tk.Tk()
    Game(root)
    root.mainloop()


if __name__ == "__main__":
    main()
