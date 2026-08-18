// Thin API client — relative /api/... URLs (proxied by Next to the backend).

const API = "/api/v1";

export function getToken() {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("cp_token");
}

export function setSession(tokens) {
  localStorage.setItem("cp_token", tokens.access_token);
  localStorage.setItem("cp_refresh", tokens.refresh_token || "");
}

export function clearSession() {
  localStorage.removeItem("cp_token");
  localStorage.removeItem("cp_refresh");
}

export function logout() {
  clearSession();
  window.location.href = "/login";
}

export async function api(path, { method = "GET", body, params } = {}) {
  const token = getToken();
  const url = new URL(API + path, window.location.origin);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, v);
    }
  }
  const res = await fetch(url, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) {
    clearSession();
    if (window.location.pathname !== "/login") window.location.href = "/login";
    throw new Error("Not authenticated");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = Array.isArray(j.detail) ? j.detail.map((d) => d.msg).join("; ") : j.detail || detail;
    } catch (_) {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

export async function upload(path, formData) {
  const token = getToken();
  const url = new URL(API + path, window.location.origin);
  const res = await fetch(url, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });
  if (res.status === 401) {
    clearSession();
    window.location.href = "/login";
    throw new Error("Not authenticated");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail || detail;
    } catch (_) {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}
