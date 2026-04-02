const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

export async function apiRequest(path, options = {}) {
  const token = localStorage.getItem("adminToken");
  const headers = new Headers(options.headers || {});
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || data.message || "Request failed");
  }

  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response;
}

export { API_BASE };
