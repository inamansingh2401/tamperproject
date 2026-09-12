'use strict';
// Previous versions persisted login tokens indefinitely. Expire those sessions once.
for (const key of ['safetrack_access_token', 'safetrack_role', 'safetrack_username', 'safetrack_assigned_shipments']) {
  localStorage.removeItem(key);
}
window.fetchWithTimeout = async (url, options = {}) => {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 65000);
  try { return await fetch(url, { ...options, signal: options.signal || controller.signal }); }
  finally { clearTimeout(timeout); }
};
// Use at HTML interpolation sites; API data remains unmodified for forms and JSON.
window.escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, char =>
  ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[char]));
window.escapeJSString = value => String(value ?? '').replace(/[\\'"<>&\r\n\u2028\u2029]/g,
  char => '\\u' + char.charCodeAt(0).toString(16).padStart(4, '0'));

document.addEventListener('DOMContentLoaded', () => {
  // Only this explicit allowlist can be dispatched from generated markup.
  const actions = new Set(['openVehicleSettings', 'resolveSingleAlert', 'openEditUserModal',
    'toggleUserStatus', 'inspectShipment', 'openEditShipmentModal', 'deleteShipmentHandler',
    'editShipment', 'removeShipment']);
  document.addEventListener('click', event => {
    const control = event.target.closest('[data-action]');
    if (!control || !actions.has(control.dataset.action)) return;
    const handler = window[control.dataset.action];
    if (typeof handler !== 'function') return;
    const numeric = ['openEditUserModal', 'toggleUserStatus'].includes(control.dataset.action);
    handler(numeric ? Number(control.dataset.value) : control.dataset.value);
  });
  if (document.getElementById('monitor')) document.body.classList.add('live-page');
  document.querySelectorAll('.table-responsive, .overflow-x-auto, .wide').forEach(region => {
    if (!region.querySelector('table')) return;
    region.tabIndex = 0;
    region.setAttribute('role', 'region');
    region.setAttribute('aria-label', 'Data table. Scroll horizontally for more columns.');
  });
  const sidebar = document.getElementById('sidebar');
  if (!sidebar) return;
  document.body.classList.add('has-sidebar');
  const main = document.querySelector('main');
  const header = main?.querySelector('header');
  if (!header) return;
  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.className = 'mobile-menu-toggle';
  toggle.textContent = '☰ Menu';
  toggle.setAttribute('aria-controls', 'sidebar');
  toggle.setAttribute('aria-expanded', 'false');
  header.prepend(toggle);
  const close = document.createElement('button');
  close.type = 'button';
  close.className = 'mobile-menu-close';
  close.textContent = 'Close menu ×';
  sidebar.prepend(close);
  const backdrop = document.createElement('button');
  backdrop.type = 'button';
  backdrop.className = 'mobile-backdrop';
  backdrop.hidden = true;
  backdrop.tabIndex = -1;
  backdrop.setAttribute('aria-label', 'Close navigation');
  document.body.append(backdrop);
  const smallScreen = matchMedia('(max-width: 1023px)');
  let restoreFocus = null;
  function setOpen(open, returnFocus = true) {
    open = Boolean(open && smallScreen.matches);
    if (open) restoreFocus = document.activeElement;
    document.body.classList.toggle('nav-open', open);
    toggle.setAttribute('aria-expanded', String(open));
    backdrop.hidden = !open;
    sidebar.inert = smallScreen.matches && !open;
    main.inert = open;
    if (open) close.focus();
    else if (returnFocus && restoreFocus) { restoreFocus.focus(); restoreFocus = null; }
  }
  toggle.addEventListener('click', () => setOpen(true));
  close.addEventListener('click', () => setOpen(false));
  backdrop.addEventListener('click', () => setOpen(false));
  sidebar.addEventListener('click', event => {
    if (event.target.closest('a')) setOpen(false);
  });
  document.addEventListener('keydown', event => {
    if (!document.body.classList.contains('nav-open')) return;
    if (event.key === 'Escape') { event.preventDefault(); setOpen(false); }
    if (event.key === 'Tab') {
      const items = [...sidebar.querySelectorAll('a[href],button,input,select,[tabindex="0"]')]
        .filter(item => !item.disabled && item.getClientRects().length);
      const first = items[0], last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  smallScreen.addEventListener('change', () => setOpen(false, false));
  setOpen(false, false);
});
