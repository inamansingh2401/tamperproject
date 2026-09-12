/**
 * SafeTrack Admin Console - Users & Roles Controller
 */

let usersList = [];

document.addEventListener('DOMContentLoaded', async () => {
    await loadUsersData();

    // Check URL params
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('action') === 'add') {
        openModal('addUserModal');
    } else if (urlParams.get('tab') === 'roles') {
        const rolesCard = document.querySelector('.grid.grid-cols-1.md\\:grid-cols-2');
        if (rolesCard) rolesCard.scrollIntoView({ behavior: 'smooth' });
    }

    if (window.lucide) lucide.createIcons();
});

async function loadUsersData() {
    try {
        usersList = await SafeTrackAPI.getUsers();
        renderUsersTable();
    } catch (err) {
        console.error("Error loading users:", err);
        showToast("Failed to load users", "error");
    }
}

function renderUsersTable() {
    const tbody = document.getElementById('usersTableBody');
    const countText = document.getElementById('usersCountText');
    if (!tbody) return;

    tbody.innerHTML = '';
    if (countText) countText.innerText = usersList.length;

    usersList.forEach(u => {
        const tr = document.createElement('tr');
        tr.className = 'hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors';

        let roleBadge = u.role === 'Admin' ? 'bg-amber-100 text-amber-700 border-amber-300 dark:bg-amber-900/40 dark:text-amber-300' :
                        u.role === 'User' ? 'bg-emerald-100 text-emerald-700 border-emerald-300 dark:bg-emerald-900/40 dark:text-emerald-300' :
                        'bg-slate-100 text-slate-700 border-slate-300';

        let statusClass = u.status === 'Active' ? 'text-emerald-600 font-semibold' : 'text-slate-400 font-semibold';

        const vehiclesDisplay = u.assigned_vehicles.map(v => `<span class="px-2 py-0.5 text-[10px] font-mono bg-slate-100 dark:bg-slate-700 rounded text-slate-600 dark:text-slate-300">${escapeHTML(v)}</span>`).join(' ');

        tr.innerHTML = `
            <td class="px-5 py-4">
                <div class="flex items-center gap-3">
                    <div class="w-8 h-8 rounded-full bg-blue-600 text-white font-bold text-xs flex items-center justify-center shadow-sm">
                        ${escapeHTML(u.name.charAt(0))}
                    </div>
                    <div>
                        <p class="font-bold text-slate-900 dark:text-white">${escapeHTML(u.name)}</p>
                        <p class="text-[11px] text-slate-400 font-mono">${escapeHTML(u.email)}</p>
                    </div>
                </div>
            </td>
            <td class="px-5 py-4">
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${roleBadge}">
                    ${escapeHTML(u.role)}
                </span>
            </td>
            <td class="px-5 py-4">
                <div class="flex flex-wrap gap-1">
                    ${vehiclesDisplay}
                </div>
            </td>
            <td class="px-5 py-4 ${statusClass}">
                ${escapeHTML(u.status)}
            </td>
            <td class="px-5 py-4 text-slate-500 font-mono text-[11px]">
                ${escapeHTML(u.last_login)}
            </td>
            <td class="px-5 py-4 text-center">
                <div class="flex items-center justify-center gap-2">
                    <button data-action="openEditUserModal" data-value="${Number(u.id)}" class="px-2.5 py-1 bg-slate-100 dark:bg-slate-700 hover:bg-blue-600 hover:text-white rounded-lg text-slate-700 dark:text-slate-200 transition-colors font-semibold">
                        Edit
                    </button>
                    <button data-action="toggleUserStatus" data-value="${Number(u.id)}" class="px-2.5 py-1 ${u.status === 'Active' ? 'bg-amber-50 text-amber-600 hover:bg-amber-600 hover:text-white' : 'bg-emerald-50 text-emerald-600 hover:bg-emerald-600 hover:text-white'} rounded-lg transition-colors font-semibold">
                        ${u.status === 'Active' ? 'Disable' : 'Enable'}
                    </button>
                </div>
            </td>
        `;

        tbody.appendChild(tr);
    });

    if (window.lucide) lucide.createIcons();
}

function openEditUserModal(userId) {
    const user = usersList.find(u => u.id === userId);
    if (!user) return;

    document.getElementById('editUserId').value = user.id;
    document.getElementById('editUserName').value = user.name;
    document.getElementById('editUserEmail').value = user.email;
    document.getElementById('editUserRole').value = user.role.toLowerCase() === 'admin' ? 'admin' : 'user';
    document.getElementById('editUserStatus').value = user.status;

    openModal('editUserModal');
}

async function handleSaveEditUser(e) {
    e.preventDefault();
    const userId = parseInt(document.getElementById('editUserId').value, 10);
    const updateData = {
        email: document.getElementById('editUserEmail').value,
        role: document.getElementById('editUserRole').value,
        status: document.getElementById('editUserStatus').value
    };

    try {
        await SafeTrackAPI.updateUser(userId, updateData);
        closeModal('editUserModal');
        await loadUsersData();
        showToast('User updated successfully!', 'success');
    } catch (err) {
        console.error('Error updating user:', err);
        showToast(err.message || 'Error updating user', 'error');
    }
}

async function handleAddUserSubmit(e) {
    e.preventDefault();
    const userData = {
        name: document.getElementById('newUserName').value,
        email: document.getElementById('newUserEmail').value,
        password: document.getElementById('newUserPassword').value,
        role: document.getElementById('newUserRole').value,
        assigned_vehicles: []
    };

    try {
        // Older backends ignore this password and create a shared default login.
        // Fail safely until the security update has reached Render.
        const schemaResponse = await fetchWithTimeout('https://safetrack-admin-c243.onrender.com/openapi.json', {cache: 'no-store'});
        const schema = await schemaResponse.json();
        if (!schemaResponse.ok || !schema.components?.schemas?.UserCreatePayload?.required?.includes('password')) {
            throw new Error('The backend security update must be deployed before creating new users.');
        }
        const created = await SafeTrackAPI.createUser(userData);
        document.getElementById('newUserPassword').value = '';
        closeModal('addUserModal');
        await loadUsersData();
        showToast(`User ${created.name} created!`, 'success');
    } catch (err) {
        showToast(err.message || 'Error creating user', 'error');
    }
}

async function toggleUserStatus(userId) {
    try {
        const updated = await SafeTrackAPI.toggleUserStatus(userId);
        await loadUsersData();
        showToast(`User ${updated.name} is now ${updated.status}`, 'warning');
    } catch (err) {
        showToast('Error updating user status', 'error');
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
