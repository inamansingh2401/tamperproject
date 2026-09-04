/**
 * SafeTrack Admin Console - Settings Controller
 */

document.addEventListener('DOMContentLoaded', async () => {
    await loadSettingsData();
    const urlParams = new URLSearchParams(window.location.search);
    const tab = urlParams.get('tab');
    if (tab === 'notifications') {
        const el = document.getElementById('notifAlerts');
        if (el) el.scrollIntoView({ behavior: 'smooth' });
    } else if (tab === 'security') {
        const el = document.getElementById('sessionTimeout');
        if (el) el.scrollIntoView({ behavior: 'smooth' });
    }
    if (window.lucide) lucide.createIcons();
});

async function loadSettingsData() {
    try {
        const s = await SafeTrackAPI.getSettings();
        if (s) {
            if (document.getElementById('sysName')) document.getElementById('sysName').value = s.system_name || '';
            if (document.getElementById('tempThresh')) document.getElementById('tempThresh').value = s.default_temp_threshold || 8.0;
            if (document.getElementById('lightThresh')) document.getElementById('lightThresh').value = s.default_alert_threshold || 800;
            if (document.getElementById('sysLanguage')) document.getElementById('sysLanguage').value = s.language || 'English';

            if (document.getElementById('notifAlerts')) document.getElementById('notifAlerts').checked = s.alert_notifications !== false;
            if (document.getElementById('notifShipments')) document.getElementById('notifShipments').checked = s.shipment_updates !== false;
            if (document.getElementById('notifEmail')) document.getElementById('notifEmail').checked = s.email_notifications !== false;

            if (document.getElementById('sessionTimeout')) document.getElementById('sessionTimeout').value = String(s.session_timeout || 30);
        }
    } catch (e) {
        console.warn("Could not load settings", e);
    }
}

async function handleSaveGeneralSettings(e) {
    e.preventDefault();
    const name = document.getElementById('sysName').value;
    const temp = document.getElementById('tempThresh').value;
    const light = document.getElementById('lightThresh').value;
    const lang = document.getElementById('sysLanguage').value;

    try {
        await SafeTrackAPI.updateSettings('general', {
            system_name: name,
            default_temp_threshold: parseFloat(temp),
            default_alert_threshold: parseFloat(light),
            language: lang
        });
        showToast("General settings saved successfully!", "success");
    } catch (err) {
        showToast(err.message || "Failed to save settings", "error");
    }
}

async function handleSaveNotifSettings(e) {
    e.preventDefault();
    const alertNotifs = document.getElementById('notifAlerts').checked;
    const shipNotifs = document.getElementById('notifShipments').checked;
    const emailNotifs = document.getElementById('notifEmail').checked;

    try {
        await SafeTrackAPI.updateSettings('notifications', {
            alert_notifications: alertNotifs,
            shipment_updates: shipNotifs,
            email_notifications: emailNotifs
        });
        showToast("Notification preferences updated!", "success");
    } catch (err) {
        showToast(err.message || "Failed to save notification preferences", "error");
    }
}

async function handleSaveSecuritySettings(e) {
    e.preventDefault();
    const timeout = parseInt(document.getElementById('sessionTimeout').value, 10);
    const currPass = document.getElementById('currentPasswordInput').value;
    const newPass = document.getElementById('newPasswordInput').value;

    try {
        await SafeTrackAPI.changePassword(currPass, newPass);
        await SafeTrackAPI.updateSettings('security', {
            session_timeout: timeout
        });
        document.getElementById('currentPasswordInput').value = '';
        document.getElementById('newPasswordInput').value = '';
        showToast("Security settings & password updated successfully!", "success");
    } catch (err) {
        console.error("Error updating security settings:", err);
        showToast(err.message || "Error updating password", "error");
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
