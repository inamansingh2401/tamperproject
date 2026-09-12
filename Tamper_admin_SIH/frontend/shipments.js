/**
 * SafeTrack Admin Console - Shipments Management Controller
 *
 * Live data source: FastAPI -> SQLite -> /api/shipments
 * The shipment inspector displays the same telemetry events that the
 * Operator/User dashboard receives from the backend.
 */

let allShipmentsList = [];
let filteredShipmentsList = [];
let inspectionRefreshTimer = null;
let currentlyInspectedCode = null;

// Admin 3D Package Orientation System (MPU6050 per shipment)
let adminPackageScene = null;
let adminPackageCamera = null;
let adminPackageRenderer = null;
let adminPackageMesh = null;
let adminPackageControls = null;
let adminTargetPitch = 0;
let adminTargetRoll = 0;
let adminCurrentPitch = 0;
let adminCurrentRoll = 0;
let adminAnimFrame = null;

const esc = (value) => {
    if (value === null || value === undefined) return "—";
    return String(value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
};

const number = (value, digits = 1) => {
    const n = Number(value);
    return Number.isFinite(n) ? n.toFixed(digits) : "—";
};

function formatDateTime(value) {
    if (!value) return "—";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return esc(value);
    return d.toLocaleString([], {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
    });
}

function formatTime(value) {
    if (!value) return "—";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return esc(value);
    return d.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
    });
}

function healthClass(health) {
    if (health === "Compromised") return "text-rose-600 bg-rose-50 border-rose-100";
    if (health === "Degraded") return "text-amber-600 bg-amber-50 border-amber-100";
    return "text-emerald-600 bg-emerald-50 border-emerald-100";
}

function statusBadgeClass(status) {
    if (status === "In Transit") return "badge-in-transit";
    if (status === "Compromised") return "badge-critical";
    return "badge-at-warehouse";
}

document.addEventListener("DOMContentLoaded", async () => {
    await loadShipmentsData();
    await populateVehicleOptions();

    const urlParams = new URLSearchParams(window.location.search);
    const requestedCode = urlParams.get("code");
    if (requestedCode) {
        await inspectShipment(requestedCode);
    }

    if (window.lucide) lucide.createIcons();
});

async function loadShipmentsData() {
    try {
        allShipmentsList = await SafeTrackAPI.getShipments();
        filteredShipmentsList = [...allShipmentsList];
        renderShipmentsTable();
    } catch (err) {
        console.error("Error loading shipments:", err);
        showToast("Failed to load shipments", "error");
    }
}

function renderShipmentsTable() {
    const tbody = document.getElementById("shipmentsTableBody");
    const countText = document.getElementById("shipmentsCountText");
    if (!tbody) return;

    tbody.innerHTML = "";
    if (countText) countText.innerText = filteredShipmentsList.length;

    if (filteredShipmentsList.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="8" class="text-center py-10 text-slate-400 font-medium">
                    No matching shipments found.
                </td>
            </tr>`;
        return;
    }

    filteredShipmentsList.forEach((s) => {
        const id = esc(s.id);
        const title = esc(s.title);
        const vehicle = esc(s.vehicle_id);
        const origin = esc(s.origin);
        const destination = esc(s.destination);
        const currentHub = esc(s.current_hub ?? s.current_warehouse);
        const status = esc(s.status);
        const temperature = number(s.latest_temperature, 1);

        const statusBadge = statusBadgeClass(s.status);
        const isSealed = s.seal_status === "Sealed" || s.seal_status === "Intact";
        const sealBadge = isSealed
            ? `<span class="badge badge-optimal"><i data-lucide="lock" class="w-3 h-3"></i> Sealed</span>`
            : `<span class="badge badge-critical"><i data-lucide="unlock" class="w-3 h-3"></i> Breached</span>`;

        const tr = document.createElement("tr");
        tr.className = "hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors";
        tr.innerHTML = `
            <td class="px-5 py-4">
                <button onclick="inspectShipment('${id}')" class="font-mono font-bold text-blue-600 dark:text-blue-400 hover:underline block text-left">
                    ${id}
                </button>
                <p class="text-[11px] text-slate-500 max-w-xs truncate" title="${title}">${title}</p>
            </td>
            <td class="px-5 py-4">
                <a href="vehicle-details.html?id=${encodeURIComponent(s.vehicle_id || "")}" class="px-2 py-0.5 text-[11px] font-mono font-semibold bg-slate-100 dark:bg-slate-700 text-slate-700 dark:text-slate-300 rounded-md hover:text-blue-600">
                    ${vehicle}
                </a>
            </td>
            <td class="px-5 py-4 text-slate-700 dark:text-slate-200">
                <p class="font-medium text-xs">${origin}</p>
                <p class="text-[11px] text-slate-400">→ ${destination}</p>
            </td>
            <td class="px-5 py-4 font-medium text-slate-700 dark:text-slate-300">
                ${currentHub}
            </td>
            <td class="px-5 py-4">
                <span class="badge ${statusBadge}">${status}</span>
            </td>
            <td class="px-5 py-4 font-bold text-blue-600 dark:text-blue-400">
                ${temperature} °C
            </td>
            <td class="px-5 py-4">${sealBadge}</td>
            <td class="px-5 py-4 text-center">
                <div class="flex items-center justify-center gap-1.5">
                    <button onclick="inspectShipment('${id}')" title="Inspect Telemetry & Logs" class="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 hover:text-blue-600 rounded-lg transition-colors">
                        <i data-lucide="eye" class="w-4 h-4"></i>
                    </button>
                    <button onclick="openEditShipmentModal('${id}')" title="Edit Shipment" class="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 hover:text-blue-600 rounded-lg transition-colors">
                        <i data-lucide="edit-3" class="w-4 h-4"></i>
                    </button>
                    <button onclick="deleteShipmentHandler('${id}')" title="Delete Shipment" class="p-1.5 hover:bg-rose-50 dark:hover:bg-rose-950/40 text-slate-400 hover:text-rose-600 rounded-lg transition-colors">
                        <i data-lucide="trash-2" class="w-4 h-4"></i>
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });

    if (window.lucide) lucide.createIcons();
}

