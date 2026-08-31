const API_BASE_URL = "http://127.0.0.1:8000";

let currentShipmentCode = "PRCL-2024-05-21-001";
let authToken = null;
let syncTimer = null;
let temperatureChart = null;
let motionChart = null;

document.addEventListener("DOMContentLoaded", init);

function init() {
  initCharts();
  if (window.lucide) lucide.createIcons();
}

async function handleLogin() {
  const username = (document.getElementById("loginUser").value || "").trim();
  const password = (document.getElementById("loginPin").value || "").trim();
  currentShipmentCode = (document.getElementById("loginProductId").value || "").trim().toUpperCase();

  try {
    const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({username, password})
    });

    if (!res.ok) {
      showToast("Authentication failed", "Check username and security passcode.", "error");
      return;
    }

    const data = await res.json();
    authToken = data.access_token;

    document.getElementById("headerUserName").textContent = data.username || username;
    document.getElementById("shipmentCode").textContent = currentShipmentCode;

    document.getElementById("loginScreen").classList.add("hidden");
    document.getElementById("appShell").classList.remove("hidden");

    showToast("Session started", "Operations console connected.", "success");
    startSync();
  } catch (e) {
    console.error(e);
    showToast("Backend unavailable", "Start FastAPI with python run_all.py.", "error");
  }
}

function handleLogout() {
  if (syncTimer) clearInterval(syncTimer);
  authToken = null;
  document.getElementById("appShell").classList.add("hidden");
  document.getElementById("loginScreen").classList.remove("hidden");
}

function startSync() {
  if (syncTimer) clearInterval(syncTimer);
  fetchShipmentData();
  syncTimer = setInterval(fetchShipmentData, 3000);
}

