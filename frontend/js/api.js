// Thin fetch wrapper; backend errors use { error: { code, message, details } }.
const TOKEN_KEY = "admin_token";

export const auth = {
  get: () => sessionStorage.getItem(TOKEN_KEY),
  set: (token) => sessionStorage.setItem(TOKEN_KEY, token),
  clear: () => sessionStorage.removeItem(TOKEN_KEY),
};

export async function api(path, options = {}) {
  const headers = { ...options.headers };
  // FormData must set its own multipart boundary.
  if (!(options.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const token = auth.get();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(path, { ...options, headers });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(body?.error?.message ?? `Request failed (${response.status})`);
    error.code = body?.error?.code ?? "http_error";
    error.status = response.status;
    throw error;
  }
  return body;
}
