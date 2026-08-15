import axios from "axios";

const CACHE_TTL_MS = 30_000;
const readCache = new Map<string, { expires: number; data: unknown }>();
const cacheKey = (config: any) => `${config.headers?.Authorization || "guest"}:${config.url || ""}?${JSON.stringify(config.params || {})}`;

export const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1" });

api.interceptors.request.use((config: any) => {
  const token = localStorage.getItem("etg_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  if ((config.method || "get").toLowerCase() !== "get") {
    readCache.clear();
    return config;
  }
  const cached = readCache.get(cacheKey(config));
  if (cached && cached.expires > Date.now()) {
    config.adapter = async () => ({ data: cached.data, status: 200, statusText: "OK (memory cache)", headers: {}, config, request: null });
  }
  return config;
});

api.interceptors.response.use((response) => {
  if ((response.config.method || "get").toLowerCase() === "get") readCache.set(cacheKey(response.config), { expires: Date.now() + CACHE_TTL_MS, data: response.data });
  return response;
});

export function warmAppData() {
  return Promise.allSettled([api.get("/equipment"), api.get("/dashboard"), api.get("/inspections"), api.get("/risk/overview"), api.get("/models/status"), api.get("/experiments")]);
}
