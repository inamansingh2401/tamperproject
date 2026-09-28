const SAFETRACK_USER_DASHBOARD = "user/dashboard.html";

function getAuthToken() {
    return sessionStorage.getItem("safetrack_access_token");
}

function getAuthRole() {
    return sessionStorage.getItem("safetrack_role");
}

function logout() {
    sessionStorage.removeItem("safetrack_access_token");
    sessionStorage.removeItem("safetrack_role");
    sessionStorage.removeItem("safetrack_username");
    sessionStorage.removeItem("safetrack_assigned_shipments");
    window.location.replace("login.html");
}

(function protectAdminPage() {
    const page = (location.pathname.split("/").pop() || "index.html").toLowerCase();
    if (page === "login.html" || page === "login") return;

    const token = getAuthToken();
    const role = getAuthRole();

    if (!token) {
        window.location.replace("login.html");
        return;
    }

    if (role !== "admin") {
        window.location.replace(SAFETRACK_USER_DASHBOARD);
    }
})();

window.SafeTrackAuth = { getAuthToken, getAuthRole, logout };
