CAYCIK: BOSS SAVASI — TAM WEB PAKETI

Dosyalar:
- index.html : Oyun sayfasi, yukleme ekrani, dokunmatik kontroller ve gamepad destegi
- bridge.py  : Tarayici/Tk uyumluluk katmani; yuksek DPI canvas cizimi
- game.py    : Orijinal Python oyununun tam kaynak kodu
- favicon.svg: Sekme simgesi

GITHUB PAGES KURULUMU:
1. ZIP'i cikart.
2. Bu dort dosyayi GitHub deposunun ana klasorune yukle.
3. Dosya adlari tam olarak index.html, bridge.py, game.py ve favicon.svg olmali.
4. Commit/push yap ve GitHub Pages'in yayinlamasini bekle.
5. Siteyi Ctrl+F5 ile yenile.

OYUN KOLU:
- Sol analog / D-pad: hareket
- A / Cross: zipla
- B / Circle: oyun sirasinda dash, menulerde geri
- X / Square veya RT: ates
- Y / Triangle veya LT: EX
- LB / L1: onceki silah
- RB / R1: sonraki silah
- Start: duraklat / devam

Mobil cihazda oyun kolu baglaninca dokunmatik tuslar gizlenir; kol ayrilinca geri gelir.
Tarayicinin oyun kolunu algilamasi icin baglandiktan sonra bir tusa basmaniz gerekebilir.

Goruntu netligi icin oyun mantiginin 960x540 koordinat sistemi korunur; canvas ekranda cihaz piksel oranina gore
daha yuksek cozunurlukte cizilir. Bu, oyunun ic mantigini degistirmez.
