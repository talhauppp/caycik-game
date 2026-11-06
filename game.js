// ÇAYCIK: Boss Savaşı - HTML5 Canvas & Web Audio Port
const W = 960, H = 540, GROUND = 452, GRAV = 0.85;
const INK = "#1b1209", CREAM = "#f7e8c0", WHITE = "#fffaf0", GOLD = "#f2b632", RED = "#c8372d", PINK = "#ff6fb5", FONT = "Georgia";

function hx(c) {
  return [parseInt(c.slice(1, 3), 16), parseInt(c.slice(3, 5), 16), parseInt(c.slice(5, 7), 16)];
}

function mix(a, b, t) {
  const ca = hx(a), cb = hx(b);
  const r = Math.round(ca[0] + (cb[0] - ca[0]) * t);
  const g = Math.round(ca[1] + (cb[1] - ca[1]) * t);
  const bl = Math.round(ca[2] + (cb[2] - ca[2]) * t);
  return `rgb(${r},${g},${bl})`;
}

function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
function seg_dist(px, py, x1, y1, x2, y2) {
  const dx = x2 - x1, dy = y2 - y1;
  const l = dx * dx + dy * dy;
  const t = l === 0 ? 0 : clamp(((px - x1) * dx + (py - y1) * dy) / l, 0, 1);
  return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
}

function star_pts(cx, cy, r1, r2, n, rot) {
  const pts = [];
  for (let i = 0; i < n * 2; i++) {
    const a = rot + i * Math.PI / n;
    const r = i % 2 === 0 ? r1 : r2;
    pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]);
  }
  return pts;
}

// ------------------------------------------------------------- SES (Web Audio)
class WebSfx {
  constructor() {
    this.ctx = null;
    this.on = true;
    const init = () => {
      if (!this.ctx) {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (AudioCtx) this.ctx = new AudioCtx();
      }
      window.removeEventListener('keydown', init);
      window.removeEventListener('touchstart', init);
      window.removeEventListener('click', init);
    };
    window.addEventListener('keydown', init);
    window.addEventListener('touchstart', init);
    window.addEventListener('click', init);
  }

  play(name) {
    if (!this.on || !this.ctx) return;
    try {
      const t = this.ctx.currentTime;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.connect(gain);
      gain.connect(this.ctx.destination);

      if (name === "blip") {
        osc.frequency.setValueAtTime(700, t);
        gain.gain.setValueAtTime(0.12, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.05);
        osc.start(t);
        osc.stop(t + 0.05);
      } else if (name === "ok") {
        osc.frequency.setValueAtTime(900, t);
        osc.frequency.linearRampToValueAtTime(1300, t + 0.09);
        gain.gain.setValueAtTime(0.15, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.09);
        osc.start(t);
        osc.stop(t + 0.09);
      } else if (name === "hurt") {
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(220, t);
        osc.frequency.linearRampToValueAtTime(60, t + 0.28);
        gain.gain.setValueAtTime(0.2, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.28);
        osc.start(t);
        osc.stop(t + 0.28);
      } else if (name === "parry") {
        osc.type = "triangle";
        osc.frequency.setValueAtTime(1100, t);
        osc.frequency.linearRampToValueAtTime(1800, t + 0.14);
        gain.gain.setValueAtTime(0.25, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.14);
        osc.start(t);
        osc.stop(t + 0.14);
      } else if (name === "dash") {
        osc.type = "square";
        osc.frequency.setValueAtTime(500, t);
        osc.frequency.linearRampToValueAtTime(250, t + 0.08);
        gain.gain.setValueAtTime(0.1, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.08);
        osc.start(t);
        osc.stop(t + 0.08);
      } else if (name === "ko") {
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(600, t);
        osc.frequency.linearRampToValueAtTime(100, t + 0.7);
        gain.gain.setValueAtTime(0.3, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.7);
        osc.start(t);
        osc.stop(t + 0.7);
      } else if (name === "go") {
        osc.frequency.setValueAtTime(500, t);
        osc.frequency.linearRampToValueAtTime(1100, t + 0.25);
        gain.gain.setValueAtTime(0.2, t);
        gain.gain.exponentialRampToValueAtTime(0.001, t + 0.25);
        osc.start(t);
        osc.stop(t + 0.25);
      }
    } catch(e) {}
  }
}

