// SafeTrack Application Logic

// ==========================================
// SINGLE PARCEL DATA STORE (PRCL-2024-05-21-001)
// ==========================================
const PRIMARY_PARCEL = {
  id: "PRCL-2024-05-21-001",
  title: "Parcel ID: PRCL-2024-05-21-001",
  category: "Medicine Package (Vaccines)",
  orderId: "ORD-784512",
  origin: "Mumbai, Maharashtra",
  destination: "Delhi, New Delhi",
  courier: "HealthCourier Express",
  status: "In Transit",
  progressPct: 88.5,
  distanceRemaining: "103.25 km from Delhi",
  currentLocationName: "Rewari, Haryana",
  sealStatus: "Intact",
  sealSub: "Seal is secure",
  temperature: 28.6,
  tempStatus: "Normal",
  tempSafeRange: "2°C – 30°C",
  humidity: 45,
  lightLux: 0.0,
  maxGForce: 2.8,
  timelineStatus: {
    packaged: true,
    dispatched: true
  },
  route: [
    { name: "Mumbai Hub", lat: 19.0760, lng: 72.8777, time: "May 20, 08:15 AM", status: "Origin" },
    { name: "Surat Checkpoint", lat: 21.1702, lng: 72.8311, time: "May 20, 06:20 PM", status: "In Transit" },
    { name: "Vadodara Facility", lat: 22.3072, lng: 73.1812, time: "May 20, 09:30 PM", status: "In Transit" },
    { name: "Kota Transit Hub", lat: 25.2138, lng: 75.8648, time: "May 21, 08:45 AM", status: "In Transit" },
    { name: "Rewari Node", lat: 28.1831, lng: 76.6173, time: "May 21, 10:15 AM", status: "Current Position" },
    { name: "Delhi Destination", lat: 28.6139, lng: 77.2090, time: "Est. May 22, 06:00 PM", status: "Destination" }
  ],
  // Incident logs (showing 5 items for dashboard recent logs)
  impactEvents: [
    { id: "INC-881", time: "May 21, 2024 10:15 AM", severity: "Medium", type: "Shock Detected", location: "Rewari, Haryana", force: "2.8g", details: "Impact detected with force 2.8g (Threshold 3.0g)" },
    { id: "INC-874", time: "May 21, 2024 08:45 AM", severity: "Low", type: "Minor Impact", location: "Kota, Rajasthan", force: "1.2g", details: "Impact detected with force 1.2g" },
    { id: "INC-862", time: "May 20, 2024 09:30 PM", severity: "High", type: "Heavy Impact", location: "Vadodara, Gujarat", force: "3.6g", details: "Impact detected with force 3.6g (High Severity!)" },
    { id: "INC-850", time: "May 20, 2024 06:20 PM", severity: "Medium", type: "Shock Detected", location: "Surat, Gujarat", force: "2.1g", details: "Impact detected with force 2.1g" },
    { id: "INC-801", time: "May 20, 2024 08:15 AM", severity: "Info", type: "Package Picked Up", location: "Mumbai, Maharashtra", force: "0.4g", details: "Package picked up and tracking started" }
  ]
};

let currentUser = {
  name: "Rahul Sharma",
  mobile: "9876543210",
  productId: "PRCL-2024-05-21-001"
};

let activeTab = "dashboard";

// Leaflet Full Map instance
let fullMapInstance = null;
let fullPolylineLayer = null;
let vehicleMarker = null;
let isAnimatingVehicle = false;
let animInterval = null;

// Chart instance
let tempChartInstance = null;

// Notifications list
let notifications = [
  { id: 1, text: "High Impact Shock (3.6g) recorded near Vadodara", time: "14 hours ago", unread: true, type: "error" },
  { id: 2, text: "Temperature stable at 28.6°C (Within safe range)", time: "2 hours ago", unread: true, type: "info" },
  { id: 3, text: "GPS Checkpoint Rewari Passed cleanly", time: "25 min ago", unread: true, type: "success" }
];

let selectedIncidentId = null;

// ==========================================
// INITIALIZATION
// ==========================================
document.addEventListener("DOMContentLoaded", () => {
  renderParcelData();
  renderNotifications();
  initCharts();
});

// ==========================================
// AUTHENTICATION LOGIC
// ==========================================
function sendOTP() {
  const userInput = document.getElementById("loginUser").value.trim();
  if (!userInput) {
    showToast("Missing Field", "Please enter Username or Mobile Number first", "error");
    return;
  }
  showToast("OTP Sent", `Verification code sent to ${userInput} (Code: 1234)`, "success");
}

