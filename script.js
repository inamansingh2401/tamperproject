// SafeTrack Admin Console - Interactivity & Data Management

// Initial Vehicle Dataset matching the screenshot
let vehiclesData = [
    {
        id: "PRCL-2024-05-21-001",
        origin: "Mumbai Central Warehouse",
        destination: "Delhi Central Facility",
        status: "In Transit"
    },
    {
        id: "PRCL-2024-05-21-002",
        origin: "Kolkata Hub",
        destination: "Bangalore Hub",
        status: "In Transit"
    },
    {
        id: "PRCL-2024-05-21-003",
        origin: "Chennai Hub",
        destination: "Hyderabad Hub",
        status: "In Transit"
    },
    {
        id: "PRCL-2024-05-21-004",
        origin: "Pune Warehouse",
        destination: "Mumbai Hub",
        status: "Delayed"
    },
    {
        id: "PRCL-2024-05-21-005",
        origin: "Ahmedabad Hub",
        destination: "Delhi Facility",
        status: "In Transit"
    }
];

let filteredVehicles = [...vehiclesData];
let currentPage = 1;
const itemsPerPage = 5;
let totalCount = 24; // Simulated total from dashboard
let isHiddenAll = false;
let isMaintenanceMode = false;

// Initialize Dashboard on Load
document.addEventListener('DOMContentLoaded', () => {
    renderTable();
    initCharts();
    if (window.lucide) {
        lucide.createIcons();
    }
});

// Render Vehicles Table
function renderTable() {
    const tbody = document.getElementById('vehicleTableBody');
    const paginationInfo = document.getElementById('paginationInfo');
    
    if (!tbody) return;

    tbody.innerHTML = '';

    if (isHiddenAll) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center py-10 text-slate-400 font-medium">
                    <div class="flex flex-col items-center gap-2">
                        <i data-lucide="eye-off" class="w-8 h-8 text-slate-300"></i>
                        <p>All vehicles are currently hidden from view.</p>
                        <button onclick="toggleHideAllVehicles(false)" class="text-xs text-blue-600 font-semibold hover:underline mt-1">Unhide Vehicles</button>
                    </div>
                </td>
            </tr>
        `;
        paginationInfo.innerText = `Showing 0 of ${totalCount} vehicles`;
        if (window.lucide) lucide.createIcons();
        return;
    }

    if (filteredVehicles.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="text-center py-8 text-slate-400 font-medium">
                    No matching vehicles found.
                </td>
            </tr>
        `;
        paginationInfo.innerText = `Showing 0 of ${totalCount} vehicles`;
        return;
    }

    filteredVehicles.forEach((v) => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors';

        // Status badge styling
        let badgeClass = 'badge-in-transit';
        if (v.status === 'Delayed') badgeClass = 'badge-delayed';
        if (v.status === 'Stopped') badgeClass = 'badge-stopped';

        tr.innerHTML = `
            <td class="px-5 py-4 font-semibold text-blue-600 dark:text-blue-400 hover:underline cursor-pointer">
                <a href="vehicle-details.html?id=${v.id}" class="hover:underline flex items-center gap-1.5">
                    <span>${v.id}</span>
                    <i data-lucide="external-link" class="w-3 h-3 text-blue-400 opacity-70"></i>
                </a>
            </td>
            <td class="px-5 py-4 text-slate-800 dark:text-slate-200">
                ${v.origin}
            </td>
            <td class="px-5 py-4 text-slate-800 dark:text-slate-200">
                ${v.destination}
            </td>
            <td class="px-5 py-4">
                <span class="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-semibold ${badgeClass}">
                    ${v.status}
                </span>
            </td>
            <td class="px-5 py-4 text-center">
                <div class="flex items-center justify-center gap-1.5 text-slate-400">
                    <!-- View Products Icon -->
                    <a href="vehicle-details.html?id=${v.id}" title="View Vehicle Products & Telemetry" class="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg hover:text-blue-600 transition-colors">
                        <i data-lucide="boxes" class="w-4 h-4"></i>
                    </a>
                    <!-- Settings Icon -->
                    <button onclick="showToast('Vehicle configuration opened for ${v.id}', 'info')" title="Vehicle Settings" class="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg hover:text-slate-700 dark:hover:text-slate-200 transition-colors">
                        <i data-lucide="settings" class="w-4 h-4"></i>
                    </button>
                    <!-- More Actions Icon -->
                    <button onclick="showToast('Options menu for ${v.id}', 'info')" title="More Options" class="p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg hover:text-slate-700 dark:hover:text-slate-200 transition-colors">
                        <i data-lucide="more-vertical" class="w-4 h-4"></i>
                    </button>
                </div>
            </td>
        `;

        tbody.appendChild(tr);
    });

    paginationInfo.innerText = `Showing 1 to ${filteredVehicles.length} of ${totalCount} vehicles`;

    if (window.lucide) {
        lucide.createIcons();
    }
}

