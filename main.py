import math
import random
import io
import wave
import struct
import json
import os
import sys

import pygame

# ----------------------------------------------------------------- Constants
W, H = 960, 540
GROUND = 452
GRAV = 0.85

def parse_hex(c):
    if isinstance(c, (tuple, list)):
        return tuple(c[:4])
    c = c.lstrip('#')
    if len(c) == 6:
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), 255)
    elif len(c) == 8:
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16), int(c[6:8], 16))
    return (255, 255, 255, 255)

INK = parse_hex("#1b1209")
CREAM = parse_hex("#f7e8c0")
WHITE = parse_hex("#fffaf0")
GOLD = parse_hex("#f2b632")
RED = parse_hex("#c8372d")
PINK = parse_hex("#ff6fb5")

def get_save_path():
    try:
        from android.storage import app_storage_path # type: ignore
        base = app_storage_path()
    except Exception:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "caycik_kayit.json")

SAVE_PATH = get_save_path()

def clamp(v, a, b):
    return max(a, min(b, v))

def mix_col(c1, c2, t):
    c1 = parse_hex(c1)
    c2 = parse_hex(c2)
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
        255
    )

def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    l = dx * dx + dy * dy
    t = 0 if l == 0 else clamp(((px - x1) * dx + (py - y1) * dy) / l, 0, 1)
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))

def star_pts(cx, cy, r1, r2, n, rot):
    pts = []
    for i in range(n * 2):
        a = rot + i * math.pi / n
        r = r1 if i % 2 == 0 else r2
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts

DIFF = [
    dict(name="KOLAY", hp=5, bhp=0.7, bt=0.82, shot=0.9, cap=79, col="#6fd04a",
         info="KOLAY: 5 can · boss %30 daha zayıf ve yavaş · en yüksek not B"),
    dict(name="NORMAL", hp=3, bhp=1.0, bt=1.0, shot=1.0, col=GOLD,
         info="NORMAL: 3 can · standart savaş"),
    dict(name="ZOR", hp=2, bhp=1.3, bt=1.15, shot=1.1, bonus=5, col="#ff5a4a",
         info="ZOR: 2 can · boss %30 daha dayanıklı ve hızlı · +5 puan"),
]

# ----------------------------------------------------------------- Sound Synth
class SfxEngine:
    def __init__(self):
        self.on = True
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
            self.sounds = {
                "blip": self._make_sound(700, 0.05),
                "ok": self._make_sound(900, 0.09, 400),
                "hurt": self._make_sound(220, 0.28, -160),
                "parry": self._make_sound(1100, 0.14, 700),
                "dash": self._make_sound(500, 0.08, -250),
                "ko": self._make_sound(600, 0.7, -500),
                "go": self._make_sound(500, 0.25, 600),
            }
        except Exception as e:
            print("Audio init exception:", e)

    def _make_sound(self, f, dur, slide=0):
        sr = 22050
        n = int(sr * dur)
        b = io.BytesIO()
        w = wave.open(b, "wb")
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        fr = bytearray()
        ph = 0.0
        for i in range(n):
            f2 = f + slide * i / n
            ph = (ph + f2 / sr) % 1.0
            v = 1 if ph < 0.5 else -1
            fr += struct.pack("<h", int(v * (1 - i / n) * 5000))
        w.writeframes(bytes(fr))
        w.close()
        b.seek(0)
        return pygame.mixer.Sound(b)

    def play(self, k):
        if self.on and k in self.sounds:
            try:
                self.sounds[k].play()
            except Exception:
                pass

# ----------------------------------------------------------------- Render Wrapper
class Renderer:
    def __init__(self, target_surf):
        self.surf = target_surf
        self.font_cache = {}

    def get_font(self, size):
        if size not in self.font_cache:
            try:
                self.font_cache[size] = pygame.font.SysFont("georgia,dejavusans,freesans,arial", max(10, int(size)), bold=True)
            except Exception:
                self.font_cache[size] = pygame.font.Font(None, max(10, int(size)))
        return self.font_cache[size]

    def ov(self, x, y, rx, ry, fill, w=3, out=INK):
        rx, ry = max(1, int(rx)), max(1, int(ry))
        rect = pygame.Rect(int(x - rx), int(y - ry), int(rx * 2), int(ry * 2))
        if fill != "" and fill is not None:
            pygame.draw.ellipse(self.surf, parse_hex(fill), rect)
        if w > 0 and out != "" and out is not None:
            pygame.draw.ellipse(self.surf, parse_hex(out), rect, max(1, int(w)))

    def rc(self, x1, y1, x2, y2, fill, w=3, out=INK):
        rx = min(x1, x2)
        ry = min(y1, y2)
        rw = abs(x2 - x1)
        rh = abs(y2 - y1)
        rect = pygame.Rect(int(rx), int(ry), int(rw), int(rh))
        if fill != "" and fill is not None:
            pygame.draw.rect(self.surf, parse_hex(fill), rect)
        if w > 0 and out != "" and out is not None:
            pygame.draw.rect(self.surf, parse_hex(out), rect, max(1, int(w)))

    def pl(self, pts, fill, w=3, smooth=False, out=INK):
        if len(pts) < 3:
            return
        ipts = [(int(px), int(py)) for px, py in pts]
        if fill != "" and fill is not None:
            pygame.draw.polygon(self.surf, parse_hex(fill), ipts)
        if w > 0 and out != "" and out is not None:
            pygame.draw.polygon(self.surf, parse_hex(out), ipts, max(1, int(w)))

    def ln(self, pts, w, fill, smooth=False):
        if len(pts) < 2:
            return
        ipts = [(int(px), int(py)) for px, py in pts]
        col = parse_hex(fill)
        pygame.draw.lines(self.surf, col, False, ipts, max(1, int(w)))

    def limb(self, a, b, bend=0):
        mid = ((a[0] + b[0]) / 2 + bend, (a[1] + b[1]) / 2)
        self.ln([a, mid, b], 9, INK, True)
        self.ln([a, mid, b], 5, CREAM, True)

    def tx(self, x, y, text, size=20, fill=CREAM, anchor="center", ow=2, out=INK):
        font = self.get_font(size)
        text_str = str(text)
        fill_col = parse_hex(fill)
        out_col = parse_hex(out)

        rendered_fill = font.render(text_str, True, fill_col)
        rect = rendered_fill.get_rect()
        if anchor == "center":
            rect.center = (int(x), int(y))
        elif anchor == "w":
            rect.midleft = (int(x), int(y))
        elif anchor == "e":
            rect.midright = (int(x), int(y))
        else:
            rect.topleft = (int(x), int(y))

        if ow > 0 and out != "" and out is not None:
            rendered_out = font.render(text_str, True, out_col)
            offs = ((-ow, 0), (ow, 0), (0, -ow), (0, ow))
            if ow >= 3:
                offs += ((-ow, -ow), (ow, ow), (-ow, ow), (ow, -ow))
            for dx, dy in offs:
                orect = rect.copy()
                orect.x += dx
                orect.y += dy
                self.surf.blit(rendered_out, orect)
        self.surf.blit(rendered_fill, rect)

    def panel(self, x1, y1, x2, y2, fill=CREAM):
        self.rc(x1 + 6, y1 + 7, x2 + 6, y2 + 7, INK, 0, "")
        self.rc(x1, y1, x2, y2, fill, 4)
        self.rc(x1 + 8, y1 + 8, x2 - 8, y2 - 8, "", 2)

# ----------------------------------------------------------------- Game Entities
class Bullet:
    def __init__(self, x, y, vx, vy, ex=False):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.ex = ex
        self.r = 18 if ex else 6
        self.age = 0
        self.dead = False
        self.hit = False

class Shot:
    def __init__(self, kind, x, y, vx=0.0, vy=0.0, r=12, pink=False, g=0.0, hp=0,
                 hh=40, sp=0.0, ph=0.0, life=700):
        self.kind, self.x, self.y, self.vx, self.vy = kind, x, y, vx, vy
        self.r, self.pink, self.g, self.hp, self.hh, self.sp, self.ph, self.life = r, pink, g, hp, hh, sp, ph, life
        self.t = 0
        self.dead = False
        self.ang = math.atan2(vy, vx) if (vx or vy) else 0.0
        self.flash = 0
        self.spin = random.uniform(0, 6)

    def update(self, G):
        self.t += 1
        k = self.kind
        if k == "carrot":
            if self.t < 200:
                p = G.p
                want = math.atan2(p.y - 30 - self.y, p.x - self.x)
                d = (want - self.ang + math.pi) % (2 * math.pi) - math.pi
                self.ang += clamp(d, -0.045, 0.045)
            self.vx = math.cos(self.ang) * self.sp
            self.vy = math.sin(self.ang) * self.sp
        elif k == "fly":
            self.vx = math.sin(self.t * 0.07 + self.ph) * 2.6
        elif k == "gear":
            if self.y >= GROUND - self.r and self.vy >= 0:
                self.y = GROUND - self.r
                self.vy = -8.5
            self.spin -= 0.2
        elif k in ("card", "star"):
            self.spin += 0.22
        self.vy += self.g
        self.x += self.vx
        self.y += self.vy
        if k == "bomb" and self.y >= GROUND - self.r:
            self.dead = True
            G.bomb_boom(self)
        if self.flash > 0:
            self.flash -= 1
        if self.t > self.life or self.x < -90 or self.x > W + 90 or self.y > H + 90 or self.y < -140:
            self.dead = True

def hits_player(sh, p):
    if sh.kind == "wave":
        return abs(sh.x - p.x) < sh.r + 10 and p.y > GROUND - sh.hh
    bx1, by1, bx2, by2 = p.box()
    cx = clamp(sh.x, bx1, bx2)
    cy = clamp(sh.y, by1, by2)
    return math.hypot(sh.x - cx, sh.y - cy) < sh.r * 0.8