function handleLogin(e) {
  e.preventDefault();

  const userInput = document.getElementById("loginUser").value.trim();
  const productIdInput = document.getElementById("loginProductId").value.trim().toUpperCase();

  if (!userInput || !productIdInput) {
    showToast("Login Failed", "Please enter Username/Mobile Number and Product ID", "error");
    return;
  }

  currentUser.name = userInput;
  currentUser.productId = productIdInput;

  document.getElementById("headerUserName").innerText = currentUser.name;
  document.getElementById("headerUserNameNav").innerText = currentUser.name;
  document.getElementById("profileModalName").innerText = currentUser.name;
  document.getElementById("profileModalProdId").innerText = PRIMARY_PARCEL.id;
  document.getElementById("profileModalUserVal").innerText = currentUser.name;

  const initials = currentUser.name.split(" ").map(n => n[0]).join("").toUpperCase() || "RS";
  document.getElementById("userAvatarInitials").innerText = initials;
  document.getElementById("profileAvatarModal").innerText = initials;

  document.getElementById("loginScreen").classList.add("hidden");

  renderParcelData();
  updateCharts();

  confetti({ particleCount: 80, spread: 60, origin: { y: 0.5 } });
  showToast("Login Successful", `Welcome ${currentUser.name}! Tracking ${PRIMARY_PARCEL.id}`, "success");
}

function handleLogout() {
  document.getElementById("profileDropdownModal").classList.add("hidden");
  document.getElementById("loginScreen").classList.remove("hidden");
  showToast("Logged Out", "Signed out successfully.", "info");
}

function toggleProfileDropdown() {
  const modal = document.getElementById("profileDropdownModal");
  modal.classList.toggle("hidden");
}

// ==========================================
// TIMELINE LOGIC (GREEN TICK FOR DONE, RED CROSS FOR NOT DONE - NO TOGGLE BUTTON)
// ==========================================
function renderTimelineUI() {
  const p = PRIMARY_PARCEL;

  // 1. Packaged Status
  const packagedCard = document.getElementById("packagedCard");
  const packagedContainer = document.getElementById("packagedIconContainer");
  const packagedIcon = document.getElementById("packagedIcon");
  const packagedBadge = document.getElementById("packagedBadge");

  if (p.timelineStatus.packaged) {
    packagedCard.className = "bg-emerald-50/60 border border-emerald-200 rounded-2xl p-4 shadow-sm flex items-center gap-3";
    packagedContainer.className = "w-10 h-10 rounded-xl flex items-center justify-center text-white shrink-0 bg-emerald-500 shadow";
    packagedIcon.setAttribute("data-lucide", "check-circle");
    packagedBadge.className = "bg-emerald-100 text-emerald-700 text-[10px] font-bold px-2 py-0.5 rounded-full inline-block mt-0.5";
    packagedBadge.innerText = "✓ Done";
  } else {
    packagedCard.className = "bg-rose-50/60 border border-rose-200 rounded-2xl p-4 shadow-sm flex items-center gap-3";
    packagedContainer.className = "w-10 h-10 rounded-xl flex items-center justify-center text-white shrink-0 bg-rose-500 shadow";
    packagedIcon.setAttribute("data-lucide", "x-circle");
    packagedBadge.className = "bg-rose-100 text-rose-700 text-[10px] font-bold px-2 py-0.5 rounded-full inline-block mt-0.5";
    packagedBadge.innerText = "✕ Not Done";
  }

  // 2. Dispatched Status
  const dispatchedCard = document.getElementById("dispatchedCard");
  const dispatchedContainer = document.getElementById("dispatchedIconContainer");
  const dispatchedIcon = document.getElementById("dispatchedIcon");
  const dispatchedBadge = document.getElementById("dispatchedBadge");

  if (p.timelineStatus.dispatched) {
    dispatchedCard.className = "bg-emerald-50/60 border border-emerald-200 rounded-2xl p-4 shadow-sm flex items-center gap-3";
    dispatchedContainer.className = "w-10 h-10 rounded-xl flex items-center justify-center text-white shrink-0 bg-emerald-500 shadow";
    dispatchedIcon.setAttribute("data-lucide", "check-circle");
    dispatchedBadge.className = "bg-emerald-100 text-emerald-700 text-[10px] font-bold px-2 py-0.5 rounded-full inline-block mt-0.5";
    dispatchedBadge.innerText = "✓ Done";
  } else {
    dispatchedCard.className = "bg-rose-50/60 border border-rose-200 rounded-2xl p-4 shadow-sm flex items-center gap-3";
    dispatchedContainer.className = "w-10 h-10 rounded-xl flex items-center justify-center text-white shrink-0 bg-rose-500 shadow";
    dispatchedIcon.setAttribute("data-lucide", "x-circle");
    dispatchedBadge.className = "bg-rose-100 text-rose-700 text-[10px] font-bold px-2 py-0.5 rounded-full inline-block mt-0.5";
    dispatchedBadge.innerText = "✕ Not Done";
  }

  lucide.createIcons();
}

