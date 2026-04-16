const API_BASE = window.__API_BASE__ || `${window.location.origin}/api`;

function getToken() {
  return localStorage.getItem("mmj-auth-token");
}

function setToken(token) {
  localStorage.setItem("mmj-auth-token", token);
}

function clearToken() {
  localStorage.removeItem("mmj-auth-token");
}

async function request(path, options = {}) {
  const token = getToken();
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error ?? "API request failed");
  }
  return payload;
}

export async function login(email, password) {
  const result = await request("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setToken(result.token);
  return result;
}

export function logout() {
  clearToken();
}

export async function fetchMe() {
  return request("/me");
}

export async function fetchState() {
  return request("/state");
}

export async function awardPoints(memberName, points, reason) {
  return request("/points/award", {
    method: "POST",
    body: JSON.stringify({ memberName, points, reason }),
  });
}

export async function fetchOpsMetrics() {
  return request("/ops/metrics");
}

export async function fetchOpsAudit() {
  return request("/ops/audit");
}

export function hasToken() {
  return Boolean(getToken());
}
