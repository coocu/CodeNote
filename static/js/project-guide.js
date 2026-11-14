/* Accessible platform selection; full guides remain readable without JavaScript. */
(() => {
  const tabs = Array.from(document.querySelectorAll('.platform-tab'));
  const panels = tabs.map(tab => document.querySelector(`.platform-panel[data-panel="${tab.dataset.platform}"]`));
  if (!tabs.length || panels.some(panel => !panel)) return;
  const list = tabs[0].parentElement;
  list.setAttribute('role', 'tablist');
  list.setAttribute('aria-label', '운영체제별 사용 안내');
  document.body.classList.add('pg-tabs-ready');
  function select(index, focus = false) {
    tabs.forEach((tab, i) => {
      const active = i === index;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      panels[i].classList.toggle('active', active);
      panels[i].hidden = !active;
    });
    if (focus) tabs[index].focus();
  }
  tabs.forEach((tab, i) => {
    tab.id = `platform-tab-${tab.dataset.platform}`;
    tab.setAttribute('role', 'tab');
    panels[i].id = `platform-panel-${tab.dataset.platform}`;
    tab.setAttribute('aria-controls', panels[i].id);
    panels[i].setAttribute('role', 'tabpanel');
    panels[i].setAttribute('aria-labelledby', tab.id);
    panels[i].tabIndex = 0;
    tab.addEventListener('click', () => select(i));
    tab.addEventListener('keydown', event => {
      let target;
      if (event.key === 'ArrowRight') target = (i + 1) % tabs.length;
      if (event.key === 'ArrowLeft') target = (i - 1 + tabs.length) % tabs.length;
      if (event.key === 'Home') target = 0;
      if (event.key === 'End') target = tabs.length - 1;
      if (target !== undefined) { event.preventDefault(); select(target, true); }
    });
  });
  select(Math.max(0, tabs.findIndex(tab => tab.classList.contains('active'))));
})();