// ------------------------------------------------------------- MERMİLER & OYUNCU
class Bullet {
  constructor(x, y, vx, vy, ex=false) {
    this.x = x; this.y = y; this.vx = vx; this.vy = vy;
    this.ex = ex;
    this.r = ex ? 18 : 6;
    this.age = 0;
    this.dead = false;
    this.hit = false;
    this.hits = new Set();
  }
}

class Player {
  constructor() {
    this.x = 170.0;
    this.y = GROUND;
    this.vx = this.vy = 0.0;
    this.face = 1;
    this.on = true;
    this.coy = 0;
    this.hp = 3;
    this.maxhp = 3;
    this.inv = 0;
    this.hurt = 0;
    this.dash = 0;
    this.dd = 1;
    this.dcd = 0;
    this.cd = 0;
    this.mz = 0;
    this.card = 0.0;
    this.parries = 0;
    this.jh = false;
    this.t = 0;
  }

  box() { return [this.x - 13, this.y - 54, this.x + 13, this.y - 3]; }

  aimvec(g) {
    const up = g.act("up");
    const mv = g.act("left") || g.act("right");
    if (up && mv) return [this.face * 0.7071, -0.7071];
    if (up) return [0.0, -1.0];
    return [this.face, 0.0];
  }

  update(g) {
    this.t++;
    if (this.inv > 0) this.inv--;
    if (this.hurt > 0) this.hurt--;
    if (this.dcd > 0) this.dcd--;
    if (this.cd > 0) this.cd--;
    if (this.mz > 0) this.mz--;

    if (this.hp <= 0) return;
    const l = g.act("left"), r = g.act("right");
    const locked = this.hurt > 14;

    if (this.dash > 0) {
      this.dash--;
      this.vx = this.dd * 14.5;
      this.vy = 0;
      if (this.t % 2 === 0) g.dust(this.x - this.dd * 10, this.y - 4, 1);
    } else {
      let tgt = ((r ? 1 : 0) - (l ? 1 : 0)) * 5.5;
      if (locked) tgt = 0;
      this.vx += (tgt - this.vx) * (this.on ? 0.42 : 0.24);
      if (!locked) {
        if (r && !l) this.face = 1;
        else if (l && !r) this.face = -1;
      }
      if (g.actp("dash") && this.dcd <= 0 && !locked) {
        this.dash = 12;
        this.dcd = 38;
        this.dd = this.face;
        g.sfx.play("dash");
        g.dust(this.x, this.y - 4, 5);
      }
    }

    const jp = g.actp("jump");
    if (jp && !locked) {
      if (this.on || this.coy > 0) {
        this.vy = -16.8;
        this.on = false;
        this.coy = 0;
        this.jh = true;
        g.dust(this.x, this.y, 5);
      } else {
        g.try_parry();
      }
    }

    if (this.jh && !g.act("jump")) {
      this.jh = false;
      if (this.vy < -6) this.vy *= 0.45;
    }

    if (this.dash === 0) this.vy = Math.min(this.vy + GRAV, 17.0);

    const [lo, hi] = g.xrange();
    this.x = clamp(this.x + this.vx, lo, hi);
    const oy = this.y;
    this.y += this.vy;
    const was = this.on;
    this.on = false;

    if (this.vy >= 0) {
      for (const [x1, x2, top] of g.plats) {
        if (x1 - 8 <= this.x && this.x <= x2 + 8 && oy <= top + 2 && this.y >= top) {
          this.y = top;
          this.vy = 0;
          this.on = true;
        }
      }
      if (this.y >= GROUND && oy <= GROUND + 2 && g.ground_at(this.x)) {
        this.y = GROUND;
        this.vy = 0;
        this.on = true;
      }
    }

    if (this.on) {
      this.coy = 6;
      if (!was) g.dust(this.x, this.y, 6);
    } else {
      this.coy = Math.max(0, this.coy - 1);
    }

    const can = g.intro <= 60 && !locked && this.dash === 0 && g.ko === 0;
    if (can && g.act("shoot") && this.cd <= 0) {
      this.cd = 5;
      const [ax, ay] = this.aimvec(g);
      const ang = Math.atan2(ay, ax) + (Math.random() - 0.5) * 0.06;
      g.bul.push(new Bullet(this.x + ax * 30, this.y - 36 + ay * 26, Math.cos(ang) * 18, Math.sin(ang) * 18));
      this.mz = 4;
    }

    if (can && g.actp("ex") && this.card >= 1) {
      this.card -= 1;
      const [ax, ay] = this.aimvec(g);
      g.bul.push(new Bullet(this.x + ax * 30, this.y - 36 + ay * 26, ax * 13, ay * 13, true));
      this.mz = 8;
      g.shake = 6;
      g.burst(this.x + ax * 30, this.y - 36, GOLD, 10, 5);
    }
  }
}

