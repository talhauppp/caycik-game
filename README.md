# 🍵 ÇAYCIK: Boss Savaşı

> 1930'lar çizgi film tarzında, Cuphead'den esinlenen 2D boss savaşı oyunu.

**🎮 [Hemen Oyna →](https://kullaniciadi.github.io/caycik)**

---

## Özellikler

- 🏆 **12 Bölüm** — Boss savaşları + Koş & Ateş bölümleri
- 🐸 **4 Boss** — Kurbağa Kral, Sihirbaz Tavşan, Kar Adam Kral, Kral Arı, Zaman Efendisi
- ⭐ **Not sistemi** — S / A / B / C / D dereceleri
- 🎮 **Kontrolcü desteği** — Xbox ve PlayStation
- 📱 **Mobil uyumlu** — Dokunmatik kontroller
- 💾 **İlerleme kaydı** — localStorage ile otomatik kayıt

## Kontroller

| Eylem | Klavye | Kontrolcü | Mobil |
|-------|--------|-----------|-------|
| Koş | A/D veya ←/→ | Sol analog / D-Pad | ←/→ buton |
| Zıpla | Space / Z | A / Cross | ⬆ buton |
| Ateş | X / J | X / Square | 🔴 buton |
| Dash | Shift / C | B / Circle | ⚡ buton |
| EX Atışı | Q / E | RB / R1 | ✨ buton |
| Duraklat | Esc / P | Start | — |

> **PARRY:** Havadayken pembe bir nesneye tekrar zıpla → 1 EX kartı kazan!

## Zorluk Seviyeleri

| Zorluk | Can | Boss HP | Açıklama |
|--------|-----|---------|----------|
| 🟢 Kolay | 5 | %70 | Boss daha zayıf ve yavaş, en yüksek not B |
| 🟡 Normal | 3 | %100 | Standart savaş |
| 🔴 Zor | 2 | %130 | Boss güçlü ve hızlı, +5 puan bonusu |

## Yerel Geliştirme

Sadece `web/index.html` dosyasını tarayıcıda aç. Sunucu gerekmez.

```bash
git clone https://github.com/kullaniciadi/caycik
cd caycik/web
# index.html'i tarayıcıda aç
```

## GitHub Pages Yayınlama

1. Repo'ya git → **Settings** → **Pages**
2. Source: `Deploy from a branch`
3. Branch: `main`, Klasör: `/web`
4. **Save** → Birkaç dakika sonra yayında!

## Teknolojiler

- **HTML5 Canvas** — Çizim motoru
- **Vanilla JavaScript** — Oyun mantığı (framework yok)
- **Web Audio API** — Prosedürel ses efektleri
- **Gamepad API** — Kontrolcü desteği
- **Touch Events** — Mobil kontroller
- **localStorage** — İlerleme kaydı

---

*Python/tkinter versiyonu: `caycik_boss_savasi2.py`*
