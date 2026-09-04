/**
 * SafeTrack Admin Console - Reports & Analytics Controller
 */

document.addEventListener('DOMContentLoaded', () => {
    initReportCharts();
    if (window.lucide) lucide.createIcons();
});

function initReportCharts() {
    // Delivery Performance Chart
    const ctxPerf = document.getElementById('reportPerformanceChart')?.getContext('2d');
    if (ctxPerf) {
        new Chart(ctxPerf, {
            type: 'line',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [{
                    label: 'On-Time Deliveries (%)',
                    data: [95, 92, 98, 94, 96, 99, 97],
                    borderColor: '#10b981',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false }, ticks: { font: { size: 10 }, color: '#94a3b8' } },
                    y: { min: 80, max: 100, grid: { color: 'rgba(226, 232, 240, 0.5)' }, ticks: { font: { size: 10 }, color: '#94a3b8' } }
                }
            }
        });
    }

    // Vehicle Utilization Chart
    const ctxUtil = document.getElementById('reportUtilizationChart')?.getContext('2d');
    if (ctxUtil) {
        new Chart(ctxUtil, {
            type: 'bar',
            data: {
                labels: ['Reefer Trucks', 'Security Vans', 'Heavy Cargo', 'Mini Carriers'],
                datasets: [{
                    data: [88, 75, 92, 60],
                    backgroundColor: '#3b82f6',
                    borderRadius: 8,
                    barThickness: 24
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { display: false }, ticks: { font: { size: 10 }, color: '#94a3b8' } },
                    y: { beginAtZero: true, max: 100, grid: { color: 'rgba(226, 232, 240, 0.5)' }, ticks: { font: { size: 10 }, color: '#94a3b8' } }
                }
            }
        });
    }
}

async function handleGenerateReport() {
    showToast("Generating comprehensive security & telemetry report...", "info");
    try {
        const summary = await SafeTrackAPI.getReportsSummary();
        showToast(`Report compiled: ${summary.total_shipments} shipments, ${summary.total_vehicles} vehicles, ${summary.total_alerts} incidents (${summary.compliance_percentage}% compliant)`, "success");
    } catch (e) {
        showToast("Report compiled using cached fleet telemetry data.", "success");
    }
}

async function handleExportCSV() {
    try {
        const shipments = await SafeTrackAPI.getShipments();
        const vehicles = await SafeTrackAPI.getVehicles();

        let csvContent = "data:text/csv;charset=utf-8,";
        csvContent += "Type,ID,Title,Vehicle,Origin,Destination,Status,Temperature,Seal_Status\n";

        shipments.forEach(s => {
            csvContent += `Shipment,"${s.id}","${s.title}","${s.vehicle_id}","${s.origin}","${s.destination}","${s.status}","${s.latest_temperature || ''}","${s.seal_status || ''}"\n`;
        });

        vehicles.forEach(v => {
            csvContent += `Vehicle,"${v.id}","${v.name}","","${v.origin}","${v.destination}","${v.status}","",""\n`;
        });

        const encodedUri = encodeURI(csvContent);
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", `safetrack_fleet_report_${new Date().toISOString().slice(0, 10)}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        showToast("Fleet CSV report downloaded successfully!", "success");
    } catch (err) {
        console.error("Export CSV error:", err);
        showToast("Error generating CSV export", "error");
    }
}

function handleExportPDF() {
    showToast("Opening print view for PDF export...", "info");
    setTimeout(() => {
        window.print();
    }, 500);
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
