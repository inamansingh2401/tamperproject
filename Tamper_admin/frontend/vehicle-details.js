/**
 * SafeTrack Admin Console - Vehicle Details Page Controller
 */

let currentVehicleId = "TRK-MH-001";
let vehicleData = null;
let assignedShipments = [];

document.addEventListener('DOMContentLoaded', async () => {
    const urlParams = new URLSearchParams(window.location.search);
    currentVehicleId = urlParams.get('id') || "TRK-MH-001";

    await loadVehicleDetails();
    if (window.lucide) lucide.createIcons();
});

async function loadVehicleDetails() {
    try {
        vehicleData = await SafeTrackAPI.getVehicleById(currentVehicleId);
        if (!vehicleData) {
            showToast(`Vehicle ${currentVehicleId} not found`, 'error');
            return;
        }

        const allShipments = await SafeTrackAPI.getShipments();
        assignedShipments = allShipments.filter(s => s.vehicle_id === currentVehicleId || (vehicleData.assigned_shipments && vehicleData.assigned_shipments.includes(s.id)));

        renderVehicleHeader();
        renderAssignedShipments();
    } catch (err) {
        console.error("Error loading vehicle details:", err);
        showToast("Failed to load vehicle specs", "error");
    }
}

function renderVehicleHeader() {
    document.getElementById('displayVehicleId').innerText = vehicleData.id;
    document.getElementById('displayVehicleSub').innerText = `${vehicleData.name} • Driver: ${vehicleData.driver}`;
    document.getElementById('infoPlate').innerText = vehicleData.license_plate;
    document.getElementById('infoName').innerText = vehicleData.name;
    document.getElementById('infoDriver').innerText = vehicleData.driver;
    document.getElementById('infoRoute').innerText = `${vehicleData.origin} → ${vehicleData.destination}`;
    document.getElementById('infoHub').innerText = `Hub: ${vehicleData.current_hub}`;
    document.getElementById('infoCount').innerText = `${assignedShipments.length} Active Cargo`;

    const badgeEl = document.getElementById('displayVehicleBadge');
    if (badgeEl) {
        badgeEl.innerText = vehicleData.status;
        badgeEl.className = 'badge ' + (
            vehicleData.status === 'In Transit' ? 'badge-in-transit' :
            vehicleData.status === 'Delayed' ? 'badge-delayed' :
            vehicleData.status === 'At Warehouse' ? 'badge-at-warehouse' : 'badge-stopped'
        );
    }
}

function renderAssignedShipments() {
    const container = document.getElementById('shipmentsContainer');
    if (!container) return;

    container.innerHTML = '';

    if (assignedShipments.length === 0) {
        container.innerHTML = `
            <div class="col-span-2 text-center py-12 text-slate-400 space-y-3">
                <i data-lucide="package-open" class="w-12 h-12 mx-auto text-slate-300"></i>
                <p class="font-medium">No shipments currently assigned to vehicle ${escapeHTML(vehicleData.id)}.</p>
                <button onclick="openAssignModal()" class="px-4 py-2 bg-blue-600 text-white font-semibold rounded-xl text-xs shadow-md">Assign Cargo Shipment</button>
            </div>
        `;
        if (window.lucide) lucide.createIcons();
        return;
    }

    assignedShipments.forEach(s => {
        const card = document.createElement('div');
        card.className = 'bg-slate-50 dark:bg-slate-700/40 p-5 rounded-2xl border border-slate-200 dark:border-slate-700 space-y-4 relative group';

        const isSealed = s.seal_status === 'Sealed' || s.seal_status === 'Intact';
        let sealBadge = isSealed ? 
            `<span class="badge badge-optimal"><i data-lucide="lock" class="w-3 h-3"></i> Sealed</span>` :
            `<span class="badge badge-critical"><i data-lucide="unlock" class="w-3 h-3"></i> Breached</span>`;

        let statusBadge = s.status === 'In Transit' ? 'badge-in-transit' :
                          s.status === 'Compromised' ? 'badge-critical' : 'badge-at-warehouse';

        card.innerHTML = `
            <div class="flex items-start justify-between border-b border-slate-200 dark:border-slate-600/60 pb-3">
                <div>
                    <span class="font-mono font-bold text-sm text-blue-600 dark:text-blue-400">${escapeHTML(s.id)}</span>
                    <h4 class="font-bold text-xs text-slate-900 dark:text-white mt-0.5">${escapeHTML(s.title)}</h4>
                    <p class="text-[11px] text-slate-500">Recipient: ${escapeHTML(s.recipient)}</p>
                </div>
                <div class="flex flex-col items-end gap-1">
                    <span class="badge ${statusBadge}">${escapeHTML(s.status)}</span>
                    ${sealBadge}
                </div>
            </div>

            <!-- SENSOR TELEMETRY READINGS -->
            <div class="grid grid-cols-4 gap-2 text-center text-xs pt-1">
                <div class="p-2 bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700">
                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Temp</span>
                    <span class="font-bold text-blue-600 dark:text-blue-400">${escapeHTML(s.latest_temperature)} °C</span>
                </div>
                <div class="p-2 bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700">
                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Light</span>
                    <span class="font-semibold text-amber-600">${escapeHTML(s.latest_light)} Lux</span>
                </div>
                <div class="p-2 bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700">
                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Humidity</span>
                    <span class="font-semibold text-sky-600">${escapeHTML(s.latest_humidity)}%</span>
                </div>
                <div class="p-2 bg-white dark:bg-slate-800 rounded-xl border border-slate-100 dark:border-slate-700">
                    <span class="text-[10px] text-slate-400 font-bold uppercase block">Motion</span>
                    <span class="font-bold ${s.latest_shock.includes('High') ? 'text-rose-500' : 'text-slate-700 dark:text-slate-300'} truncate block" title="${escapeHTML(s.latest_shock)}">${escapeHTML(s.latest_shock)}</span>
                </div>
            </div>

            <!-- ROUTE & ACTIONS FOOTER -->
            <div class="flex items-center justify-between text-xs pt-2">
                <span class="text-[11px] text-slate-500">Current: <strong>${escapeHTML(s.current_hub)}</strong></span>
                <div class="flex items-center gap-2">
                    <a href="shipments.html?code=${escapeHTML(s.id)}" class="px-2.5 py-1 bg-blue-50 dark:bg-blue-900/30 hover:bg-blue-600 hover:text-white text-blue-600 dark:text-blue-400 font-semibold rounded-lg transition-colors flex items-center gap-1">
                        <i data-lucide="eye" class="w-3.5 h-3.5"></i>
                        <span>View</span>
                    </a>
                    <button data-action="editShipment" data-value="${escapeHTML(s.id)}" class="px-2.5 py-1 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 text-slate-700 dark:text-slate-200 font-semibold rounded-lg transition-colors">
                        Edit
                    </button>
                    <button data-action="removeShipment" data-value="${escapeHTML(s.id)}" class="px-2.5 py-1 bg-rose-50 dark:bg-rose-900/30 hover:bg-rose-600 hover:text-white text-rose-600 dark:text-rose-400 font-semibold rounded-lg transition-colors">
                        Remove
                    </button>
                </div>
            </div>
        `;

        container.appendChild(card);
    });

    if (window.lucide) lucide.createIcons();
}