function openEditShipmentModal(code) {
    const s = allShipmentsList.find(item => item.id === code);
    if (!s) {
        showToast(`Shipment ${code} not found`, "error");
        return;
    }
    document.getElementById("editShipmentCode").value = s.id;
    document.getElementById("editShipmentTitle").value = s.title || "";
    document.getElementById("editShipmentOrigin").value = s.origin || "";
    document.getElementById("editShipmentDestination").value = s.destination || "";
    document.getElementById("editShipmentHub").value = s.current_hub || s.current_warehouse || "";
    document.getElementById("editShipmentStatus").value = s.status || "In Transit";

    openModal("editShipmentModal");
}

async function handleSaveEditShipment(e) {
    e.preventDefault();
    const code = document.getElementById("editShipmentCode").value;
    const updateData = {
        title: document.getElementById("editShipmentTitle").value,
        origin: document.getElementById("editShipmentOrigin").value,
        destination: document.getElementById("editShipmentDestination").value,
        current_hub: document.getElementById("editShipmentHub").value,
        status: document.getElementById("editShipmentStatus").value
    };

    try {
        await SafeTrackAPI.updateShipment(code, updateData);
        closeModal("editShipmentModal");
        await loadShipmentsData();
        showToast(`Shipment ${code} updated successfully!`, "success");
    } catch (err) {
        console.error("Failed to update shipment:", err);
        showToast(err.message || "Failed to update shipment", "error");
    }
}

async function deleteShipmentHandler(code) {
    if (!confirm(`Are you sure you want to permanently delete shipment ${code}? This will safely remove all telemetry events and alerts for this shipment.`)) {
        return;
    }

    try {
        await SafeTrackAPI.deleteShipment(code);
        await loadShipmentsData();
        showToast(`Shipment ${code} deleted successfully!`, "success");
        if (currentlyInspectedCode === code) {
            closeModal("inspectShipmentModal");
        }
    } catch (err) {
        console.error("Failed to delete shipment:", err);
        showToast(err.message || "Failed to delete shipment", "error");
    }
}

async function populateVehicleOptions() {
    const select = document.getElementById("newShipmentVehicle");
    if (!select) return;
    try {
        const vehicles = await SafeTrackAPI.getVehicles();
        select.innerHTML = vehicles.map(v => `<option value="${v.id}">${v.id} (${v.name})</option>`).join("");
    } catch (e) {
        console.warn("Could not load vehicles for select", e);
    }
}

async function handleCreateShipmentSubmit(e) {
    e.preventDefault();
    const payload = {
        id: document.getElementById("newShipmentCode").value.trim(),
        title: document.getElementById("newShipmentTitle").value.trim(),
        vehicle_id: document.getElementById("newShipmentVehicle").value,
        origin: document.getElementById("newShipmentOrigin").value.trim(),
        destination: document.getElementById("newShipmentDestination").value.trim(),
        status: "In Transit"
    };

    try {
        const created = await SafeTrackAPI.createShipment(payload);
        closeModal("addShipmentModal");
        await loadShipmentsData();
        showToast(`Shipment ${created.id} created successfully!`, "success");
    } catch (err) {
        console.error("Failed to create shipment:", err);
        showToast(err.message || "Failed to create shipment", "error");
    }
}

function filterShipmentsData() {
    const input = document.getElementById("shipmentSearchInput");
    const status = document.getElementById("statusFilter");
    const query = (input?.value || "").toLowerCase().trim();
    const statusVal = status?.value || "all";

    filteredShipmentsList = allShipmentsList.filter((s) => {
        const haystack = [
            s.id,
            s.title,
            s.vehicle_id,
            s.origin,
            s.destination,
            s.current_hub,
            s.current_warehouse
        ].filter(Boolean).join(" ").toLowerCase();

        const matchesQuery = haystack.includes(query);
        const matchesStatus = statusVal === "all" || s.status === statusVal;
        return matchesQuery && matchesStatus;
    });

    renderShipmentsTable();
}

