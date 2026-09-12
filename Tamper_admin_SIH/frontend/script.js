/**
 * SafeTrack Admin Console - Main Dashboard Logic
 */

let vehiclesList = [];
let shipmentsList = [];
let alertsList = [];
let filteredVehiclesList = [];

document.addEventListener('DOMContentLoaded', async () => {
    await loadDashboardData();
    initCharts();
    if (window.lucide) lucide.createIcons();
});

async function loadDashboardData() {
    try {
        vehiclesList = await SafeTrackAPI.getVehicles();
        shipmentsList = await SafeTrackAPI.getShipments();
        alertsList = await SafeTrackAPI.getAlerts();
        filteredVehiclesList = [...vehiclesList];

        renderKPIs();
        renderVehiclesTable();
        renderRecentAlertsFeed();
        populateVehicleDropdown();
    } catch (err) {
        console.error("Error loading dashboard data:", err);
        showToast("Error loading dashboard state", "error");
    }
}

function renderKPIs() {
    const totalShipments = shipmentsList.length;
    const activeVehiclesCount = vehiclesList.filter(v => v.status !== "Stopped").length;
    const inTransitCount = shipmentsList.filter(s => s.status === "In Transit").length;
    const activeAlertsCount = alertsList.filter(a => a.status === "Active").length;

    const kpiShipments = document.getElementById('kpiTotalShipments');
    const kpiVehicles = document.getElementById('kpiActiveVehicles');
    const kpiTransit = document.getElementById('kpiInTransit');
    const kpiAlerts = document.getElementById('kpiAlerts');
    const sidebarBadge = document.getElementById('sidebarAlertBadge');

    if (kpiShipments) kpiShipments.innerText = totalShipments;
    if (kpiVehicles) kpiVehicles.innerText = activeVehiclesCount;
    if (kpiTransit) kpiTransit.innerText = inTransitCount;
    if (kpiAlerts) kpiAlerts.innerText = activeAlertsCount;
    if (sidebarBadge) sidebarBadge.innerText = activeAlertsCount;
}

function renderVehiclesTable() {
    const tbody = document.getElementById('vehicleTableBody');
    const paginationInfo = document.getElementById('paginationInfo');
    if (!tbody) return;

    tbody.innerHTML = '';

    if (filteredVehiclesList.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center py-8 text-slate-400 font-medium">
                    No matching vehicles found.
                </td>
            </tr>
        `;
        if (paginationInfo) paginationInfo.innerText = `Showing 0 of ${vehiclesList.length} vehicles`;
        return;
    }

    filteredVehiclesList.forEach(v => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors';

        // Badge class determination
        let badgeClass = 'badge-in-transit';
        if (v.status === 'Delayed') badgeClass = 'badge-delayed';
        if (v.status === 'Stopped') badgeClass = 'badge-stopped';
        if (v.status === 'At Warehouse') badgeClass = 'badge-at-warehouse';

        // Assigned shipments formatting
        const shipmentPills = v.assigned_shipments.length > 0 ?
            v.assigned_shipments.map(sId => `<a href="shipments.html?code=${sId}" class="inline-block px-2 py-0.5 text-[11px] font-mono font-semibold bg-blue-50 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400 rounded-md border border-blue-200 dark:border-blue-800 hover:underline">${sId}</a>`).join(' ') :
            `<span class="text-slate-400 italic">None</span>`;

        tr.innerHTML = `
            <td class="px-5 py-4">
                <a href="vehicle-details.html?id=${v.id}" class="font-bold text-blue-600 dark:text-blue-400 hover:underline flex items-center gap-1.5">
                    <span>${v.id}</span>
                    <i data-lucide="external-link" class="w-3 h-3 opacity-60"></i>
                </a>
                <p class="text-[11px] text-slate-400 font-normal">${v.name}</p>
            </td>
            <td class="px-5 py-4">
                <div class="flex flex-wrap gap-1">
                    ${shipmentPills}
                </div>
            </td>
            <td class="px-5 py-4 text-slate-700 dark:text-slate-200">
                <p class="font-medium text-xs">${v.origin}</p>
                <p class="text-[11px] text-slate-400">→ ${v.destination}</p>
            </td>
            <td class="px-5 py-4 text-slate-700 dark:text-slate-300 font-medium">
                ${v.current_hub}
            </td>
            <td class="px-5 py-4">
                <span class="badge ${badgeClass}">
                    ${v.status}
                </span>
            </td>
            <td class="px-5 py-4 text-center">
                <div class="flex items-center justify-center gap-2">
                    <a href="vehicle-details.html?id=${v.id}" title="View Details" class="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg text-slate-600 dark:text-slate-300 hover:text-blue-600 transition-colors">
                        <i data-lucide="eye" class="w-4 h-4"></i>
                    </a>
                    <button onclick="openVehicleSettings('${v.id}')" title="Vehicle Settings" class="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg text-slate-600 dark:text-slate-300 hover:text-blue-600 transition-colors">
                        <i data-lucide="settings" class="w-4 h-4"></i>
                    </button>
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });

    if (paginationInfo) {
        paginationInfo.innerText = `Showing 1 to ${filteredVehiclesList.length} of ${vehiclesList.length} vehicles`;
    }

    if (window.lucide) lucide.createIcons();
}