class Player:
    def __init__(self):
        self.x = 170.0
        self.y = float(GROUND)
        self.vx = self.vy = 0.0
        self.face = 1
        self.on = True
        self.coy = 0
        self.hp = 3
        self.maxhp = 3
        self.inv = 0
        self.hurt = 0
        self.dash = 0
        self.dd = 1
        self.dcd = 0
        self.cd = 0
        self.mz = 0
        self.card = 0.0
        self.parries = 0
        self.jh = False
        self.t = 0

    def box(self):
        return (self.x - 13, self.y - 54, self.x + 13, self.y - 3)

    def aimvec(self, g):
        up = g.act("up")
        mv = g.act("left") or g.act("right")
        if up and mv:
            return (self.face * 0.7071, -0.7071)
        if up:
            return (0.0, -1.0)
        return (float(self.face), 0.0)

    def update(self, g):
        self.t += 1
        for a in ("inv", "hurt", "dcd", "cd", "mz"):
            v = getattr(self, a)
            if v > 0:
                setattr(self, a, v - 1)
        if self.hp <= 0:
            return
        l = g.act("left")
        r = g.act("right")
        locked = self.hurt > 14
        if self.dash > 0:
            self.dash -= 1
            self.vx = self.dd * 14.5
            self.vy = 0
            if self.t % 2 == 0:
                g.dust(self.x - self.dd * 10, self.y - 4, 1)
        else:
            tgt = ((1 if r else 0) - (1 if l else 0)) * 5.5
            if locked:
                tgt = 0
            self.vx += (tgt - self.vx) * (0.42 if self.on else 0.24)
            if not locked:
                if r and not l:
                    self.face = 1
                elif l and not r:
                    self.face = -1
            if g.actp("dash") and self.dcd <= 0 and not locked:
                self.dash = 12
                self.dcd = 38
                self.dd = self.face
                g.sfx.play("dash")
                g.dust(self.x, self.y - 4, 5)

        jp = g.actp("jump")
        if jp and not locked:
            if self.on or self.coy > 0:
                self.vy = -16.8
                self.on = False
                self.coy = 0
                self.jh = True
                g.dust(self.x, self.y, 5)
            else:
                g.try_parry()
        if self.jh and not g.act("jump"):
            self.jh = False
            if self.vy < -6:
                self.vy *= 0.45
        if self.dash == 0:
            self.vy = min(self.vy + GRAV, 17.0)
        self.x = clamp(self.x + self.vx, 20, W - 20)
        oy = self.y
        self.y += self.vy
        was = self.on
        self.on = False
        if self.vy >= 0:
            for (x1, x2, top) in g.plats:
                if x1 - 8 <= self.x <= x2 + 8 and oy <= top + 2 and self.y >= top:
                    self.y = float(top)
                    self.vy = 0
                    self.on = True
            if self.y >= GROUND:
                self.y = float(GROUND)
                self.vy = 0
                self.on = True
        if self.on:
            self.coy = 6
            if not was:
                g.dust(self.x, self.y, 6)
        else:
            self.coy = max(0, self.coy - 1)

        # Shoot
        can = g.intro <= 60 and not locked and self.dash == 0 and g.ko == 0
        if can and g.shooting() and self.cd <= 0:
            self.cd = 5
            ax, ay = self.aimvec(g)
            ang = math.atan2(ay, ax) + random.uniform(-0.03, 0.03)
            g.bul.append(Bullet(self.x + ax * 30, self.y - 36 + ay * 26,
                                math.cos(ang) * 18, math.sin(ang) * 18))
            self.mz = 4
        if can and g.ex_pressed() and self.card >= 1:
            self.card -= 1
            ax, ay = self.aimvec(g)
            g.bul.append(Bullet(self.x + ax * 30, self.y - 36 + ay * 26, ax * 13, ay * 13, True))
            self.mz = 8
            g.shake = 6
            g.burst(self.x + ax * 30, self.y - 36, GOLD, 10, 5)

# ----------------------------------------------------------------- Bosses
class BaseBoss:
    def pick(self, opts):
        o = [x for x in opts if x != self.last] or opts
        self.last = random.choice(o)
        return self.last

    def hurt(self, d):
        self.hp = max(0, self.hp - d)
        self.flash = 2

class Frog(BaseBoss):
    name = "KURBAĞA KRAL"
    maxhp = 250

    def __init__(self, g):
        self.g = g
        self.hp = self.maxhp
        self.x = 770.0
        self.y = float(GROUND)
        self.vx = self.vy = 0.0
        self.st = "idle"
        self.tm = 60
        self.t = 0
        self.flash = 0
        self.ph = 1
        self.face = -1
        self.n = 0
        self.sq = 1.0
        self.mouth = 0
        self.last = ""
        self.dead = False

    def boxes(self):
        return [(self.x - 70, self.y - 165, self.x + 70, self.y - 8)]

    def update(self):
        g = self.g
        p = g.p
        self.t += 1
        self.flash = max(0, self.flash - 1)
        self.mouth = max(0, self.mouth - 1)
        if self.st not in ("air",):
            self.face = -1 if p.x < self.x else 1
        if self.ph == 1 and self.hp <= self.maxhp * 0.5:
            self.ph = 2
            self.st = "roar"
            self.tm = 70
            g.shake = 12
        st = self.st
        if st == "idle":
            self.sq = 1 + 0.03 * math.sin(self.t * 0.12)
            self.tm -= 1
            if self.tm <= 0:
                a = self.pick(["spit", "jump"] + (["flies"] if self.ph == 2 else []))
                self.st = a + "_w"
                self.tm = 26
                self.n = 0
        elif st == "roar":
            self.sq = 1.1 + 0.05 * math.sin(self.t)
            self.mouth = 2
            self.tm -= 1
            if self.tm <= 0:
                self.st = "idle"
                self.tm = 30
        elif st == "spit_w":
            self.sq = 0.9
            self.tm -= 1
            if self.tm <= 0:
                self.st = "spit"
                self.tm = 0
        elif st == "spit":
            self.tm -= 1
            if self.tm <= 0:
                total = 3 if self.ph == 1 else 5
                mx = self.x + self.face * 66
                my = self.y - 100
                ang = math.atan2(p.y - 30 - my, p.x - mx) + random.uniform(-0.12, 0.12)
                sp = 5.6 if self.ph == 1 else 6.6
                pink = (self.n == total - 1) or (self.ph == 2 and self.n == 1)
                g.shots.append(Shot("ball", mx, my, math.cos(ang) * sp, math.sin(ang) * sp,
                                    r=14, pink=pink))
                self.mouth = 10
                self.n += 1
                self.tm = 18 if self.ph == 1 else 13
                self.sq = 1.08
                if self.n >= total:
                    self.st = "idle"
                    self.tm = 55 if self.ph == 1 else 38
        elif st == "jump_w":
            self.sq = 0.78
            self.tm -= 1
            if self.tm <= 0:
                self.st = "air"
                self.vy = -23.0
                T = 2 * 23.0 / 0.9
                tx = random.uniform(170, 330) if self.x > 480 else random.uniform(640, 790)
                self.vx = (tx - self.x) / T
        elif st == "air":
            self.vy += 0.9
            self.x += self.vx
            self.y += self.vy
            self.sq = 1.18 if self.vy < 0 else 1.05
            if self.y >= GROUND:
                self.y = float(GROUND)
                self.vy = 0
                self.vx = 0
                self.st = "land"
                self.tm = 34
                g.shake = 12
                g.dust(self.x, GROUND, 10)
                sp = 6.5 if self.ph == 1 else 7.8
                for d in (-1, 1):
                    g.shots.append(Shot("wave", self.x + d * 60, GROUND - 2, d * sp, 0, r=16, hh=40))
            elif self.vy > 0:
                bx = self.boxes()[0]
                px1, py1, px2, py2 = p.box()
                if px1 < bx[2] and px2 > bx[0] and py1 < bx[3] and py2 > bx[1]:
                    g.hurt_player()
        elif st == "land":
            self.sq = 0.8 + 0.2 * (1 - self.tm / 34.0)
            self.tm -= 1
            if self.tm <= 0:
                self.st = "idle"
                self.tm = 40 if self.ph == 1 else 26
        elif st == "flies_w":
            self.mouth = 2
            self.sq = 1.1
            self.tm -= 1
            if self.tm <= 0:
                self.st = "flies"
                self.tm = 0
        elif st == "flies":
            self.tm -= 1
            if self.tm <= 0:
                g.shots.append(Shot("fly", random.uniform(80, 880), -20, 0, 2.4, r=13,
                                    pink=(self.n % 3 == 2), ph=random.uniform(0, 6), life=500))
                self.n += 1
                self.tm = 16
                if self.n >= 7:
                    self.st = "idle"
                    self.tm = 45

    def draw(self, g, ox=0):
        p = g.p
        x = self.x + ox
        y = self.y
        sq = self.sq
        fl = self.flash > 0

        def C(c):
            return "#ffffff" if fl else c
        green, dk, belly = C("#69b043"), C("#3d7a2b"), C("#e4f09a")
        g.ren.ov(x, GROUND + 5, 92, 9, mix_col(g.gcol, INK, .5), 0, "")
        g.ren.ov(x - 62, y - 20 * sq, 34, 22 * sq, dk)
        g.ren.ov(x + 62, y - 20 * sq, 34, 22 * sq, dk)
        g.ren.ov(x, y - 72 * sq, 82, 72 * sq, green)
        g.ren.ov(x, y - 52 * sq, 56, 46 * sq, belly, 2)
        for d in (-1, 1):
            g.ren.ov(x + d * 60, y - 8, 36, 13, green)
            g.ren.ov(x + d * 40, y - 60 * sq, 17, 26 * sq, dk, 2)
        for d in (-1, 1):
            ex = x + d * 38
            ey = y - 146 * sq
            g.ren.ov(ex, ey, 28, 28, green)
            g.ren.ov(ex, ey, 21, 21, C("#fffbe8"), 2)
            dx = p.x - ex
            dy = (p.y - 30) - ey
            dd = math.hypot(dx, dy) or 1
            g.ren.ov(ex + dx / dd * 8, ey + dy / dd * 8, 9, 11, INK, 0, "")
            lid = 4 if self.ph == 1 else 12
            g.ren.pl([(ex + d * 30, ey - 34), (ex - d * 30, ey - 34), (ex - d * 30, ey - lid - 2),
                      (ex + d * 30, ey - lid - 18)], green, 3)
        my = y - 92 * sq
        if self.mouth > 0:
            g.ren.ov(x, my + 6, 50, 24, "#7a1f1f")
            g.ren.ov(x, my + 18, 28, 9, PINK, 0, "")
        else:
            g.ren.ln([(x - 54, my - 6), (x, my + 12), (x + 54, my - 6)], 6, INK, True)
        cy = y - 184 * sq
        g.ren.pl([(x - 26, cy + 8), (x - 26, cy - 20), (x - 13, cy - 6), (x, cy - 26),
                  (x + 13, cy - 6), (x + 26, cy - 20), (x + 26, cy + 8)], C(GOLD))
        g.ren.ov(x, cy - 2, 5, 5, C(RED), 2)
        for wx, wy in ((-50, -100), (-62, -70), (55, -105), (64, -64)):
            g.ren.ov(x + wx, y + wy * sq, 6, 5, dk, 2)