async function inspectShipment(code, silent = false) {
    try {
        currentlyInspectedCode = code;
        const details = await SafeTrackAPI.getShipmentByCode(code);
        if (!details) return;

        renderShipmentInspector(details);

        if (!silent) {
            openModal("inspectShipmentModal");
            startInspectionAutoRefresh(code);
        }

        if (window.lucide) lucide.createIcons();
    } catch (err) {
        console.error("Shipment inspection failed:", err);
        if (!silent) showToast("Error retrieving shipment details", "error");
    }
}

function renderShipmentInspector(details) {
    const titleEl = document.getElementById("inspectModalTitle");
    const bodyEl = document.getElementById("inspectModalBody");
    if (!titleEl || !bodyEl) return;

    const s = details.shipment || {};
    const latest = details.latest_telemetry || null;
    const events = Array.isArray(details.events) ? [...details.events] : [];
    const alerts = Array.isArray(details.alerts) ? details.alerts : [];

    // Backend returns newest first. Keep that order for an operator/admin view.
    events.sort((a, b) => Number(b.id || 0) - Number(a.id || 0));

    titleEl.innerHTML = `
        <i data-lucide="package" class="w-5 h-5 text-blue-600"></i>
        Telemetry & Safety Ledger: ${esc(s.id || s.code)}
    `;

    const latestTemp = latest ? number(latest.temperature, 1) : "—";
    const latestHumidity = latest ? number(latest.humidity, 1) : "—";
    const latestLight = latest ? number(latest.light_lux, 1) : "—";
    const latestAccel = latest ? number(latest.accel_g, 2) : "—";
    const latestGyro = latest ? number(latest.gyro_dps, 1) : "0.0";
    const latestHash = latest ? String(latest.record_hash || "—").substring(0, 16) + "..." : "Genesis";
    const prevHash = latest ? String(latest.previous_hash || "—").substring(0, 16) + "..." : "00000000...";

    // Calculate orientation values from latest telemetry
    const accelVal = latest ? Number(latest.accel_g) : 1.0;
    const gyroVal = latest ? Number(latest.gyro_dps) : 0.0;
    const deviation = (Number.isFinite(accelVal) ? accelVal : 1.0) - 1.0;
    const targetPitch = Math.max(-45, Math.min(45, deviation * 28));
    const targetRoll = Math.max(-45, Math.min(45, gyroVal * 0.5));
    adminTargetPitch = targetPitch;
    adminTargetRoll = targetRoll;

    // Movement & Shock evaluation
    let shockBadgeCls = "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/60";
    let shockLabel = "Normal Movement (< 2.5g)";
    if (accelVal >= 3.0) {
        shockBadgeCls = "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800/60";
        shockLabel = "Severe Shock (≥ 3.0g)";
    } else if (accelVal >= 2.5) {
        shockBadgeCls = "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/60";
        shockLabel = "Warning Shock (2.5g - 3.0g)";
    }

    // Orientation status evaluation
    const absPitch = Math.abs(targetPitch);
    const absRoll = Math.abs(targetRoll);
    let orientBadgeCls = "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/60";
    let orientLabel = "Stable (Upright)";
    if (Math.abs(gyroVal) >= 15 || accelVal >= 2.5) {
        orientBadgeCls = "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/60";
        orientLabel = "Moving / Shaking";
    } else if (absPitch >= 8 || absRoll >= 8) {
        orientBadgeCls = "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/60";
        orientLabel = `Tilted (${absPitch > absRoll ? 'Pitch' : 'Roll'} ${Math.max(absPitch, absRoll).toFixed(0)}°)`;
    }

    const logsRows = events.length
        ? events.map((event) => {
            const health = event.health_level || "Optimal";
            const hashSnippet = String(event.record_hash || "").substring(0, 10);
            return `
                <tr class="border-b border-slate-100 dark:border-slate-700/60 last:border-0 hover:bg-slate-50 dark:hover:bg-slate-700/20">
                    <td class="px-3 py-2.5 whitespace-nowrap text-slate-500 dark:text-slate-400 font-mono text-[10px]">
                        ${esc(formatTime(event.created_at))}
                    </td>
                    <td class="px-3 py-2.5 font-bold text-slate-800 dark:text-slate-100">${number(event.temperature, 1)}°C</td>
                    <td class="px-3 py-2.5 text-slate-600 dark:text-slate-300">${number(event.humidity, 1)}%</td>
                    <td class="px-3 py-2.5 text-slate-600 dark:text-slate-300">${number(event.light_lux, 1)}</td>
                    <td class="px-3 py-2.5 text-slate-600 dark:text-slate-300">${number(event.accel_g, 2)}g</td>
                    <td class="px-3 py-2.5 text-slate-600 dark:text-slate-300 font-mono text-[10px]">${number(event.gyro_dps, 1)}°/s</td>
                    <td class="px-3 py-2.5">
                        <span class="inline-flex items-center px-2 py-0.5 rounded-full border text-[9px] font-bold ${healthClass(health)}">
                            ${esc(health)}
                        </span>
                    </td>
                    <td class="px-3 py-2.5 font-mono text-[10px] text-slate-400 truncate max-w-[80px]" title="${esc(event.record_hash)}">${hashSnippet ? hashSnippet + "…" : "—"}</td>
                    <td class="px-3 py-2.5 text-right text-slate-400 font-mono text-[10px]">#${esc(event.id)}</td>
                </tr>`;
        }).join("")
        : `
            <tr>
                <td colspan="9" class="px-4 py-10 text-center text-slate-400">
                    No telemetry logs have been recorded for this shipment yet.
                </td>
            </tr>`;

    const alertRows = alerts.length
        ? alerts.map((alert) => `
            <div class="flex items-start gap-3 p-3 rounded-xl border ${alert.severity === "Critical" ? "border-rose-100 bg-rose-50/70 dark:bg-rose-950/20 dark:border-rose-900/40" : "border-amber-100 bg-amber-50/70 dark:bg-amber-950/20 dark:border-amber-900/40"}">
                <i data-lucide="${alert.severity === "Critical" ? "alert-octagon" : "alert-triangle"}" class="w-4 h-4 ${alert.severity === "Critical" ? "text-rose-500" : "text-amber-500"} mt-0.5 shrink-0"></i>
                <div class="min-w-0">
                    <div class="flex flex-wrap items-center gap-2">
                        <span class="text-[10px] font-bold uppercase tracking-wider ${alert.severity === "Critical" ? "text-rose-600" : "text-amber-600"}">${esc(alert.severity)}</span>
                        <span class="text-[10px] text-slate-400">${esc(formatDateTime(alert.created_at))}</span>
                    </div>
                    <p class="text-xs font-semibold text-slate-800 dark:text-slate-100 mt-1">${esc(alert.alert_type)}</p>
                    <p class="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">${esc(alert.message)}</p>
                </div>
            </div>`).join("")
        : `<p class="text-xs text-slate-400 text-center py-4">No incidents detected for this shipment.</p>`;

    bodyEl.innerHTML = `
        <!-- SHIPMENT SUMMARY -->
        <div class="p-4 bg-slate-50 dark:bg-slate-700/40 rounded-2xl border border-slate-200 dark:border-slate-700 space-y-3">
            <div class="flex items-center justify-between gap-3">
                <div class="min-w-0">
                    <h4 class="font-bold text-sm text-slate-900 dark:text-white truncate">${esc(s.title)}</h4>
                    <p class="text-[10px] text-slate-400 mt-0.5">Last backend update: ${latest ? esc(formatDateTime(latest.created_at)) : "No telemetry yet"}</p>
                </div>
                <span class="badge ${statusBadgeClass(s.status)} shrink-0">${esc(s.status || "Unknown")}</span>
            </div>
            <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-[11px]">
                <div><p class="text-slate-400">Sender</p><p class="font-semibold text-slate-700 dark:text-slate-200 mt-0.5">${esc(s.sender)}</p></div>
                <div><p class="text-slate-400">Recipient</p><p class="font-semibold text-slate-700 dark:text-slate-200 mt-0.5">${esc(s.recipient)}</p></div>
                <div><p class="text-slate-400">Vehicle</p><p class="font-semibold font-mono text-slate-700 dark:text-slate-200 mt-0.5">${esc(s.vehicle_id)}</p></div>
                <div><p class="text-slate-400">Current Hub</p><p class="font-semibold text-slate-700 dark:text-slate-200 mt-0.5">${esc(s.current_warehouse ?? s.current_hub)}</p></div>
            </div>
        </div>

        <!-- 3D PACKAGE CONDITION & ORIENTATION INSPECTOR (SHIPMENT SPECIFIC MPU6050) -->
        <div class="rounded-2xl border border-slate-200 dark:border-slate-700 overflow-hidden bg-white dark:bg-slate-800 p-4">
            <div class="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-700 mb-3">
                <div>
                    <div class="flex items-center gap-2">
                        <i data-lucide="box" class="w-4 h-4 text-blue-600"></i>
                        <h4 class="font-bold text-sm text-slate-900 dark:text-white">Shipment Condition & 3D Package Orientation</h4>
                    </div>
                    <p class="text-[10px] text-slate-400 mt-0.5">Sensor-driven attitude derived from MPU6050 6-DOF telemetry for shipment <span class="font-mono font-semibold text-blue-600 dark:text-blue-400">${esc(s.id || s.code)}</span></p>
                </div>
                <div class="flex items-center gap-2">
                    <button onclick="resetAdminPackageCamera()" title="Reset Camera View" class="px-2.5 py-1 text-[11px] font-semibold text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 rounded-lg transition-colors flex items-center gap-1.5">
                        <i data-lucide="rotate-ccw" class="w-3.5 h-3.5"></i>
                        <span>Reset View</span>
                    </button>
                    <span class="px-2 py-1 rounded-lg bg-blue-50 dark:bg-blue-950/40 text-blue-600 dark:text-blue-400 text-[10px] font-mono font-bold border border-blue-100 dark:border-blue-900/40">MPU6050 ACTIVE</span>
                </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
                <!-- 3D Viewport -->
                <div class="md:col-span-7 relative bg-gradient-to-b from-slate-50 to-slate-100 dark:from-slate-800/80 dark:to-slate-900/80 rounded-xl border border-slate-200 dark:border-slate-700 overflow-hidden shadow-inner">
                    <div id="adminPackage3dContainer" class="admin-package-canvas"></div>
                    <div class="absolute bottom-2 left-2 right-2 flex justify-center pointer-events-none">
                        <span class="text-[10px] text-slate-500 dark:text-slate-400 bg-white/80 dark:bg-slate-800/80 backdrop-blur-sm px-2.5 py-1 rounded-full border border-slate-200 dark:border-slate-700 shadow-sm flex items-center gap-1.5">
                            <i data-lucide="hand" class="w-3 h-3"></i> Drag to inspect · View does not overwrite sensor angle
                        </span>
                    </div>
                </div>

                <!-- Orientation & IMU Metrics Sidebar -->
                <div class="md:col-span-5 space-y-2.5 text-xs">
                    <!-- Status badges -->
                    <div class="grid grid-cols-2 gap-2">
                        <div class="p-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-700/30">
                            <p class="text-[9px] uppercase tracking-wider font-bold text-slate-400">Orientation</p>
                            <span class="inline-flex items-center gap-1 px-2 py-1 rounded-lg border text-[10px] font-bold mt-1 ${orientBadgeCls}">
                                <i data-lucide="compass" class="w-3 h-3"></i>
                                <span>${orientLabel}</span>
                            </span>
                        </div>
                        <div class="p-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-700/30">
                            <p class="text-[9px] uppercase tracking-wider font-bold text-slate-400">Motion & Shock</p>
                            <span class="inline-flex items-center gap-1 px-2 py-1 rounded-lg border text-[10px] font-bold mt-1 ${shockBadgeCls}">
                                <i data-lucide="activity" class="w-3 h-3"></i>
                                <span>${shockLabel}</span>
                            </span>
                        </div>
                    </div>

                    <!-- Angles -->
                    <div class="grid grid-cols-2 gap-2">
                        <div class="p-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
                            <p class="text-[9px] uppercase tracking-wider font-bold text-slate-400">Pitch Angle (Tilt X)</p>
                            <p class="text-base font-bold font-mono text-slate-900 dark:text-white mt-0.5">${targetPitch >= 0 ? '+' : ''}${targetPitch.toFixed(1)}°</p>
                        </div>
                        <div class="p-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
                            <p class="text-[9px] uppercase tracking-wider font-bold text-slate-400">Roll Angle (Tilt Z)</p>
                            <p class="text-base font-bold font-mono text-slate-900 dark:text-white mt-0.5">${targetRoll >= 0 ? '+' : ''}${targetRoll.toFixed(1)}°</p>
                        </div>
                    </div>

                    <!-- Technical IMU Breakdown -->
                    <div class="p-2.5 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-700/30 space-y-1.5 text-[11px]">
                        <div class="flex items-center justify-between">
                            <span class="text-slate-500 dark:text-slate-400">Accel Vector (accel_g):</span>
                            <strong class="font-mono text-slate-800 dark:text-slate-200">${latestAccel} g</strong>
                        </div>
                        <div class="flex items-center justify-between">
                            <span class="text-slate-500 dark:text-slate-400">Gyro Velocity (gyro_dps):</span>
                            <strong class="font-mono text-slate-800 dark:text-slate-200">${latestGyro} °/s</strong>
                        </div>
                        <div class="flex items-center justify-between">
                            <span class="text-slate-500 dark:text-slate-400">Record Hash:</span>
                            <strong class="font-mono text-[10px] text-blue-600 dark:text-blue-400" title="${latest ? esc(latest.record_hash) : ''}">${latestHash}</strong>
                        </div>
                        <div class="flex items-center justify-between">
                            <span class="text-slate-500 dark:text-slate-400">Previous Hash:</span>
                            <strong class="font-mono text-[10px] text-slate-400" title="${latest ? esc(latest.previous_hash) : ''}">${prevHash}</strong>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- LIVE LATEST READING -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-2">
            <div class="p-3 rounded-xl border border-blue-100 dark:border-blue-900/40 bg-blue-50/50 dark:bg-blue-950/20">
                <p class="text-[9px] uppercase tracking-wider font-bold text-slate-400">Temperature</p>
                <p class="text-base font-bold text-slate-900 dark:text-white mt-1">${latestTemp} <span class="text-xs font-medium">°C</span></p>
            </div>
            <div class="p-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
                <p class="text-[9px] uppercase tracking-wider font-bold text-slate-400">Humidity</p>
                <p class="text-base font-bold text-slate-900 dark:text-white mt-1">${latestHumidity} <span class="text-xs font-medium">%</span></p>
            </div>
            <div class="p-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
                <p class="text-[9px] uppercase tracking-wider font-bold text-slate-400">Light</p>
                <p class="text-base font-bold text-slate-900 dark:text-white mt-1">${latestLight} <span class="text-xs font-medium">LUX</span></p>
            </div>
            <div class="p-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
                <p class="text-[9px] uppercase tracking-wider font-bold text-slate-400">Acceleration</p>
                <p class="text-base font-bold text-slate-900 dark:text-white mt-1">${latestAccel} <span class="text-xs font-medium">g</span></p>
            </div>
        </div>

        <!-- TELEMETRY LOG TABLE -->
        <div class="rounded-2xl border border-slate-200 dark:border-slate-700 overflow-hidden bg-white dark:bg-slate-800">
            <div class="px-4 py-3 border-b border-slate-100 dark:border-slate-700 flex items-center justify-between gap-3">
                <div>
                    <div class="flex items-center gap-2">
                        <span class="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                        <h4 class="font-bold text-sm text-slate-900 dark:text-white">Live Telemetry Logs & Hash Ledger</h4>
                    </div>
                    <p class="text-[10px] text-slate-400 mt-0.5">Latest ${events.length} cryptographic records for shipment ${esc(s.id || s.code)}</p>
                </div>
                <span class="px-2 py-1 rounded-lg bg-slate-100 dark:bg-slate-700 text-[10px] font-bold text-slate-500 dark:text-slate-300">${events.length} EVENTS</span>
            </div>
            <div class="max-h-64 overflow-auto">
                <table class="w-full text-left text-[11px]">
                    <thead class="sticky top-0 z-10 bg-slate-50 dark:bg-slate-700 text-slate-400 uppercase tracking-wider text-[9px] font-bold">
                        <tr>
                            <th class="px-3 py-2.5">Time</th>
                            <th class="px-3 py-2.5">Temp</th>
                            <th class="px-3 py-2.5">Humidity</th>
                            <th class="px-3 py-2.5">Light</th>
                            <th class="px-3 py-2.5">Accel</th>
                            <th class="px-3 py-2.5">Gyro</th>
                            <th class="px-3 py-2.5">Health</th>
                            <th class="px-3 py-2.5">Block Hash</th>
                            <th class="px-3 py-2.5 text-right">ID</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-slate-100 dark:divide-slate-700/60">
                        ${logsRows}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- INCIDENTS -->
        <div class="rounded-2xl border border-slate-200 dark:border-slate-700 p-4 bg-white dark:bg-slate-800">
            <div class="flex items-center justify-between mb-3">
                <div>
                    <h4 class="font-bold text-sm text-slate-900 dark:text-white">Security Events</h4>
                    <p class="text-[10px] text-slate-400">Alerts generated by the backend rules engine</p>
                </div>
                <span class="text-[10px] font-bold text-slate-400">${alerts.length} ALERT${alerts.length === 1 ? "" : "S"}</span>
            </div>
            <div class="space-y-2">${alertRows}</div>
        </div>
    `;

    if (window.lucide) lucide.createIcons();

    // Mount or refresh the 3D scene for this exact shipment
    setTimeout(() => {
        initAdmin3DPackageScene();
    }, 40);
}

