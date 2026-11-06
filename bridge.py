# Browser compatibility layer for the original Tkinter game.
# The game.py source remains unchanged; this module supplies its Tk API in the browser.
import sys, types, json, os
from types import SimpleNamespace
from pyodide.ffi import create_proxy, to_js
from js import document, window

class TclError(Exception):
    pass

class CanvasAdapter:
    def __init__(self, root, **kwargs):
        self.root = root
        self.el = document.getElementById('game-canvas')
        root.canvas = self
        self.ctx = self.el.getContext('2d')
        self.width = int(kwargs.get('width', 960))
        self.height = int(kwargs.get('height', 540))
        try:
            self.dpr = min(3.0, max(1.0, float(window.devicePixelRatio or 1)))
        except Exception:
            self.dpr = 1.0
        self._resize_backing_store()
        self.items = []
        self.next_id = 1
        self.handlers = {}
        self.proxies = []
        self.flush()

    def _resize_backing_store(self):
        # Keep game coordinates at 960x540; use a denser backing buffer for crisp rendering.
        self.el.width = max(1, int(round(self.width * self.dpr)))
        self.el.height = max(1, int(round(self.height * self.dpr)))
        self.ctx.setTransform(self.dpr, 0, 0, self.dpr, 0, 0)

    def pack(self, **kwargs):
        return None

    def config(self, **kwargs):
        if 'width' in kwargs:
            self.width = max(1, int(kwargs['width']))
        if 'height' in kwargs:
            self.height = max(1, int(kwargs['height']))
        self._resize_backing_store()

    configure = config

    def _tags(self, opts):
        tags = opts.get('tags', ())
        if isinstance(tags, str): return (tags,)
        return tuple(tags or ())

    def _add(self, kind, coords, opts):
        item_id = self.next_id
        self.next_id += 1
        self.items.append({'id': item_id, 'kind': kind, 'coords': [float(x) for x in coords],
                           'opts': dict(opts), 'tags': self._tags(opts)})
        return item_id

    def create_rectangle(self, *coords, **opts): return self._add('rect', coords, opts)
    def create_oval(self, *coords, **opts): return self._add('oval', coords, opts)
    def create_polygon(self, *coords, **opts):
        if len(coords) == 1 and isinstance(coords[0], (list, tuple)): coords = tuple(coords[0])
        return self._add('poly', coords, opts)
    def create_line(self, *coords, **opts):
        if len(coords) == 1 and isinstance(coords[0], (list, tuple)): coords = tuple(coords[0])
        return self._add('line', coords, opts)
    def create_text(self, *coords, **opts): return self._add('text', coords, opts)

    def delete(self, target):
        if target == 'all': self.items = []; return
        self.items = [it for it in self.items if not (target == it['id'] or target in it['tags'])]

    def move(self, target, dx, dy):
        for it in self.items:
            if target == it['id'] or target in it['tags']:
                c = it['coords']
                for i in range(0, len(c)-1, 2): c[i] += float(dx); c[i+1] += float(dy)

    def tag_lower(self, tag, below=None):
        tagged = [it for it in self.items if tag in it['tags']]
        if not tagged: return
        self.items = [it for it in self.items if tag not in it['tags']]
        if below is None:
            self.items = tagged + self.items
            return
        idx = next((i for i,it in enumerate(self.items) if below in it['tags']), len(self.items))
        self.items[idx:idx] = tagged

    def bind(self, sequence, callback):
        self.handlers.setdefault(sequence, []).append(callback)
        def dispatch(ev):
            rect = self.el.getBoundingClientRect()
            x = (float(ev.clientX) - float(rect.left)) * self.width / max(1.0, float(rect.width))
            y = (float(ev.clientY) - float(rect.top)) * self.height / max(1.0, float(rect.height))
            delta = -1 if float(getattr(ev, 'deltaY', 0)) > 0 else 1
            e = SimpleNamespace(x=x, y=y, delta=delta)
            for cb in self.handlers.get(sequence, []): cb(e)
        event_name = None
        if sequence == '<Motion>': event_name = 'pointermove'
        elif sequence == '<MouseWheel>': event_name = 'wheel'
        elif sequence.startswith('<ButtonPress-'): event_name = 'pointerdown'
        elif sequence.startswith('<ButtonRelease-'): event_name = 'pointerup'
        if event_name:
            expected = None
            if 'ButtonPress-' in sequence or 'ButtonRelease-' in sequence:
                try: expected = int(sequence.split('-')[-1]) - 1
                except Exception: expected = None
            def filtered(ev):
                if expected is None or int(getattr(ev, 'button', -1)) == expected: dispatch(ev)
            proxy = create_proxy(filtered); self.proxies.append(proxy)
            self.el.addEventListener(event_name, proxy, False)
        return None

    def _style(self, opts):
        ctx = self.ctx
        ctx.lineWidth = max(0.1, float(opts.get('width', 1) or 1))
        ctx.lineCap = str(opts.get('capstyle', 'round'))
        ctx.lineJoin = str(opts.get('joinstyle', 'round'))
        dash = opts.get('dash')
        try: ctx.setLineDash(list(dash) if dash else [])
        except Exception: pass
        ctx.fillStyle = opts.get('fill') or 'rgba(0,0,0,0)'
        ctx.strokeStyle = opts.get('outline') or opts.get('fill') or '#000000'

    def flush(self):
        ctx = self.ctx
        if ctx is None: return
        ctx.clearRect(0, 0, self.width, self.height)
        for it in self.items:
            c, o, kind = it['coords'], it['opts'], it['kind']
            if len(c) < 2: continue
            self._style(o)
            ctx.beginPath()
            if kind == 'rect':
                x1,y1,x2,y2 = c[:4]
                ctx.rect(x1,y1,x2-x1,y2-y1)
                if o.get('fill'): ctx.fill()
                if o.get('outline'): ctx.stroke()
            elif kind == 'oval':
                x1,y1,x2,y2 = c[:4]
                ctx.ellipse((x1+x2)/2,(y1+y2)/2,abs(x2-x1)/2,abs(y2-y1)/2,0,0,6.283185307)
                if o.get('fill'): ctx.fill()
                if o.get('outline'): ctx.stroke()
            elif kind in ('poly','line'):
                smooth = bool(o.get('smooth')) and len(c) >= 6
                if smooth:
                    pts = [(c[i],c[i+1]) for i in range(0,len(c)-1,2)]
                    if kind == 'poly':
                        first = ((pts[-1][0]+pts[0][0])/2,(pts[-1][1]+pts[0][1])/2)
                        ctx.moveTo(*first)
                        for i,p in enumerate(pts):
                            nxt=pts[(i+1)%len(pts)]; mid=((p[0]+nxt[0])/2,(p[1]+nxt[1])/2)
                            ctx.quadraticCurveTo(p[0],p[1],mid[0],mid[1])
                        ctx.closePath()
                    else:
                        ctx.moveTo(*pts[0])
                        for i in range(1,len(pts)-1):
                            mid=((pts[i][0]+pts[i+1][0])/2,(pts[i][1]+pts[i+1][1])/2)
                            ctx.quadraticCurveTo(pts[i][0],pts[i][1],mid[0],mid[1])
                        ctx.lineTo(*pts[-1])
                else:
                    ctx.moveTo(c[0],c[1])
                    for i in range(2,len(c)-1,2): ctx.lineTo(c[i],c[i+1])
                    if kind == 'poly': ctx.closePath()
                if kind == 'poly':
                    if o.get('fill'): ctx.fill()
                    if o.get('outline'): ctx.stroke()
                elif o.get('fill') or o.get('outline'):
                    ctx.stroke()
            elif kind == 'text':
                text = str(o.get('text',''))
                font = o.get('font', ('Georgia', 12))
                if isinstance(font, (list,tuple)):
                    family = str(font[0]) if len(font)>0 else 'Georgia'
                    size = float(font[1]) if len(font)>1 else 12
                    bold = any(str(x).lower() in ('bold','heavy') for x in font[2:])
                    italic = any(str(x).lower() == 'italic' for x in font[2:])
                else:
                    family,size,bold,italic = 'Georgia',12,False,False
                ctx.font = ('italic ' if italic else '') + ('bold ' if bold else '') + f'{size}px "{family}"'
                anchor = str(o.get('anchor','center'))
                ctx.textAlign = 'left' if anchor.endswith('w') or anchor == 'w' else ('right' if anchor.endswith('e') or anchor == 'e' else 'center')
                ctx.textBaseline = 'top' if anchor.startswith('n') or anchor == 'n' else ('bottom' if anchor.startswith('s') or anchor == 's' else 'middle')
                ctx.fillStyle = o.get('fill') or '#000000'
                lines = text.split('\n')
                line_h = size * 1.16
                y = c[1] - (len(lines)-1)*line_h/2 if ctx.textBaseline == 'middle' else c[1]
                for line in lines:
                    ctx.fillText(line, c[0], y)
                    y += line_h