// ------------------------------------------------------------- DÜŞMAN MERMİSİ
class Shot {
  constructor(kind, x, y, vx=0, vy=0, r=12, pink=false, g=0, hp=0, hh=40, sp=0, ph=0, life=700, skin="") {
    this.skin = skin;
    this.kind = kind; this.x = x; this.y = y; this.vx = vx; this.vy = vy;
    this.r = r; this.pink = pink; this.g = g; this.hp = hp; this.hh = hh; this.sp = sp; this.ph = ph; this.life = life;
    this.t = 0;
    this.dead = false;
    this.ang = (vx || vy) ? Math.atan2(vy, vx) : 0;
    this.flash = 0;
    this.spin = Math.random() * 6;
  }

  update(G) {
    this.t++;
    const k = this.kind;
    if (k === "carrot") {
      if (this.t < 200) {
        const p = G.p;
        const want = Math.atan2(p.y - 30 - this.y, p.x - this.x);
        const d = (want - this.ang + Math.PI) % (2 * Math.PI) - Math.PI;
        this.ang += clamp(d, -0.045, 0.045);
      }
      this.vx = Math.cos(this.ang) * this.sp;
      this.vy = Math.sin(this.ang) * this.sp;
    } else if (k === "fly") {
      this.vx = Math.sin(this.t * 0.07 + this.ph) * 2.6;
    } else if (k === "gear") {
      if (this.y >= GROUND - this.r && this.vy >= 0) {
        this.y = GROUND - this.r;
        this.vy = -8.5;
      }
      this.spin -= 0.2;
    } else if (k === "card" || k === "star") {
      this.spin += 0.22;
    } else if (k === "roll") {
      this.spin -= 0.15;
    } else if (k === "bee") {
      this.vy = Math.sin(this.t * 0.12 + this.ph) * 2.6;
    }

    this.vy += this.g;
    this.x += this.vx;
    this.y += this.vy;

    if (k === "bomb" && this.y >= GROUND - this.r) {
      this.dead = true;
      G.bomb_boom(this);
    }
    if ((this.skin === "honey" || this.skin === "snow") && this.vy > 0 && this.y >= GROUND - this.r) {
      this.dead = true;
      G.burst(this.x, GROUND - 6, this.skin === "snow" ? "#ffffff" : GOLD, 8, 4);
    }
    if (k === "ice" && this.y >= GROUND - 10) {
      this.dead = true;
      G.burst(this.x, GROUND - 6, "#bfeaff", 8, 4);
    }

    if (this.flash > 0) this.flash--;
    if (this.t > this.life || this.x < G.camx - 90 || this.x > G.camx + W + 90 || this.y > H + 90 || this.y < -140) {
      this.dead = true;
    }
  }
}

function hits_player(sh, p) {
  if (sh.kind === "wave") return Math.abs(sh.x - p.x) < sh.r + 10 && p.y > GROUND - sh.hh;
  const [bx1, by1, bx2, by2] = p.box();
  const cx = clamp(sh.x, bx1, bx2);
  const cy = clamp(sh.y, by1, by2);
  return Math.hypot(sh.x - cx, sh.y - cy) < sh.r * 0.8;
}

// ------------------------------------------------------------- BOSSLAR
class BaseBoss {
  pick(opts) {
    const o = opts.filter(x => x !== this.last);
    this.last = o.length ? o[Math.floor(Math.random() * o.length)] : opts[0];
    return this.last;
  }
  hurt(d) {
    this.hp = Math.max(0, this.hp - d);
    this.flash = 2;
  }
}

class Frog extends BaseBoss {
  constructor(g) {
    super();
    this.g = g;
    this.name = "KURBAĞA KRAL";
    this.maxhp = 250;
    this.hp = this.maxhp;
    this.x = 770.0;
    this.y = GROUND;
    this.vx = this.vy = 0.0;
    this.st = "idle";
    this.tm = 60;
    this.t = 0;
    this.flash = 0;
    this.ph = 1;
    this.face = -1;
    this.n = 0;
    this.sq = 1.0;
    this.mouth = 0;
    this.last = "";
    this.dead = false;
  }

  boxes() { return [[this.x - 70, this.y - 165, this.x + 70, this.y - 8]]; }

