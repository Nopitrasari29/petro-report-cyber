"use client";

import { useState, useEffect, useCallback } from "react";
import {
  type Appearance,
  getStoredAppearance,
  setStoredAppearance,
  applyThemeClass,
  systemPrefersDark,
} from "@/utils/theme";

// Hook dipakai komponen React (terutama Settings) utk baca/ubah preferensi Light/Dark/System —
// otomatis menerapkan class .dark ke <html>, menyimpan ke localStorage, dan mengikuti
// perubahan preferensi sistem operasi live (tanpa perlu refresh) saat mode "system" aktif.
export function useAppearance() {
  const [appearance, setAppearanceState] = useState<Appearance>("system");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setAppearanceState(getStoredAppearance());
  }, []);

  // Kalau ada instance hook LAIN di halaman yang sama (mis. Settings page + kartu Appearance
  // di dalamnya) mengubah appearance, instance ini ikut sinkron lewat event ini — tanpa ini,
  // 2 instance hook di halaman yang sama bisa menampilkan nilai berbeda sampai reload.
  useEffect(() => {
    const handler = () => setAppearanceState(getStoredAppearance());
    window.addEventListener("ui_appearance_changed", handler);
    return () => window.removeEventListener("ui_appearance_changed", handler);
  }, []);

  const setAppearance = useCallback((value: Appearance) => {
    setAppearanceState(value);
    setStoredAppearance(value);
    applyThemeClass(value);
    window.dispatchEvent(new Event("ui_appearance_changed"));
  }, []);

  // Kalau mode "system" aktif, ikuti perubahan preferensi OS SECARA LIVE (mis. user ganti
  // Windows dari Light ke Dark tanpa reload halaman ini) — tanpa listener ini, perubahan OS
  // baru kepakai setelah refresh manual.
  useEffect(() => {
    if (!mounted || appearance !== "system") return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => applyThemeClass("system");
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [mounted, appearance]);

  return {
    appearance,
    setAppearance,
    isDark: mounted ? resolveDark(appearance) : false,
  };
}

function resolveDark(appearance: Appearance): boolean {
  return appearance === "dark" || (appearance === "system" && systemPrefersDark());
}