class RootAdapter:
    def __init__(self):
        self.timers = {}; self.next_timer = 1; self.handlers = {}; self.proxies = []
        self.canvas = None
    def title(self, *a): pass
    def resizable(self, *a): pass
    def configure(self, **a): pass
    def geometry(self, *a): pass
    def update_idletasks(self): pass
    def winfo_screenwidth(self): return int(window.innerWidth)
    def winfo_screenheight(self): return int(window.innerHeight)
    def attributes(self, name, value=None):
        if name == '-fullscreen':
            try:
                if value and not document.fullscreenElement: document.documentElement.requestFullscreen()
                elif not value and document.fullscreenElement: document.exitFullscreen()
            except Exception: pass
    def bind(self, sequence, callback):
        self.handlers[sequence] = callback
        if sequence in ('<KeyPress>','<KeyRelease>'):
            down = sequence == '<KeyPress>'
            def dispatch(ev):
                k = str(ev.key)
                mapping = {'ArrowLeft':'left','ArrowRight':'right','ArrowUp':'up','ArrowDown':'down',
                           ' ':'space','Shift':'shift_l','Control':'control_l','Alt':'alt_l',
                           'Enter':'return','Escape':'escape','Tab':'tab','Backspace':'backspace',
                           'Delete':'delete','CapsLock':'caps_lock'}
                key = mapping.get(k, k.lower() if len(k)==1 else k.lower())
                if key in ('space','left','right','up','down','tab','escape') or len(key)==1 or key in ('shift_l','control_l','alt_l'):
                    try: ev.preventDefault()
                    except Exception: pass
                callback(SimpleNamespace(keysym=key))
            proxy = create_proxy(dispatch); self.proxies.append(proxy)
            window.addEventListener('keydown' if down else 'keyup', proxy)
        elif sequence == '<FocusOut>':
            proxy = create_proxy(lambda ev: callback(SimpleNamespace())); self.proxies.append(proxy)
            window.addEventListener('blur', proxy)
    def after(self, ms, callback):
        ident = self.next_timer; self.next_timer += 1
        holder = {}
        def run():
            self.timers.pop(ident, None)
            try:
                callback()
                if self.canvas: self.canvas.flush()
            except Exception as exc:
                document.getElementById('error').textContent = 'Oyun hatası: ' + str(exc)
                raise
            finally:
                if holder.get('proxy') is not None: holder['proxy'].destroy()
        proxy = create_proxy(run)
        holder['proxy'] = proxy
        timer = window.setTimeout(proxy, max(1,int(ms)))
        self.timers[ident] = (timer,proxy)
        return ident
    def after_cancel(self, ident):
        item = self.timers.pop(ident, None)
        if item:
            window.clearTimeout(item[0]); item[1].destroy()
    def destroy(self):
        for timer,proxy in list(self.timers.values()):
            window.clearTimeout(timer); proxy.destroy()
        self.timers.clear()
    def mainloop(self): pass