// ==========================================
// TAB SWITCHING
// ==========================================
function switchTab(tabId) {
  activeTab = tabId;

  document.querySelectorAll(".nav-link").forEach(el => {
    el.classList.remove("bg-blue-600", "text-white", "shadow-sm", "active");
    el.classList.add("text-slate-600", "hover:bg-slate-100");
  });

  const activeNavBtn = document.getElementById(`nav-${tabId}`);
  if (activeNavBtn) {
    activeNavBtn.classList.remove("text-slate-600", "hover:bg-slate-100");
    activeNavBtn.classList.add("bg-blue-600", "text-white", "shadow-sm", "active");
  }

  document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
  const activeView = document.getElementById(`view-${tabId}`);
  if (activeView) activeView.classList.add("active");

  if (tabId === "timeline") {
    renderTimelineUI();
  }

  if (tabId === "map") {
    setTimeout(() => {
      initFullMap();
    }, 200);
  }

  closeMobileMenu();
}

function toggleMobileMenu() {
  const sidebar = document.getElementById("mobileSidebar");
  const overlay = document.getElementById("mobileMenuOverlay");
  const desktopSidebar = document.querySelector("aside.hidden.md\\:flex");
  
  if (sidebar.classList.contains("-translate-x-full")) {
    sidebar.innerHTML = desktopSidebar.innerHTML;
    sidebar.classList.remove("-translate-x-full");
    overlay.classList.remove("hidden");
    lucide.createIcons();
  } else {
    closeMobileMenu();
  }
}

function closeMobileMenu() {
  const sidebar = document.getElementById("mobileSidebar");
  const overlay = document.getElementById("mobileMenuOverlay");
  sidebar.classList.add("-translate-x-full");
  overlay.classList.add("hidden");
}

// ==========================================
// RENDERING DATA
// ==========================================
function renderParcelData() {
  const p = PRIMARY_PARCEL;

  document.getElementById("dashParcelTitle").innerText = p.title;
  document.getElementById("dashCategory").innerHTML = `<i data-lucide="package" class="w-3.5 h-3.5"></i> ${p.category}`;
  document.getElementById("dashOrderId").innerText = p.orderId;
  document.getElementById("dashOrigin").innerText = p.origin;
  document.getElementById("dashDest").innerText = p.destination;
  document.getElementById("dashCourier").innerText = p.courier;

  document.getElementById("dashSealVal").innerText = p.sealStatus;
  document.getElementById("dashSealSub").innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-emerald-500"></span> ${p.sealSub}`;
  document.getElementById("navSealBadge").innerText = p.sealStatus.includes("Tamper") ? "Tampered" : "Intact";

  document.getElementById("dashDistVal").innerText = p.distanceRemaining;
  document.getElementById("dashLocVal").innerText = p.currentLocationName;

  document.getElementById("dashTempVal").innerText = `${p.temperature} °C`;
  document.getElementById("dashTempSub").innerText = `Safe range: ${p.tempSafeRange}`;
  document.getElementById("tempViewVal").innerText = `${p.temperature} °C`;
  document.getElementById("navTempReading").innerText = `${p.temperature}°C`;

  // Render recent 5 incident logs on dashboard
  renderImpactTable(p.impactEvents.slice(0, 5));
  // Render full incident logs in All Incident Logs view
  renderFullIncidentTable(p.impactEvents);
  renderTimelineUI();

  lucide.createIcons();
}