class Mage(BaseBoss):
    name = "SİHİRBAZ TAVŞAN"
    maxhp = 320

    def __init__(self, g):
        self.g = g
        self.hp = self.maxhp
        self.bx, self.by = 760.0, 250.0
        self.x, self.y = self.bx, self.by
        self.st = "idle"
        self.tm = 70
        self.t = 0
        self.flash = 0
        self.ph = 1
        self.n = 0
        self.vol = 0
        self.last = ""
        self.dead = False
        self.vis = 1.0

    def boxes(self):
        if self.vis < 0.5:
            return []
        return [(self.x - 62, self.y - 110, self.x + 62, self.y + 105)]

    def fan(self):
        g = self.g
        p = g.p
        n = 5 if self.ph == 1 else 7
        sp = 6.2 if self.ph == 1 else 7.0
        spread = 1.0 if self.ph == 1 else 1.3
        a0 = math.atan2(p.y - 30 - self.y, p.x - self.x) + random.uniform(-0.15, 0.15)
        pk = random.randrange(n) if random.random() < 0.75 else -1
        for i in range(n):
            a = a0 - spread / 2 + spread * i / (n - 1)
            g.shots.append(Shot("card", self.x - 20, self.y, math.cos(a) * sp, math.sin(a) * sp,
                                r=12, pink=(i == pk)))

    def update(self):
        g = self.g
        p = g.p
        self.t += 1
        self.flash = max(0, self.flash - 1)
        self.y = self.by + math.sin(self.t * 0.06) * 16
        self.x = self.bx + math.sin(self.t * 0.031) * 18
        if self.ph == 1 and self.hp <= self.maxhp * 0.5:
            self.ph = 2
            g.shake = 10
            self.st = "idle"
            self.tm = 40
            g.burst(self.x, self.y, PINK, 24, 6)
        st = self.st
        if st == "idle":
            self.tm -= 1
            if self.tm <= 0:
                a = self.pick(["cards", "carrots", "tele"] + (["stars"] if self.ph == 2 else []))
                self.st = a + "_w"
                self.tm = 26
                self.n = 0
                if a == "cards":
                    self.vol = 2 if self.ph == 1 else 3
        elif st == "cards_w":
            self.tm -= 1
            if self.tm <= 0:
                self.st = "cards"
                self.tm = 0
        elif st == "cards":
            self.tm -= 1
            if self.tm <= 0:
                if self.vol <= 0:
                    self.st = "idle"
                    self.tm = 55 if self.ph == 1 else 38
                else:
                    self.fan()
                    self.vol -= 1
                    self.tm = 44
        elif st == "carrots_w":
            self.tm -= 1
            if self.tm <= 0:
                self.st = "carrots"
        elif st == "carrots":
            n = 2 if self.ph == 1 else 3
            pk = random.randrange(n)
            for i in range(n):
                a = math.atan2(p.y - 30 - self.y, p.x - self.x) + (i - (n - 1) / 2.0) * 0.7
                sp = 4.4 + 0.7 * (self.ph - 1)
                g.shots.append(Shot("carrot", self.x - 30, self.y + 10, math.cos(a) * 3, math.sin(a) * 3,
                                    r=15, pink=(i == pk and random.random() < 0.7), hp=3, sp=sp))
            self.st = "idle"
            self.tm = 85
        elif st == "tele_w":
            self.tm -= 1
            if self.tm <= 0:
                self.st = "vanish"
                self.tm = 22
                g.burst(self.x, self.y, "#e9dcff", 14, 4)
        elif st == "vanish":
            self.vis = self.tm / 22.0
            self.tm -= 1
            if self.tm <= 0:
                spots = [(800, 260), (170, 250), (480, 190)]
                spots = [q for q in spots if abs(q[0] - self.bx) > 60]
                self.bx, self.by = random.choice(spots)
                self.st = "appear"
                self.tm = 22
        elif st == "appear":
            self.vis = 1 - self.tm / 22.0
            self.tm -= 1
            if self.tm <= 0:
                self.vis = 1.0
                self.st = "cards_w"
                self.tm = 10
                self.vol = 1
                g.burst(self.bx, self.by, "#e9dcff", 14, 4)
        elif st == "stars_w":
            self.tm -= 1
            if self.tm <= 0:
                self.st = "stars"
                self.tm = 0
                self.n = 0
        elif st == "stars":
            self.tm -= 1
            if self.tm <= 0:
                if self.n >= 3:
                    self.st = "idle"
                    self.tm = 55
                else:
                    gi = random.randint(1, 8)
                    pk = random.choice([i for i in range(10) if abs(i - gi) > 1])
                    for i in range(10):
                        if abs(i - gi) <= 1:
                            continue
                        g.shots.append(Shot("star", 48 + i * (W - 96) / 9.0, -20, 0, 4.2, r=16,
                                            pink=(i == pk), life=300))
                    self.n += 1
                    self.tm = 70

    def draw(self, g, ox=0):
        p = g.p
        if self.vis < 0.06:
            return
        x = self.x + ox
        y = self.y
        fl = self.flash > 0

        def C(c):
            return "#ffffff" if fl else c
        sc = 0.55 + 0.45 * self.vis
        g.ren.ov(x, GROUND + 5, 60 * sc, 8, mix_col(g.gcol, INK, .5), 0, "")
        g.ren.pl([(x - 60 * sc, y + 10), (x + 60 * sc, y + 10), (x + 92 * sc, y + 140 * sc),
                  (x - 92 * sc, y + 140 * sc)], C("#7a35b5"), 3, True)
        g.ren.ov(x, y + 55 * sc, 48 * sc, 62 * sc, C("#241532"))
        g.ren.ov(x, y + 55 * sc, 22 * sc, 42 * sc, C("#fff6e0"), 2)
        sw = math.sin(self.t * 0.12) * 6
        g.ren.limb((x - 36 * sc, y + 44), (x - 80 * sc, y + 20 + sw), 6)
        g.ren.ov(x - 82 * sc, y + 18 + sw, 10, 10, WHITE)
        g.ren.limb((x + 36 * sc, y + 44), (x + 78 * sc, y + 64 - sw), -6)
        g.ren.ov(x + 80 * sc, y + 66 - sw, 10, 10, WHITE)
        for d in (-1, 1):
            e = [(x + d * 14, y - 30), (x + d * 22, y - 118 * sc - 6), (x + d * 46, y - 112 * sc),
                 (x + d * 36, y - 30)]
            g.ren.pl(e, C(WHITE), 3, True)
            g.ren.pl([(x + d * 20, y - 36), (x + d * 27, y - 100 * sc), (x + d * 38, y - 96 * sc),
                      (x + d * 31, y - 36)], C("#ffb3d1"), 0, True, "")
        g.ren.ov(x, y - 6, 42 * sc, 38 * sc, C(WHITE))
        g.ren.rc(x - 27, y - 84, x + 27, y - 40, C("#1b1b22"))
        g.ren.rc(x - 27, y - 58, x + 27, y - 46, C(RED), 2)
        g.ren.ov(x, y - 41, 42, 8, C("#1b1b22"))
        if self.st in ("cards_w", "carrots_w", "stars_w", "tele_w"):
            g.ren.pl(star_pts(x, y - 98, 12, 5, 4, self.t * 0.2), GOLD, 2)
        for d in (-1, 1):
            ex = x + d * 15
            ey = y - 10
            g.ren.ov(ex, ey, 9, 11, WHITE, 2)
            dx = p.x - ex
            dy = (p.y - 30) - ey
            dd = math.hypot(dx, dy) or 1
            g.ren.ov(ex + dx / dd * 3, ey + dy / dd * 3, 4, 6, INK, 0, "")
            g.ren.ln([(ex - d * 12, ey - 17 + (4 if self.ph == 2 else 0)), (ex + d * 8, ey - 10)], 4, INK)
        g.ren.ov(x, y + 3, 6, 4, C(PINK), 2)
        g.ren.rc(x - 6, y + 9, x + 6, y + 21, WHITE, 2)
        g.ren.ln([(x, y + 9), (x, y + 21)], 1, INK)
        for d in (-1, 1):
            g.ren.ln([(x + d * 10, y + 4), (x + d * 38, y)], 2, INK)
            g.ren.ln([(x + d * 10, y + 8), (x + d * 38, y + 12)], 2, INK)

