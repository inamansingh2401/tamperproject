const API_BASE_URL = `http://${window.location.hostname || '127.0.0.1'}:8000`;
const TOKEN_KEY = "safetrack_access_token";
const ROLE_KEY = "safetrack_role";
const USER_KEY = "safetrack_username";
const ASSIGNMENTS_KEY = "safetrack_assigned_shipments";

let authToken = localStorage.getItem(TOKEN_KEY);
let currentShipmentCode = null;
let assignedShipments = [];
let refreshTimer = null;
let isFetchingShipment = false;
let temperatureChart = null;
let motionChart = null;

// 3D Package Orientation System (MPU6050)
let packageScene = null;
let packageCamera = null;
let packageRenderer = null;
let packageMesh = null;
let packageControls = null;
let packageSealPillMat = null;
let targetPitchDeg = 0;
let targetRollDeg = 0;
let targetYawDeg = 0;
let currentPitchDeg = 0;
let currentRollDeg = 0;
let currentYawDeg = 0;
let packageAnimFrame = null;
let lastMPUEventTime = null;

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#039;"}[ch]));

window.addEventListener("DOMContentLoaded", () => {
  bindUI();
  if (window.lucide) lucide.createIcons();
  restoreSession();
});

function bindUI() {
  $("loginForm")?.addEventListener("submit", handleLogin);
  $("logoutBtn")?.addEventListener("click", handleLogout);
  $("shipmentSelector")?.addEventListener("change", (e) => selectShipment(e.target.value));
  $("resetPackageViewBtn")?.addEventListener("click", resetPackageCamera);

  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => openTab(btn.dataset.tab));
  });
  document.querySelectorAll("[data-open-tab]").forEach(btn => {
    btn.addEventListener("click", () => openTab(btn.dataset.openTab));
  });

  window.addEventListener("resize", onPackageResize);
}

function restoreSession() {
  const role = localStorage.getItem(ROLE_KEY);
  const username = localStorage.getItem(USER_KEY);
  let saved = [];
  try { saved = JSON.parse(localStorage.getItem(ASSIGNMENTS_KEY) || "[]"); } catch (_) { saved = []; }

  if (!authToken || role !== "user" || !username) return;

  assignedShipments = Array.isArray(saved) ? saved : [];
  currentShipmentCode = assignedShipments[0] || null;
  showApp(username);
  populateShipmentSelector();
  if (currentShipmentCode) fetchShipmentData();
  startRefresh();
}

async function handleLogin(event) {
  event.preventDefault();
  const username = $("loginUser").value.trim();
  const password = $("loginPin").value;
  $("loginError").textContent = "";

  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      $("loginError").textContent = data.detail || "Invalid username or password.";
      return;
    }

    if (data.role !== "user") {
      $("loginError").textContent = "This portal is for user accounts. Admins should use the Admin dashboard.";
      return;
    }

    authToken = data.access_token;
    assignedShipments = Array.isArray(data.assigned_shipments) ? data.assigned_shipments : [];
    currentShipmentCode = assignedShipments[0] || data.shipment_code || null;

    localStorage.setItem(TOKEN_KEY, authToken);
    localStorage.setItem(ROLE_KEY, data.role);
    localStorage.setItem(USER_KEY, data.username || username);
    localStorage.setItem(ASSIGNMENTS_KEY, JSON.stringify(assignedShipments));

    showApp(data.username || username);
    populateShipmentSelector();
    if (currentShipmentCode) await fetchShipmentData();
    startRefresh();
    showToast("Welcome back", "Your shipment portal is ready.", "success");
  } catch (error) {
    console.error(error);
    $("loginError").textContent = "Backend unavailable. Start the SafeTrack backend first.";
  }
}

function showApp(username) {
  $("loginScreen")?.classList.add("hidden");
  $("appShell")?.classList.remove("hidden");
  $("headerUserName").textContent = username;
  $("welcomeTitle").textContent = `Good ${getDayPart()}, ${username.split(" ")[0]}`;
  $("userInitials").textContent = getInitials(username);
}

function handleLogout() {
  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = null;
  authToken = null;
  currentShipmentCode = null;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(ASSIGNMENTS_KEY);
  window.location.reload();
}

function startRefresh() {
  if (refreshTimer) clearInterval(refreshTimer);
  refreshTimer = setInterval(() => {
    if (authToken && currentShipmentCode) fetchShipmentData();
  }, 1500);
}

