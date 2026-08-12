/**
 * Centralized API Base URL config.
 * Reads from process.env.NEXT_PUBLIC_API_URL if provided, otherwise defaults to http://localhost:8000
 */
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** Token JWT yang tersimpan di localStorage, atau null kalau belum login / di server. */
export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("token");
}

// Sebelumnya pola ini (baca token dari localStorage lalu susun header Authorization) ditulis
// ulang identik di 10 file frontend berbeda (30 titik pemanggilan) — disatukan di sini supaya
// perubahan pada cara token disimpan/dibaca cukup dilakukan 1 tempat. `extra` dipakai untuk
// header tambahan yang sebelumnya sering digabung manual di pemanggil (mis. Content-Type).
export function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = getToken();
  const headers: Record<string, string> = { ...extra };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}