// Search Filtering
function handleSearch() {
    const query = document.getElementById('searchInput').value.toLowerCase().trim();
    filteredVehicles = vehiclesData.filter(v => 
        v.id.toLowerCase().includes(query) ||
        v.origin.toLowerCase().includes(query) ||
        v.destination.toLowerCase().includes(query) ||
        v.status.toLowerCase().includes(query)
    );
    renderTable();
}

// Filter Status
function applyStatusFilter(status) {
    toggleDropdown('filterPopover');
    if (status === 'all') {
        filteredVehicles = [...vehiclesData];
        showToast('Showing all vehicles', 'info');
    } else {
        filteredVehicles = vehiclesData.filter(v => v.status === status);
        showToast(`Filtered by ${status}`, 'info');
    }
    renderTable();
}

// Submenu Vehicles Filter
function filterByVehicleSubmenu(type) {
    setActiveNav(null, 'vehicles');
    filteredVehicles = [...vehiclesData];
    isHiddenAll = false;
    renderTable();
    showToast('Displaying All Vehicles', 'info');
}

// Hide All Vehicles Toggle
function toggleHideAllVehicles(hide) {
    isHiddenAll = hide;
    renderTable();
    if (hide) {
        showToast('All vehicles hidden from table view', 'warning');
    } else {
        showToast('All vehicles unhidden', 'success');
    }
}

// Maintenance Mode Toggle
function toggleMaintenanceMode() {
    isMaintenanceMode = !isMaintenanceMode;
    if (isMaintenanceMode) {
        showToast('System in Maintenance Mode: Vehicle feeds paused', 'warning');
    } else {
        showToast('Maintenance Mode disabled', 'success');
    }
}

// View Vehicle Modal
function viewVehicle(id) {
    const vehicle = vehiclesData.find(v => v.id === id);
    if (!vehicle) return;

    document.getElementById('modalVehicleTitle').innerHTML = `
        <i data-lucide="truck" class="w-5 h-5 text-blue-600"></i>
        Details for ${vehicle.id}
    `;

    document.getElementById('modalVehicleContent').innerHTML = `
        <div class="grid grid-cols-2 gap-3 bg-slate-50 dark:bg-slate-700/40 p-3.5 rounded-2xl border border-slate-100 dark:border-slate-700">
            <div>
                <span class="text-slate-400 block text-[10px] uppercase font-bold">Vehicle ID</span>
                <span class="font-mono font-semibold text-slate-800 dark:text-slate-200">${vehicle.id}</span>
            </div>
            <div>
                <span class="text-slate-400 block text-[10px] uppercase font-bold">Status</span>
                <span class="font-semibold text-emerald-600">${vehicle.status}</span>
            </div>
            <div>
                <span class="text-slate-400 block text-[10px] uppercase font-bold">Origin</span>
                <span class="text-slate-700 dark:text-slate-300 font-medium">${vehicle.origin}</span>
            </div>
            <div>
                <span class="text-slate-400 block text-[10px] uppercase font-bold">Destination</span>
                <span class="text-slate-700 dark:text-slate-300 font-medium">${vehicle.destination}</span>
            </div>
        </div>

        <div class="pt-2">
            <a href="vehicle-details.html?id=${vehicle.id}" class="w-full flex items-center justify-center gap-2 p-2.5 bg-blue-600 hover:bg-blue-700 text-white font-bold rounded-xl text-xs shadow-md transition-all">
                <i data-lucide="boxes" class="w-4 h-4"></i>
                <span>View Products & Sensor Telemetry →</span>
            </a>
        </div>
    `;

    openModal('viewVehicleModal');
    if (window.lucide) lucide.createIcons();
}

// Handle Add New Vehicle
function handleAddVehicle(e) {
    e.preventDefault();
    const newVehicle = {
        id: document.getElementById('newVehicleId').value,
        origin: document.getElementById('newOrigin').value,
        destination: document.getElementById('newDestination').value,
        status: document.getElementById('newStatus').value
    };

    vehiclesData.unshift(newVehicle);
    filteredVehicles = [...vehiclesData];
    totalCount += 1;
    renderTable();
    closeModal('addVehicleModal');
    showToast(`Vehicle ${newVehicle.id} added successfully!`, 'success');
}

// Modal Helpers
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

