// Vehicle Details & Product Telemetry Management

const vehicleProductsData = {
    "PRCL-2024-05-21-001": {
        vehicleId: "PRCL-2024-05-21-001",
        shipmentId: "PRCL-2024-05-21-001",
        origin: "Mumbai Central Warehouse",
        destination: "Delhi Central Facility",
        status: "In Transit",
        driver: "Rajesh Kumar (ID: DRV-882)",
        temp: "4.2 °C",
        humidity: "45% RH",
        light: "0 Lux",
        shock: "Normal (0.2g)",
        products: [
            { id: "PRD-101", shipmentId: "PRCL-2024-05-21-001", name: "COVID-19 Vaccines (Pfizer)", category: "Biopharmaceuticals", qty: "400 Vials", temp: "3.8 °C", light: "0 Lux", humidity: "42%", shockType: "Normal", shockVal: "0.1g", status: "Optimal" },
            { id: "PRD-102", shipmentId: "PRCL-2024-05-21-001", name: "Insulin Injection Pens", category: "Cold-Chain Pharma", qty: "250 Boxes", temp: "4.1 °C", light: "0 Lux", humidity: "44%", shockType: "Low Vibration", shockVal: "0.4g", status: "Optimal" },
            { id: "PRD-103", shipmentId: "PRCL-2024-05-21-001", name: "Blood Plasma Containers", category: "Medical Supplies", qty: "150 Units", temp: "4.5 °C", light: "2 Lux", humidity: "48%", shockType: "Normal", shockVal: "0.2g", status: "Optimal" },
            { id: "PRD-104", shipmentId: "PRCL-2024-05-21-001", name: "Diagnostic Test Reagents", category: "Lab Reagents", qty: "300 Kits", temp: "4.6 °C", light: "0 Lux", humidity: "46%", shockType: "Minor Bump", shockVal: "0.9g", status: "Warning" }
        ]
    },
    "PRCL-2024-05-21-002": {
        vehicleId: "PRCL-2024-05-21-002",
        shipmentId: "PRCL-2024-05-21-002",
        origin: "Kolkata Hub",
        destination: "Bangalore Hub",
        status: "In Transit",
        driver: "Amitabh Sen (ID: DRV-419)",
        temp: "5.1 °C",
        humidity: "52% RH",
        light: "12 Lux",
        shock: "Minor Bump (0.8g)",
        products: [
            { id: "PRD-201", shipmentId: "PRCL-2024-05-21-002", name: "Biologic Cancer Therapy", category: "Oncology Pharma", qty: "180 Vials", temp: "5.1 °C", light: "12 Lux", humidity: "52%", shockType: "Minor Bump", shockVal: "0.8g", status: "Warning" },
            { id: "PRD-202", shipmentId: "PRCL-2024-05-21-002", name: "Surgical Anesthetics", category: "Controlled Meds", qty: "500 Ampoules", temp: "5.0 °C", light: "0 Lux", humidity: "50%", shockType: "Normal", shockVal: "0.3g", status: "Optimal" },
            { id: "PRD-203", shipmentId: "PRCL-2024-05-21-002", name: "Organ Preservation Solutions", category: "Transplant Supplies", qty: "80 Containers", temp: "4.8 °C", light: "0 Lux", humidity: "51%", shockType: "Normal", shockVal: "0.2g", status: "Optimal" }
        ]
    },
    "PRCL-2024-05-21-003": {
        vehicleId: "PRCL-2024-05-21-003",
        shipmentId: "PRCL-2024-05-21-003",
        origin: "Chennai Hub",
        destination: "Hyderabad Hub",
        status: "In Transit",
        driver: "Srinivasan R. (ID: DRV-305)",
        temp: "3.8 °C",
        humidity: "38% RH",
        light: "0 Lux",
        shock: "Normal (0.1g)",
        products: [
            { id: "PRD-301", shipmentId: "PRCL-2024-05-21-003", name: "mRNA Booster Doses", category: "Vaccines", qty: "600 Vials", temp: "3.7 °C", light: "0 Lux", humidity: "37%", shockType: "Normal", shockVal: "0.1g", status: "Optimal" },
            { id: "PRD-302", shipmentId: "PRCL-2024-05-21-003", name: "Cell Therapy Cultures", category: "Advanced Therapy", qty: "50 Flasks", temp: "3.9 °C", light: "0 Lux", humidity: "39%", shockType: "Low Vibration", shockVal: "0.3g", status: "Optimal" }
        ]
    },
    "PRCL-2024-05-21-004": {
        vehicleId: "PRCL-2024-05-21-004",
        shipmentId: "PRCL-2024-05-21-004",
        origin: "Pune Warehouse",
        destination: "Mumbai Hub",
        status: "Delayed",
        driver: "Vikram Patil (ID: DRV-771)",
        temp: "6.2 °C",
        humidity: "65% RH",
        light: "180 Lux",
        shock: "High Impact Shock (3.4g)",
        products: [
            { id: "PRD-401", shipmentId: "PRCL-2024-05-21-004", name: "Monoclonal Antibodies", category: "Immunotherapy", qty: "320 Vials", temp: "6.8 °C", light: "180 Lux", humidity: "65%", shockType: "High Impact Shock", shockVal: "3.4g", status: "Critical" },
            { id: "PRD-402", shipmentId: "PRCL-2024-05-21-004", name: "Pediatric Antibiotics Suspension", category: "Liquid Meds", qty: "800 Bottles", temp: "5.8 °C", light: "45 Lux", humidity: "60%", shockType: "Pothole Impact", shockVal: "1.8g", status: "Warning" }
        ]
    },
    "PRCL-2024-05-21-005": {
        vehicleId: "PRCL-2024-05-21-005",
        shipmentId: "PRCL-2024-05-21-005",
        origin: "Ahmedabad Hub",
        destination: "Delhi Facility",
        status: "In Transit",
        driver: "Karan Shah (ID: DRV-612)",
        temp: "4.0 °C",
        humidity: "40% RH",
        light: "0 Lux",
        shock: "Normal (0.2g)",
        products: [
            { id: "PRD-501", shipmentId: "PRCL-2024-05-21-005", name: "Ophthalmic Eye Drops", category: "Sterile Solutions", qty: "1,000 Units", temp: "4.0 °C", light: "0 Lux", humidity: "40%", shockType: "Normal", shockVal: "0.2g", status: "Optimal" },
            { id: "PRD-502", shipmentId: "PRCL-2024-05-21-005", name: "Injectable Hormones", category: "Endocrine Pharma", qty: "350 Vials", temp: "4.1 °C", light: "0 Lux", humidity: "41%", shockType: "Normal", shockVal: "0.1g", status: "Optimal" }
        ]
    }
};

