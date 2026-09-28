'use strict';

const API_BASE_URL = 'https://safetrack-api-live.vercel.app';
const TOKEN_KEY = 'safetrack_access_token';
const ROLE_KEY = 'safetrack_role';
const USER_KEY = 'safetrack_username';
const ASSIGNMENTS_KEY = 'safetrack_assigned_shipments';
const LIVE_POLL_MS = 500;
const SHARED_LOGIN = document.documentElement.dataset.sharedLogin || '';

let authToken = sessionStorage.getItem(TOKEN_KEY);
let assignedShipments = [];
let currentShipmentCode = null;
let latestEventId = null;
let liveTimer = null;
let snapshotLoading = false;
let liveLoading = false;
let currentAlerts = [];
let latestLedgerEvent = null;

const $ = id => document.getElementById(id);
const escapeValue = value => window.escapeHTML
  ? window.escapeHTML(value)
  : String(value ?? '').replace(/[&<>"']/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[char]));

document.addEventListener('DOMContentLoaded', () => {
  bindInterface();
  refreshIcons();
  restoreSession();
});

function bindInterface() {
  $('loginForm')?.addEventListener('submit', handleLogin);
  $('logoutBtn')?.addEventListener('click', logout);
  $('retryBtn')?.addEventListener('click', () => loadSnapshot());
  $('shipmentSelector')?.addEventListener('change', event => selectShipment(event.target.value));
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && authToken && currentShipmentCode) loadSnapshot({ quiet: true });
  });
  window.addEventListener('online', () => loadSnapshot({ quiet: true }));
  window.addEventListener('offline', () => setConnectionState('offline', 'Offline', 'Showing the last received data'));

  window.addEventListener('hashchange', () => setActiveNavigation(location.hash));
  setActiveNavigation(location.hash);

}

function restoreSession() {
  const role = sessionStorage.getItem(ROLE_KEY);
  const username = sessionStorage.getItem(USER_KEY);
  try { assignedShipments = JSON.parse(sessionStorage.getItem(ASSIGNMENTS_KEY) || '[]'); }
  catch (_) { assignedShipments = []; }
  if (!Array.isArray(assignedShipments)) assignedShipments = [];
  if (SHARED_LOGIN && authToken && role === 'admin') return window.location.replace('../index.html');
  if (!authToken || role !== 'user' || !username) return showLogin();

  currentShipmentCode = assignedShipments[0] || null;
  showDashboard(username);
  populateShipmentSelector();
  if (currentShipmentCode) loadSnapshot();
  else renderUnassignedState();
}

async function handleLogin(event) {
  event.preventDefault();
  const username = $('loginUser').value.trim();
  const password = $('loginPin').value;
  const button = $('loginButton');
  $('loginError').textContent = '';
  button.disabled = true;
  button.querySelector('span').textContent = 'Verifying…';

  try {
    const response = await window.fetchWithTimeout(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || 'Invalid username or password.');
    if (data.role !== 'user') throw new Error('Use a user account to access this shipment portal.');

    authToken = data.access_token;
    assignedShipments = Array.isArray(data.assigned_shipments) ? data.assigned_shipments : [];
    currentShipmentCode = assignedShipments[0] || data.shipment_code || null;
    sessionStorage.setItem(TOKEN_KEY, authToken);
    sessionStorage.setItem(ROLE_KEY, data.role);
    sessionStorage.setItem(USER_KEY, data.username || username);
    sessionStorage.setItem(ASSIGNMENTS_KEY, JSON.stringify(assignedShipments));
    $('loginPin').value = '';
    showDashboard(data.username || username);
    populateShipmentSelector();
    if (currentShipmentCode) await loadSnapshot();
    else renderUnassignedState();
  } catch (error) {
    $('loginError').textContent = error.name === 'AbortError' ? 'The server took too long to respond. Try again.' : error.message;
  } finally {
    button.disabled = false;
    button.querySelector('span').textContent = 'Open dashboard';
  }
}

function showLogin() {
  if (SHARED_LOGIN) { window.location.replace(SHARED_LOGIN); return; }
  $('loginScreen').hidden = false;
  $('appShell').hidden = true;
}