  update() {
    const g = this.g;
    const p = g.p;
    this.t++;
    if (this.flash > 0) this.flash--;
    if (this.mouth > 0) this.mouth--;
    if (this.st !== "air") this.face = p.x < this.x ? -1 : 1;

    if (this.ph === 1 && this.hp <= this.maxhp * 0.5) {
      this.ph = 2;
      this.st = "roar";
      this.tm = 70;
      g.shake = 12;
    }

    const st = this.st;
    if (st === "idle") {
      this.sq = 1 + 0.03 * Math.sin(this.t * 0.12);
      this.tm--;
      if (this.tm <= 0) {
        const a = this.pick(["spit", "jump"].concat(this.ph === 2 ? ["flies"] : []));
        this.st = a + "_w";
        this.tm = 26;
        this.n = 0;
      }
    } else if (st === "roar") {
      this.sq = 1.1 + 0.05 * Math.sin(this.t);
      this.mouth = 2;
      this.tm--;
      if (this.tm <= 0) { this.st = "idle"; this.tm = 30; }
    } else if (st === "spit_w") {
      this.sq = 0.9;
      this.tm--;
      if (this.tm <= 0) { this.st = "spit"; this.tm = 0; }
    } else if (st === "spit") {
      this.tm--;
      if (this.tm <= 0) {
        const total = this.ph === 1 ? 3 : 5;
        const mx = this.x + this.face * 66;
        const my = this.y - 100;
        const ang = Math.atan2(p.y - 30 - my, p.x - mx) + (Math.random() - 0.5) * 0.24;
        const sp = this.ph === 1 ? 5.6 : 6.6;
        const pink = (this.n === total - 1) || (this.ph === 2 && this.n === 1);
        g.shots.push(new Shot("ball", mx, my, Math.cos(ang) * sp, Math.sin(ang) * sp, 14, pink));
        this.mouth = 10;
        this.n++;
        this.tm = this.ph === 1 ? 18 : 13;
        this.sq = 1.08;
        if (this.n >= total) { this.st = "idle"; this.tm = this.ph === 1 ? 55 : 38; }
      }
    } else if (st === "jump_w") {
      this.sq = 0.78;
      this.tm--;
      if (this.tm <= 0) {
        this.st = "air";
        this.vy = -23.0;
        const T = 2 * 23.0 / 0.9;
        const tx = this.x > 480 ? 170 + Math.random() * 160 : 640 + Math.random() * 150;
        this.vx = (tx - this.x) / T;
      }
    } else if (st === "air") {
      this.vy += 0.9;
      this.x += this.vx;
      this.y += this.vy;
      this.sq = this.vy < 0 ? 1.18 : 1.05;
      if (this.y >= GROUND) {
        this.y = GROUND;
        this.vy = 0;
        this.vx = 0;
        this.st = "land";
        this.tm = 34;
        g.shake = 12;
        g.dust(this.x, GROUND, 10);
        const sp = this.ph === 1 ? 6.5 : 7.8;
        g.shots.push(new Shot("wave", this.x - 60, GROUND - 2, -sp, 0, 16, false, 0, 0, 40));
        g.shots.push(new Shot("wave", this.x + 60, GROUND - 2, sp, 0, 16, false, 0, 0, 40));
      } else if (this.vy > 0) {
        const bx = this.boxes()[0];
        const [px1, py1, px2, py2] = p.box();
        if (px1 < bx[2] && px2 > bx[0] && py1 < bx[3] && py2 > bx[1]) g.hurt_player();
      }
    } else if (st === "land") {
      this.sq = 0.8 + 0.2 * (1 - this.tm / 34.0);
      this.tm--;
      if (this.tm <= 0) { this.st = "idle"; this.tm = this.ph === 1 ? 40 : 26; }
    } else if (st === "flies_w") {
      this.mouth = 2;
      this.sq = 1.1;
      this.tm--;
      if (this.tm <= 0) { this.st = "flies"; this.tm = 0; }
    } else if (st === "flies") {
      this.tm--;
      if (this.tm <= 0) {
        g.shots.push(new Shot("fly", 80 + Math.random() * 800, -20, 0, 2.4, 13, this.n % 3 === 2, 0, 0, 40, 0, Math.random() * 6, 500));
        this.n++;
        this.tm = 16;
        if (this.n >= 7) { this.st = "idle"; this.tm = 45; }
      }
    }
  }

