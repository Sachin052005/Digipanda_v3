/**
 * Custom dropdown menus for the 3 header pills (Date / Branch / Channel).
 * Native <select> popups can't centre their text on Windows, so this draws its
 * own centred list. The hidden <select> stays the source of truth: picking an
 * item sets select.value and fires 'change', so filters.js works unchanged.
 */
const PillDropdowns = (() => {
  let openMenu = null;

  const close = () => {
    if (!openMenu) return;
    openMenu.menu.remove();
    openMenu.pill.classList.remove('is-open');
    openMenu = null;
  };

  const open = (pill, select) => {
    close();
    const menu = document.createElement('div');
    menu.className = 'pill-menu';
    menu.setAttribute('role', 'listbox');
    Array.from(select.options).forEach(opt => {
      const item = document.createElement('button');
      item.type = 'button';
      item.className = 'pill-menu-item' + (opt.value === select.value ? ' is-selected' : '');
      item.setAttribute('role', 'option');
      item.textContent = opt.textContent;
      item.addEventListener('click', (e) => {
        e.stopPropagation();
        close();
        // set value + fire change inside the click so the date picker can still open
        if (opt.value === 'pick_date' || select.value !== opt.value) {
          select.value = opt.value;
          select.dispatchEvent(new Event('change', { bubbles: true }));
        }
      });
      menu.appendChild(item);
    });
    pill.appendChild(menu);
    pill.classList.add('is-open');
    openMenu = { pill, menu };
    const r = menu.getBoundingClientRect();
    if (r.right > window.innerWidth - 8) { menu.style.left = 'auto'; menu.style.right = '0'; }
    menu.querySelector('.is-selected')?.scrollIntoView({ block: 'nearest' });
  };

  const init = () => {
    document.querySelectorAll('.filter-pill').forEach(pill => {
      const select = pill.querySelector('select.pill-select-overlay');
      if (!select) return;
      select.tabIndex = -1;
      select.style.pointerEvents = 'none';
      pill.tabIndex = 0;
      pill.setAttribute('role', 'button');
      pill.setAttribute('aria-haspopup', 'listbox');
      pill.setAttribute('aria-label', select.getAttribute('aria-label') || 'Filter');
      const toggle = (e) => {
        if (e.target.closest('.pill-menu')) return;
        e.stopPropagation();
        openMenu && openMenu.pill === pill ? close() : open(pill, select);
      };
      pill.addEventListener('click', toggle);
      pill.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(e); }
      });
    });
    document.addEventListener('click', close);
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') close(); });
  };

  return { init, close };
})();