function renderImpactTable(events) {
  const tbody = document.getElementById("dashImpactTableBody");
  if (!tbody) return;

  tbody.innerHTML = events.map(ev => {
    let sevBadge = "bg-blue-100 text-blue-700";
    if (ev.severity === "High") sevBadge = "bg-rose-100 text-rose-700 font-bold";
    if (ev.severity === "Medium") sevBadge = "bg-amber-100 text-amber-700";

    return `
      <tr class="hover:bg-slate-50/80 transition-colors">
        <td class="py-3.5 pl-2 font-medium text-slate-700 flex items-center gap-2">
          <span class="w-2 h-2 rounded-full ${ev.severity === 'High' ? 'bg-rose-500' : (ev.severity === 'Medium' ? 'bg-amber-500' : 'bg-emerald-500')}"></span>
          ${ev.time}
        </td>
        <td class="py-3.5"><span class="${sevBadge} font-semibold px-2.5 py-1 rounded-full text-[10px]">${ev.severity}</span></td>
        <td class="py-3.5 font-medium text-slate-700">
          <div class="flex items-center gap-2"><i data-lucide="activity" class="w-4 h-4 text-slate-400"></i> ${ev.type}</div>
        </td>
        <td class="py-3.5">
          <p class="font-medium text-slate-800">${ev.location}</p>
        </td>
        <td class="py-3.5 text-slate-600 font-medium">${ev.details}</td>
        <td class="py-3.5 text-right">
          <button onclick="openIncidentModal('${ev.id}')" class="text-blue-600 hover:underline text-xs font-semibold">Details</button>
        </td>
      </tr>
    `;
  }).join("");
}

function renderFullIncidentTable(events) {
  const tbody = document.getElementById("fullIncidentTable");
  if (!tbody) return;

  tbody.innerHTML = events.map(ev => {
    let sevBadge = "bg-blue-100 text-blue-700";
    if (ev.severity === "High") sevBadge = "bg-rose-100 text-rose-700 font-bold";
    if (ev.severity === "Medium") sevBadge = "bg-amber-100 text-amber-700";

    return `
      <tr class="hover:bg-slate-50 transition-colors">
        <td class="p-3 font-mono font-bold text-blue-600">${ev.id}</td>
        <td class="p-3 text-slate-600">${ev.time}</td>
        <td class="p-3"><span class="${sevBadge} px-2.5 py-0.5 rounded-full text-[10px]">${ev.severity}</span></td>
        <td class="p-3 font-semibold text-slate-800">${ev.details}</td>
        <td class="p-3 text-slate-600">${ev.location}</td>
        <td class="p-3 text-right">
          <button onclick="openIncidentModal('${ev.id}')" class="bg-slate-100 hover:bg-slate-200 text-slate-800 font-bold px-3 py-1 rounded-xl text-[11px] transition-colors">Inspect</button>
        </td>
      </tr>
    `;
  }).join("");
}

function filterIncidents() {
  const p = PRIMARY_PARCEL;
  const query = document.getElementById("incidentSearch").value.toLowerCase();
  const sevFilter = document.getElementById("incidentFilter").value;

  const filtered = p.impactEvents.filter(ev => {
    const matchesQuery = ev.details.toLowerCase().includes(query) || ev.location.toLowerCase().includes(query) || ev.id.toLowerCase().includes(query);
    const matchesSev = sevFilter === "all" || ev.severity === sevFilter;
    return matchesQuery && matchesSev;
  });

  renderFullIncidentTable(filtered);
}

// ==========================================
// MAP INITIALIZATION (FULL LIVE TRACKING MAP)
// ==========================================
function initFullMap() {
  if (!document.getElementById("fullMap")) return;

  const p = PRIMARY_PARCEL;
  const routePoints = p.route.map(r => [r.lat, r.lng]);

  if (fullMapInstance) fullMapInstance.remove();

  fullMapInstance = L.map("fullMap").setView([24.5000, 75.5000], 6);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "© OpenStreetMap"
  }).addTo(fullMapInstance);

  updateFullMapMarkers();
}

function setTileStyle(type) {
  showToast("Map View", type === "sat" ? "Switched to Satellite Telemetry" : "Switched to Standard Vector Map", "info");
}