function startInspectionAutoRefresh(code) {
    stopInspectionAutoRefresh();
    inspectionRefreshTimer = setInterval(async () => {
        const modal = document.getElementById("inspectShipmentModal");
        if (!modal || modal.classList.contains("hidden") || currentlyInspectedCode !== code) {
            stopInspectionAutoRefresh();
            return;
        }
        await inspectShipment(code, true);
    }, 3000);
}

function stopInspectionAutoRefresh() {
    if (inspectionRefreshTimer) {
        clearInterval(inspectionRefreshTimer);
        inspectionRefreshTimer = null;
    }
}

function openModal(id) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.remove("hidden");
        el.classList.add("flex");
    }
}

function closeModal(id) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.add("hidden");
        el.classList.remove("flex");
    }
    if (id === "inspectShipmentModal") {
        currentlyInspectedCode = null;
        stopInspectionAutoRefresh();
        destroyAdminPackageScene();
    }
}

function toggleDarkMode() {
    document.documentElement.classList.toggle("dark");
    if (window.lucide) lucide.createIcons();
    // Update 3D scene lighting/background if dark mode changes
    if (adminPackageRenderer) {
        onAdminPackageResize();
    }
}

function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = "toast-slide-in pointer-events-auto bg-slate-900 text-white dark:bg-white dark:text-slate-900 px-4 py-2.5 rounded-xl shadow-2xl flex items-center gap-3 text-xs font-semibold border border-slate-700 dark:border-slate-200";

    let iconName = "info";
    if (type === "success") iconName = "check-circle";
    if (type === "warning" || type === "error") iconName = "alert-triangle";

    toast.innerHTML = `
        <i data-lucide="${iconName}" class="w-4 h-4 ${type === "success" ? "text-emerald-400" : type === "warning" || type === "error" ? "text-rose-400" : "text-blue-400"}"></i>
        <span>${esc(message)}</span>
    `;

    container.appendChild(toast);
    if (window.lucide) lucide.createIcons();

    setTimeout(() => {
        toast.classList.add("toast-fade-out");
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ==========================================================================
// ADMIN 3D PACKAGE ORIENTATION SYSTEM (THREE.JS + MPU6050 ISOLATED PER SHIPMENT)
// ==========================================================================

function initAdmin3DPackageScene() {
    const container = document.getElementById("adminPackage3dContainer");
    if (!container || !window.THREE) return;

    // Destroy old canvas if switching shipments
    if (adminPackageRenderer) {
        destroyAdminPackageScene();
    }

    const width = container.clientWidth || 400;
    const height = container.clientHeight || 280;

    // Create Scene
    adminPackageScene = new THREE.Scene();

    // Camera
    adminPackageCamera = new THREE.PerspectiveCamera(40, width / height, 0.1, 100);
    adminPackageCamera.position.set(3.2, 2.3, 3.6);

    // WebGL Renderer
    adminPackageRenderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    adminPackageRenderer.setSize(width, height);
    adminPackageRenderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    adminPackageRenderer.shadowMap.enabled = true;
    adminPackageRenderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(adminPackageRenderer.domElement);

    // OrbitControls
    if (window.THREE.OrbitControls) {
        adminPackageControls = new THREE.OrbitControls(adminPackageCamera, adminPackageRenderer.domElement);
        adminPackageControls.enableDamping = true;
        adminPackageControls.dampingFactor = 0.08;
        adminPackageControls.enableZoom = true;
        adminPackageControls.minDistance = 2.0;
        adminPackageControls.maxDistance = 7.0;
        adminPackageControls.maxPolarAngle = Math.PI / 2 + 0.1;
    }

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
    adminPackageScene.add(ambientLight);

    const keyLight = new THREE.DirectionalLight(0xffffff, 0.9);
    keyLight.position.set(5, 7, 5);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.width = 1024;
    keyLight.shadow.mapSize.height = 1024;
    adminPackageScene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0x93c5fd, 0.35);
    fillLight.position.set(-5, 3, -3);
    adminPackageScene.add(fillLight);

    // Shadow plane
    const planeGeo = new THREE.PlaneGeometry(10, 10);
    const planeMat = new THREE.ShadowMaterial({ opacity: 0.12 });
    const shadowPlane = new THREE.Mesh(planeGeo, planeMat);
    shadowPlane.rotation.x = -Math.PI / 2;
    shadowPlane.position.y = -1.02;
    shadowPlane.receiveShadow = true;
    adminPackageScene.add(shadowPlane);

    // Grid helper
    const isDark = document.documentElement.classList.contains("dark");
    const gridHelper = new THREE.GridHelper(6, 12, isDark ? 0x475569 : 0xcbd5e1, isDark ? 0x334155 : 0xe2e8f0);
    gridHelper.position.y = -1.01;
    adminPackageScene.add(gridHelper);

    // Build Cargo Model
    buildAdminPackageMesh();

    // Start Animation Loop
    animateAdminPackageScene();
}

function buildAdminPackageMesh() {
    const boxWidth = 2.1;
    const boxHeight = 1.3;
    const boxDepth = 1.6;

    adminPackageMesh = new THREE.Group();

    // Procedural Cardboard Texture
    const canvas = document.createElement("canvas");
    canvas.width = 512;
    canvas.height = 512;
    const ctx = canvas.getContext("2d");

    ctx.fillStyle = "#e2c9a5";
    ctx.fillRect(0, 0, 512, 512);

    for (let i = 0; i < 4000; i++) {
        const x = Math.random() * 512;
        const y = Math.random() * 512;
        ctx.fillStyle = Math.random() > 0.5 ? "rgba(180, 150, 115, 0.15)" : "rgba(240, 225, 205, 0.15)";
        ctx.fillRect(x, y, Math.random() * 3, 1);
    }

    ctx.strokeStyle = "rgba(160, 130, 95, 0.4)";
    ctx.lineWidth = 3;
    ctx.strokeRect(10, 10, 492, 492);

    // Label
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(40, 40, 250, 160);
    ctx.strokeStyle = "#cbd5e1";
    ctx.lineWidth = 1;
    ctx.strokeRect(40, 40, 250, 160);

    // Barcode
    ctx.fillStyle = "#0f172a";
    let bx = 60;
    while (bx < 270) {
        const bw = Math.random() > 0.5 ? 4 : 2;
        ctx.fillRect(bx, 130, bw, 50);
        bx += bw + 3;
    }

    ctx.font = "bold 15px sans-serif";
    ctx.fillStyle = "#2563eb";
    ctx.fillText("SAFETRACK INSPECTION", 55, 68);
    ctx.font = "10.5px monospace";
    ctx.fillStyle = "#475569";
    ctx.fillText("WAYBILL: " + (currentlyInspectedCode || "PRCL-ACTIVE"), 55, 88);
    ctx.fillText("MPU6050 TELEMETRY LOGGED", 55, 104);

    ctx.font = "bold 22px sans-serif";
    ctx.fillStyle = "#e11d48";
    ctx.fillText("↑↑ THIS SIDE UP", 315, 78);

    const texture = new THREE.CanvasTexture(canvas);
    const boxMat = new THREE.MeshStandardMaterial({ map: texture, roughness: 0.78, metalness: 0.05 });
    const boxGeo = new THREE.BoxGeometry(boxWidth, boxHeight, boxDepth);
    const boxCore = new THREE.Mesh(boxGeo, boxMat);
    boxCore.castShadow = true;
    boxCore.receiveShadow = true;
    adminPackageMesh.add(boxCore);

    // Security Tape Strip
    const tapeMat = new THREE.MeshStandardMaterial({ color: 0x2563eb, roughness: 0.35, metalness: 0.1 });
    const tapeGeo = new THREE.BoxGeometry(boxWidth + 0.01, 0.08, 0.28);
    const tapeMesh = new THREE.Mesh(tapeGeo, tapeMat);
    tapeMesh.position.y = boxHeight / 2 + 0.01;
    adminPackageMesh.add(tapeMesh);

    // Seal Status Pill
    const sealPillGeo = new THREE.BoxGeometry(0.5, 0.18, 0.03);
    const sealPillMat = new THREE.MeshStandardMaterial({ color: 0x059669, roughness: 0.2, metalness: 0.1 });
    const sealPill = new THREE.Mesh(sealPillGeo, sealPillMat);
    sealPill.position.set(0, 0.1, boxDepth / 2 + 0.01);
    adminPackageMesh.add(sealPill);

    adminPackageScene.add(adminPackageMesh);
}

function onAdminPackageResize() {
    const container = document.getElementById("adminPackage3dContainer");
    if (!container || !adminPackageRenderer || !adminPackageCamera) return;
    const width = container.clientWidth;
    const height = container.clientHeight;
    if (width === 0 || height === 0) return;
    adminPackageCamera.aspect = width / height;
    adminPackageCamera.updateProjectionMatrix();
    adminPackageRenderer.setSize(width, height);
}

function resetAdminPackageCamera() {
    if (!adminPackageCamera || !adminPackageControls) return;
    adminPackageCamera.position.set(3.2, 2.3, 3.6);
    adminPackageControls.target.set(0, 0, 0);
    adminPackageControls.update();
}

function animateAdminPackageScene() {
    adminAnimFrame = requestAnimationFrame(animateAdminPackageScene);

    if (adminPackageControls) {
        adminPackageControls.update();
    }

    // Physical orientation driven by real sensor telemetry (smooth lerp, no artificial endless rotation)
    if (adminPackageMesh) {
        const lerpSpeed = 0.08;
        adminCurrentPitch += (adminTargetPitch - adminCurrentPitch) * lerpSpeed;
        adminCurrentRoll += (adminTargetRoll - adminCurrentRoll) * lerpSpeed;

        adminPackageMesh.rotation.x = THREE.MathUtils.degToRad(adminCurrentPitch);
        adminPackageMesh.rotation.z = THREE.MathUtils.degToRad(adminCurrentRoll);
        adminPackageMesh.rotation.y = 0;
    }

    if (adminPackageRenderer && adminPackageScene && adminPackageCamera) {
        adminPackageRenderer.render(adminPackageScene, adminPackageCamera);
    }
}

function destroyAdminPackageScene() {
    if (adminAnimFrame) {
        cancelAnimationFrame(adminAnimFrame);
        adminAnimFrame = null;
    }
    if (adminPackageRenderer) {
        const dom = adminPackageRenderer.domElement;
        if (dom && dom.parentElement) {
            dom.parentElement.removeChild(dom);
        }
        adminPackageRenderer.dispose();
        adminPackageRenderer = null;
    }
    adminPackageScene = null;
    adminPackageCamera = null;
    adminPackageMesh = null;
    adminPackageControls = null;
    adminTargetPitch = 0;
    adminTargetRoll = 0;
    adminCurrentPitch = 0;
    adminCurrentRoll = 0;
}

window.addEventListener("resize", onAdminPackageResize);
