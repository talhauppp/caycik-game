// Mobil dokunmatik kontrolleri klavye olaylarına köprüler
(function() {
  function dispatchKey(code, type) {
    const keyMap = {
      'ArrowLeft': 'ArrowLeft',
      'ArrowRight': 'ArrowRight',
      'Space': ' ',
      'KeyX': 'x',
      'ShiftLeft': 'Shift',
      'KeyQ': 'q'
    };
    const key = keyMap[code] || code;
    const event = new KeyboardEvent(type, {
      code: code,
      key: key,
      bubbles: true,
      cancelable: true
    });
    window.dispatchEvent(event);
  }

  function bindTouchButton(btn) {
    const code = btn.dataset.key;
    if (!code) return;

    let pressed = false;

    const startPress = (e) => {
      e.preventDefault();
      if (!pressed) {
        pressed = true;
        btn.classList.add('active');
        dispatchKey(code, 'keydown');
      }
    };

    const endPress = (e) => {
      e.preventDefault();
      if (pressed) {
        pressed = false;
        btn.classList.remove('active');
        dispatchKey(code, 'keyup');
      }
    };

    btn.addEventListener('touchstart', startPress, { passive: false });
    btn.addEventListener('touchend', endPress, { passive: false });
    btn.addEventListener('touchcancel', endPress, { passive: false });

    btn.addEventListener('mousedown', startPress);
    btn.addEventListener('mouseup', endPress);
    btn.addEventListener('mouseleave', endPress);
  }

  window.addEventListener('DOMContentLoaded', () => {
    const buttons = document.querySelectorAll('#mobile-controls button');
    buttons.forEach(bindTouchButton);
  });
})();