function filterByVehicleStatus(status) {
    applyStatusFilter(status);
}

function populateVehicleDropdown() {
    const select = document.getElementById('newShipmentVehicle');
    if (!select || !vehiclesList) return;
    select.innerHTML = vehiclesList.map(v => `<option value="${v.id}">${v.id} (${v.name})</option>`).join('');
}

function openVehicleSettings(vehicleId) {
    const v = vehiclesList.find(item => item.id === vehicleId);
    if (!v) {
        showToast(`Vehicle ${vehicleId} not found`, 'error');
        return;
    }
    document.getElementById('settingVehicleId').value = v.id;
    document.getElementById('settingLicensePlate').value = v.license_plate || '';
    document.getElementById('settingVehicleName').value = v.name || '';
    document.getElementById('settingDriver').value = v.driver || '';
    document.getElementById('settingOrigin').value = v.origin || '';
    document.getElementById('settingDestination').value = v.destination || '';
    document.getElementById('settingCurrentHub').value = v.current_hub || '';
    document.getElementById('settingStatus').value = v.status || 'In Transit';

    openModal('vehicleSettingsModal');
}

async function handleSaveVehicleSettings(e) {
    e.preventDefault();
    const vehicleId = document.getElementById('settingVehicleId').value;
    const updateData = {
        license_plate: document.getElementById('settingLicensePlate').value,
        name: document.getElementById('settingVehicleName').value,
        driver: document.getElementById('settingDriver').value,
        origin: document.getElementById('settingOrigin').value,
        destination: document.getElementById('settingDestination').value,
        current_hub: document.getElementById('settingCurrentHub').value,
        status: document.getElementById('settingStatus').value
    };

    try {
        const updated = await SafeTrackAPI.updateVehicle(vehicleId, updateData);
        closeModal('vehicleSettingsModal');
        await loadDashboardData();
        showToast(`Vehicle ${vehicleId} updated successfully!`, 'success');
    } catch (err) {
        console.error("Error updating vehicle:", err);
        showToast(err.message || 'Error updating vehicle', 'error');
    }
}

async function handleDeleteVehicleFromModal() {
    const vehicleId = document.getElementById('settingVehicleId').value;
    if (!confirm(`Are you sure you want to delete vehicle ${vehicleId}? All assigned shipments will be unassigned.`)) {
        return;
    }

    try {
        await SafeTrackAPI.deleteVehicle(vehicleId);
        closeModal('vehicleSettingsModal');
        await loadDashboardData();
        showToast(`Vehicle ${vehicleId} deleted successfully!`, 'success');
    } catch (err) {
        console.error("Error deleting vehicle:", err);
        showToast(err.message || 'Error deleting vehicle', 'error');
    }
}

function handleVehicleSearch() {
    const query = document.getElementById('searchInput').value.toLowerCase().trim();
    filteredVehiclesList = vehiclesList.filter(v =>
        v.id.toLowerCase().includes(query) ||
        v.name.toLowerCase().includes(query) ||
        v.driver.toLowerCase().includes(query) ||
        v.origin.toLowerCase().includes(query) ||
        v.destination.toLowerCase().includes(query)
    );
    renderVehiclesTable();
}