function populateShipmentSelector() {
  const select = $("shipmentSelector");
  if (!select) return;
  select.innerHTML = "";
  if (!assignedShipments.length) {
    select.innerHTML = `<option>No shipment assigned</option>`;
    return;
  }
  assignedShipments.forEach(code => {
    const option = document.createElement("option");
    option.value = code;
    option.textContent = code;
    select.appendChild(option);
  });
  select.value = currentShipmentCode;
}

function selectShipment(code) {
  if (!assignedShipments.includes(code)) return;
  currentShipmentCode = code;
  if (temperatureChart) {
    temperatureChart.destroy();
    temperatureChart = null;
  }
  if (motionChart) {
    motionChart.destroy();
    motionChart = null;
  }
  fetchShipmentData();
  openTab("overview");
}

async function fetchShipmentData() {
  if (!authToken || !currentShipmentCode) return;
  if (isFetchingShipment) return;
  isFetchingShipment = true;

  try {
    const response = await fetch(`${API_BASE_URL}/api/shipments/${encodeURIComponent(currentShipmentCode)}`, {
      headers: { Authorization: `Bearer ${authToken}` }
    });

    if (response.status === 401 || response.status === 403) {
      handleLogout();
      return;
    }
    if (!response.ok) throw new Error(`Shipment request failed: ${response.status}`);

    const data = await response.json();
    const latest = data.latest_telemetry || (data.events || [])[0] || null;
    renderShipment(data.shipment || {});
    renderEnvironment(latest, data.shipment || {});
    renderPackageOrientation(latest);
    renderCharts(Array.isArray(data.events) ? data.events : []);
    renderAlerts(Array.isArray(data.alerts) ? data.alerts : []);
    renderHistory(Array.isArray(data.events) ? data.events : []);
    if ($("lastUpdated")) {
      $("lastUpdated").textContent = (latest && latest.created_at) ? formatTime(latest.created_at) : new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
  } catch (error) {
    console.error(error);
  } finally {
    isFetchingShipment = false;
  }
}

function renderShipment(s) {
  const health = s.health_level || "Optimal";
  const status = s.status || "In Transit";
  const seal = String(s.seal_status || "INTACT").toUpperCase();
  const isCompromised = seal === "COMPROMISED" || seal === "BREACHED";

  // Overview Hero
  if ($("overviewShipmentCode")) $("overviewShipmentCode").textContent = s.code || currentShipmentCode || "—";
  if ($("overviewShipmentTitle")) $("overviewShipmentTitle").textContent = s.title || "Protected Cargo";
  if ($("overviewSubDetails")) {
    $("overviewSubDetails").textContent = `Assigned Carrier: ${s.vehicle_registration || s.vehicle_id || 'Vehicle en-route'} · ${s.recipient ? 'Deliver to ' + s.recipient : 'Direct custody'}`;
  }
  
  // Seal Badge & Hero Icon
  if ($("overviewSealBadge")) {
    $("overviewSealBadge").className = `status ${isCompromised ? 'danger' : 'good'}`;
    $("overviewSealBadge").innerHTML = `<i data-lucide="${isCompromised ? 'unlock' : 'lock'}" style="width:12px; height:12px;"></i> ${isCompromised ? 'COMPROMISED' : 'INTACT'}`;
  }
  if ($("heroBadgeIcon")) {
    $("heroBadgeIcon").setAttribute("data-lucide", isCompromised ? "alert-triangle" : "shield-check");
    const parentBox = $("heroBadgeIcon").parentElement;
    if (parentBox) {
      parentBox.style.color = isCompromised ? "var(--rose)" : "var(--primary)";
      parentBox.style.background = isCompromised ? "var(--rose-soft)" : "var(--primary-soft)";
      parentBox.style.borderColor = isCompromised ? "var(--rose-border)" : "var(--primary-border)";
    }
  }

  // Health Badges
  setStatus($("overviewHealth"), health, health === "Compromised" ? "COMPROMISED" : health === "Degraded" ? "ATTENTION" : "OPTIMAL");
  setStatus($("overviewStatusBadge"), status, status.toUpperCase());
  setStatus($("shipmentStatus"), status, status.toUpperCase());

  // Route Points
  if ($("overviewOrigin")) $("overviewOrigin").textContent = s.origin || "—";
  if ($("overviewHub")) $("overviewHub").textContent = s.current_warehouse || "—";
  if ($("overviewDestination")) $("overviewDestination").textContent = s.destination || "—";

  // Detailed Tab Attributes & Manifest Specifications
  if ($("shipOrigin")) $("shipOrigin").textContent = s.origin || "—";
  if ($("shipWarehouse")) $("shipWarehouse").textContent = s.current_warehouse || "—";
  if ($("shipDestination")) $("shipDestination").textContent = s.destination || "—";
  if ($("shipCode")) $("shipCode").textContent = s.code || currentShipmentCode || "—";
  if ($("shipTitle")) $("shipTitle").textContent = s.title || "—";
  if ($("shipSender")) $("shipSender").textContent = s.sender || "—";
  if ($("shipRecipient")) $("shipRecipient").textContent = s.recipient || "—";
  if ($("shipVehicle")) $("shipVehicle").textContent = s.vehicle_registration || s.vehicle_id || "—";
  if ($("shipOriginDetail")) $("shipOriginDetail").textContent = s.origin || "—";
  if ($("shipDestDetail")) $("shipDestDetail").textContent = s.destination || "—";
  if ($("shipSeal")) {
    $("shipSeal").textContent = isCompromised ? "COMPROMISED" : "INTACT";
    $("shipSeal").style.color = isCompromised ? "var(--rose)" : "var(--emerald)";
  }
  if ($("shipHealth")) {
    $("shipHealth").textContent = health;
    $("shipHealth").style.color = health === "Compromised" ? "var(--rose)" : health === "Degraded" ? "var(--amber)" : "var(--emerald)";
  }

  if (window.lucide) lucide.createIcons();
}

function renderEnvironment(t, shipment) {
  if (!t) return;
  const temp = Number(t.temperature);
  const humidity = Number(t.humidity);
  const light = Number(t.light_lux);
  const accel = Number(t.accel_g);

  const tempVal = Number.isFinite(temp) ? temp.toFixed(1) : "—";
  const humidityVal = Number.isFinite(humidity) ? humidity.toFixed(0) : "—";
  const lightVal = Number.isFinite(light) ? light.toFixed(0) : "—";
  const motionVal = Number.isFinite(accel) ? accel.toFixed(2) : "—";

  // Overview 4 Cards
  if ($("overviewTemp")) $("overviewTemp").textContent = tempVal;
  if ($("overviewHumidity")) $("overviewHumidity").textContent = humidityVal;
  if ($("overviewLight")) $("overviewLight").textContent = lightVal;
  if ($("overviewMotion")) $("overviewMotion").textContent = motionVal;

  // Sensor Tab 4 Cards
  if ($("envTemp")) $("envTemp").textContent = tempVal;
  if ($("envHumidity")) $("envHumidity").textContent = humidityVal;
  if ($("envLight")) $("envLight").textContent = lightVal;
  if ($("envMotion")) $("envMotion").textContent = motionVal;

  // Sub-status badges & descriptors
  const isSealCompromised = (String(shipment.seal_status || "").toUpperCase() === "COMPROMISED" || String(shipment.seal_status || "").toUpperCase() === "BREACHED" || (Number.isFinite(light) && light >= 800));
  const isImpact = accel >= 3.0;
  const isTempHigh = temp > 15.0;
  const isTempWarn = temp > 8.0;

  if ($("envTempStatus")) {
    $("envTempStatus").textContent = isTempHigh ? "Excursion: Temperature High (>15°C)" : isTempWarn ? "Warning: Temperature Elevated (>8°C)" : "Safe Range (2°C - 8°C)";
    $("envTempStatus").style.color = isTempHigh ? "var(--rose)" : isTempWarn ? "var(--amber)" : "var(--emerald)";
  }
  if ($("overviewTempSub")) {
    $("overviewTempSub").innerHTML = `<i data-lucide="${isTempHigh ? 'alert-octagon' : isTempWarn ? 'alert-triangle' : 'check-circle'}" style="width:13px; color:${isTempHigh ? 'var(--rose)' : isTempWarn ? 'var(--amber)' : 'var(--emerald)'};"></i><span>${isTempHigh ? 'Excursion Detected (>15°C)' : isTempWarn ? 'Elevated (>8°C)' : 'Safe Range (2°C - 8°C)'}</span>`;
  }

  const lightUnit = (t && t.light_unit) ? t.light_unit : "LUX";
  document.querySelectorAll(".metric-icon.light + .metric-value-wrap .metric-unit").forEach(u => u.textContent = lightUnit);

  if ($("envLightStatus")) {
    $("envLightStatus").textContent = isSealCompromised ? "Compromised: Light Detected (Exposed)" : "Intact: Container Closed (No Light)";
    $("envLightStatus").style.color = isSealCompromised ? "var(--rose)" : "var(--emerald)";
  }
  if ($("overviewLightSub")) {
    $("overviewLightSub").innerHTML = `<i data-lucide="${isSealCompromised ? 'unlock' : 'shield-check'}" style="width:13px; color:${isSealCompromised ? 'var(--rose)' : 'var(--emerald)'};"></i><span>${isSealCompromised ? 'Compromised (Light Detected)' : 'Seal Intact (No Light)'}</span>`;
  }

  if ($("envMotionStatus")) {
    $("envMotionStatus").textContent = isImpact ? "Impact Detected (≥3.0g)" : "Normal Transit Movement";
    $("envMotionStatus").style.color = isImpact ? "var(--rose)" : "var(--emerald)";
  }
  if ($("overviewMotionSub")) {
    $("overviewMotionSub").innerHTML = `<i data-lucide="${isImpact ? 'alert-triangle' : 'shield'}" style="width:13px; color:${isImpact ? 'var(--rose)' : 'var(--emerald)'};"></i><span>${isImpact ? 'Severe Impact (≥3.0g)' : 'Smooth Motion (<3.0g)'}</span>`;
  }

  if (window.lucide) lucide.createIcons();
}

function renderCharts(events) {
  const tempCanvas = $("temperatureChart");
  const motionCanvas = $("motionChart");
  if (!tempCanvas || !motionCanvas || !window.Chart) return;

  const ordered = [...events].reverse();
  const labels = ordered.map(e => formatTime(e.created_at));
  const temps = ordered.map(e => Number(e.temperature));
  const motion = ordered.map(e => Number(e.accel_g));

  if (temperatureChart && motionChart) {
    temperatureChart.data.labels = labels;
    temperatureChart.data.datasets[0].data = temps;
    temperatureChart.update("none");

    motionChart.data.labels = labels;
    motionChart.data.datasets[0].data = motion;
    motionChart.update("none");
    return;
  }

  const common = {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: '#0f172a',
        titleFont: { size: 11, family: 'Inter' },
        bodyFont: { size: 12, family: 'JetBrains Mono', weight: 'bold' },
        padding: 10,
        cornerRadius: 6
      }
    },
    scales: {
      x: { grid: { color: "#f1f5f9" }, ticks: { color: "#94a3b8", font: { size: 10, family: 'Inter' } } },
      y: { grid: { color: "#f1f5f9" }, ticks: { color: "#94a3b8", font: { size: 10, family: 'JetBrains Mono' } } }
    }
  };

  if (!temperatureChart) {
    temperatureChart = new Chart(tempCanvas, {
      type: "line",
      data: {
        labels,
        datasets: [{
          label: 'Temp (°C)',
          data: temps,
          borderColor: "#0284c7",
          backgroundColor: "rgba(2, 132, 199, 0.08)",
          fill: true,
          tension: 0.25,
          borderWidth: 2,
          pointRadius: 2.5,
          pointHoverRadius: 5
        }]
      },
      options: common
    });
  }

  if (!motionChart) {
    motionChart = new Chart(motionCanvas, {
      type: "line",
      data: {
        labels,
        datasets: [{
          label: 'Shock (g)',
          data: motion,
          borderColor: "#64748b",
          backgroundColor: "rgba(100, 116, 139, 0.08)",
          fill: true,
          tension: 0.2,
          borderWidth: 2,
          pointRadius: 2.5,
          pointHoverRadius: 5
        }]
      },
      options: common
    });
  }
}

