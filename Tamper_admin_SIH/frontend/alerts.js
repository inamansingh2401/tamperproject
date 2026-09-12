/**
 * SafeTrack Admin Console - Alerts & Incidents Controller
 */

let allAlertsList = [];
let currentFilter = 'all';

document.addEventListener('DOMContentLoaded', async () => {
    await loadAlertsData();
    if (window.lucide) lucide.createIcons();
});

async function loadAlertsData() {
    try {
        allAlertsList = await SafeTrackAPI.getAlerts();
        renderAlertsFeed();
    } catch (err) {
        console.error("Error loading alerts:", err);
        showToast("Failed to load alerts", "error");
    }
}

function renderAlertsFeed() {
    const container = document.getElementById('alertsContainer');
    const countDisplay = document.getElementById('alertsDisplayCount');
    const sidebarBadge = document.getElementById('alertsCountBadge');
    if (!container) return;

    container.innerHTML = '';

    const filtered = allAlertsList.filter(a => {
        if (currentFilter === 'all') return true;
        return a.severity === currentFilter || a.status === currentFilter;
    });

    if (countDisplay) countDisplay.innerText = filtered.length;
    const activeCount = allAlertsList.filter(a => a.status === 'Active').length;
    if (sidebarBadge) sidebarBadge.innerText = activeCount;

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="bg-white dark:bg-slate-800 rounded-2xl p-12 text-center text-slate-400 space-y-2 border border-slate-200 dark:border-slate-700">
                <i data-lucide="shield-check" class="w-12 h-12 mx-auto text-emerald-500"></i>
                <p class="font-bold text-slate-800 dark:text-white">No incidents matching filter.</p>
                <p class="text-xs">All monitored shipments in this view are safe.</p>
            </div>
        `;
        if (window.lucide) lucide.createIcons();
        return;
    }

    filtered.forEach(a => {
        const card = document.createElement('div');
        card.className = 'bg-white dark:bg-slate-800 p-5 rounded-2xl border border-slate-200 dark:border-slate-700 shadow-sm space-y-3';

        let badgeClass = a.severity === 'Critical' ? 'badge-critical' :
                         a.severity === 'Warning' ? 'badge-warning' : 'badge-optimal';

        let iconName = a.severity === 'Critical' ? 'alert-octagon' :
                       a.severity === 'Warning' ? 'alert-triangle' : 'check-circle-2';

        let iconBg = a.severity === 'Critical' ? 'bg-rose-50 text-rose-600 dark:bg-rose-900/30' :
                     a.severity === 'Warning' ? 'bg-amber-50 text-amber-600 dark:bg-amber-900/30' : 'bg-emerald-50 text-emerald-600 dark:bg-emerald-900/30';

        card.innerHTML = `
            <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 dark:border-slate-700/80 pb-3">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl ${iconBg} flex items-center justify-center shrink-0">
                        <i data-lucide="${iconName}" class="w-5 h-5"></i>
                    </div>
                    <div>
                        <h4 class="font-bold text-sm text-slate-900 dark:text-white">${a.alert_type}</h4>
                        <p class="text-[11px] text-slate-400">Timestamp: ${a.timestamp} • Location: ${a.location}</p>
                    </div>
                </div>

                <div class="flex items-center gap-2">
                    <span class="badge ${badgeClass}">${a.severity}</span>
                    <span class="text-xs font-semibold px-2.5 py-0.5 rounded-full ${a.status === 'Active' ? 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300' : 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300'}">
                        ${a.status}
                    </span>
                </div>
            </div>

            <!-- MESSAGE & META -->
            <p class="text-xs font-medium text-slate-700 dark:text-slate-200 bg-slate-50 dark:bg-slate-700/40 p-3 rounded-xl border border-slate-100 dark:border-slate-700 font-mono">
                ${a.message}
            </p>

            <!-- FOOTER ACTIONS -->
            <div class="flex items-center justify-between text-xs pt-1">
                <div class="flex items-center gap-3 text-slate-500">
                    <span>Shipment: <a href="shipments.html?code=${a.shipment_id}" class="font-mono font-bold text-blue-600 dark:text-blue-400 hover:underline">${a.shipment_id}</a></span>
                    <span>Vehicle: <a href="vehicle-details.html?id=${a.vehicle_id}" class="font-mono font-bold text-blue-600 dark:text-blue-400 hover:underline">${a.vehicle_id}</a></span>
                </div>

                <div class="flex items-center gap-2">
                    <a href="shipments.html?code=${a.shipment_id}" class="px-3 py-1.5 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 hover:bg-blue-600 hover:text-white font-semibold rounded-xl transition-colors">
                        View Shipment
                    </a>
                    ${a.status === 'Active' ? `
                        <button onclick="resolveSingleAlert('${a.id}')" class="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold rounded-xl shadow-sm transition-colors">
                            Mark Resolved
                        </button>
                    ` : `
                        <span class="text-emerald-600 font-bold flex items-center gap-1">
                            <i data-lucide="check" class="w-4 h-4"></i> Resolved
                        </span>
                    `}
                </div>
            </div>
        `;

        container.appendChild(card);
    });

    if (window.lucide) lucide.createIcons();
}

function filterAlertsTab(filter, btn) {
    currentFilter = filter;
    document.querySelectorAll('.alert-tab-btn').forEach(b => {
        b.className = 'alert-tab-btn px-3 py-1.5 rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600 transition-all font-semibold';
    });
    if (btn) {
        btn.className = 'alert-tab-btn px-3 py-1.5 rounded-lg bg-blue-600 text-white shadow-sm transition-all font-bold';
    }
    renderAlertsFeed();
}

async function resolveSingleAlert(alertId) {
    try {
        await SafeTrackAPI.resolveAlert(alertId);
        await loadAlertsData();
        showToast(`Incident ${alertId} marked resolved`, 'success');
    } catch (err) {
        showToast('Error resolving alert', 'error');
    }
}

async function markAllAlertsResolved() {
    try {
        await SafeTrackAPI.resolveAllAlerts();
        await loadAlertsData();
        showToast('All active alerts marked resolved', 'success');
    } catch (err) {
        console.error("Error resolving all alerts:", err);
        showToast('Error resolving alerts', 'error');
    }
}

function toggleDarkMode() {
    document.documentElement.classList.toggle('dark');
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