function updateFullMapMarkers() {
  if (!fullMapInstance) return;

  const p = PRIMARY_PARCEL;
  const routePoints = p.route.map(r => [r.lat, r.lng]);

  fullMapInstance.eachLayer(layer => {
    if (layer instanceof L.Polyline || layer instanceof L.Marker) {
      fullMapInstance.removeLayer(layer);
    }
  });

  fullPolylineLayer = L.polyline(routePoints, { color: "#2563eb", weight: 5, opacity: 0.85, dashArray: "8, 8" }).addTo(fullMapInstance);

  p.route.forEach((wp, idx) => {
    const isCurrent = idx === 4 || idx === p.route.length - 2;
    const color = isCurrent ? "#2563eb" : (idx === 0 ? "#10b981" : "#64748b");

    const marker = L.circleMarker([wp.lat, wp.lng], {
      radius: isCurrent ? 9 : 6,
      fillColor: color,
      color: "#ffffff",
      weight: 2,
      fillOpacity: 1
    }).addTo(fullMapInstance);

    marker.bindPopup(`
      <div class="p-1 space-y-1">
        <h4 class="font-bold text-slate-900 text-xs">${wp.name}</h4>
        <p class="text-[11px] text-slate-500">${wp.time}</p>
        <span class="bg-blue-100 text-blue-700 text-[10px] font-bold px-1.5 py-0.5 rounded">${wp.status}</span>
      </div>
    `);
  });

  const currentPos = p.route[4] || p.route[p.route.length - 2];
  const vehicleIcon = L.divIcon({
    html: `<div class="custom-map-pin">📦</div>`,
    iconSize: [36, 36],
    iconAnchor: [18, 18]
  });

  vehicleMarker = L.marker([currentPos.lat, currentPos.lng], { icon: vehicleIcon }).addTo(fullMapInstance);
  vehicleMarker.bindPopup(`<b>Carrier Express #994</b><br>Speed: 62 km/h<br>Temp: ${p.temperature}°C`).openPopup();

  fullMapInstance.fitBounds(fullPolylineLayer.getBounds(), { padding: [50, 50] });
}

function recenterMap() {
  if (fullMapInstance) {
    const p = PRIMARY_PARCEL;
    const pos = p.route[4] || p.route[0];
    fullMapInstance.setView([pos.lat, pos.lng], 9, { animate: true });
  }
}

function toggleVehicleAnimation() {
  isAnimatingVehicle = !isAnimatingVehicle;
  const btn = document.getElementById("animateBtn");

  if (isAnimatingVehicle) {
    btn.innerHTML = `<i data-lucide="pause" class="w-3.5 h-3.5"></i> Pause Movement`;
    btn.className = "bg-amber-600 text-white px-3.5 py-1.5 rounded-xl text-xs font-semibold hover:bg-amber-700 transition-all shadow-sm flex items-center gap-1.5";
    
    let step = 0;
    const route = PRIMARY_PARCEL.route;
    animInterval = setInterval(() => {
      step = (step + 1) % route.length;
      if (vehicleMarker && fullMapInstance) {
        vehicleMarker.setLatLng([route[step].lat, route[step].lng]);
        fullMapInstance.panTo([route[step].lat, route[step].lng]);
      }
    }, 1500);
    showToast("Movement Simulation", "Vehicle GPS position advancing along highway", "info");
  } else {
    clearInterval(animInterval);
    btn.innerHTML = `<i data-lucide="play" class="w-3.5 h-3.5"></i> Simulate Vehicle Movement`;
    btn.className = "bg-blue-600 text-white px-3.5 py-1.5 rounded-xl text-xs font-semibold hover:bg-blue-700 transition-all shadow-sm flex items-center gap-1.5";
  }
  lucide.createIcons();
}

