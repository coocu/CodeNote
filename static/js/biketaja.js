/* Progressive enhancement: every screenshot group remains visible without JavaScript. */
(() => {
  const filter = document.querySelector('.bike-filter');
  if (!filter) return;
  const buttons = Array.from(filter.querySelectorAll('[data-screen]'));
  const panels = buttons.map(button => document.getElementById(button.dataset.screen));
  if (panels.some(panel => !panel)) return;
  filter.hidden = false;
  filter.setAttribute('role', 'tablist');
  function select(index, focus = false) {
    buttons.forEach((button, i) => {
      const active = i === index;
      button.setAttribute('aria-selected', String(active));
      button.tabIndex = active ? 0 : -1;
      panels[i].hidden = !active;
    });
    if (focus) buttons[index].focus();
  }
  buttons.forEach((button, index) => {
    button.setAttribute('role', 'tab');
    button.setAttribute('aria-controls', panels[index].id);
    panels[index].setAttribute('role', 'tabpanel');
    panels[index].setAttribute('aria-labelledby', button.id);
    panels[index].tabIndex = 0;
    button.addEventListener('click', () => select(index));
    button.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % buttons.length;
      if (event.key === 'ArrowLeft') next = (index - 1 + buttons.length) % buttons.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = buttons.length - 1;
      if (next !== undefined) { event.preventDefault(); select(next, true); }
    });
  });
  select(0);
})();