function renderAlerts(alerts) {
  const container = $("alertsContainer");
  const resolvedContainer = $("resolvedAlertsContainer");
  const active = alerts.filter(a => String(a.status).toLowerCase() === "active");
  const resolved = alerts.filter(a => String(a.status).toLowerCase() !== "active");

  if ($("alertBadge")) {
    $("alertBadge").textContent = active.length;
    $("alertBadge").className = active.length > 0 ? "tab-badge" : "tab-badge zero";
  }
  if ($("activeIncidentsCount")) {
    $("activeIncidentsCount").textContent = active.length;
    $("activeIncidentsCount").style.display = active.length > 0 ? "inline-block" : "none";
  }

  if ($("alertSummary")) {
    if (!active.length) {
      $("alertSummary").className = "status good";
      $("alertSummary").textContent = "NO ACTIVE ALERTS";
    } else {
      $("alertSummary").className = "status danger";
      $("alertSummary").textContent = `${active.length} ACTIVE INCIDENT${active.length > 1 ? "S" : ""}`;
    }
  }

  // Render Active Incidents
  if (container) {
    if (!active.length) {
      container.innerHTML = `
        <div class="empty-box" style="padding:28px 16px; background:var(--surface); border:1px solid var(--line); border-radius:var(--radius);">
          <i data-lucide="shield-check" style="color:var(--emerald); width:32px; height:32px;"></i>
          <strong>No Active Incidents</strong>
          <p>All environmental parameters and seal sensors are within nominal tolerances.</p>
        </div>`;
    } else {
      container.innerHTML = active.map(alert => renderAlertCard(alert, false)).join("");
    }
  }

  // Render Resolved / Historical Incidents
  if (resolvedContainer) {
    if (!resolved.length) {
      resolvedContainer.innerHTML = `
        <div class="empty-box" style="padding:20px 16px; background:var(--surface); border:1px solid var(--line); border-radius:var(--radius);">
          <i data-lucide="archive" style="color:var(--text-dim); width:24px; height:24px;"></i>
          <p>No prior incident records logged for this waybill.</p>
        </div>`;
    } else {
      resolvedContainer.innerHTML = resolved.map(alert => renderAlertCard(alert, true)).join("");
    }
  }

  if (window.lucide) lucide.createIcons();
}