// ==========================================
// TEMPERATURE CHART IMPLEMENTATION (CHART.JS)
// ==========================================
function initCharts() {
  const tempCtx = document.getElementById("tempChart");
  if (tempCtx) {
    tempChartInstance = new Chart(tempCtx, {
      type: "line",
      data: {
        labels: ["08:00 AM", "10:00 AM", "12:00 PM", "02:00 PM", "04:00 PM", "06:00 PM", "08:00 PM", "10:00 PM", "Live"],
        datasets: [
          {
            label: "Internal Temperature (°C)",
            data: [22.1, 23.4, 24.8, 26.2, 27.0, 27.8, 28.1, 28.4, 28.6],
            borderColor: "#3b82f6",
            backgroundColor: "rgba(59, 130, 246, 0.1)",
            fill: true,
            tension: 0.4,
            borderWidth: 3
          },
          {
            label: "Max Safe Limit (30°C)",
            data: [30, 30, 30, 30, 30, 30, 30, 30, 30],
            borderColor: "#ef4444",
            borderDash: [6, 6],
            pointRadius: 0,
            fill: false
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { min: 0, max: 35, title: { display: true, text: "Temperature (°C)" } }
        }
      }
    });
  }
}

function updateCharts() {
  if (tempChartInstance) {
    tempChartInstance.data.datasets[0].data[8] = PRIMARY_PARCEL.temperature;
    tempChartInstance.update();
  }
}

// ==========================================
// NOTIFICATIONS & TOASTS
// ==========================================
function renderNotifications() {
  const list = document.getElementById("notifList");
  const fullList = document.getElementById("fullNotifList");

  const html = notifications.map(n => `
    <div class="p-2.5 rounded-xl ${n.unread ? 'bg-blue-50 border border-blue-100' : 'bg-slate-50'} text-xs space-y-0.5">
      <p class="font-bold text-slate-800">${n.text}</p>
      <p class="text-[10px] text-slate-400 font-mono">${n.time}</p>
    </div>
  `).join("");

  if (list) list.innerHTML = html;
  if (fullList) fullList.innerHTML = html;
}

function toggleNotifications() {
  const dropdown = document.getElementById("notifDropdown");
  dropdown.classList.toggle("hidden");
}

function clearNotifs() {
  notifications.forEach(n => n.unread = false);
  document.getElementById("notifBadge").classList.add("hidden");
  renderNotifications();
}

function showToast(title, message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  let bg = "bg-slate-900 text-white";
  if (type === "error") bg = "bg-rose-600 text-white shadow-rose-500/20";
  if (type === "success") bg = "bg-emerald-600 text-white shadow-emerald-500/20";
  if (type === "info") bg = "bg-blue-600 text-white shadow-blue-500/20";

  toast.className = `toast-notification p-4 rounded-2xl shadow-xl border ${bg} pointer-events-auto flex items-start gap-3 z-50`;
  toast.innerHTML = `
    <div class="flex-1">
      <h5 class="font-bold text-xs">${title}</h5>
      <p class="text-[11px] opacity-90 mt-0.5">${message}</p>
    </div>
    <button onclick="this.parentElement.remove()" class="text-white opacity-70 hover:opacity-100 text-xs">✕</button>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    if (toast.parentElement) toast.remove();
  }, 4000);
}

// ==========================================
// MODALS
// ==========================================
function openExportModal() {
  document.getElementById("exportModal").classList.remove("hidden");
}

function closeExportModal() {
  document.getElementById("exportModal").classList.add("hidden");
}

function generateAuditReport() {
  closeExportModal();
  confetti({ particleCount: 100, spread: 70, origin: { y: 0.6 } });
  showToast("Audit Manifest Exported!", "Official signed PDF manifest downloaded.", "success");
}

function openIncidentModal(incId) {
  const p = PRIMARY_PARCEL;
  const ev = p.impactEvents.find(e => e.id === incId);
  if (!ev) return;

  selectedIncidentId = incId;
  document.getElementById("incModalTitle").innerText = `Incident Inspection: ${ev.id}`;
  document.getElementById("incModalBody").innerHTML = `
    <div class="p-3 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
      <p><strong>Timestamp:</strong> ${ev.time}</p>
      <p><strong>Location:</strong> ${ev.location}</p>
      <p><strong>Severity:</strong> <span class="bg-rose-100 text-rose-700 font-bold px-2 py-0.5 rounded-full text-[10px]">${ev.severity}</span></p>
      <p><strong>Recorded Force:</strong> ${ev.force}</p>
    </div>
    <div class="space-y-1">
      <p class="font-bold text-slate-800">Telemetry Details:</p>
      <p class="text-slate-600">${ev.details}</p>
    </div>
  `;

  document.getElementById("incidentModal").classList.remove("hidden");
}

function closeIncidentModal() {
  document.getElementById("incidentModal").classList.add("hidden");
}

function resolveCurrentIncident() {
  if (!selectedIncidentId) return;
  const p = PRIMARY_PARCEL;
  p.impactEvents = p.impactEvents.filter(e => e.id !== selectedIncidentId);

  renderImpactTable(p.impactEvents.slice(0, 5));
  renderFullIncidentTable(p.impactEvents);
  closeIncidentModal();
  confetti({ particleCount: 60, spread: 50, origin: { y: 0.5 } });
  showToast("Incident Cleared", `Incident ${selectedIncidentId} archived as resolved.`, "success");
}