  draw(g, ox=0) {
    const p = g.p;
    const x = this.x + ox, y = this.y, sq = this.sq;
    const fl = this.flash > 0;
    const C = (c) => fl ? "#ffffff" : c;

    const green = C("#69b043"), dk = C("#3d7a2b"), belly = C("#e4f09a");
    g.ov(x, GROUND + 5, 92, 9, mix(g.gcol, INK, 0.5), 0, "");
    g.ov(x - 62, y - 20 * sq, 34, 22 * sq, dk);
    g.ov(x + 62, y - 20 * sq, 34, 22 * sq, dk);
    g.ov(x, y - 72 * sq, 82, 72 * sq, green);
    g.ov(x, y - 52 * sq, 56, 46 * sq, belly, 2);

    for (const d of [-1, 1]) {
      g.ov(x + d * 60, y - 8, 36, 13, green);
      g.ov(x + d * 40, y - 60 * sq, 17, 26 * sq, dk, 2);
      const ex = x + d * 38, ey = y - 146 * sq;
      g.ov(ex, ey, 28, 28, green);
      g.ov(ex, ey, 21, 21, C("#fffbe8"), 2);
      const dx = p.x - ex, dy = (p.y - 30) - ey;
      const dd = Math.hypot(dx, dy) || 1;
      g.ov(ex + dx / dd * 8, ey + dy / dd * 8, 9, 11, INK, 0, "");
      const lid = this.ph === 1 ? 4 : 12;
      g.pl([[ex + d * 30, ey - 34], [ex - d * 30, ey - 34], [ex - d * 30, ey - lid - 2], [ex + d * 30, ey - lid - 18]], green, 3);
    }

    const my = y - 92 * sq;
    if (this.mouth > 0) {
      g.ov(x, my + 6, 50, 24, "#7a1f1f");
      g.ov(x, my + 18, 28, 9, PINK, 0, "");
    } else {
      g.ln([[x - 54, my - 6], [x, my + 12], [x + 54, my - 6]], 6, INK, true);
    }

    const cy = y - 184 * sq;
    g.pl([[x - 26, cy + 8], [x - 26, cy - 20], [x - 13, cy - 6], [x, cy - 26], [x + 13, cy - 6], [x + 26, cy - 20], [x + 26, cy + 8]], C(GOLD));
    g.ov(x, cy - 2, 5, 5, C(RED), 2);
  }
}

// ------------------------------------------------------------- BÖLÜMLER
const LEVELS = [
  { name: "KURBAĞA KRAL", sub: "Bataklıkta Kavga", cls: Frog, theme: "swamp", sky: ["#fbe08a", "#f08f45"], ray: "#fff0b0", ground: "#6f9a3a", plats: [], par: 75, stars: 1 }
];

const DIFF = [
  { name: "KOLAY", hp: 5, bhp: 0.7, bt: 0.82, shot: 0.9, cap: 79, col: "#6fd04a", info: "KOLAY: 5 can · boss %30 daha zayıf ve yavaş" },
  { name: "NORMAL", hp: 3, bhp: 1.0, bt: 1.0, shot: 1.0, col: GOLD, info: "NORMAL: 3 can · standart savaş" },
  { name: "ZOR", hp: 2, bhp: 1.3, bt: 1.15, shot: 1.1, bonus: 5, col: "#ff5a4a", info: "ZOR: 2 can · boss %30 daha dayanıklı" }
];

// ------------------------------------------------------------- ANA OYUN MOTORU
class WebGame {
  constructor(canvas) {
    this.cv = canvas;
    this.ctx = canvas.getContext('2d');
    this.sfx = new WebSfx();

    this.keys = new Set();
    this.pressed = new Set();
    this.state = "menu";
    this.sel = 0;
    this.t = 0;
    this.lv = 0;
    this.dif = DIFF[1];
    this.p = new Player();
    this.boss = null;
    this.shots = [];
    this.bul = [];
    this.parts = [];
    this.pops = [];
    this.plats = [];
    this.camx = 0;
    this.intro = 0;
    this.ko = 0;
    this.shake = 0;
    this.hitstop = 0;
    this.ft = 0;
    this.gcol = "#7b4d2b";
    this.cfg = LEVELS[0];

    window.addEventListener('keydown', (e) => {
      const code = e.code;
      if (!this.keys.has(code)) {
        this.keys.add(code);
        this.pressed.add(code);
      }
    });

    window.addEventListener('keyup', (e) => {
      this.keys.delete(e.code);
    });

    this.loop = this.loop.bind(this);
    requestAnimationFrame(this.loop);
  }