class Clock(BaseBoss):
    name = "ZAMAN EFENDİSİ"
    maxhp = 420
    cx = 745.0
    cy = 225.0
    L = 520

    def __init__(self, g):
        self.g = g
        self.hp = self.maxhp
        self.st = "idle"
        self.tm = 80
        self.t = 0
        self.flash = 0
        self.ph = 1
        self.n = 0
        self.last = ""
        self.dead = False
        self.beams = []
        self.live = False
        self.a0 = 0.0
        self.dr = 1
        self.el = 0
        self.om = 0.034
        self.hand = 0.0

    def boxes(self):
        return [(self.cx - 100, self.cy - 100, self.cx + 100, self.cy + 100)]

    def ring(self):
        g = self.g
        n = 16 if self.ph == 1 else 22
        off = random.uniform(0, math.tau)
        sp = 3.8 if self.ph == 1 else 4.5
        pk = set(random.sample(range(n), 2))
        for i in range(n):
            a = off + i * math.tau / n
            g.shots.append(Shot("ball", self.cx, self.cy, math.cos(a) * sp, math.sin(a) * sp,
                                r=10, pink=(i in pk), life=400))

    def update(self):
        g = self.g
        p = g.p
        self.t += 1
        self.flash = max(0, self.flash - 1)
        self.hand += 0.03
        if self.ph == 1 and self.hp <= self.maxhp * 0.5:
            self.ph = 2
            self.st = "idle"
            self.tm = 50
            self.beams = []
            self.live = False
            g.shake = 12
            self.ring()
        st = self.st
        if st == "idle":
            self.tm -= 1
            if self.tm <= 0:
                a = self.pick(["ring", "sweep", "gear"] + (["bomb"] if self.ph == 2 else []))
                self.st = a + "_w"
                self.tm = 36
                self.n = 0
                if a == "sweep":
                    self.dr = random.choice((-1, 1))
                    ang = math.atan2(p.y - 30 - self.cy, p.x - self.cx)
                    self.a0 = ang - self.dr * 1.1
                    self.om = 0.034 if self.ph == 1 else 0.040
                    self.live = False
                    self.beams = [self.a0] + ([self.a0 + math.pi] if self.ph == 2 else [])
                    self.tm = 50
        elif st == "ring_w":
            self.tm -= 1
            if self.tm <= 0:
                self.st = "ring"
                self.tm = 0
        elif st == "ring":
            self.tm -= 1
            if self.tm <= 0:
                if self.n >= (2 if self.ph == 1 else 3):
                    self.st = "idle"
                    self.tm = 60
                else:
                    self.ring()
                    self.n += 1
                    self.tm = 44
        elif st == "sweep_w":
            self.tm -= 1
            if self.tm <= 0:
                self.st = "sweep"
                self.el = 0
                self.live = True
                self.tm = 150
        elif st == "sweep":
            self.el += 1
            a = self.a0 + self.dr * self.el * self.om
            self.beams = [a] + ([a + math.pi] if self.ph == 2 else [])
            for b in self.beams:
                d = seg_dist(p.x, p.y - 28, self.cx, self.cy, self.cx + self.L * math.cos(b),
                             self.cy + self.L * math.sin(b))
                if d < 20:
                    g.hurt_player()
            self.tm -= 1
            if self.tm <= 0:
                self.beams = []
                self.live = False
                self.st = "idle"
                self.tm = 60
        elif st == "gear_w":
            self.tm -= 1
            if self.tm <= 0:
                self.st = "gear"
                self.tm = 0
        elif st == "gear":
            self.tm -= 1
            if self.tm <= 0:
                total = 2 if self.ph == 1 else 3
                g.shots.append(Shot("gear", W + 30, GROUND - 28, -5.4 if self.ph == 1 else -6.4, 0,
                                    r=28, g=0.5, pink=(self.n == 1), life=500))
                self.n += 1
                self.tm = 55
                if self.n >= total:
                    self.st = "idle"
                    self.tm = 80
        elif st == "bomb_w":
            self.tm -= 1
            if self.tm <= 0:
                self.st = "bomb"
                self.tm = 0
        elif st == "bomb":
            self.tm -= 1
            if self.tm <= 0:
                x = clamp(p.x + random.uniform(-150, 150), 40, 920)
                g.shots.append(Shot("bomb", x, -24, 0, 2.5, r=17, g=0.22, life=300))
                self.n += 1
                self.tm = 24
                if self.n >= 4:
                    self.st = "idle"
                    self.tm = 75

    def draw(self, g, ox=0):
        p = g.p
        cx = self.cx + ox
        cy = self.cy + math.sin(self.t * 0.05) * 5
        fl = self.flash > 0

        def C(c):
            return "#ffffff" if fl else c
        gold = C("#e8b43a")
        g.ren.ov(cx, GROUND + 5, 90, 9, mix_col(g.gcol, INK, .5), 0, "")
        for d in (-1, 1):
            g.ren.ln([(cx + d * 40, cy + 100), (cx + d * 55, GROUND - 16)], 14, INK)
            g.ren.ln([(cx + d * 40, cy + 100), (cx + d * 55, GROUND - 16)], 8, CREAM)
            g.ren.ov(cx + d * 62, GROUND - 8, 24, 11, "#8a4a22")
        ring_ = math.sin(self.t * 0.9) * 0.2 if self.st.endswith("_w") else 0
        for d in (-1, 1):
            bxp = cx + d * 70
            byp = cy - 100
            g.ren.ln([(cx + d * 40, cy - 90), (bxp, byp)], 8, INK)
            g.ren.ov(bxp + d * ring_ * 30, byp - 8, 28, 20, C("#d9d9e8"))
            g.ren.ov(bxp + d * ring_ * 30, byp - 8, 10, 7, INK, 0, "")
        g.ren.ov(cx, cy, 118, 118, gold, 5)
        g.ren.ov(cx, cy, 96, 96, C(CREAM), 3)
        for i in range(12):
            a = i * math.pi / 6
            g.ren.ln([(cx + math.cos(a) * 80, cy + math.sin(a) * 80),
                      (cx + math.cos(a) * 92, cy + math.sin(a) * 92)], 4, INK)
        for d in (-1, 1):
            ex = cx + d * 30
            ey = cy - 20
            g.ren.ov(ex, ey, 14, 20, INK, 0, "")
            dx = p.x - ex
            dy = (p.y - 30) - ey
            dd = math.hypot(dx, dy) or 1
            g.ren.ov(ex + dx / dd * 4, ey + dy / dd * 6, 6, 8, "#ffffff", 0, "")
            g.ren.ln([(ex - d * 18, ey - 28), (ex + d * 14, ey - 18)], 5, INK)
        g.ren.pl([(cx - 36, cy + 28), (cx, cy + 46), (cx + 36, cy + 28), (cx + 30, cy + 22),
                  (cx, cy + 32), (cx - 30, cy + 22)], INK, 3, True)
        for i in range(-2, 3):
            g.ren.rc(cx + i * 11 - 4, cy + 28, cx + i * 11 + 4, cy + 36, WHITE, 1)
        if not self.beams:
            for ln_, ang, w in ((50, self.hand, 6), (34, self.hand / 12.0, 8)):
                g.ren.ln([(cx, cy), (cx + math.cos(ang) * ln_, cy + math.sin(ang) * ln_)], w, INK)
        for a in self.beams:
            tx = cx + self.L * math.cos(a)
            ty = cy + self.L * math.sin(a)
            if not self.live:
                if (self.t // 4) % 2 == 0:
                    g.ren.ln([(cx, cy), (tx, ty)], 3, RED)
                    g.ren.tx(clamp(cx + 150 * math.cos(a), 30, W - 30),
                             clamp(cy + 150 * math.sin(a), 60, H - 80), "!", 30, RED)
            else:
                nx, ny = -math.sin(a), math.cos(a)
                g.ren.pl([(cx + nx * 12, cy + ny * 12), (tx, ty), (cx - nx * 12, cy - ny * 12)],
                         C(GOLD), 4)
                g.ren.ln([(cx, cy), (cx + (tx - cx) * 0.9, cy + (ty - cy) * 0.9)], 3, WHITE)

# ----------------------------------------------------------------- Levels
LEVELS = [
    dict(name="KURBAĞA KRAL", sub="Bataklıkta Kavga", cls=Frog, theme="swamp",
         sky=("#fbe08a", "#f08f45"), ray="#fff0b0", ground="#6f9a3a", plats=[], par=75, stars=1),
    dict(name="SİHİRBAZ TAVŞAN", sub="Şapkadan Çıkan Bela", cls=Mage, theme="stage",
         sky=("#4b2a7a", "#c25a8a"), ray="#7a4aa8", ground="#8a4a2a",
         plats=[(120, 300, 350), (660, 840, 350)], par=95, stars=2),
    dict(name="ZAMAN EFENDİSİ", sub="Vakit Daralıyor", cls=Clock, theme="tower",
         sky=("#17424a", "#3e8a7a"), ray="#2c6a68", ground="#5a4a3a",
         plats=[(90, 250, 360), (400, 560, 305)], par=120, stars=3),
]
MENU_CFG = dict(theme="menu", sky=("#f7d77a", "#ee9446"), ray="#ffe9a0", ground="#7b4d2b", plats=[])
GRADE_RANK = {"": 0, "D": 1, "C": 2, "B": 3, "A": 4, "S": 5}

HOWTO = [
    "Her bölümde dev bir boss ile savaşırsın. Dikkatli ol, canın sınırlı!",
    "",
    "DOKUNMATİK KONTROLLER (Ekranda):",
    "Sol D-Pad / Butonlar : Sola, Sağa koş ve Yukarı nişan al",
    "[A] Zıpla / PARRY     [B] Ateş (Basılı tut)",
    "[DASH] Hızlı Atılma    [EX] Güçlü Özel Atış (1 Kart)",
    "",
    "KLAVYE DESTEĞİ:",
    "A/D veya Sol/Sağ: Koş   |   Space / Z: Zıpla",
    "X / J: Ateş             |   Shift / C: Dash    |   Q / E: EX",
    "",
    "PARRY: Havadayken PEMBE bir nesneye tekrar zıpla!",
    "Her parry sana 1 EX kartı kazandırır.",
    "Hızlı bitir, az hasar al, çok parry yap = daha yüksek not!",
]

# ----------------------------------------------------------------- Main Game Engine
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("ÇAYCIK: Boss Savaşı (Mobile)")

        # Fullscreen / Scaled Display Setup
        self.logical_surf = pygame.Surface((W, H))
        self.ren = Renderer(self.logical_surf)
        self.screen = pygame.display.set_mode((W, H), pygame.RESIZABLE | pygame.SCALED)
        self.clock = pygame.time.Clock()

        self.save = self.load()
        self.settings = self.save["settings"]
        self.sfx = SfxEngine()
        self.sfx.on = bool(self.settings.get("sound", True))

        # Touch Controls definition
        self.touches = {} # touch_id -> (lx, ly)
        self.active_buttons = set()
        self.buttons_layout = {
            # D-pad Left side
            "left": pygame.Rect(40, H - 110, 65, 65),
            "right": pygame.Rect(125, H - 110, 65, 65),
            "up": pygame.Rect(82, H - 185, 65, 65),
            # Actions Right side
            "jump": pygame.Rect(W - 105, H - 95, 75, 75),
            "shoot": pygame.Rect(W - 195, H - 95, 75, 75),
            "dash": pygame.Rect(W - 105, H - 185, 70, 70),
            "ex": pygame.Rect(W - 195, H - 185, 70, 70),
            # Top menu buttons
            "pause": pygame.Rect(W - 60, 15, 45, 45),
        }

        self.keyboard_keys = set()
        self.pressed_actions = set()

        self.state = "menu"
        self.sel = 0
        self.lsel = 0
        self.psel = 0
        self.dsel = 0
        self.t = 0
        self.iris = None
        self.iris_c = (W / 2, H / 2)
        self.p = Player()
        self.boss = None
        self.shots, self.bul, self.parts, self.pops = [], [], [], []
        self.plats = []
        self.cfg = MENU_CFG
        self.gcol = MENU_CFG["ground"]
        self.intro = 0
        self.ko = 0
        self.ft = 0
        self.shake = 0
        self.hitstop = 0
        self.dying = 0
        self.lv = 0
        self.rt = 0
        self.res = {}
        self.quit = False
        self.bacc = 0.0
        self.dif = DIFF[1]
        self.msg = ""
        self.msgt = 0
        self.touch_active = False

    def load(self):
        d = {}
        try:
            if os.path.exists(SAVE_PATH):
                with open(SAVE_PATH, "r", encoding="utf-8") as f:
                    d = json.load(f)
        except Exception:
            d = {}
        d.setdefault("unlocked", 1)
        d.setdefault("grades", {})
        d.setdefault("times", {})
        d.setdefault("settings", {"diff": [1, 1, 1], "sound": True, "grain": True, "shake": True})
        return d

    def store(self):
        try:
            with open(SAVE_PATH, "w", encoding="utf-8") as f:
                json.dump(self.save, f)
        except Exception:
            pass

    def act(self, name):
        if name in self.active_buttons:
            return True
        keymap = {
            "left": (pygame.K_LEFT, pygame.K_a),
            "right": (pygame.K_RIGHT, pygame.K_d),
            "up": (pygame.K_UP, pygame.K_w),
            "down": (pygame.K_DOWN, pygame.K_s),
            "jump": (pygame.K_SPACE, pygame.K_z, pygame.K_k),
            "shoot": (pygame.K_x, pygame.K_j),
            "dash": (pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_c, pygame.K_l),
            "ex": (pygame.K_q, pygame.K_e, pygame.K_v),
            "return": (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z),
            "escape": (pygame.K_ESCAPE,),
        }
        for k in keymap.get(name, ()):
            if k in self.keyboard_keys:
                return True
        return False

    def actp(self, name):
        return name in self.pressed_actions

    def shooting(self):
        return self.act("shoot")

    def ex_pressed(self):
        return self.actp("ex")

    def trigger_action(self, action_name):
        self.pressed_actions.add(action_name)

    # ------------------------------------------------------------- Transitions
    def go(self, cb, center=None):
        if self.iris is None:
            self.iris = [0, 0, cb]
            self.iris_c = center or (W / 2, H / 2)

    def set_state(self, st):
        self.state = st
        if st == "menu":
            self.sel = 0
        self.rt = 0

    def start_level(self, i):
        self.lv = i
        self.cfg = LEVELS[i]
        self.p = Player()
        self.boss = self.cfg["cls"](self)
        self.dif = DIFF[clamp(self.settings["diff"][i], 0, 2)]
        self.p.hp = self.p.maxhp = self.dif["hp"]
        self.boss.maxhp = int(self.boss.maxhp * self.dif["bhp"])
        self.boss.hp = self.boss.maxhp
        self.bacc = 0.0
        self.shots, self.bul, self.parts, self.pops = [], [], [], []
        self.plats = self.cfg["plats"]
        self.gcol = self.cfg["ground"]
        self.intro = 130
        self.ft = 0
        self.ko = 0
        self.shake = 0
        self.hitstop = 0
        self.dying = 0
        self.state = "fight"
        self.sfx.play("go")

    def to_menu(self):
        self.state = "menu"
        self.sel = 0
        self.p = Player()
        self.plats = []
        self.shots, self.bul, self.parts, self.pops = [], [], [], []

    # ------------------------------------------------------------- Effects
    def dust(self, x, y, n=5):
        for _ in range(n):
            self.parts.append([x + random.uniform(-8, 8), y - 2, random.uniform(-1.5, 1.5),
                               random.uniform(-1.2, -0.2), 18, 18, "#efe3c4", random.uniform(4, 7), 2])

    def burst(self, x, y, col, n=12, sp=5.0):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(1, sp)
            self.parts.append([x, y, math.cos(a) * v, math.sin(a) * v - 1, random.randint(16, 32),
                               32, col, random.uniform(3, 6), random.choice((0, 0, 1))])

    def pop(self, x, y, text, col):
        self.pops.append([x, y, text, 45, col])

    def bomb_boom(self, sh):
        self.burst(sh.x, GROUND - 10, "#ffb347", 18, 6)
        self.shake = 6
        for d in (-1, 1):
            self.shots.append(Shot("wave", sh.x + d * 20, GROUND - 2, d * 5.5, 0, r=12, hh=24, life=200))

    def try_parry(self):
        p = self.p
        for sh in self.shots:
            if sh.pink and not sh.dead and math.hypot(sh.x - p.x, sh.y - (p.y - 30)) < sh.r + 38:
                sh.dead = True
                p.card = min(5.0, p.card + 1)
                p.parries += 1
                p.vy = -13.0
                p.jh = False
                self.hitstop = 5
                self.burst(sh.x, sh.y, PINK, 18, 6)
                self.pop(p.x, p.y - 70, "PARRY!", PINK)
                self.sfx.play("parry")
                return

    def hurt_player(self):
        p = self.p
        if p.inv > 0 or p.dash > 0 or p.hp <= 0 or self.ko > 0 or self.intro > 30:
            return False
        p.hp -= 1
        p.inv = 110
        p.hurt = 26
        p.vy = -9.0
        p.vx = -p.face * 4.0
        p.on = False
        self.shake = 14
        self.hitstop = 6
        self.burst(p.x, p.y - 30, "#ffffff", 16, 6)
        self.sfx.play("hurt")
        if p.hp <= 0:
            self.dying = 1
            self.pop(p.x, p.y - 80, "ÖLDÜN!", RED)
        return True

    # ------------------------------------------------------------- Update
    def update(self):
        self.t += 1
        if self.msgt > 0:
            self.msgt -= 1
        if self.iris:
            it = self.iris
            it[1] += 1
            if it[0] == 0 and it[1] >= 22:
                it[2]()
                it[0] = 1
                it[1] = 0
            elif it[0] == 1 and it[1] >= 22:
                self.iris = None
            self.pressed_actions.clear()
            return

        st = self.state
        if st == "menu":
            self.upd_menu()
        elif st == "select":
            self.upd_select()
        elif st == "howto":
            if self.actp("return") or self.actp("escape") or self.actp("jump"):
                self.sfx.play("blip")
                self.go(lambda: self.set_state("menu"))
        elif st == "fight":
            self.upd_fight()
        elif st == "pause":
            self.upd_pause()
        elif st == "result":
            self.rt += 1
            if self.rt > 80 and (self.actp("return") or self.actp("jump") or self.actp("shoot")):
                self.sfx.play("ok")
                self.go(self.after_result)
        elif st == "dead":
            self.rt += 1
            if self.actp("up") or self.actp("down"):
                self.dsel = 1 - self.dsel
                self.sfx.play("blip")
            if self.rt > 20 and (self.actp("return") or self.actp("jump")):
                self.sfx.play("ok")
                if self.dsel == 0:
                    self.go(lambda: self.start_level(self.lv))
                else:
                    self.go(self.to_menu)
        elif st == "ending":
            self.rt += 1
            if self.rt % 4 == 0:
                self.parts.append([random.uniform(0, W), -10, random.uniform(-1, 1), random.uniform(1, 3),
                                   200, 200, random.choice((GOLD, PINK, parse_hex("#7ad0ff"), RED, parse_hex("#9be36b"))),
                                   random.uniform(4, 8), 3])
            self.upd_parts()
            if self.rt > 90 and (self.actp("return") or self.actp("jump")):
                self.go(self.to_menu)

        self.pressed_actions.clear()

    def upd_menu(self):
        n = 4 # Başla, Bölüm Seç, Nasıl Oynanır, Çıkış
        if self.actp("up"):
            self.sel = (self.sel - 1) % n
            self.sfx.play("blip")
        if self.actp("down"):
            self.sel = (self.sel + 1) % n
            self.sfx.play("blip")
        if self.actp("return") or self.actp("jump"):
            self.sfx.play("ok")
            if self.sel == 0:
                i = min(self.save["unlocked"], len(LEVELS)) - 1
                self.go(lambda: self.start_level(i))
            elif self.sel == 1:
                self.go(lambda: self.set_state("select"))
            elif self.sel == 2:
                self.go(lambda: self.set_state("howto"))
            else:
                self.quit = True

    def upd_select(self):
        n = len(LEVELS)
        if self.actp("left"):
            self.lsel = (self.lsel - 1) % n
            self.sfx.play("blip")
        if self.actp("right"):
            self.lsel = (self.lsel + 1) % n
            self.sfx.play("blip")
        if self.actp("up") or self.actp("down"):
            dd = self.settings["diff"]
            dd[self.lsel] = (dd[self.lsel] + (1 if self.actp("down") else -1)) % 3
            self.store()
            self.sfx.play("blip")
        if self.actp("escape"):
            self.go(lambda: self.set_state("menu"))
        elif self.actp("return") or self.actp("jump"):
            if self.lsel < self.save["unlocked"]:
                self.sfx.play("ok")
                i = self.lsel
                self.go(lambda: self.start_level(i))
            else:
                self.sfx.play("hurt")

    def upd_pause(self):
        if self.actp("up") or self.actp("down"):
            self.psel = (self.psel + (1 if self.actp("down") else -1)) % 3
            self.sfx.play("blip")
        if self.actp("escape") or self.actp("pause"):
            self.state = "fight"
        elif self.actp("return") or self.actp("jump"):
            if self.psel == 0:
                self.state = "fight"
            elif self.psel == 1:
                self.go(lambda: self.start_level(self.lv))
            else:
                self.go(self.to_menu)

    def upd_parts(self):
        for q in self.parts:
            q[0] += q[2]
            q[1] += q[3]
            if q[8] in (0, 1, 3):
                q[3] += 0.22
            else:
                q[2] *= 0.92
                q[3] *= 0.92
            q[4] -= 1
        self.parts = [q for q in self.parts if q[4] > 0]
        for q in self.pops:
            q[1] -= 0.8
            q[3] -= 1
        self.pops = [q for q in self.pops if q[3] > 0]

    def upd_fight(self):
        if self.actp("escape") or self.actp("pause"):
            self.state = "pause"
            self.psel = 0
            return
        if self.hitstop > 0:
            self.hitstop -= 1
            return
        if 0 < self.ko < 70 and self.t % 2 == 0:
            return
        if self.shake > 0:
            self.shake -= 1
        p = self.p
        if self.intro > 0:
            self.intro -= 1
        b = self.boss
        p.update(self)
        if self.intro <= 30 and not b.dead:
            n0 = len(self.shots)
            self.bacc += self.dif["bt"]
            while self.bacc >= 1 and not b.dead:
                self.bacc -= 1
                b.update()
            sm = self.dif["shot"]
            if sm != 1:
                for sh in self.shots[n0:]:
                    sh.vx *= sm
                    sh.vy *= sm
                    sh.sp *= sm
            if p.hp > 0:
                self.ft += 1
        for sh in self.shots:
            sh.update(self)
            if not sh.dead and hits_player(sh, p):
                if self.hurt_player() and sh.kind not in ("wave", "gear"):
                    sh.dead = True
        self.shots = [x for x in self.shots if not x.dead]
        for bl in self.bul:
            bl.x += bl.vx
            bl.y += bl.vy
            bl.age += 1
            if bl.x < -40 or bl.x > W + 40 or bl.y < -40 or bl.y > H + 40:
                bl.dead = True
                continue
            if self.intro > 30 or b.dead:
                continue
            for sh in self.shots:
                if sh.hp > 0 and not bl.dead and not sh.dead and \
                        math.hypot(sh.x - bl.x, sh.y - bl.y) < sh.r + bl.r:
                    if not bl.ex:
                        bl.dead = True
                    sh.hp -= 3 if bl.ex else 1
                    sh.flash = 3
                    self.burst(bl.x, bl.y, "#fff2b0", 3, 3)
                    if sh.hp <= 0:
                        sh.dead = True
                        self.burst(sh.x, sh.y, "#ff9a3c", 14, 5)
            if bl.dead:
                continue
            for (x1, y1, x2, y2) in b.boxes():
                if x1 - bl.r <= bl.x <= x2 + bl.r and y1 - bl.r <= bl.y <= y2 + bl.r:
                    if bl.ex:
                        if not bl.hit:
                            bl.hit = True
                            b.hurt(12)
                            self.burst(bl.x, bl.y, GOLD, 16, 6)
                            self.shake = 5
                    else:
                        bl.dead = True
                        b.hurt(1)
                        p.card = min(5.0, p.card + 0.035)
                        self.burst(bl.x, bl.y, "#fff2b0", 3, 3)
                    break
        self.bul = [x for x in self.bul if not x.dead]
        self.upd_parts()
        if b.hp <= 0 and self.ko == 0 and p.hp > 0:
            self.ko = 1
            b.dead = True
            self.shots = []
            self.shake = 16
            self.sfx.play("ko")
        if self.ko > 0:
            self.ko += 1
            if self.ko % 4 == 0:
                bx = b.boxes()[0] if b.boxes() else (600, 100, 800, 300)
                self.burst(random.uniform(bx[0], bx[2]), random.uniform(bx[1], bx[3]),
                           random.choice((GOLD, RED, "#ffffff")), 10, 6)
            if self.ko == 165:
                self.go(self.show_result, (p.x, p.y - 30))
        if self.dying > 0:
            self.dying += 1
            if self.dying == 110:
                self.go(self.show_dead, (p.x, p.y - 30))

    def show_result(self):
        p = self.p
        t = self.ft / 60.0
        par = LEVELS[self.lv]["par"]
        score = 100 - max(0, t - par) * 0.6 - (1 - p.hp / float(p.maxhp)) * 36 + min(p.parries, 6) * 3
        score = score + self.dif.get("bonus", 0)
        score = clamp(score, 0, self.dif.get("cap", 100))
        g = "S" if score >= 92 else "A" if score >= 80 else "B" if score >= 68 else \
            "C" if score >= 52 else "D"
        self.res = dict(time=t, hp=p.hp, maxhp=p.maxhp, parries=p.parries, grade=g, diff=self.dif["name"])
        self.save["unlocked"] = max(self.save["unlocked"], min(len(LEVELS), self.lv + 2))
        k = str(self.lv)
        if GRADE_RANK[g] > GRADE_RANK.get(self.save["grades"].get(k, ""), 0):
            self.save["grades"][k] = g
        bt = self.save["times"].get(k)
        if bt is None or t < bt:
            self.save["times"][k] = round(t, 1)
        self.store()
        self.state = "result"
        self.rt = 0
        self.parts = []

    def show_dead(self):
        self.state = "dead"
        self.rt = 0
        self.dsel = 0
        self.parts = []

    def after_result(self):
        if self.lv + 1 < len(LEVELS):
            self.start_level(self.lv + 1)
        else:
            self.state = "ending"
            self.rt = 0
            self.parts = []

    # ------------------------------------------------------------- Drawing Helpers
    def floor_y(self, p):
        base = GROUND
        for (x1, x2, y) in self.plats:
            if x1 - 8 <= p.x <= x2 + 8 and p.y <= y + 2:
                base = min(base, y)
        return base

    def rays(self, cx, cy, col, n=18, spd=0.004):
        R = 1300
        for i in range(n):
            a = i * math.tau / n + self.t * spd
            b = a + math.pi / n
            pts = [(cx, cy),
                   (cx + R * math.cos(a), cy + R * math.sin(a)),
                   (cx + R * math.cos(b), cy + R * math.sin(b))]
            self.ren.pl(pts, col, 0, False, "")

    def draw_bg(self, cfg):
        top, bot = cfg["sky"]
        bands = 32
        for i in range(bands):
            y1 = int(-40 + i * (H + 80) / bands)
            y2 = int(-40 + (i + 1) * (H + 80) / bands + 2)
            c = mix_col(top, bot, i / (bands - 1.0))
            self.ren.rc(-40, y1, W + 40, y2, c, 0, "")
        th = cfg["theme"]
        if th == "swamp":
            for cx, r, col in ((140, 220, "#8dbb50"), (520, 290, "#7aa944"), (900, 240, "#8dbb50")):
                self.ren.ov(cx, GROUND + 80, r, r, col, 3, INK)
            for x, h in ((60, 300), (905, 340), (430, 170)):
                self.ren.rc(x - 14, GROUND - h, x + 14, GROUND, "#6b4a2a", 3, INK)
                for dx, dy, r in ((-40, 0, 62), (36, -10, 66), (0, -46, 72)):
                    self.ren.ov(x + dx, GROUND - h + dy, r, r, "#4e8a35", 3, INK)
        elif th == "stage":
            for x0 in (250, 480, 710):
                self.ren.pl([(x0, -10), (x0 + 60, -10), (x0 + 200, GROUND), (x0 - 200, GROUND)],
                            "#c98ab0", 0, False, "")
            for i in range(24):
                sx = (i * 137) % W
                sy = (i * 71) % 260 + 30
                self.ren.pl(star_pts(sx, sy, 7, 3, 4, 0.3), "#ffe9a0", 0, False, "")
        elif th == "tower":
            for cx, cy, r, n in ((130, 150, 150, 12), (860, 420, 190, 14), (480, 90, 100, 10)):
                pts = star_pts(cx, cy, r, r * 0.82, n, 0.2)
                self.ren.pl(pts, "#2b6a66", 3, False, INK)
                self.ren.ov(cx, cy, r * .55, r * .55, "#3c8a82", 3, INK)
        else: # menu
            for cx, r, col in ((100, 260, "#e08a3a"), (520, 330, "#d27a2f"), (940, 280, "#e08a3a")):
                self.ren.ov(cx, GROUND + 90, r, r, col, 3, INK)

        # Ground
        gc = cfg["ground"]
        self.ren.rc(-40, GROUND, W + 40, H + 40, gc, 0, "")
        for i in range(-1, 14):
            if i % 2 == 0:
                self.ren.pl([(i * 80, GROUND), (i * 80 + 80, GROUND), (i * 80 + 110, H + 40), (i * 80 - 30, H + 40)],
                            mix_col(gc, "#ffffff", 0.12), 0, False, "")
        self.ren.ln([(-40, GROUND), (W + 40, GROUND)], 5, INK)
        self.ren.rc(-40, GROUND + 5, W + 40, GROUND + 14, mix_col(gc, "#ffffff", 0.3), 0, "")

        # Platforms
        for (x1, x2, y) in cfg.get("plats", []):
            self.ren.rc(x1 + 8, y + 16, x2 - 8, y + 30, mix_col(INK, "#8a5a2a", .5), 3, INK)
            self.ren.rc(x1, y, x2, y + 18, "#c98a45", 4, INK)
            self.ren.ln([(x1 + 6, y + 5), (x2 - 6, y + 5)], 3, "#e9b678")

    def draw_shot(self, sh):
        k = sh.kind
        x, y, r = sh.x, sh.y, sh.r
        pk = sh.pink
        col = PINK if pk else "#ff5a2c"
        core = "#ffffff" if pk else "#ffe9a8"
        if sh.flash > 0:
            col = "#ffffff"
        if k == "ball":
            pu = 1 + 0.12 * math.sin(self.t * 0.4) if pk else 1
            self.ren.ov(x, y, r * pu, r * pu, col)
            self.ren.ov(x, y, r * 0.5, r * 0.5, core, 0, "")
        elif k == "fly":
            wg = abs(math.sin(self.t * 0.5)) * 8 + 4
            wc = PINK if pk else "#ffffff"
            self.ren.ov(x - 9, y - 7, 8, wg, wc, 2)
            self.ren.ov(x + 9, y - 7, 8, wg, wc, 2)
            self.ren.ov(x, y, 8, 11, INK)
            self.ren.ov(x - 3, y - 3, 2, 2, RED, 0, "")
            self.ren.ov(x + 3, y - 3, 2, 2, RED, 0, "")
        elif k == "card":
            a = sh.spin
            pts = []
            for dx, dy in ((-9, -13), (9, -13), (9, 13), (-9, 13)):
                pts.append((x + dx * math.cos(a) - dy * math.sin(a), y + dx * math.sin(a) + dy * math.cos(a)))
            self.ren.pl(pts, PINK if pk else WHITE)
            self.ren.ov(x, y, 4, 4, "#ffffff" if pk else RED, 0, "")
        elif k == "carrot":
            a = sh.ang
            nx, ny = -math.sin(a), math.cos(a)
            tip = (x + math.cos(a) * 22, y + math.sin(a) * 22)
            bk = (x - math.cos(a) * 14, y - math.sin(a) * 14)
            for sgn in (-1, 1):
                self.ren.ln([bk, (bk[0] - math.cos(a) * 14 + nx * sgn * 8, bk[1] - math.sin(a) * 14 + ny * sgn * 8)],
                            5, "#4fa83a")
            c1 = PINK if pk else "#ff8c1a"
            if sh.flash > 0:
                c1 = "#ffffff"
            self.ren.pl([tip, (bk[0] + nx * 10, bk[1] + ny * 10), (bk[0] - nx * 10, bk[1] - ny * 10)], c1)
        elif k == "star":
            self.ren.pl(star_pts(x, y, r, r * 0.45, 5, sh.spin), PINK if pk else GOLD)
        elif k == "wave":
            hh = sh.hh
            self.ren.ov(x, GROUND - hh * 0.5, sh.r, hh * 0.5, "#fff3b0")
            self.ren.ov(x, GROUND - hh * 0.4, sh.r * 0.5, hh * 0.28, "#ffffff", 0, "")
        elif k == "gear":
            self.ren.pl(star_pts(x, y, r, r * 0.78, 8, sh.spin), PINK if pk else "#d8a02a")
            self.ren.ov(x, y, r * 0.55, r * 0.55, "#fff0c0" if pk else "#f2c85c", 3)
            self.ren.ov(x, y, r * 0.2, r * 0.2, INK, 0, "")
        elif k == "bomb":
            self.ren.ov(x, y, r, r, "#2b2b33")
            self.ren.ov(x - 5, y - 5, 4, 4, "#8a8a99", 0, "")
            self.ren.ln([(x + 4, y - r + 2), (x + 10, y - r - 8)], 3, "#a06a2a")
            self.ren.ov(x + 11, y - r - 10, 4, 4, "#ffd23a", 0, "")

    def draw_player(self, p, ox=0, ghost=False):
        f = p.face
        x = p.x + ox
        y = p.y
        if ghost:
            gy = y - self.dying * 1.4
            self.ren.ov(x, gy - 78, 17, 6, GOLD, 3)
            self.ren.pl([(x - 13, gy - 60), (x + 13, gy - 60), (x + 15, gy - 51), (x + 12, gy - 39), (x + 7, gy - 31),
                         (x - 7, gy - 31), (x - 12, gy - 39), (x - 15, gy - 51)], "#e6f6fa", 3, True)
            self.ren.ov(x - 5, gy - 50, 3, 5, INK, 0, "")
            self.ren.ov(x + 5, gy - 50, 3, 5, INK, 0, "")
            for d in (-1, 1):
                self.ren.ov(x + d * 24, gy - 42, 10, 16, WHITE, 3)
            return
        if p.inv > 0 and (self.t // 3) % 2:
            return
        base = self.floor_y(p)
        self.ren.ov(x, base + 3, 18, 5, mix_col(self.gcol, INK, .5), 0, "")
        if p.dash > 0:
            for i in range(3):
                self.ren.ov(x - f * (14 + i * 18), y - 30, 18 - i * 4, 10 - i * 2, mix_col(WHITE, self.gcol, i * .25), 2)
            self.ren.ov(x, y - 30, 24, 15, "#f4fbff")
            self.ren.ov(x + f * 6, y - 32, 5, 7, INK, 0, "")
            self.ren.ov(x + f * 8, y - 31, 7, 5, RED, 0, "")
            return
        run = p.on and abs(p.vx) > 1.2
        ph = self.t * 0.38
        bob = abs(math.sin(ph)) * 3 if run else (math.sin(self.t * 0.1) * 1.5 if p.on else 0)
        hipy = y - 24 - bob
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
            self.ren.limb((x, hipy), ft, 4 * f)
            self.ren.ov(ft[0] + f * 4, ft[1] - 1, 9, 5, "#7a3a18")
        self.ren.ov(x, hipy - 2, 11, 9, RED)
        self.ren.ov(x, hipy - 14, 8, 10, CREAM)
        sh_y = hipy - 18
        ax, ay = p.aimvec(self) if self.state == "fight" else (f, 0)
        is_shoot = self.state == "fight" and self.shooting() and self.intro <= 60
        if is_shoot or p.mz > 0:
            hand = (x + ax * 22, sh_y + 4 + ay * 20)
        else:
            hand = (x + f * 12, sh_y + 12 + math.sin(self.t * 0.2) * 2)
        self.ren.limb((x, sh_y), hand, 3)
        self.ren.ov(hand[0], hand[1], 6, 6, WHITE)
        h2 = (x - f * 12 + (math.sin(ph) * 8 if run else 0), sh_y + 14)
        self.ren.limb((x, sh_y), h2, -3)
        self.ren.ov(h2[0], h2[1], 6, 6, WHITE)
        hx_, hy_ = x + f * 2, hipy - 38
        if not p.on:
            hy_ -= 2
        self.ren.ln([(hx_ - 4, hy_ + 2), (hx_ - 10, hy_ - 22)], 7, INK)
        self.ren.ln([(hx_ - 4, hy_ + 2), (hx_ - 10, hy_ - 22)], 3, RED)
        glass = [(hx_ - 13, hy_ - 15), (hx_ + 13, hy_ - 15), (hx_ + 15, hy_ - 6), (hx_ + 12, hy_ + 6),
                 (hx_ + 7, hy_ + 14), (hx_ - 7, hy_ + 14), (hx_ - 12, hy_ + 6), (hx_ - 15, hy_ - 6)]
        self.ren.pl(glass, "#e6f6fa", 0, True, "")
        self.ren.pl([(hx_ - 14, hy_ - 4), (hx_ + 14, hy_ - 4), (hx_ + 12, hy_ + 6), (hx_ + 7, hy_ + 14),
                     (hx_ - 7, hy_ + 14), (hx_ - 12, hy_ + 6)], "#c4501a", 0, True, "")
        self.ren.pl(glass, "", 3, True)
        self.ren.ln([(hx_ - 11, hy_ - 12), (hx_ + 11, hy_ - 12)], 2, "#ffffff")
        for d in (-4, 6):
            self.ren.ov(hx_ + d + f * 2, hy_ - 1, 3, 5, INK, 0, "")
            self.ren.ov(hx_ + d + f * 2 + 1, hy_ - 3, 1, 1, "#ffffff", 0, "")
        if p.mz > 0 or p.hurt > 0:
            self.ren.ov(hx_ + f * 5, hy_ + 7, 3, 3, INK, 0, "")
        else:
            self.ren.ln([(hx_ + f * 2 - 2, hy_ + 7), (hx_ + f * 2 + 3, hy_ + 7)], 2, INK)
        if p.mz > 0:
            mx = hand[0] + ax * 14
            my = hand[1] + ay * 14
            self.ren.pl(star_pts(mx, my, 10, 4, 4, self.t), GOLD, 2)

    def draw_hud(self):
        p = self.p
        b = self.boss
        self.ren.panel(14, H - 58, 96, H - 16)
        col = RED if (p.hp <= 1 and (self.t // 10) % 2 == 0) else INK
        self.ren.tx(55, H - 37, "HP %d" % max(0, p.hp), 20, col, ow=0)
        for i in range(5):
            x = 112 + i * 27
            fr = clamp(p.card - i, 0, 1)
            self.ren.rc(x, H - 58, x + 21, H - 16, WHITE, 3)
            if fr > 0:
                self.ren.rc(x + 2, H - 16 - 2 - fr * 38, x + 19, H - 18, GOLD if fr < 1 else "#ffd95a", 0, "")
                if fr >= 1:
                    self.ren.pl(star_pts(x + 10.5, H - 37, 7, 3, 4, self.t * 0.05), INK, 1)
            self.ren.rc(x, H - 58, x + 21, H - 16, "", 3)
        bw = 440
        x0 = W / 2 - bw / 2
        self.ren.rc(x0 - 3, 20, x0 + bw + 3, 40, INK, 0, "")
        frac = clamp(b.hp / b.maxhp, 0, 1)
        self.ren.rc(x0, 23, x0 + bw, 37, "#5a2a1a", 0, "")
        if frac > 0:
            self.ren.rc(x0, 23, x0 + bw * frac, 37, RED if b.ph == 1 else "#ff7a2c", 0, "")
        self.ren.rc(x0 - 3, 20, x0 + bw + 3, 40, "", 3, CREAM)
        self.ren.tx(W / 2, 55, b.name, 14, CREAM, ow=2)

    def draw_touch_controls(self):
        # Draw on-screen virtual buttons for mobile
        alpha_surf = pygame.Surface((W, H), pygame.SRCALPHA)
        for name, rect in self.buttons_layout.items():
            if name == "pause" and self.state != "fight":
                continue
            is_active = name in self.active_buttons
            bg_col = (242, 182, 50, 170) if is_active else (27, 18, 9, 110)
            border_col = (255, 250, 240, 220) if is_active else (247, 232, 192, 160)

            pygame.draw.ellipse(alpha_surf, bg_col, rect)
            pygame.draw.ellipse(alpha_surf, border_col, rect, 3)

            labels = {
                "left": "◀", "right": "▶", "up": "▲",
                "jump": "A", "shoot": "B", "dash": "DASH", "ex": "EX",
                "pause": "❚❚"
            }
            lbl = labels.get(name, "")
            font = self.ren.get_font(18 if len(lbl) <= 2 else 12)
            t_surf = font.render(lbl, True, (255, 255, 255) if is_active else (247, 232, 192))
            t_rect = t_surf.get_rect(center=rect.center)
            alpha_surf.blit(t_surf, t_rect)

        self.logical_surf.blit(alpha_surf, (0, 0))

    def draw_banners(self):
        if self.ko > 0 and self.ko < 150:
            k = min(1.0, self.ko / 14.0)
            self.ren.tx(W / 2, H / 2 - 40, "K.O.!", int(40 + 90 * k), GOLD, ow=4)
        elif self.intro > 0:
            if self.intro > 60:
                yy = H / 2 - 30 - max(0, self.intro - 110) * 8
                self.ren.tx(W / 2, yy, "HAZIR MISIN?", 56, CREAM, ow=4)
            else:
                self.ren.tx(W / 2, H / 2 - 30, "DÖVÜŞ!", 90 - int((60 - self.intro) * 0.5), GOLD, ow=4)

    def draw(self):
        st = self.state
        if st in ("fight", "pause"):
            self.draw_bg(self.cfg)
            self.rays(W * 0.75, 200, self.cfg["ray"], 16, 0.003)
            ox = (self.intro - 40) * 9 if self.intro > 40 else 0
            bshake = random.randint(-4, 4) if (0 < self.ko < 150) else 0
            self.boss.draw(self, ox + bshake)
            for sh in self.shots:
                self.draw_shot(sh)
            self.draw_player(self.p, 0, ghost=self.p.hp <= 0)
            for bl in self.bul:
                if bl.ex:
                    self.ren.ov(bl.x, bl.y, 20, 16, GOLD, 3)
                    self.ren.ov(bl.x, bl.y, 10, 8, "#ffffff", 0, "")
                    self.ren.pl(star_pts(bl.x, bl.y, 26, 12, 6, self.t * 0.3), "", 2, False, GOLD)
                else:
                    self.ren.ov(bl.x, bl.y, 7, 5, WHITE, 2)
            # Parts & Particles
            for q in self.parts:
                px, py, vx, vy, l, ml, col, sz, k = q
                r = max(0.6, sz * l / ml)
                if k == 0:
                    self.ren.ov(px, py, r, r, col, 2)
                elif k == 1:
                    self.ren.pl(star_pts(px, py, r * 1.8, r * 0.7, 4, l * 0.2), col, 2)
                elif k == 2:
                    self.ren.ov(px, py, r * 1.5, r * 1.1, col, 0, "")
                else:
                    self.ren.rc(px - r, py - r * 0.6, px + r, py + r * 0.6, col, 1)
            for px, py, text, l, col in self.pops:
                self.ren.tx(px, py, text, 20, col)
            self.draw_hud()
            self.draw_banners()
            if self.state == "pause":
                self.ren.panel(300, 120, 660, 420)
                self.ren.tx(480, 165, "DURAKLATILDI", 26, INK, ow=0)
                for i, lab in enumerate(("DEVAM", "YENİDEN BAŞLA", "ANA MENÜ")):
                    y = 235 + i * 54
                    if i == self.psel:
                        self.ren.rc(330, y - 20, 630, y + 20, GOLD, 3)
                    self.ren.tx(480, y, lab, 20, INK, ow=0)
        elif st == "menu":
            self.draw_bg(MENU_CFG)
            self.rays(W / 2, 300, MENU_CFG["ray"])
            self.p.face = 1
            self.draw_player(self.p)
            bob = math.sin(self.t * 0.06) * 5
            self.ren.tx(W / 2 + 5, 98 + bob + 5, "ÇAYCIK", 84, RED, ow=0, out=INK)
            self.ren.tx(W / 2, 98 + bob, "ÇAYCIK", 84, CREAM, ow=4)
            self.ren.pl([(W / 2 - 150, 150), (W / 2 + 150, 150), (W / 2 + 170, 172), (W / 2 + 150, 194),
                         (W / 2 - 150, 194), (W / 2 - 170, 172)], GOLD, 4)
            self.ren.tx(W / 2, 172, "BOSS SAVAŞI", 22, INK, ow=0)
            for i, lab in enumerate(("BAŞLA", "BÖLÜM SEÇ", "NASIL OYNANIR", "ÇIKIŞ")):
                y = 246 + i * 50
                if i == self.sel:
                    self.ren.rc(W / 2 - 150, y - 22, W / 2 + 150, y + 22, GOLD, 4)
                    self.ren.pl([(W / 2 - 135, y - 10), (W / 2 - 120, y), (W / 2 - 135, y + 10)], INK, 1)
                    self.ren.tx(W / 2, y, lab, 22, INK, ow=0)
                else:
                    self.ren.tx(W / 2, y, lab, 22, CREAM, ow=3)
        elif st == "select":
            self.draw_bg(MENU_CFG)
            self.ren.tx(W / 2, 52, "BÖLÜM SEÇ", 36, CREAM, ow=4)
            for i, lv in enumerate(LEVELS):
                x1 = 50 + i * 290
                y1 = 100 + (-14 if i == self.lsel else 0)
                x2, y2 = x1 + 260, y1 + 360
                lock = i >= self.save["unlocked"]
                self.ren.panel(x1, y1, x2, y2, "#8a8372" if lock else CREAM)
                if i == self.lsel:
                    self.ren.rc(x1 - 6, y1 - 6, x2 + 6, y2 + 6, "", 5, GOLD)
                top, bot = lv["sky"]
                for k in range(8):
                    self.ren.rc(x1 + 16, y1 + 16 + k * 14, x2 - 16, y1 + 30 + k * 14, mix_col(top, bot, k / 7.0), 0, "")
                cx = (x1 + x2) / 2
                if lock:
                    self.ren.rc(cx - 22, y1 + 66, cx + 22, y1 + 108, "#555555", 3)
                    self.ren.tx(cx, y1 + 170, "KİLİTLİ", 22, INK, ow=0)
                else:
                    self.ren.tx(cx, y1 + 72, str(i + 1), 64, CREAM, ow=4)
                    self.ren.tx(cx, y1 + 160, lv["name"], 18, INK, ow=0)
                    self.ren.tx(cx, y1 + 188, lv["sub"], 13, RED, ow=0)
                    self.ren.tx(cx, y1 + 222, "★" * lv["stars"] + "☆" * (3 - lv["stars"]), 22, "#d29a1a", ow=0)
                    dd = DIFF[clamp(self.settings["diff"][i], 0, 2)]
                    self.ren.tx(cx, y1 + 254, ("◄ %s ►" % dd["name"]) if i == self.lsel else dd["name"], 15, dd["col"], ow=2)
                    g = self.save["grades"].get(str(i))
                    if g:
                        self.ren.ov(cx, y1 + 305, 28, 28, GOLD, 4)
                        self.ren.tx(cx, y1 + 305, g, 30, INK, ow=0)
        elif st == "howto":
            self.draw_bg(MENU_CFG)
            self.ren.panel(110, 50, 850, 490)
            self.ren.tx(W / 2, 85, "NASIL OYNANIR", 30, INK, ow=0)
            for i, t in enumerate(HOWTO):
                self.ren.tx(135, 125 + i * 26, t, 13, INK, "w", 0)
            self.ren.tx(W / 2, 470, "Dokun veya Zıpla tuşuna bas: Geri", 14, RED, ow=0)
        elif st == "result":
            self.draw_bg(MENU_CFG)
            r = self.res
            self.ren.panel(190, 50, 770, 490)
            self.ren.tx(W / 2, 100, "SONUÇ", 38, INK, ow=0)
            lines = [("Süre", "%d:%04.1f" % (int(r["time"] // 60), r["time"] % 60)),
                     ("Kalan can", "%d / %d" % (r["hp"], r["maxhp"])),
                     ("Parry", str(r["parries"])),
                     ("Zorluk", r["diff"])]
            for i, (a, b) in enumerate(lines):
                if self.rt > 20 + i * 18:
                    y = 170 + i * 46
                    self.ren.tx(250, y, a, 22, INK, "w", 0)
                    self.ren.tx(710, y, b, 22, RED, "e", 0)
                    self.ren.ln([(250, y + 20), (710, y + 20)], 2, "#b9a97d")
            if self.rt > 70:
                self.ren.ov(W / 2, 395, 54, 54, GOLD, 5)
                self.ren.tx(W / 2, 395, r["grade"], 64, INK, ow=0)
            if self.rt > 80 and (self.t // 25) % 2 == 0:
                txt = "Dokun: Sonraki Bölüm" if self.lv + 1 < len(LEVELS) else "Dokun: Devam"
                self.ren.tx(W / 2, 470, txt, 17, RED, ow=0)
        elif st == "dead":
            self.draw_bg(MENU_CFG)
            b = self.boss
            self.ren.panel(200, 80, 760, 460)
            self.ren.tx(W / 2, 135, "ÖLDÜN!", 50, RED, ow=0)
            self.ren.tx(W / 2, 200, b.name if b else "", 20, INK, ow=0)
            frac = clamp(b.hp / b.maxhp, 0, 1) if b else 0
            self.ren.rc(260, 230, 700, 256, "#5a2a1a", 3)
            self.ren.rc(262, 232, 262 + 436 * frac, 254, RED, 0, "")
            self.ren.tx(W / 2, 285, "Boss Kalan Canı: %%%d" % int(frac * 100), 15, INK, ow=0)
            for i, lab in enumerate(("TEKRAR DENE", "ANA MENÜ")):
                y = 345 + i * 50
                if i == self.dsel:
                    self.ren.rc(300, y - 20, 660, y + 20, GOLD, 3)
                self.ren.tx(W / 2, y, lab, 20, INK, ow=0)
        elif st == "ending":
            self.draw_bg(MENU_CFG)
            self.ren.tx(W / 2, 150, "TEBRİKLER!", 70, CREAM, ow=5)
            self.ren.tx(W / 2, 235, "Tüm bosslar yenildi.", 24, GOLD, ow=3)
            self.ren.tx(W / 2, 285, "Bardak artık huzur içinde çayını yudumlayabilir.", 18, CREAM, ow=2)
            self.p.x, self.p.face = W / 2, 1
            self.p.y = GROUND
            self.p.hp = 3
            self.draw_player(self.p)
            for px, py, vx, vy, l, ml, col, sz, k in self.parts:
                self.ren.ov(px, py, sz, sz, col, 0, "")
            if self.rt > 90 and (self.t // 25) % 2 == 0:
                self.ren.tx(W / 2, 400, "Dokun: Ana Menü", 18, CREAM, ow=3)

        # Draw On-screen touch buttons for mobile play
        self.draw_touch_controls()

        # Film Grain & Borders
        for _ in range(16):
            rx = random.randint(0, W)
            ry = random.randint(0, H)
            self.ren.rc(rx, ry, rx + 2, ry + 2, parse_hex("#3a2a14"), 0, "")
        self.ren.rc(0, 0, W, H, "", 16, INK)

        # Iris Transition
        if self.iris:
            it = self.iris
            R = 640
            k = clamp(it[1] / 22.0, 0, 1)
            r = R * (1 - k) ** 1.5 if it[0] == 0 else R * k ** 1.5
            cx, cy = self.iris_c
            if r < 2:
                self.ren.rc(0, 0, W, H, INK, 0, "")
            else:
                self.ren.ov(cx, cy, r + 40, r + 40, "", 80, INK)

    # ------------------------------------------------------------- Main Loop
    def run(self):
        while not self.quit:
            # Handle Window / Screen scaling
            sw, sh = self.screen.get_size()
            scale_x = W / max(1, sw)
            scale_y = H / max(1, sh)

            self.pressed_actions.clear()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit = True

                elif event.type == pygame.KEYDOWN:
                    self.keyboard_keys.add(event.key)
                    if event.key in (pygame.K_SPACE, pygame.K_z):
                        self.trigger_action("jump")
                        self.trigger_action("return")
                    elif event.key == pygame.K_RETURN:
                        self.trigger_action("return")
                    elif event.key in (pygame.K_x, pygame.K_j):
                        self.trigger_action("shoot")
                    elif event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT, pygame.K_c):
                        self.trigger_action("dash")
                    elif event.key in (pygame.K_q, pygame.K_e):
                        self.trigger_action("ex")
                    elif event.key in (pygame.K_UP, pygame.K_w):
                        self.trigger_action("up")
                    elif event.key in (pygame.K_DOWN, pygame.K_s):
                        self.trigger_action("down")
                    elif event.key in (pygame.K_LEFT, pygame.K_a):
                        self.trigger_action("left")
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        self.trigger_action("right")
                    elif event.key == pygame.K_ESCAPE:
                        self.trigger_action("escape")

                elif event.type == pygame.KEYUP:
                    self.keyboard_keys.discard(event.key)

                # Touch Event handling (Native Multi-touch on Android / Finger events)
                elif event.type in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
                    tid = event.finger_id
                    lx = event.x * W
                    ly = event.y * H
                    if event.type in (pygame.FINGERDOWN, pygame.FINGERMOTION):
                        self.touches[tid] = (lx, ly)
                    elif event.type == pygame.FINGERUP:
                        self.touches.pop(tid, None)

                # Mouse click / touch fallback for desktop testing
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    lx = event.pos[0] * scale_x
                    ly = event.pos[1] * scale_y
                    self.touches[-1] = (lx, ly)
                    # Screen tap as enter in menus
                    if self.state in ("menu", "select", "howto", "result", "dead", "ending"):
                        self.trigger_action("return")
                        self.trigger_action("jump")

                elif event.type == pygame.MOUSEMOTION:
                    if -1 in self.touches:
                        lx = event.pos[0] * scale_x
                        ly = event.pos[1] * scale_y
                        self.touches[-1] = (lx, ly)

                elif event.type == pygame.MOUSEBUTTONUP:
                    self.touches.pop(-1, None)

            # Map active touches to buttons
            new_active_buttons = set()
            for lx, ly in self.touches.values():
                for bname, rect in self.buttons_layout.items():
                    if rect.collidepoint(lx, ly):
                        new_active_buttons.add(bname)

            for bname in new_active_buttons - self.active_buttons:
                self.trigger_action(bname)
                if bname in ("jump", "shoot", "dash", "ex", "pause", "up", "down", "left", "right"):
                    if bname == "jump":
                        self.trigger_action("return")
                    elif bname == "pause":
                        self.trigger_action("escape")

            self.active_buttons = new_active_buttons

            self.update()
            self.draw()

            # Blit logical canvas to main screen
            scaled_surf = pygame.transform.smoothscale(self.logical_surf, (sw, sh))
            self.screen.blit(scaled_surf, (0, 0))
            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    game = Game()
    game.run()
