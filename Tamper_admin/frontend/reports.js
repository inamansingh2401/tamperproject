/**
 * SafeTrack Admin Console - Reports & Analytics Controller
 */

document.addEventListener('DOMContentLoaded', () => {
    handleGenerateReport();
    if (window.lucide) lucide.createIcons();
});

let reportCharts = [];
function initReportCharts(summary) {
    reportCharts.forEach(chart => chart.destroy());
    reportCharts = [];
    // Delivery Performance Chart
    const ctxPerf = document.getElementById('reportPerformanceChart')?.getContext('2d');
    if (ctxPerf) {
        reportCharts.push(new Chart(ctxPerf, {
            type: 'bar',
            data: {
                labels: summary.shipment_statuses.map(item => item.status || 'Unknown'),
                datasets: [{
                    label: 'Stored shipment count',
                    data: summary.shipment_statuses.map(item => item.count),
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
                    y: { beginAtZero: true, grid: { color: 'rgba(226, 232, 240, 0.5)' }, ticks: { precision: 0, font: { size: 10 }, color: '#94a3b8' } }
                }
            }
        }));
    }

    // Vehicle Utilization Chart
    const ctxUtil = document.getElementById('reportUtilizationChart')?.getContext('2d');
    if (ctxUtil) {
        reportCharts.push(new Chart(ctxUtil, {
            type: 'bar',
            data: {
                labels: summary.vehicle_statuses.map(item => item.status || 'Unknown'),
                datasets: [{
                    data: summary.vehicle_statuses.map(item => item.count),
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
                    y: { beginAtZero: true, grid: { color: 'rgba(226, 232, 240, 0.5)' }, ticks: { precision: 0, font: { size: 10 }, color: '#94a3b8' } }
                }
            }
        }));
    }
}

async function handleGenerateReport() {
    showToast("Generating comprehensive security & telemetry report...", "info");
    try {
        const summary = await SafeTrackAPI.getReportsSummary();
        initReportCharts(summary);
        const set = (id,value) => { const node=document.getElementById(id);if(node)node.textContent=value; };
        set('report-temperature-percent',summary.compliance_percentage == null ? 'No readings' : `${summary.compliance_percentage}% in reference range`);
        set('report-temperature-description',`${summary.temperature_in_range} of ${summary.temperature_readings} stored temperature readings within 2–8°C. All stored history; not a clinical or shipment-specific compliance certification.`);
        set('report-temp-alerts',`${summary.temp_alerts} alerts`);
        set('report-tamper-alerts',`${summary.tamper_alerts} alerts`);
        set('report-shock-alerts',`${summary.shock_alerts} alerts`);
        showToast(`Report: ${summary.total_shipments} shipments, ${summary.total_vehicles} vehicles, ${summary.total_alerts} stored alerts`, "success");
    } catch (e) {
        showToast("Report unavailable: the cloud request failed. Try again when connected.", "error");
    }
}

async function handleExportCSV() {
    try {
        const shipments = await SafeTrackAPI.getShipments();
        const vehicles = await SafeTrackAPI.getVehicles();

        // Quote embedded quotes and neutralize spreadsheet formulas from stored fields.
        const csvCell = value => {
            let text = String(value ?? '');
            if (/^[\s]*[=+@-]/.test(text) || /^[\t\r\n]/.test(text)) text = "'" + text;
            return '"' + text.replace(/"/g, '""') + '"';
        };
        let csvContent = '\uFEFF';
        csvContent += "Type,ID,Title,Vehicle,Origin,Destination,Status,Temperature,Seal_Status\n";

        shipments.forEach(s => {
            csvContent += ['Shipment',s.id,s.title,s.vehicle_id,s.origin,s.destination,s.status,s.latest_temperature,s.seal_status].map(csvCell).join(',') + '\r\n';
        });

        vehicles.forEach(v => {
            csvContent += ['Vehicle',v.id,v.name,'',v.origin,v.destination,v.status,'',''].map(csvCell).join(',') + '\r\n';
        });

        const encodedUri = URL.createObjectURL(new Blob([csvContent], {type:'text/csv;charset=utf-8'}));
        const link = document.createElement("a");
        link.setAttribute("href", encodedUri);
        link.setAttribute("download", `safetrack_fleet_report_${new Date().toISOString().slice(0, 10)}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        setTimeout(() => URL.revokeObjectURL(encodedUri), 60000);

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
        <span>${escapeHTML(message)}</span>
    `;

    container.appendChild(toast);
    if (window.lucide) lucide.createIcons();

    setTimeout(() => {
        toast.classList.add('toast-fade-out');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}