let currentVehicle = null;
let filteredProducts = [];

// Initialize Page
document.addEventListener('DOMContentLoaded', () => {
    // Get Vehicle ID from URL param
    const urlParams = new URLSearchParams(window.location.search);
    const vehicleId = urlParams.get('id') || "PRCL-2024-05-21-001";

    // Retrieve or dynamically generate vehicle payload data
    if (vehicleProductsData[vehicleId]) {
        currentVehicle = vehicleProductsData[vehicleId];
    } else {
        currentVehicle = {
            vehicleId: vehicleId,
            shipmentId: vehicleId,
            origin: "Regional Distribution Hub",
            destination: "Central Logistics Center",
            status: "In Transit",
            driver: "Registered Cargo Operator",
            temp: "4.2 °C",
            humidity: "45% RH",
            light: "0 Lux",
            shock: "Normal (0.2g)",
            products: [
                { id: "PRD-901", shipmentId: vehicleId, name: "Temperature Sensitive Biologicals", category: "Pharmaceuticals", qty: "500 Units", temp: "4.2 °C", light: "0 Lux", humidity: "45%", shockType: "Normal", shockVal: "0.2g", status: "Optimal" },
                { id: "PRD-902", shipmentId: vehicleId, name: "Cold-Chain Plasma Supplies", category: "Medical Supplies", qty: "200 Units", temp: "4.0 °C", light: "0 Lux", humidity: "43%", shockType: "Low Vibration", shockVal: "0.4g", status: "Optimal" }
            ]
        };
    }

    filteredProducts = [...currentVehicle.products];

    renderVehicleHeader();
    renderProductsTable();

    if (window.lucide) {
        lucide.createIcons();
    }
});

// Render Page Header & Stats Cards
function renderVehicleHeader() {
    document.getElementById('headerVehicleId').innerText = currentVehicle.vehicleId;
    document.getElementById('headerVehicleStatus').innerText = currentVehicle.status;
    document.getElementById('headerVehicleRoute').innerText = `Route: ${currentVehicle.origin} → ${currentVehicle.destination}`;

    document.getElementById('bannerTitle').innerText = `Cargo Products in Vehicle ${currentVehicle.vehicleId}`;
    document.getElementById('infoOrigin').innerText = currentVehicle.origin;
    document.getElementById('infoDestination').innerText = currentVehicle.destination;
    document.getElementById('infoDriver').innerText = currentVehicle.driver;

    document.getElementById('statTotalProducts').innerText = `${currentVehicle.products.length} Products`;
    document.getElementById('statTemp').innerText = currentVehicle.temp;
    document.getElementById('statLight').innerText = currentVehicle.light;
    document.getElementById('statHumidity').innerText = currentVehicle.humidity;
    document.getElementById('statShock').innerText = currentVehicle.shock;
}