function renderAlertCard(alert, isResolved) {
  const isCritical = String(alert.severity).toLowerCase().includes("critical");
  return `
    <article class="alert-item ${isResolved ? '' : isCritical ? 'critical' : 'warning'}" style="${isResolved ? 'opacity:0.85; background:var(--surface-alt);' : ''}">
      <div class="alert-item-icon" style="${isResolved ? 'background:var(--emerald-soft); color:var(--emerald);' : ''}">
        <i data-lucide="${isResolved ? 'check-circle' : isCritical ? 'alert-octagon' : 'alert-triangle'}"></i>
      </div>
      <div class="alert-content">
        <div style="display:flex; align-items:center; gap:8px;">
          <h4>${esc(alert.alert_type || "Anomaly Detected")}</h4>
          ${isResolved ? '<span class="status good" style="font-size:9px; padding:1px 6px;">RESOLVED</span>' : ''}
        </div>
        <p>${esc(alert.message || "Excursion detected outside safe thresholds.")}</p>
        <div class="alert-foot">
          <span><i data-lucide="map-pin" style="width:11px; height:11px; display:inline; margin-right:3px;"></i>${esc(alert.warehouse_location || "En-Route")}</span>
          <span>·</span>
          <span><i data-lucide="clock" style="width:11px; height:11px; display:inline; margin-right:3px;"></i>${formatDateTime(alert.created_at)}</span>
        </div>
      </div>
      <span class="status ${isResolved ? 'good' : isCritical ? 'danger' : 'warning'}">${isResolved ? 'Resolved' : esc(alert.severity || "Alert")}</span>
    </article>`;
}

