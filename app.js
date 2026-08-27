// ==========================================
// STATE & CONFIGURATION
// ==========================================
const API_BASE_URL = "http://127.0.0.1:8000";
let currentShipmentCode = "PRCL-2024-05-21-001";
let userRole = "user"; // 'admin' or 'user'
let authToken = null;
let chartInstance = null;

document.addEventListener("DOMContentLoaded", () => {
  initTelemetryChart();
  if (window.lucide) lucide.createIcons();
});

// ==========================================
// AUTHENTICATION CONTROLLER
// ==========================================
async function handleLogin() {
  const usernameInput = (
    document.getElementById("loginUser")?.value || "Rahul Sharma"
  ).trim();
  const pinInput = (document.getElementById("loginPin")?.value || "1234").trim();
  const shipmentInput = (
    document.getElementById("loginShipment")?.value || "PRCL-2024-05-21-001"
  )
    .trim()
    .toUpperCase();

  try {
    const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({username: usernameInput, password: pinInput}),
    });

    if (res.ok) {
      const data = await res.json();
      authToken = data.access_token;
      userRole = data.role;
      currentShipmentCode = shipmentInput;

      // Update UI for User vs Admin Role
      document.getElementById("headerUserName").innerText = data.username;
      document.getElementById("headerRoleBadge").innerText =
        `${userRole.toUpperCase()} ROLE`;
      document.getElementById("sidebarRoleBadge").innerText =
        userRole === "admin" ? "Admin Control Hub" : "Recipient Portal";

      // Hide/Show Admin Tabs
      const adminNavBtn = document.getElementById("nav-admin-audit");
      if (adminNavBtn) {
        adminNavBtn.style.display = userRole === "admin" ? "flex" : "none";
      }

      // Dismiss Login Modal
      const modal = document.getElementById("loginScreen");
      if (modal) modal.style.display = "none";

      showToast(
        "Authenticated",
        `Logged in as ${data.username} (${userRole})`,
        "success",
      );

      // Start Real-time Data Sync
      startDataSync();
    } else {
      showToast(
        "Authentication Failed",
        "Invalid username or security passcode.",
        "error",
      );
    }
  } catch (err) {
    showToast(
      "Connection Error",
      "FastAPI server unreachable on localhost:8000",
      "error",
    );
  }
}

function handleLogout() {
  authToken = null;
  const modal = document.getElementById("loginScreen");
  if (modal) modal.style.display = "flex";
  showToast("Logged Out", "Session ended securely.", "info");
}

// ==========================================
// LIVE TELEMETRY & HEALTH ENGINE POLLER
// ==========================================
function startDataSync() {
  fetchShipmentData();
  setInterval(fetchShipmentData, 3000);
}

async function fetchShipmentData() {
  try {
    const res = await fetch(
      `${API_BASE_URL}/api/shipments/${currentShipmentCode}`,
    );
    if (!res.ok) return;

    const data = await res.json();
    const ship = data.shipment;
    const latest = data.latest_telemetry;

    if (latest) {
      // Update Live Readings
      document.getElementById("liveLux").innerText = `${latest.light_lux} LUX`;
      document.getElementById("liveTemp").innerText =
        `${latest.temperature} °C`;
      document.getElementById("liveAccel").innerText = `${latest.accel_g} g`;
      document.getElementById("liveSeal").innerText = ship.seal_status;
      document.getElementById("chartTempDisplay").innerText =
        `${latest.temperature} °C`;

      // Update 3-Level Health UI
      updateHealthUI(ship.health_level);

      // Update Chart
      if (chartInstance && data.events) {
        const history = [...data.events].reverse();
        chartInstance.data.labels = history.map((e) =>
          new Date(e.created_at).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          }),
        );
        chartInstance.data.datasets[0].data = history.map((e) => e.temperature);
        chartInstance.update();
      }

      // Update Admin Audit Table
      if (userRole === "admin") {
        renderAuditTable(data.events);
      }
    }
  } catch (e) {
    console.error("Sync error:", e);
  }
}