function showDashboard(username) {
  $('loginScreen').hidden = true;
  $('appShell').hidden = false;
  $('headerUserName').textContent = username;
  $('userInitials').textContent = initials(username);
  refreshIcons();
}

function logout() {
  stopPolling();
  authToken = null;
  assignedShipments = [];
  currentShipmentCode = null;
  [TOKEN_KEY, ROLE_KEY, USER_KEY, ASSIGNMENTS_KEY].forEach(key => sessionStorage.removeItem(key));
  window.location.reload();
}

function populateShipmentSelector() {
  const select = $('shipmentSelector');
  select.replaceChildren();
  if (!assignedShipments.length) {
    const option = new Option('No shipment assigned', '');
    select.add(option);
    select.disabled = true;
    return;
  }
  select.disabled = false;
  assignedShipments.forEach(code => select.add(new Option(code, code)));
  select.value = currentShipmentCode || assignedShipments[0];
}

function selectShipment(code) {
  if (!assignedShipments.includes(code) || code === currentShipmentCode) return;
  currentShipmentCode = code;
  latestEventId = null;
  currentAlerts = [];
  latestLedgerEvent = null;
  resetDashboardLoading();
  loadSnapshot();
  location.hash = 'overview';
  setActiveNavigation('#overview');
}

async function loadSnapshot({ quiet = false } = {}) {
  if (!authToken || !currentShipmentCode || snapshotLoading) return;
  snapshotLoading = true;
  const requestedCode = currentShipmentCode;
  if (!quiet) setConnectionState('connecting', 'Connecting', 'Retrieving shipment data');
  try {
    const response = await api(`/api/shipments/${encodeURIComponent(requestedCode)}`);
    if (requestedCode !== currentShipmentCode) return;
    const data = await response.json();
    currentAlerts = Array.isArray(data.alerts) ? data.alerts : [];
    const events = Array.isArray(data.events) ? data.events : [];
    const latest = data.latest_telemetry || events[0] || null;
    latestLedgerEvent = events[0] || latest;
    latestEventId = eventKey(latest);
    renderShipment(data.shipment || {});
    renderTelemetry(latest);
    renderIntegrity(data.shipment || {}, latest, currentAlerts);
    renderAlerts(currentAlerts);
    renderEvents(events);
    renderLocation(data.shipment || {}, latest);
    hideError();
    updateReceipt(latest?.created_at);
    startPolling();
  } catch (error) {
    handleRequestError(error, quiet);
  } finally {
    snapshotLoading = false;
  }
}

async function pollLive() {
  if (!authToken || !currentShipmentCode || liveLoading || snapshotLoading || document.hidden) return;
  liveLoading = true;
  const requestedCode = currentShipmentCode;
  try {
    const response = await api(`/api/shipments/${encodeURIComponent(requestedCode)}/live`);
    if (requestedCode !== currentShipmentCode) return;
    const data = await response.json();
    const latest = data.latest_telemetry || null;
    renderShipment(data.shipment || {});
    renderTelemetry(latest);
    renderIntegrity(data.shipment || {}, latest, currentAlerts);
    renderLocation(data.shipment || {}, latest);
    updateReceipt(latest?.created_at);
    hideError();
    const nextEventId = eventKey(latest);
    if (nextEventId && latestEventId && nextEventId !== latestEventId) {
      latestEventId = nextEventId;
      queueMicrotask(() => loadSnapshot({ quiet: true }));
    } else if (nextEventId) {
      latestEventId = nextEventId;
    }
  } catch (error) {
    handleRequestError(error, true);
  } finally {
    liveLoading = false;
  }
}

async function api(path) {
  const response = await window.fetchWithTimeout(`${API_BASE_URL}${path}`, {
    headers: { Authorization: `Bearer ${authToken}` },
    cache: 'no-store'
  });
  if (response.status === 401 || response.status === 403) {
    logout();
    throw new Error('Your session has expired.');
  }
  if (!response.ok) throw new Error(`Shipment service returned ${response.status}.`);
  return response;
}

