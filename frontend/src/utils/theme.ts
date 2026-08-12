// Utilitas Appearance (Light/Dark/System) — SEBELUMNYA pengaturan ini tersimpan di DB
// (User.appearance) tapi tidak ada kontrol UI sama sekali (nilainya selalu dikirim hardcode
// "light"), dan tidak ada satu pun bagian aplikasi yang benar-benar berubah tampilan gelap.
// File ini satu-satunya sumber kebenaran untuk baca/tulis/terapkan preferensi ini di seluruh
// aplikasi, dipakai bersama oleh ThemeInitScript (cegah flash tema salah sebelum React hidrasi)
// dan useAppearance (dipakai komponen React, mis. Settings).
export type Appearance = "light" | "dark" | "system";

export const APPEARANCE_STORAGE_KEY = "ui_appearance";

export function getStoredAppearance(): Appearance {
  if (typeof window === "undefined") return "light";
  const stored = localStorage.getItem(APPEARANCE_STORAGE_KEY);
  if (stored === "light" || stored === "dark" || stored === "system") return stored;
  return "system";
}

export function setStoredAppearance(value: Appearance) {
  if (typeof window === "undefined") return;
  localStorage.setItem(APPEARANCE_STORAGE_KEY, value);
}

export function systemPrefersDark(): boolean {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function resolveIsDark(appearance: Appearance): boolean {
  return appearance === "dark" || (appearance === "system" && systemPrefersDark());
}

export function applyThemeClass(appearance: Appearance) {
  if (typeof document === "undefined") return;
  document.documentElement.classList.toggle("dark", resolveIsDark(appearance));
}

// Script inline yang dijalankan SEBELUM React hidrasi (lihat ThemeInitScript.tsx) — kalau
// class .dark cuma diterapkan lewat useEffect (setelah render pertama), user akan melihat
// "kedipan" tema terang sesaat sebelum berganti ke gelap. Dibungkus jadi string supaya bisa
// dipakai langsung sebagai dangerouslySetInnerHTML di server component (layout.tsx).
export function themeInitScriptString(): string {
  return `
(function() {
  try {
    var v = localStorage.getItem("${APPEARANCE_STORAGE_KEY}") || "system";
    var isDark = v === "dark" || (v === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.classList.toggle("dark", isDark);
  } catch (e) {}
})();
`.trim();
}