  act(name) {
    const m = {
      left: ['ArrowLeft', 'KeyA'],
      right: ['ArrowRight', 'KeyD'],
      up: ['ArrowUp', 'KeyW'],
      jump: ['Space', 'KeyZ', 'KeyK'],
      shoot: ['KeyX', 'KeyJ'],
      dash: ['ShiftLeft', 'ShiftRight', 'KeyC'],
      ex: ['KeyQ', 'KeyE']
    };
    return (m[name] || []).some(k => this.keys.has(k));
  }

  actp(name) {
    const m = {
      left: ['ArrowLeft', 'KeyA'],
      right: ['ArrowRight', 'KeyD'],
      up: ['ArrowUp', 'KeyW'],
      jump: ['Space', 'KeyZ', 'KeyK'],
      shoot: ['KeyX', 'KeyJ'],
      dash: ['ShiftLeft', 'ShiftRight', 'KeyC'],
      ex: ['KeyQ', 'KeyE']
    };
    return (m[name] || []).some(k => this.pressed.has(k));
  }

  hit(...keys) { return keys.some(k => this.pressed.has(k)); }
  xrange() { return [20, W - 20]; }
  ground_at(x) { return true; }

  dust(x, y, n=5) {
    for (let i = 0; i < n; i++) {
      this.parts.push([x + (Math.random() - 0.5) * 16, y - 2, (Math.random() - 0.5) * 3, -Math.random() * 1.2, 18, 18, "#efe3c4", 5, 2]);
    }
  }