function startPolling() {
  stopPolling();
  liveTimer = window.setInterval(pollLive, LIVE_POLL_MS);
}

function stopPolling() {
  if (liveTimer) window.clearInterval(liveTimer);
  liveTimer = null;
}

function handleRequestError(error, quiet) {
  console.error(error);
  const message = error.name === 'AbortError' ? 'The shipment service timed out.' : error.message || 'Live data is temporarily unavailable.';
  showError(message);
  setConnectionState('offline', 'Connection interrupted', quiet ? 'Last received data remains visible' : 'Unable to load shipment');
}

function renderShipment(shipment) {
  const status = shipment.status || 'Registered';
  setText('shipmentTitle', shipment.title || 'Protected shipment');
  setText('shipmentCode', shipment.code || shipment.id || currentShipmentCode || '—');
  setText('vehicleName', shipment.vehicle_registration || shipment.vehicle_name || shipment.vehicle_id || 'Vehicle not assigned');
  setText('originValue', shipment.origin || 'Not available');
  setText('destinationValue', shipment.destination || 'Not available');
  setText('currentLocation', shipment.current_warehouse || 'Location not available');
  setText('etaValue', shipment.estimated_delivery || 'Not provided');

  const badge = $('shipmentStatus');
  badge.textContent = status;
  badge.className = `status-badge ${statusClass(status)}`;
  renderJourney(status);
}

function renderJourney(status) {
  const normalized = String(status || '').toLowerCase();
  let active = 0;
  if (normalized.includes('deliver') && !normalized.includes('out')) active = 3;
  else if (normalized.includes('out') || normalized.includes('last mile')) active = 2;
  else if (normalized.includes('transit') || normalized.includes('route')) active = 1;

  document.querySelectorAll('#journeyTrack li').forEach((item, index) => {
    item.classList.toggle('done', index < active || (active === 3 && index === 3));
    item.classList.toggle('active', index === active && active !== 3);
  });
  const desktopProgress = active === 0 ? 0 : (active / 3) * 86;
  const mobileProgress = active === 0 ? 0 : (active / 3) * 100;
  $('journeyTrack').style.setProperty('--journey-progress', `${desktopProgress}%`);
  $('journeyTrack').style.setProperty('--journey-mobile-progress', `${mobileProgress}%`);
  setText('routeProgressLabel', `Stage ${active + 1} of 4`);
}

function renderTelemetry(reading) {
  window.SafeTrackParcel?.update(reading);
  if (!reading) {
    ['temperatureValue','humidityValue','lightValue','accelerationValue','orientationValue'].forEach(id => setText(id, '—'));
    return;
  }

  const temperature = finite(reading.temperature);
  const humidity = finite(reading.humidity);
  const light = finite(reading.light_lux);
  const acceleration = finite(reading.accel_g);
  const pitch = finite(reading.pitch);
  const roll = finite(reading.roll);

  setMetric('temperature', temperature, value => value.toFixed(1), temperature == null ? 'Waiting' : temperature > 15 ? 'Critical' : temperature > 8 || temperature < 2 ? 'Warning' : 'In range', temperature == null ? 'neutral' : temperature > 15 ? 'danger' : temperature > 8 || temperature < 2 ? 'warning' : 'good', scale(temperature, -5, 25));
  setMetric('humidity', humidity, value => value.toFixed(0), humidity == null ? 'Waiting' : humidity < 40 || humidity > 60 ? 'Review' : 'In range', humidity == null ? 'neutral' : humidity < 30 || humidity > 70 ? 'danger' : humidity < 40 || humidity > 60 ? 'warning' : 'good', scale(humidity, 0, 100));
  setMetric('light', light, value => value.toFixed(0), light == null ? 'Waiting' : light >= 800 ? 'Seal exposed' : 'Seal protected', light == null ? 'neutral' : light >= 800 ? 'danger' : 'good', scale(light, 0, 1200));
  setMetric('acceleration', acceleration, value => value.toFixed(2), acceleration == null ? 'Waiting' : acceleration >= 3 ? 'Impact detected' : 'Normal motion', acceleration == null ? 'neutral' : acceleration >= 3 ? 'danger' : 'good', scale(acceleration, 0, 5));

  const orientationKnown = reading.mpu_read_ok !== false && (pitch != null || roll != null);
  const maxTilt = Math.max(Math.abs(pitch || 0), Math.abs(roll || 0));
  const orientationLabel = !orientationKnown ? 'Unavailable' : maxTilt > 60 ? 'Package tilted' : maxTilt > 25 ? 'Tilt detected' : 'Stable / upright';
  const orientationTone = !orientationKnown ? 'neutral' : maxTilt > 60 ? 'danger' : maxTilt > 25 ? 'warning' : 'good';
  setText('orientationValue', orientationLabel);
  setText('orientationState', !orientationKnown ? 'No MPU reading' : orientationTone === 'good' ? 'Stable' : 'Review');
  if ($('orientationState')) $('orientationState').className = `metric-state ${orientationTone}`;
  setText('orientationDetail', `Pitch ${formatAngle(pitch)} · Roll ${formatAngle(roll)}`);
  $('axisBox')?.style.setProperty('--pitch', `${clamp(pitch || 0, -55, 55)}deg`);
  $('axisBox')?.style.setProperty('--roll', `${clamp(roll || 0, -55, 55)}deg`);
}

