// In production the SPA and API share an origin: `/api/*` is proxied to the
// backend by Vercel (see frontend/vercel.json) so the session cookie stays
// first-party. Always use that same-origin path in prod — never a cross-site
// backend URL, which would make `ps_session` a (blocked) third-party cookie.
// In dev, point at the local backend (overridable via VITE_API_BASE_URL).
const apiBaseUrl = import.meta.env.PROD
  ? "/api"
  : (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000");

export const config = {
  apiBaseUrl,
  supabaseUrl: import.meta.env.VITE_SUPABASE_URL ?? "",
  supabaseAnonKey: import.meta.env.VITE_SUPABASE_ANON_KEY ?? "",
};