function renderHistory(events) {
  const body = $("historyTableBody");
  const empty = $("historyEmpty");
  if (!events.length) {
    body.innerHTML = "";
    empty.classList.remove("hidden");
    return;
  }
  empty.classList.add("hidden");
  body.innerHTML = events.map(e => {
    const health = e.health_level || "Optimal";
    const cls = health === "Compromised" ? "danger" : health === "Degraded" ? "warning" : "good";
    const ax = e.accel_x !== undefined && e.accel_x !== null ? Number(e.accel_x).toFixed(2) : "0.00";
    const ay = e.accel_y !== undefined && e.accel_y !== null ? Number(e.accel_y).toFixed(2) : "0.00";
    const az = e.accel_z !== undefined && e.accel_z !== null ? Number(e.accel_z).toFixed(2) : "1.00";
    const gx = e.gyro_x !== undefined && e.gyro_x !== null ? Number(e.gyro_x).toFixed(1) : "0.0";
    const gy = e.gyro_y !== undefined && e.gyro_y !== null ? Number(e.gyro_y).toFixed(1) : "0.0";
    const gz = e.gyro_z !== undefined && e.gyro_z !== null ? Number(e.gyro_z).toFixed(1) : "0.0";
    const mpuTooltip = `MPU6050 3-Axis Readout:\nAccel: X=${ax}g, Y=${ay}g, Z=${az}g\nGyro: X=${gx}°/s, Y=${gy}°/s, Z=${gz}°/s\nPitch: ${Number(e.pitch || 0).toFixed(1)}°, Roll: ${Number(e.roll || 0).toFixed(1)}°`;
    return `<tr>
      <td>${formatDateTime(e.created_at)}</td>
      <td><b>${number(e.temperature)} °C</b></td>
      <td>${number(e.humidity, 0)} %</td>
      <td>${number(e.light_lux, 0)} LUX</td>
      <td title="${mpuTooltip}" style="cursor:help;">${number(e.accel_g, 2)} g</td>
      <td><span class="status ${cls}">${esc(health)}</span></td>
    </tr>`;
  }).join("");
}