async function fetchShipmentData() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/shipments/${encodeURIComponent(currentShipmentCode)}`);
    if (!res.ok) return;

    const data = await res.json();
    const shipment = data.shipment || {};
    const events = Array.isArray(data.events) ? data.events : [];
    const alerts = Array.isArray(data.alerts) ? data.alerts : [];
    const latest = data.latest_telemetry || events[0];

    renderShipment(shipment);
    renderLatest(latest, shipment);
    renderCharts(events);
    renderIncidents(alerts);
    renderTelemetry(events);
    updateHealth(shipment.health_level || latest?.health_level || "Optimal");

    const stream = document.getElementById("streamState");
    if (stream) {
      stream.textContent = "Receiving";
      stream.className = "ok-dot";
    }
  } catch (e) {
    console.error("Telemetry sync:", e);
  }
}

function renderShipment(s) {
  if (!s) return;
  setText("shipmentCode", s.code || currentShipmentCode);
  setText("shipmentTitle", s.title || "Protected shipment");
  setText("shipOrigin", s.origin || "—");
  setText("shipDestination", s.destination || "—");
  setText("shipWarehouse", s.current_warehouse || "—");

  const status = document.getElementById("shipmentStatus");
  if (status) {
    status.textContent = String(s.status || "In Transit").toUpperCase();
    status.className = "status " + (String(s.status).toLowerCase() === "delivered" ? "info" : "good");
  }
}

function renderLatest(t, shipment) {
  if (!t) return;

  const temp = Number(t.temperature) || 0;
  const humidity = Number(t.humidity) || 0;
  const lux = Number(t.light_lux) || 0;
  const accel = Number(t.accel_g) || 0;
  const seal = shipment.seal_status || "Intact";

  setText("liveTemp", `${temp.toFixed(1)} °C`);
  setText("liveHumidity", `${humidity.toFixed(0)} %`);
  setText("liveLux", `${lux.toFixed(1)} LUX`);
  setText("liveAccel", `${accel.toFixed(2)} g`);
  setText("liveSeal", seal);

  setText("tempStatus", temp > 15 ? "Critical range" : temp > 8 ? "Above safe range" : "Within range");
  setText("luxStatus", lux >= 800 ? "High exposure / possible tamper" : "Normal sealed exposure");
  setText("motionStatus", accel >= 3 ? "Severe shock" : accel >= 1.5 ? "Elevated movement" : "Normal");
  setText("sealSub", seal === "BREACHED" ? "Tamper detected" : "Seal secure");

  setWidth("tempTrack", clamp(temp * 4, 4, 100));
  setWidth("luxTrack", clamp(lux, 4, 100));
  setWidth("humidityTrack", clamp(humidity, 4, 100));
  setWidth("motionTrack", clamp(accel * 20, 4, 100));

  setText("tempLatestFoot", `${temp.toFixed(1)} °C`);
  setText("accelLatestFoot", `${accel.toFixed(2)} g`);

  const sealEl = document.getElementById("liveSeal");
  if (sealEl) sealEl.className = seal === "BREACHED" ? "danger-value" : "good-value";
}

function renderCharts(events) {
  const history = [...events].reverse();
  const labels = history.map(e => formatTime(e.created_at));

  if (temperatureChart) {
    temperatureChart.data.labels = labels;
    temperatureChart.data.datasets[0].data = history.map(e => Number(e.temperature) || 0);
    temperatureChart.update("none");
  }

  if (motionChart) {
    motionChart.data.labels = labels;
    motionChart.data.datasets[0].data = history.map(e => Number(e.accel_g) || 0);
    motionChart.update("none");
  }
}

function renderIncidents(alerts) {
  const body = document.getElementById("incidentTableBody");
  const empty = document.getElementById("incidentEmpty");
  if (!body) return;

  const rows = alerts.slice(0, 8);
  empty.classList.toggle("hidden", rows.length > 0);

  body.innerHTML = rows.map(a => `
    <tr>
      <td class="mono">${formatDateTime(a.created_at)}</td>
      <td>${severityBadge(a.severity)}</td>
      <td><b>${escapeHtml(a.alert_type || "Sensor Alert")}</b></td>
      <td>${escapeHtml(a.warehouse_location || "En route")}</td>
      <td>${escapeHtml(a.message || "Threshold condition detected")}</td>
    </tr>
  `).join("");

  setText("navIncidentBadge", String(alerts.length));
  setText("incidentSummary", `${alerts.length} INCIDENT${alerts.length === 1 ? "" : "S"}`);
  document.getElementById("incidentSummary").className = "status " + (alerts.length ? "warning" : "neutral");
}

function renderTelemetry(events) {
  const body = document.getElementById("telemetryTableBody");
  if (!body) return;

  body.innerHTML = events.slice(0, 10).map(e => `
    <tr>
      <td class="mono blue-text">EV-${e.id}</td>
      <td class="mono">${formatDateTime(e.created_at)}</td>
      <td><b>${Number(e.temperature).toFixed(1)}°C</b></td>
      <td>${Number(e.humidity).toFixed(0)}%</td>
      <td>${Number(e.light_lux).toFixed(1)} LUX</td>
      <td>${Number(e.accel_g).toFixed(2)} g</td>
      <td>${healthBadge(e.health_level)}</td>
      <td>${sealBadge(e.health_level)}</td>
    </tr>
  `).join("");
}

function updateHealth(level) {
  const value = String(level || "Optimal").toLowerCase();
  ["healthOptimal","healthDegraded","healthCompromised"].forEach(id => document.getElementById(id)?.classList.remove("active"));

  let id = "healthOptimal", text = "OPTIMAL", type = "good";
  if (value === "degraded") { id = "healthDegraded"; text = "DEGRADED"; type = "warning"; }
  if (value === "compromised") { id = "healthCompromised"; text = "COMPROMISED"; type = "danger"; }

  document.getElementById(id)?.classList.add("active");
  const badge = document.getElementById("healthBadge");
  badge.textContent = text;
  badge.className = "status " + type;
}

function initCharts() {
  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: { legend: {display:false}, tooltip: {displayColors:false} },
    scales: {
      x: {grid:{display:false}, ticks:{color:"#94a3b8", font:{size:10}, maxTicksLimit:7}},
      y: {grid:{color:"#edf2f7"}, ticks:{color:"#94a3b8", font:{size:10}}}
    }
  };

  temperatureChart = new Chart(document.getElementById("temperatureChart"), {
    type: "line",
    data: {labels:[], datasets:[{
      data:[], borderColor:"#2563eb", backgroundColor:"rgba(37,99,235,.07)",
      fill:true, tension:.32, borderWidth:2.2, pointRadius:2.5, pointHoverRadius:5
    }]},
    options
  });

  motionChart = new Chart(document.getElementById("motionChart"), {
    type: "bar",
    data: {labels:[], datasets:[{
      data:[], backgroundColor:"rgba(100,116,139,.55)", borderRadius:3
    }]},
    options
  });
}

function scrollToSection(id) {
  document.getElementById(id)?.scrollIntoView({behavior:"smooth", block:"start"});
}

function severityBadge(s) {
  const x = String(s || "").toLowerCase();
  if (x.includes("critical") || x.includes("high")) return '<span class="status danger">HIGH</span>';
  if (x.includes("warning") || x.includes("medium")) return '<span class="status warning">MEDIUM</span>';
  return '<span class="status info">INFO</span>';
}

function healthBadge(s) {
  const x = String(s || "").toLowerCase();
  if (x === "compromised") return '<span class="status danger">COMPROMISED</span>';
  if (x === "degraded") return '<span class="status warning">DEGRADED</span>';
  return '<span class="status good">OPTIMAL</span>';
}

function sealBadge(level) {
  return String(level).toLowerCase() === "compromised"
    ? '<span class="status danger">CHECK</span>'
    : '<span class="status good">SECURE</span>';
}

function formatTime(v) {
  if (!v) return "--";
  return new Date(v).toLocaleTimeString([], {hour:"2-digit", minute:"2-digit"});
}

function formatDateTime(v) {
  if (!v) return "--";
  return new Date(v).toLocaleString([], {month:"short", day:"2-digit", hour:"2-digit", minute:"2-digit", second:"2-digit"});
}

function setText(id, value) {
  const e = document.getElementById(id);
  if (e) e.textContent = value;
}

function setWidth(id, value) {
  const e = document.getElementById(id);
  if (e) e.style.width = `${value}%`;
}

function clamp(n, min, max) {
  return Math.max(min, Math.min(max, n));
}

function escapeHtml(v) {
  return String(v).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;").replaceAll("'","&#039;");
}

function showToast(title, message, type="info") {
  const box = document.getElementById("toastContainer");
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `<b>${escapeHtml(title)}</b><span>${escapeHtml(message)}</span>`;
  box.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}