function updateHealthUI(level) {
  const title = document.getElementById("healthTitle");
  const badge = document.getElementById("healthBadge");
  const c1 = document.getElementById("cardLevel1");
  const c2 = document.getElementById("cardLevel2");
  const c3 = document.getElementById("cardLevel3");

  c1.className =
    "border border-slate-200 bg-slate-50/50 rounded-2xl p-4 space-y-2 opacity-60";
  c2.className =
    "border border-slate-200 bg-slate-50/50 rounded-2xl p-4 space-y-2 opacity-60";
  c3.className =
    "border border-slate-200 bg-slate-50/50 rounded-2xl p-4 space-y-2 opacity-60";

  if (level === "Optimal") {
    title.innerText = "Product Integrity: Level 1 (Optimal)";
    badge.className =
      "bg-emerald-100 text-emerald-800 px-4 py-2 rounded-2xl font-bold text-sm flex items-center gap-2";
    badge.innerHTML =
      '<span class="w-3 h-3 rounded-full bg-emerald-500 animate-pulse"></span> LEVEL 1: OPTIMAL';
    c1.className =
      "border-2 border-emerald-500 bg-emerald-50/40 rounded-2xl p-4 space-y-2";
  } else if (level === "Degraded") {
    title.innerText = "Product Integrity: Level 2 (Degraded)";
    badge.className =
      "bg-amber-100 text-amber-800 px-4 py-2 rounded-2xl font-bold text-sm flex items-center gap-2";
    badge.innerHTML =
      '<span class="w-3 h-3 rounded-full bg-amber-500 animate-pulse"></span> LEVEL 2: DEGRADED';
    c2.className =
      "border-2 border-amber-500 bg-amber-50/40 rounded-2xl p-4 space-y-2";
  } else {
    title.innerText = "Product Integrity: Level 3 (Compromised)";
    badge.className =
      "bg-rose-100 text-rose-800 px-4 py-2 rounded-2xl font-bold text-sm flex items-center gap-2";
    badge.innerHTML =
      '<span class="w-3 h-3 rounded-full bg-rose-500 animate-pulse"></span> LEVEL 3: COMPROMISED';
    c3.className =
      "border-2 border-rose-500 bg-rose-50/40 rounded-2xl p-4 space-y-2";
  }
}

function renderAuditTable(events) {
  const tbody = document.getElementById("auditTableBody");
  if (!tbody || !events) return;

  tbody.innerHTML = events
    .map(
      (ev) => `
        <tr class="hover:bg-slate-50 transition-colors">
            <td class="p-3 font-mono font-bold text-blue-600">EV-${ev.id}</td>
            <td class="p-3 text-slate-500">${new Date(ev.created_at).toLocaleTimeString()}</td>
            <td class="p-3 font-semibold ${ev.light_lux >= 50 ? "text-rose-600 font-bold" : "text-slate-700"}">${ev.light_lux} LUX</td>
            <td class="p-3 font-semibold ${ev.temperature > 8 ? "text-amber-600" : "text-slate-700"}">${ev.temperature} °C</td>
            <td class="p-3 text-slate-700">${ev.accel_g} g</td>
            <td class="p-3"><span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${ev.health_level === "Optimal" ? "bg-emerald-100 text-emerald-800" : ev.health_level === "Degraded" ? "bg-amber-100 text-amber-800" : "bg-rose-100 text-rose-800"}">${ev.health_level}</span></td>
            <td class="p-3 font-mono text-[10px] text-slate-400 truncate max-w-xs">${ev.record_hash}</td>
        </tr>
    `,
    )
    .join("");
}

// ==========================================
// TABS & NAVIGATION
// ==========================================
function switchTab(tabId) {
  document.querySelectorAll(".nav-link").forEach((el) => {
    el.classList.remove("bg-blue-600", "text-white", "shadow-sm", "active");
    el.classList.add("text-slate-600", "hover:bg-slate-100");
  });

  const activeBtn = document.getElementById(`nav-${tabId}`);
  if (activeBtn) {
    activeBtn.classList.remove("text-slate-600", "hover:bg-slate-100");
    activeBtn.classList.add(
      "bg-blue-600",
      "text-white",
      "shadow-sm",
      "active",
    );
  }

  document.querySelectorAll(".tab-content").forEach((el) => {
    el.classList.remove("active");
    el.classList.add("hidden");
  });

  const activeView = document.getElementById(`view-${tabId}`);
  if (activeView) {
    activeView.classList.remove("hidden");
    activeView.classList.add("active");
  }
}

// ==========================================
// CHART.JS INITIALIZATION
// ==========================================
function initTelemetryChart() {
  const ctx = document.getElementById("telemetryChart");
  if (!ctx) return;

  chartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Internal Temperature (°C)",
          data: [],
          borderColor: "#2563eb",
          backgroundColor: "rgba(37, 99, 235, 0.1)",
          fill: true,
          tension: 0.3,
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {y: {min: 0, max: 20}},
    },
  });
}

function showToast(title, msg, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  let bg = "bg-slate-900 text-white";
  if (type === "error") bg = "bg-rose-600 text-white";
  if (type === "success") bg = "bg-emerald-600 text-white";

  toast.className = `p-4 rounded-2xl shadow-xl ${bg} text-xs flex justify-between gap-3 pointer-events-auto`;
  toast.innerHTML = `<div><p class="font-bold">${title}</p><p class="opacity-90 mt-0.5">${msg}</p></div><button onclick="this.parentElement.remove()">✕</button>`;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}