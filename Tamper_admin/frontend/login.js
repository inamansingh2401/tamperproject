const API_BASE_URL = "https://safetrack-api-live.vercel.app/api";
const USER_DASHBOARD = "user/dashboard.html";

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
  const submit = event.currentTarget.querySelector('button[type="submit"]');
  if (submit.disabled) return;
  submit.disabled = true;
  submit.textContent = "Connecting…";
  error.classList.add("hidden");

  try {
    const request = () => fetchWithTimeout(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    let response;
    try { response = await request(); }
    catch (networkError) {
      if (!(networkError instanceof TypeError)) throw networkError;
      // Retry only a failed connection, never an HTTP authentication rejection.
      await new Promise(resolve => setTimeout(resolve, 800));
      response = await request();
    }

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Invalid credentials");

    if (!data.access_token || !["admin", "user"].includes(data.role)) throw new Error("This account has no supported dashboard role.");

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
    error.textContent = err instanceof TypeError
      ? "Cannot reach the SafeTrack API from this browser. Check your connection and try again; the ESP32 is not required for login."
      : err.name === "AbortError" ? "The server took too long to respond. Please try again."
      : err.message || "Unable to sign in";
    error.classList.remove("hidden");
  } finally {
    submit.disabled = false;
    submit.textContent = "Log In";
  }
}