function setMetric(name, value, format, label, tone, marker) {
  setText(`${name}Value`, value == null ? '—' : format(value));
  setText(`${name}State`, label);
  $(`${name}State`).className = `metric-state ${tone}`;
  $(`${name}Marker`).style.left = `${marker}%`;
}

function renderIntegrity(shipment, latest, alerts) {
  const sealBreached = String(shipment.seal_status || '').toLowerCase().includes('breach') || finite(latest?.light_lux) >= 800;
  const criticalAlert = alerts.some(alert => String(alert.status).toLowerCase() === 'active' && String(alert.severity).toLowerCase().includes('critical'));
  const activeAlerts = alerts.filter(alert => String(alert.status).toLowerCase() === 'active');
  const degraded = String(shipment.health_level || '').toLowerCase().includes('degrad') || activeAlerts.length > 0;
  const ledgerEvent = latest?.record_hash ? latest : latestLedgerEvent;
  const hasLedger = Boolean(ledgerEvent?.record_hash);

  let state = 'verified';
  let title = hasLedger ? 'Integrity verified' : 'Shipment is being monitored';
  let message = hasLedger ? 'The latest signed reading was accepted and linked to the tamper-evident event ledger.' : 'Live shipment data is available; a ledger hash has not been returned yet.';
  let icon = 'shield-check';
  let eyebrow = 'VERIFIED CHAIN OF CUSTODY';
  if (sealBreached || criticalAlert) {
    state = 'critical'; title = 'Integrity action required'; message = 'A critical condition or container exposure has been detected. Review the active alert before accepting custody.'; icon = 'shield-alert'; eyebrow = 'CRITICAL SECURITY STATE';
  } else if (degraded) {
    state = 'warning'; title = 'Shipment needs attention'; message = 'An active warning is recorded for this shipment. The custody ledger remains available for review.'; icon = 'triangle-alert'; eyebrow = 'SECURITY WARNING';
  } else if (!latest) {
    state = 'monitoring'; title = 'Awaiting verified event'; message = 'TrackSure is connecting to the shipment’s secure event stream.'; icon = 'shield'; eyebrow = 'SECURITY MONITORING';
  }

  $('integrityCard').className = `integrity-card state-${state}`;
  $('integrityIcon').setAttribute('data-lucide', icon);
  setText('integrityEyebrow', eyebrow);
  setText('integrityStatus', title);
  setText('integrityMessage', message);
  setText('cryptoStatus', hasLedger ? 'Gateway verified · ledger linked' : 'Awaiting ledger record');
  setText('sealStatus', sealBreached ? 'Breach detected' : shipment.seal_status || 'Intact');
  setText('deviceIdentity', latest?.device_id || ledgerEvent?.device_id || 'Awaiting device');
  refreshIcons();
}