function applyStatusFilter(status) {
    toggleDropdown('filterPopover');
    if (status === 'all') {
        filteredVehiclesList = [...vehiclesList];
        showToast('Showing all vehicles', 'info');
    } else {
        filteredVehiclesList = vehiclesList.filter(v => v.status === status);
        showToast(`Filtered by ${status}`, 'info');
    }
    renderVehiclesTable();
}

function renderRecentAlertsFeed() {
    const feedContainer = document.getElementById('recentAlertsFeed');
    if (!feedContainer) return;

    feedContainer.innerHTML = '';
    const recentAlerts = alertsList.slice(0, 3);

    recentAlerts.forEach(a => {
        let iconName = 'alert-triangle';
        let bgClass = 'bg-rose-50 text-rose-600 dark:bg-rose-900/30';
        let dotColor = 'bg-rose-500';

        if (a.severity === 'Warning') {
            bgClass = 'bg-amber-50 text-amber-600 dark:bg-amber-900/30';
            dotColor = 'bg-amber-500';
        }

        const div = document.createElement('div');
        div.className = 'flex items-start justify-between gap-3 text-xs';
        div.innerHTML = `
            <div class="flex items-start gap-3">
                <div class="w-8 h-8 rounded-xl ${bgClass} flex items-center justify-center shrink-0 mt-0.5">
                    <i data-lucide="${iconName}" class="w-4 h-4"></i>
                </div>
                <div>
                    <p class="font-bold text-slate-800 dark:text-white">${a.alert_type}</p>
                    <p class="text-[11px] text-slate-400 font-mono">${a.shipment_id}</p>
                </div>
            </div>
            <div class="flex items-center gap-1.5 shrink-0 text-[11px] text-slate-400">
                <span>Recent</span>
                <span class="w-2 h-2 rounded-full ${dotColor}"></span>
            </div>
        `;
        feedContainer.appendChild(div);
    });

    if (window.lucide) lucide.createIcons();
}

async function handleAddVehicleSubmit(e) {
    e.preventDefault();
    const vehicleData = {
        id: document.getElementById('newVehicleId').value,
        name: document.getElementById('newVehicleName').value,
        origin: document.getElementById('newOrigin').value,
        destination: document.getElementById('newDestination').value,
        driver: document.getElementById('newDriver').value,
        status: document.getElementById('newVehicleStatus').value,
        assigned_shipments: []
    };

    try {
        const created = await SafeTrackAPI.createVehicle(vehicleData);
        vehiclesList.unshift(created);
        filteredVehiclesList = [...vehiclesList];
        renderVehiclesTable();
        renderKPIs();
        closeModal('addVehicleModal');
        showToast(`Vehicle ${created.id} added successfully!`, 'success');
    } catch (err) {
        showToast('Error adding vehicle', 'error');
    }
}

async function handleAddShipmentSubmit(e) {
    e.preventDefault();
    const shipmentData = {
        id: document.getElementById('newShipmentCode').value,
        title: document.getElementById('newShipmentTitle').value,
        vehicle_id: document.getElementById('newShipmentVehicle').value,
        origin: document.getElementById('newShipmentOrigin').value,
        destination: document.getElementById('newShipmentDestination').value,
        status: "In Transit"
    };

    try {
        const created = await SafeTrackAPI.createShipment(shipmentData);
        shipmentsList.unshift(created);
        closeModal('addShipmentModal');
        await loadDashboardData();
        showToast(`Shipment ${created.id} created successfully!`, 'success');
    } catch (err) {
        showToast('Error creating shipment', 'error');
    }
}