// Dropdown Toggle
function toggleDropdown(id) {
    const dropdown = document.getElementById(id);
    if (!dropdown) return;
    
    // Close other dropdowns
    document.querySelectorAll('#notifMenu, #filterPopover, #hideOptionsPopover').forEach(d => {
        if (d.id !== id) d.classList.add('hidden');
    });

    dropdown.classList.toggle('hidden');
}

// Submenu Accordion Toggle
function toggleSubmenu(menuId, chevronId) {
    const menu = document.getElementById(menuId);
    const chevron = document.getElementById(chevronId);
    if (menu) menu.classList.toggle('hidden');
    if (chevron) chevron.classList.toggle('rotate-180');
}

// Active Nav state handler
function setActiveNav(element, name) {
    if (element) {
        document.querySelectorAll('#sidebar nav a').forEach(a => {
            a.classList.remove('bg-blue-600', 'text-white', 'shadow-md', 'shadow-blue-600/20', 'font-semibold');
            a.classList.add('hover:bg-sidebar-hover', 'text-slate-300', 'hover:text-white');
        });
        element.classList.add('bg-blue-600', 'text-white', 'shadow-md', 'shadow-blue-600/20', 'font-semibold');
    }
    showToast(`Navigated to ${name.toUpperCase()}`, 'info');
}

// Dark Mode Toggle
function toggleDarkMode() {
    document.documentElement.classList.toggle('dark');
    const isDark = document.documentElement.classList.contains('dark');
    showToast(`Switched to ${isDark ? 'Dark' : 'Light'} Mode`, 'info');
}

// Pagination placeholder function
function changePage(page) {
    currentPage = page;
    showToast(`Page ${page} loaded`, 'info');
}

// Toast Notification Utility
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = 'toast-slide-in pointer-events-auto bg-slate-900 text-white dark:bg-white dark:text-slate-900 px-4 py-2.5 rounded-xl shadow-2xl flex items-center gap-3 text-xs font-semibold border border-slate-700 dark:border-slate-200';
    
    let iconName = 'info';
    if (type === 'success') iconName = 'check-circle';
    if (type === 'warning') iconName = 'alert-triangle';

    toast.innerHTML = `
        <i data-lucide="${iconName}" class="w-4 h-4 ${type === 'success' ? 'text-emerald-400' : type === 'warning' ? 'text-amber-400' : 'text-blue-400'}"></i>
        <span>${message}</span>
    `;

    container.appendChild(toast);
    if (window.lucide) lucide.createIcons();

    setTimeout(() => {
        toast.classList.add('toast-fade-out');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Initialize Charts via Chart.js
function initCharts() {
    // Chart 1: Shipment Status Overview (Bar Chart)
    const ctxBar = document.getElementById('shipmentStatusChart')?.getContext('2d');
    if (ctxBar) {
        new Chart(ctxBar, {
            type: 'bar',
            data: {
                labels: ['In Transit', 'Delivered', 'Delayed', 'Exception'],
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
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { font: { family: 'Inter', size: 11 }, color: '#94a3b8' }
                    },
                    y: {
                        beginAtZero: true,
                        max: 20,
                        grid: { color: 'rgba(226, 232, 240, 0.5)' },
                        ticks: { font: { family: 'Inter', size: 11 }, color: '#94a3b8', stepSize: 5 }
                    }
                }
            }
        });
    }

    // Chart 2: Temperature Monitoring (Line Chart)
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
                    data: [3.5, 3.0, 3.8, 3.2, 5.0, 3.5, 3.9],
                    borderColor: '#3b82f6',
                    borderWidth: 2,
                    fill: true,
                    backgroundColor: gradient,
                    tension: 0.4,
                    pointRadius: 0,
                    pointHoverRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { font: { family: 'Inter', size: 10 }, color: '#94a3b8' }
                    },
                    y: {
                        min: 0,
                        max: 8,
                        grid: { color: 'rgba(226, 232, 240, 0.5)' },
                        ticks: { font: { family: 'Inter', size: 10 }, color: '#94a3b8', callback: v => v + '°C' }
                    }
                }
            }
        });
    }

    // Chart 3: System Overview (Donut Chart)
    const ctxDonut = document.getElementById('systemOverviewDonut')?.getContext('2d');
    if (ctxDonut) {
        new Chart(ctxDonut, {
            type: 'doughnut',
            data: {
                labels: ['In Transit', 'Delayed', 'Stopped'],
                datasets: [{
                    data: [18, 4, 2],
                    backgroundColor: ['#10b981', '#f59e0b', '#ef4444'],
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '76%',
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }
}