function renderAlerts(alerts) {
  const active = alerts.filter(alert => String(alert.status).toLowerCase() === 'active');
  setText('alertCount', `${active.length} active`);
  $('alertCount').className = `count-badge${active.length ? ' has-alerts' : ''}`;
  if (!active.length) {
    $('alertsList').innerHTML = `<div class="empty-state compact"><i data-lucide="shield-check"></i><span><strong>No active alerts</strong><small>Current conditions are within recorded limits.</small></span></div>`;
    refreshIcons();
    return;
  }
  $('alertsList').innerHTML = active.slice(0, 3).map(alert => {
    const critical = String(alert.severity || '').toLowerCase().includes('critical');
    return `<article class="alert-item ${critical ? 'critical' : ''}">
      <span class="alert-symbol"><i data-lucide="${critical ? 'shield-alert' : 'triangle-alert'}"></i></span>
      <div class="alert-copy"><strong>${escapeValue(alert.alert_type || 'Condition warning')}</strong><p>${escapeValue(alert.message || 'A monitored condition requires review.')}</p><span>${escapeValue(alert.warehouse_location || 'En route')} · ${formatDateTime(alert.created_at)}</span></div>
    </article>`;
  }).join('');
  refreshIcons();
}

function renderEvents(events) {
  setText('eventCount', `${events.length} event${events.length === 1 ? '' : 's'}`);
  if (!events.length) {
    $('eventList').innerHTML = `<div class="empty-state"><i data-lucide="inbox"></i><span><strong>No events recorded yet</strong><small>The first verified device reading will appear here.</small></span></div>`;
    refreshIcons();
    return;
  }
  $('eventList').innerHTML = events.map(event => {
    const descriptor = describeEvent(event);
    const hash = event.record_hash ? shortHash(event.record_hash) : 'Not recorded';
    const verified = Boolean(event.record_hash);
    return `<article class="event-item">
      <div class="event-kind"><span class="event-icon ${descriptor.tone}"><i data-lucide="${descriptor.icon}"></i></span><span><strong>${descriptor.label}</strong><small>${escapeValue(event.event_id || event.device_id || 'Sensor event')}</small></span></div>
      <div class="event-reading">${escapeValue(descriptor.value)}</div>
      <time class="event-time" datetime="${escapeValue(event.created_at || '')}">${formatDateTime(event.created_at)}</time>
      <code class="event-hash" title="${escapeValue(event.record_hash || '')}">${escapeValue(hash)}</code>
      <span class="verification ${verified ? '' : 'pending'}"><i data-lucide="${verified ? 'badge-check' : 'clock-3'}"></i>${verified ? 'Gateway verified' : 'Pending'}</span>
    </article>`;
  }).join('');
  refreshIcons();
}

function describeEvent(event) {
  const temperature = finite(event.temperature);
  const light = finite(event.light_lux);
  const acceleration = finite(event.accel_g);
  if (light != null && light >= 800) return { label: 'Seal exposure detected', value: `${light.toFixed(0)} lux`, icon: 'sun-medium', tone: 'danger' };
  if (acceleration != null && acceleration >= 3) return { label: 'Impact threshold crossed', value: `${acceleration.toFixed(2)} g`, icon: 'activity', tone: 'danger' };
  if (temperature != null && (temperature > 8 || temperature < 2)) return { label: 'Temperature warning', value: `${temperature.toFixed(1)} °C`, icon: 'thermometer', tone: 'warning' };
  return { label: 'Telemetry receipt', value: temperature == null ? 'Sensor update' : `${temperature.toFixed(1)} °C`, icon: 'radio-tower', tone: '' };
}

function renderLocation(shipment, latest) {
  setText('locationDetail', shipment.current_warehouse || shipment.origin || 'Location not available');
  setText('locationTimestamp', latest?.created_at ? `Telemetry received ${formatRelative(latest.created_at)}` : 'Waiting for a live reading');
}