# Make the unchanged source's `import tkinter as tk` resolve to the browser adapter.
tk = types.ModuleType('tkinter')
tk.TclError = TclError
tk.Tk = RootAdapter
tk.Canvas = CanvasAdapter
sys.modules['tkinter'] = tk

# JavaScript entry point uses this to create and start the original Game class.
def start_original_game(source):
    ns = {'__name__':'caycik_web_game', '__file__':'/caycik/game.py'}
    # These imports are only used by the desktop audio backend; browser audio is supplied separately.
    desktop_only = {'import io','import wave','import struct','import sys','import subprocess','import tempfile','import shutil','import atexit','import threading','from array import array'}
    browser_source = '\n'.join(line for line in source.splitlines() if line.strip() not in desktop_only)
    exec(compile(browser_source, '/caycik/game.py', 'exec'), ns)
    os.makedirs('/caycik', exist_ok=True)
    OriginalSfx = ns['Sfx']
    class BrowserSfx:
        SR = OriginalSfx.SR
        def __init__(self):
            self.on=True; self.music_on=True; self.want=None; self.cur=None
            self.tracks={}; self.SR=OriginalSfx.SR
        def synth(self, parts, slow=False):
            return OriginalSfx.synth(self, parts, False)
        def compose(self, name):
            return OriginalSfx.compose(self, name)
        def play(self, key):
            if self.on:
                try: window.caycikPlaySfx(str(key))
                except Exception: pass
        def set_music(self, track): self.want=track
        def stop_music(self):
            try: window.caycikStopMusic()
            except Exception: pass
            self.cur=None
        def tick(self):
            target=self.want if self.music_on else None
            if target == self.cur: return
            self.stop_music()
            if target:
                try:
                    if target not in self.tracks: self.tracks[target]=self.compose(target)
                    window.caycikPlayMusic(to_js(self.tracks[target]))
                    self.cur=target
                except Exception: self.cur=None
        def close(self): self.stop_music()
    ns['Sfx'] = BrowserSfx
    Game = ns['Game']
    Game.load = lambda self: _load_save(ns)
    original_store = Game.store
    def store(self):
        original_store(self)
        try:
            with open(ns['SAVE'], 'r', encoding='utf-8') as f:
                window.localStorage.setItem('caycik_kayit', f.read())
        except Exception: pass
    Game.store = store
    root = RootAdapter()
    game = Game(root)
    root.canvas.flush()
    return game