// Chart Initializations
function initCharts() {
    // 1. Shipment Status Bar Chart
    const ctxBar = document.getElementById('shipmentStatusChart')?.getContext('2d');
    if (ctxBar) {
        new Chart(ctxBar, {
            type: 'bar',
            data: {
                labels: ['In Transit', 'At Warehouse', 'Delayed', 'Compromised'],
                datasets: [{
                    data: [18, 6, 4, 2],
                    backgroundColor: ['#10b981', '#3b82f6', '#f59e0b', '#ef4444'],
                    borderRadius: 8,
                    barThickness: 28
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false }, ticks: { font: { family: 'Inter', size: 11 }, color: '#94a3b8' } },
                    y: { beginAtZero: true, max: 20, grid: { color: 'rgba(226, 232, 240, 0.5)' }, ticks: { font: { family: 'Inter', size: 11 }, color: '#94a3b8' } }
                }
            }
        });
    }

    // 2. Temperature Line Chart
    const ctxLine = document.getElementById('tempMonitoringChart')?.getContext('2d');
    if (ctxLine) {
        const gradient = ctxLine.createLinearGradient(0, 0, 0, 200);
        gradient.addColorStop(0, 'rgba(59, 130, 246, 0.3)');
        gradient.addColorStop(1, 'rgba(59, 130, 246, 0.0)');

        new Chart(ctxLine, {
            type: 'line',
            data: {
                labels: ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00', '24:00'],
                datasets: [{
                    data: [3.5, 3.2, 4.1, 4.2, 5.0, 3.8, 4.2],
                    borderColor: '#3b82f6',
                    borderWidth: 2,
                    fill: true,
                    backgroundColor: gradient,
                    tension: 0.4,
                    pointRadius: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false }, ticks: { font: { family: 'Inter', size: 10 }, color: '#94a3b8' } },
                    y: { min: 0, max: 10, grid: { color: 'rgba(226, 232, 240, 0.5)' }, ticks: { font: { family: 'Inter', size: 10 }, color: '#94a3b8', callback: v => v + '°C' } }
                }
            }
        });
    }

    // 3. System Overview Donut Chart
    const ctxDonut = document.getElementById('systemOverviewDonut')?.getContext('2d');
    if (ctxDonut) {
        new Chart(ctxDonut, {
            type: 'doughnut',
            data: {
                labels: ['In Transit', 'Delayed', 'Stopped'],
                datasets: [{
                    data: [18, 4, 2],
                    backgroundColor: ['#10b981', '#f59e0b', '#ef4444'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '76%',
                plugins: { legend: { display: false } }
            }
        });
    }
}

// UI Helper Functions
function toggleSubmenu(menuId, chevronId) {
    const menu = document.getElementById(menuId);
    const chevron = document.getElementById(chevronId);
    if (menu) menu.classList.toggle('hidden');
    if (chevron) chevron.classList.toggle('rotate-180');
}

function toggleDropdown(id) {
    const dropdown = document.getElementById(id);
    if (!dropdown) return;
    document.querySelectorAll('#notifMenu, #filterPopover').forEach(d => {
        if (d.id !== id) d.classList.add('hidden');
    });
    dropdown.classList.toggle('hidden');
}

function openModal(id) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.remove('hidden');
        el.classList.add('flex');
    }
}

function closeModal(id) {
    const el = document.getElementById(id);
    if (el) {
        el.classList.add('hidden');
        el.classList.remove('flex');
    }
}

function toggleDarkMode() {
    document.documentElement.classList.toggle('dark');
    const isDark = document.documentElement.classList.contains('dark');
    showToast(`Switched to ${isDark ? 'Dark' : 'Light'} Mode`, 'info');
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = 'toast-slide-in pointer-events-auto bg-slate-900 text-white dark:bg-white dark:text-slate-900 px-4 py-2.5 rounded-xl shadow-2xl flex items-center gap-3 text-xs font-semibold border border-slate-700 dark:border-slate-200';

    let iconName = 'info';
    if (type === 'success') iconName = 'check-circle';
    if (type === 'warning' || type === 'error') iconName = 'alert-triangle';

    toast.innerHTML = `
        <i data-lucide="${iconName}" class="w-4 h-4 ${type === 'success' ? 'text-emerald-400' : type === 'warning' || type === 'error' ? 'text-rose-400' : 'text-blue-400'}"></i>
        <span>${message}</span>
    `;

    container.appendChild(toast);
    if (window.lucide) lucide.createIcons();

    setTimeout(() => {
        toast.classList.add('toast-fade-out');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}