  burst(x, y, col, n=12, sp=5) {
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2;
      const v = 1 + Math.random() * sp;
      this.parts.push([x, y, Math.cos(a) * v, Math.sin(a) * v - 1, 24, 24, col, 4, 0]);
    }
  }

  try_parry() {
    const p = this.p;
    for (const sh of this.shots) {
      if (sh.pink && !sh.dead && Math.hypot(sh.x - p.x, sh.y - (p.y - 30)) < sh.r + 38) {
        sh.dead = true;
        p.card = Math.min(5.0, p.card + 1);
        p.parries++;
        p.vy = -13.0;
        p.jh = false;
        this.hitstop = 5;
        this.burst(sh.x, sh.y, PINK, 18, 6);
        this.sfx.play("parry");
        return;
      }
    }
  }

  hurt_player() {
    const p = this.p;
    if (p.inv > 0 || p.dash > 0 || p.hp <= 0 || this.ko > 0 || this.intro > 30) return false;
    p.hp--;
    p.inv = 110;
    p.hurt = 26;
    p.vy = -9.0;
    p.vx = -p.face * 4.0;
    p.on = false;
    this.shake = 14;
    this.hitstop = 6;
    this.burst(p.x, p.y - 30, "#ffffff", 16, 6);
    this.sfx.play("hurt");
    return true;
  }

  start_level(i) {
    this.lv = i;
    this.cfg = LEVELS[i];
    this.p = new Player();
    this.boss = new this.cfg.cls(this);
    this.shots = [];
    this.bul = [];
    this.parts = [];
    this.intro = 120;
    this.ko = 0;
    this.state = "fight";
    this.gcol = this.cfg.ground;
    this.sfx.play("go");
  }

  update() {
    this.t++;
    if (this.state === "menu") {
      if (this.hit("ArrowUp", "KeyW")) { this.sel = (this.sel - 1 + 2) % 2; this.sfx.play("blip"); }
      if (this.hit("ArrowDown", "KeyS")) { this.sel = (this.sel + 1) % 2; this.sfx.play("blip"); }
      if (this.hit("Enter", "Space", "KeyZ")) {
        this.sfx.play("ok");
        if (this.sel === 0) this.start_level(0);
      }
    } else if (this.state === "fight") {
      if (this.hitstop > 0) { this.hitstop--; this.pressed.clear(); return; }
      if (this.shake > 0) this.shake--;
      if (this.intro > 0) this.intro--;

      const p = this.p, b = this.boss;
      p.update(this);

      if (this.intro <= 30 && !b.dead) {
        b.update();
        if (p.hp > 0) this.ft++;
      }

      for (const sh of this.shots) {
        sh.update(this);
        if (!sh.dead && hits_player(sh, p)) {
          if (this.hurt_player() && sh.kind !== "wave") sh.dead = true;
        }
      }
      this.shots = this.shots.filter(x => !x.dead);

      for (const bl of this.bul) {
        bl.x += bl.vx;
        bl.y += bl.vy;
        bl.age++;
        if (bl.x < -40 || bl.x > W + 40 || bl.y < -40 || bl.y > H + 40) { bl.dead = true; continue; }
        if (this.intro > 30 || b.dead) continue;

        for (const [x1, y1, x2, y2] of b.boxes()) {
          if (x1 - bl.r <= bl.x && bl.x <= x2 + bl.r && y1 - bl.r <= bl.y && bl.y <= y2 + bl.r) {
            if (bl.ex) {
              if (!bl.hit) {
                bl.hit = true;
                b.hurt(12);
                this.burst(bl.x, bl.y, GOLD, 16, 6);
                this.shake = 5;
              }
            } else {
              bl.dead = true;
              b.hurt(1);
              p.card = Math.min(5.0, p.card + 0.035);
              this.burst(bl.x, bl.y, "#fff2b0", 3, 3);
            }
            break;
          }
        }
      }
      this.bul = this.bul.filter(x => !x.dead);

      if (b.hp <= 0 && this.ko === 0 && p.hp > 0) {
        this.ko = 1;
        b.dead = true;
        this.shots = [];
        this.shake = 16;
        this.sfx.play("ko");
      }

      if (this.ko > 0) {
        this.ko++;
        if (this.ko > 150) this.state = "menu";
      }

      if (p.hp <= 0) {
        if (this.hit("Enter", "Space")) this.start_level(0);
      }
    }

    for (const q of this.parts) {
      q[0] += q[2]; q[1] += q[3]; q[3] += 0.22; q[4]--;
    }
    this.parts = this.parts.filter(q => q[4] > 0);

    this.pressed.clear();
  }

  // ------------------------------------------------------------- ÇİZİM FONKSİYONLARI
  ov(x, y, rx, ry, fill, w=3, out=INK) {
    const ctx = this.ctx;
    ctx.beginPath();
    ctx.ellipse(x, y, Math.max(1, rx), Math.max(1, ry), 0, 0, Math.PI * 2);
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (w > 0 && out) { ctx.lineWidth = w; ctx.strokeStyle = out; ctx.stroke(); }
  }

  rc(x1, y1, x2, y2, fill, w=3, out=INK) {
    const ctx = this.ctx;
    ctx.beginPath();
    ctx.rect(x1, y1, x2 - x1, y2 - y1);
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (w > 0 && out) { ctx.lineWidth = w; ctx.strokeStyle = out; ctx.stroke(); }
  }

  pl(pts, fill, w=3, smooth=false, out=INK) {
    const ctx = this.ctx;
    if (pts.length < 2) return;
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
    ctx.closePath();
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (w > 0 && out) { ctx.lineWidth = w; ctx.strokeStyle = out; ctx.stroke(); }
  }

  ln(pts, w, fill, smooth=false) {
    const ctx = this.ctx;
    if (pts.length < 2) return;
    ctx.beginPath();
    ctx.moveTo(pts[0][0], pts[0][1]);
    for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0], pts[i][1]);
    ctx.lineWidth = w;
    ctx.strokeStyle = fill;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.stroke();
  }

  tx(x, y, text, size=20, fill=CREAM, anchor="center", ow=2, out=INK) {
    const ctx = this.ctx;
    ctx.font = `bold ${size}px ${FONT}`;
    ctx.textAlign = anchor;
    ctx.textBaseline = "middle";
    if (ow > 0) {
      ctx.lineWidth = ow * 2;
      ctx.strokeStyle = out;
      ctx.strokeText(text, x, y);
    }
    ctx.fillStyle = fill;
    ctx.fillText(text, x, y);
  }

  draw_player(p) {
    const x = p.x, y = p.y, f = p.face;
    if (p.inv > 0 && Math.floor(this.t / 3) % 2) return;

    this.ov(x, GROUND + 3, 18, 5, mix(this.gcol, INK, 0.5), 0, "");
    if (p.dash > 0) {
      this.ov(x, y - 30, 24, 15, "#f4fbff");
      this.ov(x + f * 6, y - 32, 5, 7, INK, 0, "");
      return;
    }

    const hipy = y - 24;
    this.ov(x, hipy - 2, 11, 9, RED);
    this.ov(x, hipy - 14, 8, 10, CREAM);

    // Bacaklar
    this.ln([[x - 8, hipy], [x - 8, y]], 4, INK);
    this.ln([[x + 8, hipy], [x + 8, y]], 4, INK);

    // Kafa / Çay bardağı
    const hx_ = x + f * 2, hy_ = hipy - 38;
    this.rc(hx_ - 14, hy_ - 14, hx_ + 14, hy_ + 14, "#e6f6fa", 3, INK);
    this.rc(hx_ - 12, hy_ - 2, hx_ + 12, hy_ + 12, "#c4501a", 0, "");
    this.ov(hx_ + f * 4, hy_, 3, 5, INK, 0, "");
  }

  draw() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, W, H);

    let sx = 0, sy = 0;
    if (this.shake > 0) {
      sx = (Math.random() - 0.5) * this.shake;
      sy = (Math.random() - 0.5) * this.shake;
    }
    ctx.save();
    ctx.translate(sx, sy);

    if (this.state === "menu") {
      // Arkaplan
      this.rc(0, 0, W, H, "#3a2110", 0, "");
      this.ov(W/2, GROUND + 120, 480, 260, "#5a3a22", 4);
      this.rc(0, GROUND, W, H, "#6f9a3a", 4);

      this.tx(W / 2, 120, "ÇAYCIK", 84, CREAM, "center", 5, RED);
      this.tx(W / 2, 190, "BOSS SAVAŞI", 24, GOLD, "center", 3);

      const items = ["BAŞLA", "KONTROLLER"];
      for (let i = 0; i < items.length; i++) {
        const y = 280 + i * 50;
        if (i === this.sel) {
          this.rc(W / 2 - 120, y - 20, W / 2 + 120, y + 20, GOLD, 3);
          this.tx(W / 2, y, items[i], 22, INK, "center", 0);
        } else {
          this.tx(W / 2, y, items[i], 22, CREAM, "center", 2);
        }
      }
      this.tx(W / 2, H - 40, "Klavye, Gamepad veya Dokunmatik Kontroller", 14, CREAM, "center", 2);
    } else if (this.state === "fight") {
      // Arkaplan
      this.rc(0, 0, W, H, "#e89446", 0, "");
      this.rc(0, GROUND, W, H, this.gcol, 4);

      this.boss.draw(this);
      for (const sh of this.shots) {
        this.ov(sh.x, sh.y, sh.r, sh.r, sh.pink ? PINK : RED, 2);
      }

      this.draw_player(this.p);

      for (const bl of this.bul) {
        this.ov(bl.x, bl.y, bl.r, bl.r, bl.ex ? GOLD : WHITE, 2);
      }

      // Parçacıklar
      for (const q of this.parts) {
        this.ov(q[0], q[1], q[7], q[7], q[6], 0, "");
      }

      // HUD
      this.rc(20, H - 50, 110, H - 18, CREAM, 3);
      this.tx(65, H - 34, `HP ${Math.max(0, this.p.hp)}`, 18, INK, "center", 0);

      // Kartlar
      for (let i = 0; i < 5; i++) {
        const x = 125 + i * 24;
        this.rc(x, H - 50, x + 18, H - 18, this.p.card >= i + 1 ? GOLD : WHITE, 2);
      }

      // Boss can barı
      const bFrac = clamp(this.boss.hp / this.boss.maxhp, 0, 1);
      this.rc(W / 2 - 200, 20, W / 2 + 200, 36, "#3a1515", 2);
      this.rc(W / 2 - 200, 20, W / 2 - 200 + 400 * bFrac, 36, RED, 0, "");
      this.tx(W / 2, 48, this.boss.name, 14, CREAM, "center", 2);

      if (this.intro > 0) {
        this.tx(W / 2, H / 2, this.intro > 40 ? "HAZIR OL!" : "DÖVÜŞ!", 64, GOLD, "center", 4);
      }

      if (this.ko > 0) {
        this.tx(W / 2, H / 2, "K.O.!", 90, GOLD, "center", 5);
      }

      if (this.p.hp <= 0) {
        this.tx(W / 2, H / 2 - 20, "ÖLDÜN!", 72, RED, "center", 4);
        this.tx(W / 2, H / 2 + 40, "Yeniden başlamak için Enter/Zıpla", 18, CREAM, "center", 2);
      }
    }

    ctx.restore();
  }

  loop() {
    this.update();
    this.draw();
    requestAnimationFrame(this.loop);
  }
}

window.addEventListener('DOMContentLoaded', () => {
  const canvas = document.getElementById('canvas');
  new WebGame(canvas);
});