def _load_save(ns):
    d = {}
    try:
        raw = window.localStorage.getItem('caycik_kayit')
        if raw: d = json.loads(str(raw))
    except Exception: d = {}
    # Keep the original save migration and defaults intact.
    d.setdefault('unlocked',1); d.setdefault('grades',{}); d.setdefault('times',{})
    if d.get('ver') != 2:
        d['unlocked']=1; d['grades']={}; d['times']={}; d['coins']={}; d['ver']=2
    d.setdefault('coins',{})
    if not isinstance(d.get('settings'),dict): d['settings']={}
    st=d['settings']
    defaults=ns['DEFAULT_SETTINGS']
    for k,v in defaults.items():
        if k not in st: st[k]=list(v) if isinstance(v,list) else v
    if not isinstance(st.get('diff'),list): st['diff']=[]
    st['diff']=(list(st['diff'])+[1]*len(ns['LEVELS']))[:len(ns['LEVELS'])]
    st['diff']=[ns['clamp'](int(x),0,2) if isinstance(x,int) else 1 for x in st['diff']]
    if not isinstance(st.get('binds'),dict): st['binds']={}
    for a,v in ns['DEFAULT_BINDS'].items():
        b=st['binds'].get(a)
        if not (isinstance(b,list) and len(b)==2): st['binds'][a]=list(v)
    return d