// Render Products Table
function renderProductsTable() {
    const tbody = document.getElementById('productTableBody');
    if (!tbody) return;

    tbody.innerHTML = '';

    if (filteredProducts.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="text-center py-10 text-slate-400 font-medium">
                    No matching products found inside vehicle ${currentVehicle.vehicleId}.
                </td>
            </tr>
        `;
        return;
    }

    filteredProducts.forEach((p) => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors';

        // Badge color logic
        let statusBadgeClass = 'bg-emerald-100 text-emerald-700 border-emerald-300 dark:bg-emerald-900/40 dark:text-emerald-400';
        if (p.status === 'Warning') {
            statusBadgeClass = 'bg-amber-100 text-amber-700 border-amber-300 dark:bg-amber-900/40 dark:text-amber-400';
        } else if (p.status === 'Critical') {
            statusBadgeClass = 'bg-rose-100 text-rose-700 border-rose-300 dark:bg-rose-900/40 dark:text-rose-400';
        }

        // Shock badge color
        let shockBadgeClass = 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300';
        if (p.shockType.includes('High Impact')) {
            shockBadgeClass = 'bg-rose-100 text-rose-700 font-bold dark:bg-rose-900/40 dark:text-rose-400';
        } else if (p.shockType.includes('Bump') || p.shockType.includes('Pothole')) {
            shockBadgeClass = 'bg-amber-100 text-amber-700 font-semibold dark:bg-amber-900/40 dark:text-amber-400';
        }

        tr.innerHTML = `
            <td class="px-5 py-4 font-bold text-slate-900 dark:text-white">
                <div class="flex items-center gap-2">
                    <div class="w-8 h-8 rounded-lg bg-blue-50 dark:bg-blue-900/30 text-blue-600 flex items-center justify-center shrink-0">
                        <i data-lucide="package" class="w-4 h-4"></i>
                    </div>
                    <div>
                        <p class="text-xs font-bold text-slate-900 dark:text-white leading-tight">${p.name}</p>
                        <p class="text-[10px] text-blue-600 dark:text-blue-400 font-mono font-semibold">Shipment ID: ${p.shipmentId || currentVehicle.vehicleId}</p>
                    </div>
                </div>
            </td>
            <td class="px-5 py-4 text-slate-600 dark:text-slate-300">
                ${p.category}
            </td>
            <td class="px-5 py-4 font-semibold text-slate-800 dark:text-slate-200">
                ${p.qty}
            </td>
            <td class="px-5 py-4 font-bold text-blue-600 dark:text-blue-400">
                <div class="flex items-center gap-1">
                    <i data-lucide="thermometer" class="w-3.5 h-3.5 text-blue-500"></i>
                    <span>${p.temp}</span>
                </div>
            </td>
            <td class="px-5 py-4 font-medium text-slate-700 dark:text-slate-300">
                <div class="flex items-center gap-1">
                    <i data-lucide="sun" class="w-3.5 h-3.5 text-amber-500"></i>
                    <span>${p.light}</span>
                </div>
            </td>
            <td class="px-5 py-4 font-medium text-slate-700 dark:text-slate-300">
                <div class="flex items-center gap-1">
                    <i data-lucide="droplets" class="w-3.5 h-3.5 text-sky-500"></i>
                    <span>${p.humidity}</span>
                </div>
            </td>
            <td class="px-5 py-4">
                <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-medium border ${shockBadgeClass}">
                    <i data-lucide="activity" class="w-3 h-3"></i>
                    <span>${p.shockType} (${p.shockVal})</span>
                </span>
            </td>
            <td class="px-5 py-4">
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${statusBadgeClass}">
                    ${p.status}
                </span>
            </td>
            <td class="px-5 py-4 text-center">
                <button onclick="openProductTelemetryModal('${p.id}')" title="Inspect Sensor History" class="p-1.5 hover:bg-blue-50 dark:hover:bg-slate-700 text-blue-600 rounded-lg transition-colors">
                    <i data-lucide="line-chart" class="w-4 h-4"></i>
                </button>
            </td>
        `;

        tbody.appendChild(tr);
    });

    if (window.lucide) {
        lucide.createIcons();
    }
}

// Product Search Handler
function handleProductSearch() {
    const q = document.getElementById('productSearchInput').value.toLowerCase().trim();
    filteredProducts = currentVehicle.products.filter(p => 
        p.name.toLowerCase().includes(q) ||
        (p.shipmentId && p.shipmentId.toLowerCase().includes(q)) ||
        p.category.toLowerCase().includes(q) ||
        p.shockType.toLowerCase().includes(q)
    );
    renderProductsTable();
}

// Product Filter Popover Toggle
function toggleProductFilterMenu() {
    const menu = document.getElementById('productFilterPopover');
    if (menu) menu.classList.toggle('hidden');
}

function filterProducts(status) {
    toggleProductFilterMenu();
    if (status === 'all') {
        filteredProducts = [...currentVehicle.products];
    } else {
        filteredProducts = currentVehicle.products.filter(p => p.status === status || p.shockType.includes(status));
    }
    renderProductsTable();
    showToast(`Filter applied: ${status}`, 'info');
}

// Open Sensor Telemetry History Modal for Product
function openProductTelemetryModal(productId) {
    const product = currentVehicle.products.find(p => p.id === productId);
    if (!product) return;

    document.getElementById('modalProductTitle').innerHTML = `
        <i data-lucide="package" class="w-5 h-5 text-blue-600"></i>
        Sensor Telemetry for ${product.name}
    `;

    document.getElementById('modalProductDetails').innerHTML = `
        <div class="grid grid-cols-2 gap-3 bg-slate-50 dark:bg-slate-700/40 p-4 rounded-2xl border border-slate-100 dark:border-slate-700">
            <div>
                <span class="text-slate-400 block text-[10px] uppercase font-bold">Shipment ID</span>
                <span class="font-mono font-bold text-blue-600 dark:text-blue-400">${product.shipmentId || currentVehicle.vehicleId}</span>
            </div>
            <div>
                <span class="text-slate-400 block text-[10px] uppercase font-bold">Category</span>
                <span class="font-semibold text-slate-700 dark:text-slate-300">${product.category}</span>
            </div>
            <div>
                <span class="text-slate-400 block text-[10px] uppercase font-bold">Temperature</span>
                <span class="font-bold text-blue-600 dark:text-blue-400">${product.temp}</span>
            </div>
            <div>
                <span class="text-slate-400 block text-[10px] uppercase font-bold">Light Level</span>
                <span class="font-semibold text-amber-600">${product.light}</span>
            </div>
            <div>
                <span class="text-slate-400 block text-[10px] uppercase font-bold">Humidity</span>
                <span class="font-semibold text-sky-600">${product.humidity}</span>
            </div>
            <div>
                <span class="text-slate-400 block text-[10px] uppercase font-bold">Shock Type</span>
                <span class="font-bold text-purple-600">${product.shockType} (${product.shockVal})</span>
            </div>
        </div>

        <div class="bg-white dark:bg-slate-800 p-4 rounded-2xl border border-slate-200 dark:border-slate-700 space-y-2">
            <h4 class="font-bold text-xs text-slate-800 dark:text-white">Recent Telemetry Trend</h4>
            <div class="h-36 relative">
                <canvas id="productChartCanvas"></canvas>
            </div>
        </div>
    `;

    openProductModal();
    if (window.lucide) lucide.createIcons();

    setTimeout(() => {
        const ctx = document.getElementById('productChartCanvas')?.getContext('2d');
        if (ctx) {
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: ['10m ago', '8m ago', '6m ago', '4m ago', '2m ago', 'Just now'],
                    datasets: [{
                        label: 'Temperature (°C)',
                        data: [3.5, 3.7, 3.8, 4.0, 3.9, parseFloat(product.temp)],
                        borderColor: '#3b82f6',
                        borderWidth: 2,
                        tension: 0.3,
                        pointRadius: 3
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: { display: false }, ticks: { font: { size: 9 }, color: '#94a3b8' } },
                        y: { grid: { color: 'rgba(226, 232, 240, 0.5)' }, ticks: { font: { size: 9 }, color: '#94a3b8' } }
                    }
                }
            });
        }
    }, 100);
}

function openProductModal() {
    const el = document.getElementById('productModal');
    if (el) {
        el.classList.remove('hidden');
        el.classList.add('flex');
    }
}

function closeProductModal() {
    const el = document.getElementById('productModal');
    if (el) {
        el.classList.add('hidden');
        el.classList.remove('flex');
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