function openTab(tabName) {
  document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.toggle("active", btn.dataset.tab === tabName));
  document.querySelectorAll(".tab-panel").forEach(panel => panel.classList.remove("active-panel"));
  $(`tab-${tabName}`)?.classList.add("active-panel");
  if (window.lucide) lucide.createIcons();

  if (tabName === "shipment") {
    setTimeout(() => {
      init3DPackageScene();
      onPackageResize();
    }, 50);
  }

  if (tabName === "environment") {
    setTimeout(() => {
      if (temperatureChart) temperatureChart.resize();
      if (motionChart) motionChart.resize();
    }, 50);
  }
}

function setStatus(element, value, label) {
  if (!element) return;
  const x = String(value || "").toLowerCase();
  const cls = x.includes("compromised") || x.includes("breach") || x.includes("critical") ? "danger" : x.includes("degraded") || x.includes("warning") || x.includes("delay") ? "warning" : x.includes("optimal") || x.includes("secure") || x.includes("transit") ? "good" : "info";
  element.className = `status ${cls}`;
  element.textContent = label;
}

function formatTime(value) {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
function formatDateTime(value) {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString([], { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}
function number(value, digits = 1) { const n = Number(value); return Number.isFinite(n) ? n.toFixed(digits) : "—"; }
function getInitials(name) { return String(name || "U").split(" ").filter(Boolean).slice(0,2).map(x => x[0]).join("").toUpperCase(); }
function getDayPart() { const h = new Date().getHours(); return h < 12 ? "morning" : h < 17 ? "afternoon" : "evening"; }

function showToast(title, message, type = "info") {
  const container = $("toastContainer");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<b>${esc(title)}</b><span>${esc(message)}</span>`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

// ==========================================================================
// 3D PACKAGE ORIENTATION & MPU6050 SENSOR-DRIVEN RENDERER (THREE.JS)
// ==========================================================================

function init3DPackageScene() {
  const container = $("package3dContainer");
  if (!container || !window.THREE) return;
  if (packageRenderer) {
    onPackageResize();
    return;
  }

  const width = container.clientWidth || 400;
  const height = container.clientHeight || 340;

  // Scene
  packageScene = new THREE.Scene();

  // Camera
  packageCamera = new THREE.PerspectiveCamera(42, width / height, 0.1, 100);
  packageCamera.position.set(3.2, 2.4, 3.8);

  // Renderer
  packageRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  packageRenderer.setSize(width, height);
  packageRenderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  packageRenderer.shadowMap.enabled = true;
  packageRenderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(packageRenderer.domElement);

  // OrbitControls for manual camera rotation
  if (window.THREE.OrbitControls) {
    packageControls = new THREE.OrbitControls(packageCamera, packageRenderer.domElement);
    packageControls.enableDamping = true;
    packageControls.dampingFactor = 0.08;
    packageControls.enableZoom = true;
    packageControls.minDistance = 2.5;
    packageControls.maxDistance = 8.0;
    packageControls.maxPolarAngle = Math.PI / 2 + 0.1; // Don't flip upside down
  }

  // Lighting
  const ambientLight = new THREE.AmbientLight(0xffffff, 0.75);
  packageScene.add(ambientLight);

  const keyLight = new THREE.DirectionalLight(0xffffff, 0.85);
  keyLight.position.set(5, 8, 5);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.width = 1024;
  keyLight.shadow.mapSize.height = 1024;
  packageScene.add(keyLight);

  const fillLight = new THREE.DirectionalLight(0xbae6fd, 0.35);
  fillLight.position.set(-5, 3, -3);
  packageScene.add(fillLight);

  // Shadow ground plane
  const planeGeo = new THREE.PlaneGeometry(10, 10);
  const planeMat = new THREE.ShadowMaterial({ opacity: 0.12 });
  const shadowPlane = new THREE.Mesh(planeGeo, planeMat);
  shadowPlane.rotation.x = -Math.PI / 2;
  shadowPlane.position.y = -1.05;
  shadowPlane.receiveShadow = true;
  packageScene.add(shadowPlane);

  // Subtle coordinate grid plane on ground
  const gridHelper = new THREE.GridHelper(6, 12, 0xcbd5e1, 0xe2e8f0);
  gridHelper.position.y = -1.04;
  packageScene.add(gridHelper);

  // Build realistic cargo parcel box
  buildPackageMesh();

  // Start smooth rendering loop
  animatePackageScene();
}

function buildPackageMesh() {
  const boxWidth = 2.2;
  const boxHeight = 1.35;
  const boxDepth = 1.7;

  // Group to allow rotation about pivot without affecting camera controls
  packageMesh = new THREE.Group();

  // Create textured box faces using HTML Canvas textures
  const cardboardCanvas = createCardboardTexture();
  const boxTexture = new THREE.CanvasTexture(cardboardCanvas);
  
  const boxMat = new THREE.MeshStandardMaterial({
    map: boxTexture,
    roughness: 0.78,
    metalness: 0.05
  });

  const boxGeo = new THREE.BoxGeometry(boxWidth, boxHeight, boxDepth);
  const boxCore = new THREE.Mesh(boxGeo, boxMat);
  boxCore.castShadow = true;
  boxCore.receiveShadow = true;
  packageMesh.add(boxCore);

  // Security Tape strip across top & sides
  const tapeMat = new THREE.MeshStandardMaterial({
    color: 0x0284c7, // Cerulean blue tamper tape
    roughness: 0.35,
    metalness: 0.1
  });
  const tapeGeo = new THREE.BoxGeometry(boxWidth + 0.01, 0.08, 0.28);
  const tapeMesh = new THREE.Mesh(tapeGeo, tapeMat);
  tapeMesh.position.y = boxHeight / 2 + 0.01;
  packageMesh.add(tapeMesh);

  // Security Seal indicator pill on front face
  const sealPillGeo = new THREE.BoxGeometry(0.5, 0.2, 0.03);
  packageSealPillMat = new THREE.MeshStandardMaterial({
    color: 0x059669, // Emerald green sealed
    roughness: 0.2,
    metalness: 0.1
  });
  const sealPill = new THREE.Mesh(sealPillGeo, packageSealPillMat);
  sealPill.position.set(0, 0.1, boxDepth / 2 + 0.01);
  packageMesh.add(sealPill);

  packageScene.add(packageMesh);
}

function createCardboardTexture() {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext("2d");

  // Kraft cardboard base
  ctx.fillStyle = "#e2c9a5";
  ctx.fillRect(0, 0, 512, 512);

  // Fiber grain noise
  for (let i = 0; i < 4000; i++) {
    const x = Math.random() * 512;
    const y = Math.random() * 512;
    const l = Math.random() * 3;
    ctx.fillStyle = Math.random() > 0.5 ? "rgba(180, 150, 115, 0.15)" : "rgba(240, 225, 205, 0.15)";
    ctx.fillRect(x, y, l, 1);
  }

  // Edge seam lines
  ctx.strokeStyle = "rgba(160, 130, 95, 0.4)";
  ctx.lineWidth = 3;
  ctx.strokeRect(10, 10, 492, 492);

  // SafeTrack Shipping Label
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(40, 40, 240, 160);
  ctx.strokeStyle = "#cbd5e1";
  ctx.lineWidth = 1;
  ctx.strokeRect(40, 40, 240, 160);

  // Barcode lines
  ctx.fillStyle = "#0f172a";
  let bx = 60;
  while (bx < 260) {
    const bw = Math.random() > 0.5 ? 4 : 2;
    ctx.fillRect(bx, 130, bw, 50);
    bx += bw + 3;
  }

  // Label text
  ctx.font = "bold 16px sans-serif";
  ctx.fillStyle = "#0284c7";
  ctx.fillText("SAFETRACK COLD-CHAIN", 55, 68);

  ctx.font = "11px monospace";
  ctx.fillStyle = "#475569";
  ctx.fillText("PRIORITY PARCEL", 55, 88);
  ctx.fillText("CRYPTO INTEGRITY MONITOR", 55, 104);

  // Fragile Glass Icon & Arrows
  ctx.font = "bold 24px sans-serif";
  ctx.fillStyle = "#e11d48";
  ctx.fillText("↑↑ THIS SIDE UP", 320, 80);

  return canvas;
}

function onPackageResize() {
  const container = $("package3dContainer");
  if (!container || !packageRenderer || !packageCamera) return;
  const width = container.clientWidth;
  const height = container.clientHeight;
  if (width === 0 || height === 0) return;
  packageCamera.aspect = width / height;
  packageCamera.updateProjectionMatrix();
  packageRenderer.setSize(width, height);
}

function resetPackageCamera() {
  if (!packageCamera || !packageControls) return;
  packageCamera.position.set(3.2, 2.4, 3.8);
  packageControls.target.set(0, 0, 0);
  packageControls.update();
}

function renderPackageOrientation(telemetry) {
  if (!telemetry) return;

  const accel = Number(telemetry.accel_g);
  const gyro = Number(telemetry.gyro_dps);
  lastMPUEventTime = telemetry.created_at || new Date().toISOString();

  // Update Raw Readout Elements
  if ($("packageAccelVal")) $("packageAccelVal").textContent = Number.isFinite(accel) ? `${accel.toFixed(2)} g` : "— g";
  if ($("packageGyroVal")) $("packageGyroVal").textContent = Number.isFinite(gyro) ? `${gyro.toFixed(1)} °/s` : "— °/s";
  if ($("packageLastSync")) $("packageLastSync").textContent = formatTime(lastMPUEventTime);

  // 1. Calculate realistic Pitch & Roll from sensor telemetry
  if (telemetry && telemetry.pitch !== undefined && telemetry.pitch !== null && (telemetry.pitch !== 0 || telemetry.roll !== 0 || telemetry.accel_x !== 0)) {
    targetPitchDeg = Math.max(-60, Math.min(60, Number(telemetry.pitch)));
    targetRollDeg = Math.max(-60, Math.min(60, Number(telemetry.roll)));
  } else if (Number.isFinite(accel)) {
    const deviation = accel - 1.0;
    const rawPitch = Math.max(-45, Math.min(45, deviation * 28));
    const rawRoll = Math.max(-45, Math.min(45, (gyro || 0) * 0.5));
    targetPitchDeg = rawPitch;
    targetRollDeg = rawRoll;
  }

  // Update Angle displays
  if ($("anglePitchVal")) $("anglePitchVal").textContent = `${targetPitchDeg >= 0 ? '+' : ''}${targetPitchDeg.toFixed(1)}°`;
  if ($("angleRollVal")) $("angleRollVal").textContent = `${targetRollDeg >= 0 ? '+' : ''}${targetRollDeg.toFixed(1)}°`;

  // 2. Evaluate Movement & Shock Status based on user thresholds:
  // < 2.5g -> Normal
  // 2.5 - < 3.0g -> Warning
  // >= 3.0g -> Severe
  const shockBadge = $("motionShockBadge");
  const shockText = $("motionShockText");
  if (shockBadge && shockText) {
    if (accel >= 3.0) {
      shockBadge.className = "status danger";
      shockText.textContent = "Severe Shock (≥ 3.0g)";
    } else if (accel >= 2.5) {
      shockBadge.className = "status warning";
      shockText.textContent = "Warning Shock (2.5g - 3.0g)";
    } else {
      shockBadge.className = "status good";
      shockText.textContent = "Normal Movement (< 2.5g)";
    }
  }

  // 3. Evaluate Orientation Status
  // Stable: Pitch & Roll < 5 deg, gyro < 2 dps
  // Tilted: Pitch or Roll >= 5 deg
  // Moving: gyro >= 15 dps or active shock
  const orientBadge = $("orientationBadge");
  const orientText = $("orientationText");
  const absPitch = Math.abs(targetPitchDeg);
  const absRoll = Math.abs(targetRollDeg);
  const absGyro = Math.abs(gyro || 0);

  if (orientBadge && orientText) {
    if (absGyro >= 15 || accel >= 2.5) {
      orientBadge.className = "status warning";
      orientText.textContent = "Moving / Shaking";
    } else if (absPitch >= 8 || absRoll >= 8) {
      orientBadge.className = "status warning";
      orientText.textContent = `Tilted (${absPitch > absRoll ? 'Pitch' : 'Roll'} ${Math.max(absPitch, absRoll).toFixed(0)}°)`;
    } else {
      orientBadge.className = "status good";
      orientText.textContent = "Stable (Upright)";
    }
  }

  if (packageSealPillMat) {
    const isCompromised = (String(telemetry.seal_status || "").toUpperCase() === "COMPROMISED" || Number(telemetry.light_lux) >= 800);
    packageSealPillMat.color.setHex(isCompromised ? 0xe11d48 : 0x059669);
  }

  if (window.lucide) lucide.createIcons();
}

function animatePackageScene() {
  packageAnimFrame = requestAnimationFrame(animatePackageScene);

  // Update OrbitControls if user is inspecting
  if (packageControls) {
    packageControls.update();
  }

  // Smoothly interpolate physical orientation to target angles (NO fake continuous rotation)
  // Package remains completely stable when sensor is stable
  if (packageMesh) {
    const lerpSpeed = 0.20;
    currentPitchDeg += (targetPitchDeg - currentPitchDeg) * lerpSpeed;
    currentRollDeg += (targetRollDeg - currentRollDeg) * lerpSpeed;

    // Convert degrees to radians
    packageMesh.rotation.x = THREE.MathUtils.degToRad(currentPitchDeg);
    packageMesh.rotation.z = THREE.MathUtils.degToRad(currentRollDeg);
    packageMesh.rotation.y = 0; // Yaw is held stable unless physical rotation
  }

  if (packageRenderer && packageScene && packageCamera) {
    packageRenderer.render(packageScene, packageCamera);
  }
}
