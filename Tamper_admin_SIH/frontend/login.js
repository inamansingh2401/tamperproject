const API_BASE_URL = `http://${window.location.hostname || '127.0.0.1'}:8000/api`;
const USER_DASHBOARD = `http://${window.location.hostname || '127.0.0.1'}:5500`;

document.addEventListener("DOMContentLoaded", () => {
  const token = localStorage.getItem("safetrack_access_token");
  const role = localStorage.getItem("safetrack_role");
  if (token && role === "admin") window.location.replace("index.html");
  if (token && role === "user") window.location.replace(USER_DASHBOARD);

  document.getElementById("loginForm").addEventListener("submit", handleLogin);
});

async function handleLogin(event) {
  event.preventDefault();
  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  const error = document.getElementById("loginError");
  error.classList.add("hidden");

  try {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Invalid credentials");

    localStorage.setItem("safetrack_access_token", data.access_token);
    localStorage.setItem("safetrack_role", data.role);
    localStorage.setItem("safetrack_username", data.username);
    localStorage.setItem("safetrack_assigned_shipments", JSON.stringify(data.assigned_shipments || []));

    if (data.role === "admin") {
      window.location.replace("index.html");
    } else {
      window.location.replace(USER_DASHBOARD);
    }
  } catch (err) {
    error.textContent = err.message || "Unable to sign in";
    error.classList.remove("hidden");
  }
}