async function openAssignModal() {
    try {
        const allShipments = await SafeTrackAPI.getShipments();
        const available = allShipments.filter(s => s.vehicle_id !== currentVehicleId);
        const select = document.getElementById('assignShipmentSelect');
        if (!select) return;

        if (available.length === 0) {
            showToast('All shipments are already assigned to this vehicle', 'info');
            return;
        }

        select.innerHTML = available.map(s => `<option value="${escapeHTML(s.id)}">${escapeHTML(s.id)} — ${escapeHTML(s.title)} (${escapeHTML(s.vehicle_id ? 'Current: ' + s.vehicle_id : 'Unassigned')})</option>`).join('');
        openModal('assignShipmentModal');
    } catch (e) {
        showToast('Error loading available shipments', 'error');
    }
}

async function handleAssignShipmentSubmit(e) {
    e.preventDefault();
    const select = document.getElementById('assignShipmentSelect');
    const shipmentCode = select ? select.value : null;
    if (!shipmentCode) return;

    try {
        await SafeTrackAPI.assignShipmentToVehicle(currentVehicleId, shipmentCode);
        closeModal('assignShipmentModal');
        await loadVehicleDetails();
        showToast(`Shipment ${shipmentCode} assigned to ${currentVehicleId}!`, 'success');
    } catch (err) {
        console.error("Error assigning shipment:", err);
        showToast(err.message || 'Error assigning shipment', 'error');
    }
}

function editShipment(shipmentId) {
    const shipment = assignedShipments.find(s => s.id === shipmentId);
    if (!shipment) return;

    document.getElementById('editShipmentId').value = shipment.id;
    document.getElementById('editShipmentTitle').value = shipment.title;
    document.getElementById('editShipmentHub').value = shipment.current_hub;
    document.getElementById('editShipmentStatus').value = shipment.status;

    openModal('editShipmentModal');
}

async function handleSaveEditShipment(e) {
    e.preventDefault();
    const id = document.getElementById('editShipmentId').value;
    const updateData = {
        title: document.getElementById('editShipmentTitle').value,
        current_hub: document.getElementById('editShipmentHub').value,
        status: document.getElementById('editShipmentStatus').value
    };

    try {
        await SafeTrackAPI.updateShipment(id, updateData);
        closeModal('editShipmentModal');
        await loadVehicleDetails();
        showToast(`Shipment ${id} updated successfully!`, 'success');
    } catch (err) {
        showToast('Error updating shipment', 'error');
    }
}

async function removeShipment(shipmentId) {
    if (confirm(`Remove shipment ${shipmentId} from vehicle ${currentVehicleId}?`)) {
        try {
            await SafeTrackAPI.removeShipmentFromVehicle(shipmentId, currentVehicleId);
            await loadVehicleDetails();
            showToast(`Shipment ${shipmentId} unassigned from vehicle`, 'warning');
        } catch (err) {
            showToast('Error unassigning shipment', 'error');
        }
    }
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
        <span>${escapeHTML(message)}</span>
    `;

    container.appendChild(toast);
    if (window.lucide) lucide.createIcons();

    setTimeout(() => {
        toast.classList.add('toast-fade-out');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}
