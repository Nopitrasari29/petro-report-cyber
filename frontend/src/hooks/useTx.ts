"use client";

import { useState, useEffect } from "react";
import { t } from "@/utils/i18n";

// Pengaman hidrasi (Next.js: render server & client harus sama persis di render PERTAMA,
// jadi teks yang bergantung pada localStorage/preferensi browser baru "aman" ditampilkan
// setelah mounted=true) + fungsi tx() turunannya - SEBELUMNYA pola identik (useState(false) +
// useEffect + fungsi tx) ditulis ulang manual di 21 file berbeda, kandidat jelas utk 1 hook
// bersama supaya tidak perlu disalin lagi di file baru ke depan.
export function useTx() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);
  const tx = (key: string, fallback: string) => (mounted ? t(key) : fallback);
  return { mounted, tx };
}
