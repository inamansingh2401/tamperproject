const SAFETRACK_USER_DASHBOARD = "http://127.0.0.1:5500";

function getAuthToken() {
    return localStorage.getItem("safetrack_access_token");
}

function getAuthRole() {
    return localStorage.getItem("safetrack_role");
}

function logout() {
    localStorage.removeItem("safetrack_access_token");
    localStorage.removeItem("safetrack_role");
    localStorage.removeItem("safetrack_username");
    localStorage.removeItem("safetrack_assigned_shipments");
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