function updateReceipt(value) {
  if (!value) return setConnectionState('stale', 'No live readings', 'Waiting for telemetry');
  const date = parseDate(value);
  if (!date || Number.isNaN(date.getTime())) return setConnectionState('stale', 'Reading received', 'Timestamp unavailable');
  const age = Date.now() - date.getTime();
  if (age <= 20000) setConnectionState('live', 'Live', `Updated ${formatRelative(value)}`);
  else setConnectionState('stale', 'Data is stale', `Last update ${formatRelative(value)}`);
}

function setConnectionState(state, title, detail) {
  $('syncDot').className = `sync-dot ${state}`;
  setText('syncStatus', title);
  setText('lastUpdated', detail);
}

function showError(message) {
  setText('errorText', message);
  $('errorBanner').hidden = false;
  refreshIcons();
}

function hideError() { $('errorBanner').hidden = true; }

function renderUnassignedState() {
  setText('shipmentTitle', 'No shipment assigned');
  setText('shipmentCode', '—');
  setConnectionState('stale', 'No assignment', 'Contact an administrator');
  $('eventList').innerHTML = `<div class="empty-state"><i data-lucide="package-x"></i><span><strong>No shipment to display</strong><small>This account does not have an assigned shipment.</small></span></div>`;
  $('alertsList').innerHTML = `<div class="empty-state compact"><i data-lucide="inbox"></i><span><strong>No alert history</strong><small>Assign a shipment to begin monitoring.</small></span></div>`;
  refreshIcons();
}

function resetDashboardLoading() {
  stopPolling();
  setText('shipmentTitle', 'Loading shipment…');
  setText('shipmentCode', currentShipmentCode || '—');
  setConnectionState('connecting', 'Connecting', 'Retrieving shipment data');
  $('eventList').innerHTML = `<div class="empty-state"><i data-lucide="loader-circle"></i><span><strong>Loading event ledger</strong><small>Retrieving the latest custody records…</small></span></div>`;
  refreshIcons();
}

function setActiveNavigation(hash) {
  if (!['#overview', '#telemetry', '#events'].includes(hash)) hash = '#overview';
  document.querySelectorAll('[data-dashboard-section]').forEach(section => { section.hidden = section.dataset.dashboardSection !== hash.slice(1); });
  document.querySelectorAll('.desktop-nav a, .mobile-nav a').forEach(link => { const active = link.getAttribute('href') === hash; link.classList.toggle('active', active); if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current'); });
}

function statusClass(value) {
  const text = String(value || '').toLowerCase();
  if (text.includes('comprom') || text.includes('breach') || text.includes('critical')) return 'danger';
  if (text.includes('delay') || text.includes('warning') || text.includes('degrad')) return 'warning';
  if (text.includes('transit') || text.includes('deliver') || text.includes('active')) return 'good';
  return 'neutral';
}

function eventKey(event) { return event?.event_id || event?.id || event?.created_at || null; }
function finite(value) { const number = Number(value); return value !== null && value !== '' && Number.isFinite(number) ? number : null; }
function clamp(value, min, max) { return Math.min(max, Math.max(min, value)); }
function scale(value, min, max) { return value == null ? 0 : clamp(((value - min) / (max - min)) * 100, 0, 100); }
function formatAngle(value) { return value == null ? '—' : `${value.toFixed(1)}°`; }
function setText(id, value) { const element = $(id); if (element) element.textContent = value; }
function initials(name) { return String(name || 'U').split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase(); }
function shortHash(hash) { const value = String(hash); return value.length > 16 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value; }
function parseDate(value) { if (!value) return null; return new Date(/[zZ]|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`); }
function formatDateTime(value) { const date = parseDate(value); return !date || Number.isNaN(date.getTime()) ? 'Time unavailable' : date.toLocaleString([], { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }); }
function formatRelative(value) {
  const date = parseDate(value);
  if (!date || Number.isNaN(date.getTime())) return 'at an unknown time';
  const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
  if (seconds < 5) return 'just now';
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return hours < 24 ? `${hours}h ago` : date.toLocaleDateString([], { day: '2-digit', month: 'short' });
}
function refreshIcons() { if (window.lucide) window.lucide.createIcons(); }
