// Gamepad (Xbox, PlayStation vb.) API köprüsü
(function() {
  const gpState = {
    left: false,
    right: false,
    up: false,
    down: false,
    jump: false,
    shoot: false,
    dash: false,
    ex: false,
    start: false
  };

  function sendKey(code, key, isDown) {
    const event = new KeyboardEvent(isDown ? 'keydown' : 'keyup', {
      code: code,
      key: key,
      bubbles: true,
      cancelable: true
    });
    window.dispatchEvent(event);
  }

  function updateGamepad() {
    const gamepads = navigator.getGamepads ? navigator.getGamepads() : [];
    let gp = null;
    for (let i = 0; i < gamepads.length; i++) {
      if (gamepads[i]) {
        gp = gamepads[i];
        break;
      }
    }

    if (gp) {
      const axisX = gp.axes[0] || 0;
      const axisY = gp.axes[1] || 0;

      // D-Pad veya Analog
      const left = axisX < -0.45 || (gp.buttons[14] && gp.buttons[14].pressed);
      const right = axisX > 0.45 || (gp.buttons[15] && gp.buttons[15].pressed);
      const up = axisY < -0.45 || (gp.buttons[12] && gp.buttons[12].pressed);
      const down = axisY > 0.45 || (gp.buttons[13] && gp.buttons[13].pressed);

      // Butonlar: A/Cross -> Jump, X/Square -> Shoot, B/Circle -> Dash, RB/R1 -> EX, Start -> Pause
      const jump = (gp.buttons[0] && gp.buttons[0].pressed);
      const dash = (gp.buttons[1] && gp.buttons[1].pressed);
      const shoot = (gp.buttons[2] && gp.buttons[2].pressed);
      const ex = (gp.buttons[5] && gp.buttons[5].pressed);
      const start = (gp.buttons[9] && gp.buttons[9].pressed);

      if (left !== gpState.left) { gpState.left = left; sendKey('ArrowLeft', 'ArrowLeft', left); }
      if (right !== gpState.right) { gpState.right = right; sendKey('ArrowRight', 'ArrowRight', right); }
      if (up !== gpState.up) { gpState.up = up; sendKey('ArrowUp', 'ArrowUp', up); }
      if (down !== gpState.down) { gpState.down = down; sendKey('ArrowDown', 'ArrowDown', down); }
      if (jump !== gpState.jump) { gpState.jump = jump; sendKey('Space', ' ', jump); }
      if (shoot !== gpState.shoot) { gpState.shoot = shoot; sendKey('KeyX', 'x', shoot); }
      if (dash !== gpState.dash) { gpState.dash = dash; sendKey('ShiftLeft', 'Shift', dash); }
      if (ex !== gpState.ex) { gpState.ex = ex; sendKey('KeyQ', 'q', ex); }
      if (start !== gpState.start) { gpState.start = start; sendKey('Escape', 'Escape', start); }
    }

    requestAnimationFrame(updateGamepad);
  }

  window.addEventListener('gamepadconnected', () => {
    requestAnimationFrame(updateGamepad);
  });
})();
