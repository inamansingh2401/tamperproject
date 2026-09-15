const API_BASE_URL = "https://safetrack-api-live.vercel.app/api";
const USER_DASHBOARD = "https://safetrack-user-live-chi.vercel.app/";

document.addEventListener("DOMContentLoaded", () => {
  const token = sessionStorage.getItem("safetrack_access_token");
  const role = sessionStorage.getItem("safetrack_role");
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
    const response = await fetchWithTimeout(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Invalid credentials");

    sessionStorage.setItem("safetrack_access_token", data.access_token);
    sessionStorage.setItem("safetrack_role", data.role);
    sessionStorage.setItem("safetrack_username", data.username);
    sessionStorage.setItem("safetrack_assigned_shipments", JSON.stringify(data.assigned_shipments || []));

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
