import React from "react";
import { createPortal } from "react-dom";
import ScrollReveal from "@/components/ScrollReveal";
import { REPORT_SECTIONS } from "@/utils/reportSections";

// Konversi warna utk color wheel kustom (menggantikan <input type="color"> bawaan browser,
// lihat komentar di dekat colorWheelTriggerRef di bawah) — HEX <-> RGB <-> HSV.
function hexToRgb(hex: string): [number, number, number] {
  const clean = hex.replace(/^#/, "").padEnd(6, "0").slice(0, 6);
  const bigint = parseInt(clean, 16) || 0;
  return [(bigint >> 16) & 255, (bigint >> 8) & 255, bigint & 255];
}

function rgbToHex(r: number, g: number, b: number): string {
  const clamp = (v: number) => Math.max(0, Math.min(255, Math.round(v)));
  return (
    "#" +
    [clamp(r), clamp(g), clamp(b)]
      .map((v) => v.toString(16).padStart(2, "0"))
      .join("")
      .toUpperCase()
  );
}

function rgbToHsv(r: number, g: number, b: number): { h: number; s: number; v: number } {
  const rn = r / 255, gn = g / 255, bn = b / 255;
  const max = Math.max(rn, gn, bn), min = Math.min(rn, gn, bn);
  const d = max - min;
  let h = 0;
  if (d !== 0) {
    if (max === rn) h = ((gn - bn) / d) % 6;
    else if (max === gn) h = (bn - rn) / d + 2;
    else h = (rn - gn) / d + 4;
    h *= 60;
    if (h < 0) h += 360;
  }
  const s = max === 0 ? 0 : d / max;
  return { h, s: s * 100, v: max * 100 };
}

function hsvToRgb(h: number, s: number, v: number): [number, number, number] {
  const sn = s / 100, vn = v / 100;
  const c = vn * sn;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = vn - c;
  let r = 0, g = 0, b = 0;
  if (h < 60) [r, g, b] = [c, x, 0];
  else if (h < 120) [r, g, b] = [x, c, 0];
  else if (h < 180) [r, g, b] = [0, c, x];
  else if (h < 240) [r, g, b] = [0, x, c];
  else if (h < 300) [r, g, b] = [x, 0, c];
  else [r, g, b] = [c, 0, x];
  return [(r + m) * 255, (g + m) * 255, (b + m) * 255];
}

export interface DynamicSectionItem {
  key: string;
  title: string;
  description?: string;
  enabled: boolean;
  order?: number;
  recommended?: boolean;
}

interface Step2SettingsProps {
  periodStart: string;
  setPeriodStart: (val: string) => void;
  periodEnd: string;
  setPeriodEnd: (val: string) => void;
  periodAutoDetected: boolean;
  periodDetecting: boolean;
  onPeriodManualEdit: () => void;
  language: string;
  setLanguage: (val: string) => void;
  exportFormats: Record<string, boolean>;
  setExportFormats: React.Dispatch<
    React.SetStateAction<Record<string, boolean>>
  >;
  sections: Record<string, boolean>;
  setSections: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  dynamicSections?: DynamicSectionItem[];
  setDynamicSections?: React.Dispatch<
    React.SetStateAction<DynamicSectionItem[]>
  >;
  sectionsLoading?: boolean;
  headerTitle?: string;
  setHeaderTitle?: (val: string) => void;
  headerSubtitle?: string;
  setHeaderSubtitle?: (val: string) => void;
  themeColor?: string;
  setThemeColor?: (val: string) => void;
  stylePreset?: string;
  setStylePreset?: (val: string) => void;
  templateType?: string;
  setTemplateType?: (val: string) => void;
  tone: string;
  setTone: (val: string) => void;
  defaultLevel: string;
  setDefaultLevel: (val: string) => void;
  onNext: () => void;
  onBack: () => void;
  tx: (key: string, fallback: string) => string;
}

export default function Step2Settings({
  periodStart,
  setPeriodStart,
  periodEnd,
  setPeriodEnd,
  periodAutoDetected,
  periodDetecting,
  onPeriodManualEdit,
  language,
  setLanguage,
  exportFormats,
  setExportFormats,
  sections,
  setSections,
  dynamicSections = [],
  setDynamicSections,
  sectionsLoading = false,
  headerTitle = "PT PETROKIMIA GRESIK",
  setHeaderTitle,
  headerSubtitle = "Sistem Otomasi Laporan & Eksekutif Presentasi Berbasis AI",
  setHeaderSubtitle,
  themeColor = "green",
  setThemeColor,
  stylePreset = "auto",
  setStylePreset,
  templateType = "SOC Executive Summary",
  setTemplateType,
  tone,
  setTone,
  defaultLevel,
  setDefaultLevel,
  onNext,
  onBack,
  tx,
}: Step2SettingsProps) {
  const [customSectionInput, setCustomSectionInput] = React.useState("");
  const [showColorPicker, setShowColorPicker] = React.useState(false);
  const [customHex, setCustomHex] = React.useState(
    themeColor && themeColor.startsWith("#") ? themeColor : "#004D25"
  );
  const colorPickerRef = React.useRef<HTMLDivElement>(null);
  // BUG YANG DIPERBAIKI (dilaporkan user, screenshot: popup keluar dari kotaknya & tabrakan
  // dgn kartu "Export Format" di bawahnya): popup sebelumnya position:absolute di DALAM kartu
  // "Template & Theme" — kartu itu (class premium-card-hover) punya position:relative +
  // transition transform sendiri, jadi popup nyasar terjebak/salah tumpuk di belakang kartu
  // lain alih-alih mengambang bersih di atas SEMUA konten. Sekarang dirender lewat React
  // Portal ke document.body (posisi dihitung dari getBoundingClientRect tombol pemicu) —
  // pola dropdown standar yang TIDAK mungkin lagi terjebak konteks tumpukan kartu manapun.
  const colorTriggerRef = React.useRef<HTMLButtonElement>(null);
  const colorPopupRef = React.useRef<HTMLDivElement>(null);
  const [popupPos, setPopupPos] = React.useState({ top: 0, left: 0, width: 0 });

  const openColorPicker = () => {
    const rect = colorTriggerRef.current?.getBoundingClientRect();
    if (rect) {
      setPopupPos({ top: rect.bottom + 8, left: rect.left, width: rect.width });
    }
    setShowColorPicker(true);
  };

  // Tutup color picker saat klik di luar (cek tombol pemicu MAUPUN isi popup — popup sekarang
  // di document.body via portal, di luar subtree colorPickerRef).
  React.useEffect(() => {
    if (!showColorPicker) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      // BUG DIPERBAIKI (ketemu lewat tes klik-sungguhan, bukan cuma mockup): panel color
      // wheel (wheelPopupRef) juga di-portal ke document.body sbg SIBLING popup ini, BUKAN
      // anak DOM dari colorPopupRef — jadi klik di dalam panel color wheel (mis. menyeret
      // kotak saturation/value) sebelumnya selalu terhitung "di luar" popup utama ini &
      // menutup KEDUA popup di tengah drag. Sekarang klik di dalam wheelPopupRef/
      // wheelTriggerRef juga dianggap "di dalam".
      if (
        colorPickerRef.current && !colorPickerRef.current.contains(target) &&
        colorPopupRef.current && !colorPopupRef.current.contains(target) &&
        !(wheelPopupRef.current && wheelPopupRef.current.contains(target)) &&
        !(wheelTriggerRef.current && wheelTriggerRef.current.contains(target))
      ) {
        setShowColorPicker(false);
      }
    };
    const onScrollOrResize = () => {
      const rect = colorTriggerRef.current?.getBoundingClientRect();
      if (rect) setPopupPos({ top: rect.bottom + 8, left: rect.left, width: rect.width });
    };
    document.addEventListener("mousedown", handler);
    window.addEventListener("scroll", onScrollOrResize, true);
    window.addEventListener("resize", onScrollOrResize);
    return () => {
      document.removeEventListener("mousedown", handler);
      window.removeEventListener("scroll", onScrollOrResize, true);
      window.removeEventListener("resize", onScrollOrResize);
    };
  }, [showColorPicker]);

  // Panel "color wheel" kustom (gantikan <input type="color"> bawaan browser — BUG YANG
  // DIPERBAIKI, dilaporkan user: color picker native browser posisinya di luar kendali CSS
  // kita, jadi bisa muncul tertumpuk aneh di belakang kartu popup kita sendiri). Dirender
  // lewat React Portal juga (pola sama persis dgn colorPopupRef di atas), terbuka di
  // samping kartu popup utama — lihat colorWheelPos.
  const [showColorWheel, setShowColorWheel] = React.useState(false);
  const [hsv, setHsv] = React.useState(() => {
    const [r, g, b] = hexToRgb(customHex);
    return rgbToHsv(r, g, b);
  });
  const wheelTriggerRef = React.useRef<HTMLDivElement>(null);
  const wheelPopupRef = React.useRef<HTMLDivElement>(null);
  const svSquareRef = React.useRef<HTMLDivElement>(null);
  const hueSliderRef = React.useRef<HTMLDivElement>(null);
  const [wheelPos, setWheelPos] = React.useState({ top: 0, left: 0 });
  const eyedropperSupported =
    typeof window !== "undefined" && "EyeDropper" in window;

  const applyHsv = (next: { h: number; s: number; v: number }) => {
    setHsv(next);
    const [r, g, b] = hsvToRgb(next.h, next.s, next.v);
    const hex = rgbToHex(r, g, b);
    setCustomHex(hex);
    setThemeColor && setThemeColor(hex);
  };

  const openColorWheel = () => {
    const [r, g, b] = hexToRgb(customHex);
    setHsv(rgbToHsv(r, g, b));
    const popupRect = colorPopupRef.current?.getBoundingClientRect();
    if (popupRect) {
      const wheelWidth = 216;
      const fitsRight = popupRect.right + 10 + wheelWidth <= window.innerWidth - 12;
      setWheelPos({
        top: popupRect.top,
        left: fitsRight ? popupRect.right + 10 : Math.max(12, popupRect.left - wheelWidth - 10),
      });
    }
    setShowColorWheel(true);
  };

  React.useEffect(() => {
    if (!showColorPicker) setShowColorWheel(false);
  }, [showColorPicker]);

  React.useEffect(() => {
    if (!showColorWheel) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        wheelTriggerRef.current && !wheelTriggerRef.current.contains(target) &&
        wheelPopupRef.current && !wheelPopupRef.current.contains(target)
      ) {
        setShowColorWheel(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showColorWheel]);

  const dragSvSquare = (clientX: number, clientY: number) => {
    const rect = svSquareRef.current?.getBoundingClientRect();
    if (!rect) return;
    const s = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    const v = Math.max(0, Math.min(1, 1 - (clientY - rect.top) / rect.height));
    applyHsv({ h: hsv.h, s: s * 100, v: v * 100 });
  };

  const dragHueSlider = (clientX: number) => {
    const rect = hueSliderRef.current?.getBoundingClientRect();
    if (!rect) return;
    const h = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width)) * 360;
    applyHsv({ h, s: hsv.s, v: hsv.v });
  };

  // PERMINTAAN USER: kursor tangan tetap terlihat saat menyeret handle bulat, padahal
  // maunya handle bulat itu sendiri yang MEMBESAR saat diseret (jadi indikator visual
  // posisi warna, bukan kursornya) — lihat draggingHandle, dipakai utk scale-up handle +
  // sembunyikan kursor (cursor-none) selama drag berlangsung.
  const [draggingHandle, setDraggingHandle] = React.useState<"sv" | "hue" | null>(null);

  const handleSvPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    setDraggingHandle("sv");
    // BUG DIPERBAIKI (dilaporkan user): cursor-none di kotaknya cuma berlaku selama
    // mouse SECARA FISIK ada tepat di atas kotak itu — begitu gerakan menyeret sedikit
    // saja melewati batas kotak (wajar krn kotaknya kecil), kursor balik kelihatan lagi
    // walau nilai warnanya tetap ke-update benar (posisi di-clamp). Selama drag AKTIF,
    // paksa cursor:none di document.body juga supaya tetap tersembunyi ke mana pun mouse
    // bergerak, dilepas lagi begitu drag selesai.
    document.body.style.cursor = "none";
    dragSvSquare(e.clientX, e.clientY);
    const onMove = (ev: PointerEvent) => dragSvSquare(ev.clientX, ev.clientY);
    const onUp = () => {
      setDraggingHandle(null);
      document.body.style.cursor = "";
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  const handleHuePointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId);
    setDraggingHandle("hue");
    document.body.style.cursor = "none";
    dragHueSlider(e.clientX);
    const onMove = (ev: PointerEvent) => dragHueSlider(ev.clientX);
    const onUp = () => {
      setDraggingHandle(null);
      document.body.style.cursor = "";
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  const handleEyedropper = async () => {
    if (!eyedropperSupported) return;
    try {
      // @ts-expect-error EyeDropper belum ada di lib.dom.d.ts standar TypeScript
      const dropper = new window.EyeDropper();
      const result = await dropper.open();
      const hex = (result.sRGBHex as string).toUpperCase();
      setCustomHex(hex);
      setThemeColor && setThemeColor(hex);
      const [r, g, b] = hexToRgb(hex);
      setHsv(rgbToHsv(r, g, b));
    } catch {
      // User membatalkan (klik Escape) — tidak perlu ditangani sbg error.
    }
  };

  const wheelRgb = hsvToRgb(hsv.h, hsv.s, hsv.v);
  const wheelHex = rgbToHex(wheelRgb[0], wheelRgb[1], wheelRgb[2]);
  const hueBg = `hsl(${hsv.h}, 100%, 50%)`;
  const svHandleSize = draggingHandle === "sv" ? 24 : 14;
  const hueHandleSize = draggingHandle === "hue" ? 26 : 18;

  // BUG DIPERBAIKI (dilaporkan user, screenshot ke-3): CSS grid `align-items: stretch` biasa
  // TIDAK bisa diandalkan di sini — begitu daftar section AI panjang (7-9+ item), tinggi
  // ALAMI kartu "Include Sections" (kolom 3) sendiri ikut dipakai browser sebagai acuan tinggi
  // BARIS grid (karena `grid-auto-rows: auto` dihitung dari max-content SEBELUM stretch
  // diterapkan), jadi kartu ini malah ikut memanjang tanpa batas alih-alih discroll — pola yang
  // sama seperti yang sudah diselesaikan di Step4PreviewEdit.tsx (lihat previewCardHeight di
  // sana): tinggi kartu "Template & Theme" (kolom 2, isinya stabil/dikenal) diukur lewat
  // ResizeObserver, lalu dipaksakan sebagai `height` tetap (px, BUKAN cuma CSS) ke kartu
  // "Include Sections" — supaya kartu ini SELALU persis setinggi kolom 2 apa pun panjang
  // daftarnya, dan overflow-y-auto di dalamnya BENAR-BENAR jadi satu-satunya jalan keluar
  // kalau section-nya banyak (bukan si kartu yang melar).
  const templateCardRef = React.useRef<HTMLDivElement>(null);
  const [templateCardHeight, setTemplateCardHeight] = React.useState<
    number | undefined
  >(undefined);
  React.useEffect(() => {
    const el = templateCardRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const borderBoxSize = entry.borderBoxSize?.[0];
        setTemplateCardHeight(
          borderBoxSize ? borderBoxSize.blockSize : entry.contentRect.height,
        );
      }
    });
    ro.observe(el, { box: "border-box" });
    return () => ro.disconnect();
  }, []);

  const handleAddCustomSection = () => {
    if (!customSectionInput.trim() || !setDynamicSections) return;
    const newKey = `custom_${Date.now()}`;
    const newItem: DynamicSectionItem = {
      key: newKey,
      title: customSectionInput.trim(),
      description: tx("Section kustom pengguna", "User-added custom section"),
      enabled: true,
    };
    setDynamicSections([...dynamicSections, newItem]);
    setCustomSectionInput("");
  };

  const handleToggleDynamicSection = (index: number) => {
    if (!setDynamicSections) return;
    const updated = [...dynamicSections];
    updated[index].enabled = !updated[index].enabled;
    setDynamicSections(updated);
  };

  return (
    <ScrollReveal animation="fadeInUp" className="space-y-6">
      <div className="text-left -mt-2 mb-3">
        <h2 className="text-2xl font-extrabold text-stone-900">
          {tx("Report Settings", "Report Settings")}
        </h2>
        <p className="text-sm text-stone-500 font-semibold mt-1">
          {tx(
            "Configure report template, theme colors, and AI-suggested sections",
            "Configure report template, theme colors, and AI-suggested sections",
          )}
        </p>
      </div>

      {/* 3-Column Top Cards — Opsi C (disetujui user via canvas desain): tetap 3 kolom seperti
          semula, tapi Kolom 1 dipadatkan dgn memindahkan Judul Kop/Subjudul Kop ke sini juga
          (sebelumnya di Kolom 2), supaya tidak terlalu kosong dibanding 2 kolom lain. */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 text-left">
        {/* Column 1: Informasi Laporan (Periode, Bahasa, Judul/Subjudul Kop) */}
        <div className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm space-y-4 premium-card-hover transition-colors">
          <h3 className="font-extrabold text-stone-855 text-sm border-b border-stone-100 pb-2">
            {tx("Informasi Laporan", "Report Information")}
          </h3>

          <div className="space-y-3">
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider">
                  {tx("Report Period", "Report Period")}
                </label>
                {periodDetecting && (
                  <span className="inline-flex items-center gap-1 text-[10px] font-bold text-stone-400">
                    <span className="w-2.5 h-2.5 border-2 border-stone-300 border-t-petro-green rounded-full animate-spin"></span>
                    {tx("Detecting...", "Detecting...")}
                  </span>
                )}
                {!periodDetecting && periodAutoDetected && (
                  <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-600">
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      className="w-3 h-3"
                    >
                      <path
                        fillRule="evenodd"
                        d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z"
                        clipRule="evenodd"
                      />
                    </svg>
                    {tx("Auto-detected", "Auto-detected")}
                  </span>
                )}
              </div>
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="date"
                  value={periodStart}
                  onChange={(e) => {
                    setPeriodStart(e.target.value);
                    onPeriodManualEdit();
                  }}
                  className="bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 text-xs text-stone-700 font-bold focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
                />
                <input
                  type="date"
                  value={periodEnd}
                  onChange={(e) => {
                    setPeriodEnd(e.target.value);
                    onPeriodManualEdit();
                  }}
                  className="bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 text-xs text-stone-700 font-bold focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider mb-1.5">
                {tx("Language", "Language")}
              </label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 text-xs text-stone-700 font-bold focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
              >
                <option value="Indonesian">Bahasa Indonesia</option>
                <option value="English">English</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider mb-1.5">
                {tx("Kop Header Title", "Judul Kop")}
              </label>
              <input
                type="text"
                value={headerTitle}
                onChange={(e) =>
                  setHeaderTitle && setHeaderTitle(e.target.value)
                }
                placeholder="PT PETROKIMIA GRESIK"
                className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 text-xs font-bold text-stone-800 focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider mb-1.5">
                {tx("Kop Subtitle", "Subjudul Kop")}
              </label>
              <input
                type="text"
                value={headerSubtitle}
                onChange={(e) =>
                  setHeaderSubtitle && setHeaderSubtitle(e.target.value)
                }
                placeholder="Sistem Otomasi Laporan & Eksekutif Presentasi Berbasis AI"
                className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 text-xs text-stone-700 font-medium focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
              />
            </div>
          </div>
        </div>

        {/* Column 2: Template & Theme Selector — ref di sini dipakai ResizeObserver (lihat
            templateCardHeight di atas) supaya tinggi kartu ini bisa "dipinjam" persis oleh
            kartu Include Sections di kolom 3. */}
        <div
          ref={templateCardRef}
          className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm space-y-4 premium-card-hover transition-colors"
        >
          <h3 className="font-extrabold text-stone-850 text-sm border-b border-stone-100 pb-2 flex items-center justify-between">
            <span>{tx("Template & Theme", "Template & Theme")}</span>
            <span className="text-[10px] bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full font-bold border border-amber-200">
              {tx("Custom Kop", "Kop Kustom")}
            </span>
          </h3>

          <div className="space-y-3.5">
            {/* Tipe Template Laporan — Card Stack Vertikal agar teks judul & deskripsi tidak pernah terpotong (truncate) */}
            <div>
              <label className="block text-[11px] font-bold text-stone-600 uppercase tracking-wider mb-1.5">
                {tx("Report Template Type", "Tipe Template Laporan")}
              </label>
              <div className="space-y-2">
                {[
                  {
                    id: "SOC Executive Summary",
                    name: tx("Descriptive Report", "Laporan Deskriptif"),
                    desc: tx("Analisis mendalam, ringkasan eksekutif & temuan komprehensif", "Analisis mendalam, ringkasan eksekutif & temuan komprehensif"),
                    badge: "Standard",
                    icon: (
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-4 h-4">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                      </svg>
                    ),
                  },
                  {
                    id: "Management Report",
                    name: tx("Visual Report", "Laporan Visual"),
                    desc: tx("Visual tinggi, KPI ringkas, peta risiko & action items eksekutif", "Visual tinggi, KPI ringkas, peta risiko & action items eksekutif"),
                    badge: "Visual / KPI",
                    icon: (
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-4 h-4">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
                      </svg>
                    ),
                  },
                ].map((tOption) => {
                  const isSelected =
                    (templateType || "SOC Executive Summary").toLowerCase() ===
                    tOption.id.toLowerCase();
                  return (
                    <button
                      type="button"
                      key={tOption.id}
                      onClick={() =>
                        setTemplateType && setTemplateType(tOption.id)
                      }
                      className={`w-full flex items-start gap-3 p-3 rounded-xl border transition-all cursor-pointer text-left ${
                        isSelected
                          ? "border-petro-green bg-emerald-50/60 ring-2 ring-petro-green/20 shadow-sm"
                          : "border-stone-200 bg-white hover:bg-stone-50/80 hover:border-stone-300"
                      }`}
                    >
                      <div
                        className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-colors ${
                          isSelected
                            ? "bg-petro-green text-white shadow-sm"
                            : "bg-stone-100 text-stone-500"
                        }`}
                      >
                        {tOption.icon}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2 mb-0.5">
                          <span
                            className={`text-xs font-black leading-tight ${
                              isSelected ? "text-petro-green" : "text-stone-850"
                            }`}
                          >
                            {tOption.name}
                          </span>
                          <span
                            className={`text-[8px] font-extrabold px-1.5 py-0.5 rounded-full shrink-0 ${
                              isSelected
                                ? "bg-petro-green text-white shadow-xs"
                                : "bg-stone-100 text-stone-500"
                            }`}
                          >
                            {tOption.badge}
                          </span>
                        </div>
                        <p className="text-[10px] text-stone-500 font-medium leading-relaxed">
                          {tOption.desc}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Theme Color — sekarang popup mengambang (tidak lagi mendorong Style Preset di
                bawahnya turun saat dibuka) — BUG YANG DIPERBAIKI (dilaporkan user): dulu
                "Inline Expandable Accordion" ikut mendorong-dorong tata letak kartu ini. */}
            <div className="relative" ref={colorPickerRef}>
              <div className="flex items-center justify-between">
                <label className="block text-[11px] font-bold text-stone-600 uppercase tracking-wider">
                  {tx("Theme Color", "Warna Tema Laporan")}
                </label>
              </div>

              {/* Compute Active Color Info */}
              {(() => {
                const colorMap: Record<string, { name: string; hex: string }> = {
                  green: { name: tx("Petrokimia Green", "Hijau Petrokimia"), hex: "#004D25" },
                  navy: { name: tx("Slate Navy", "Navy Gelap"), hex: "#0F172A" },
                  dark: { name: tx("Cyber Dark", "Gelap Siber"), hex: "#111827" },
                  gold: { name: tx("Amber Gold", "Emas Amber"), hex: "#78350F" },
                  teal: { name: tx("Deep Teal", "Teal Gelap"), hex: "#0F766E" },
                  ocean: { name: tx("Ocean Blue", "Biru Samudra"), hex: "#0284C7" },
                  indigo: { name: tx("Royal Indigo", "Indigo Elegan"), hex: "#4338CA" },
                  ruby: { name: tx("Ruby Red", "Merah Ruby"), hex: "#991B1B" },
                };
                const activeColor =
                  themeColor && themeColor.startsWith("#")
                    ? { name: tx("Custom Color", "Warna Kustom"), hex: themeColor }
                    : colorMap[themeColor || "green"] || colorMap.green;

                return (
                  <div className="space-y-2.5">
                    {/* The Sleek Single-Row Pill Trigger */}
                    <button
                      type="button"
                      ref={colorTriggerRef}
                      onClick={() => (showColorPicker ? setShowColorPicker(false) : openColorPicker())}
                      className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl border transition-all duration-200 cursor-pointer group shadow-2xs ${
                        showColorPicker
                          ? "bg-white border-petro-green ring-2 ring-petro-green/20 shadow-xs"
                          : "bg-stone-50/90 hover:bg-stone-100/90 border-stone-200"
                      }`}
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <span
                          className="w-4 h-4 rounded-full shadow-inner border border-white/80 ring-1 ring-black/10 shrink-0 transition-transform group-hover:scale-110"
                          style={{ backgroundColor: activeColor.hex }}
                        />
                        <span className="text-xs font-bold text-stone-850 truncate leading-tight">
                          {activeColor.name}
                        </span>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <span className="text-[10px] font-mono font-extrabold px-2 py-0.5 rounded-md bg-white border border-stone-200/90 text-stone-700 shadow-2xs">
                          {activeColor.hex.toUpperCase()}
                        </span>
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          viewBox="0 0 20 20"
                          fill="currentColor"
                          className={`w-4 h-4 text-stone-400 transition-transform duration-300 ${
                            showColorPicker ? "rotate-180 text-petro-green" : "group-hover:text-stone-600"
                          }`}
                        >
                          <path
                            fillRule="evenodd"
                            d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z"
                            clipRule="evenodd"
                          />
                        </svg>
                      </div>
                    </button>

                    {/* Popup mengambang lewat React Portal ke document.body (posisi dihitung
                        dari tombol pemicu, lihat popupPos/openColorPicker) — TIDAK ikut alur
                        dokumen jadi tidak mendorong turun elemen di bawahnya, DAN tidak lagi
                        bisa terjebak di belakang/tabrakan dgn kartu lain (BUG YANG
                        DIPERBAIKI, dilaporkan user). Ditutup via klik-di-luar (cek
                        colorPickerRef + colorPopupRef, sudah ada di atas). */}
                    {showColorPicker && createPortal(
                      <div
                        ref={colorPopupRef}
                        className="fixed z-50 bg-white border border-stone-200/90 rounded-2xl p-3.5 space-y-3 shadow-xl animate-fadeIn"
                        style={{ top: popupPos.top, left: popupPos.left, width: Math.max(popupPos.width, 280) }}
                      >
                        {/* Section 1: 8 Clean Brand Presets */}
                        <div>
                          <span className="text-[9px] font-extrabold text-stone-400 uppercase tracking-wider block mb-2">
                            {tx("Choose Palette Preset", "Pilih Palet Warna")}
                          </span>
                          <div className="grid grid-cols-2 gap-1.5">
                            {[
                              { id: "green", name: "Petro Green", hex: "#004D25" },
                              { id: "navy", name: "Slate Navy", hex: "#0F172A" },
                              { id: "dark", name: "Cyber Dark", hex: "#111827" },
                              { id: "gold", name: "Amber Gold", hex: "#78350F" },
                              { id: "#0F766E", name: "Deep Teal", hex: "#0F766E" },
                              { id: "#0284C7", name: "Ocean Blue", hex: "#0284C7" },
                              { id: "#4338CA", name: "Royal Indigo", hex: "#4338CA" },
                              { id: "#991B1B", name: "Ruby Crimson", hex: "#991B1B" },
                            ].map((p) => {
                              const isSelected =
                                themeColor === p.id ||
                                (themeColor && themeColor.toLowerCase() === p.hex.toLowerCase());
                              return (
                                <button
                                  key={p.id}
                                  type="button"
                                  onClick={() => {
                                    setCustomHex(p.hex);
                                    setThemeColor && setThemeColor(p.id);
                                  }}
                                  className={`flex items-center gap-2 px-2.5 py-2 rounded-xl border text-left transition-all duration-150 cursor-pointer ${
                                    isSelected
                                      ? "bg-white border-petro-green ring-2 ring-petro-green/15 text-petro-green font-black shadow-xs"
                                      : "bg-white/80 hover:bg-white border-stone-200 text-stone-700 font-bold hover:border-stone-300"
                                  }`}
                                >
                                  <span
                                    className="w-3.5 h-3.5 rounded-full shrink-0 shadow-2xs border border-white/80"
                                    style={{ backgroundColor: p.hex }}
                                  />
                                  <span className="text-[11px] truncate leading-tight">
                                    {p.name}
                                  </span>
                                </button>
                              );
                            })}
                          </div>
                        </div>

                        <div className="h-px bg-stone-200/60" />

                        {/* Section 2: Custom Color Wheel & Hex Input */}
                        <div>
                          <span className="text-[9px] font-extrabold text-stone-400 uppercase tracking-wider block mb-2">
                            {tx("Custom Hex / Color Wheel", "Warna Kustom")}
                          </span>
                          <div className="flex items-center gap-1.5">
                            {/* Color Wheel Trigger — BUG DIPERBAIKI (dilaporkan user,
                                screenshot): sebelumnya <input type="color"> bawaan browser,
                                posisinya di luar kendali CSS kita jadi bisa muncul tertumpuk
                                aneh di belakang kartu popup kita sendiri. Sekarang buka
                                panel color wheel BUATAN SENDIRI (lihat showColorWheel di
                                atas), portal juga jadi tidak mungkin lagi tertumpuk. */}
                            <div
                              ref={wheelTriggerRef}
                              onClick={() => (showColorWheel ? setShowColorWheel(false) : openColorWheel())}
                              className="relative w-8.5 h-8.5 rounded-full shrink-0 cursor-pointer flex items-center justify-center shadow-xs ring-2 ring-petro-green/20"
                              style={{
                                background:
                                  "conic-gradient(from 180deg, #ff0000, #ffcc00, #33ff00, #00ffee, #0066ff, #cc00ff, #ff0000)",
                              }}
                              title={tx("Click to open color wheel", "Klik untuk buka color wheel")}
                            />

                            {/* Eyedropper — ambil warna langsung dari layar (EyeDropper API,
                                Chrome/Edge; disembunyikan kalau browser tidak dukung). */}
                            {eyedropperSupported && (
                              <button
                                type="button"
                                onClick={handleEyedropper}
                                title={tx("Pick color from screen", "Ambil warna dari layar")}
                                className="w-8.5 h-8.5 rounded-xl bg-violet-50 border border-violet-200/80 shrink-0 cursor-pointer flex items-center justify-center hover:bg-violet-100 transition-colors"
                              >
                                <svg viewBox="0 0 24 24" fill="none" stroke="#6d4fd6" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
                                  <path d="M18.5 3.5a2.121 2.121 0 0 1 3 3L19 9l-3-3 2.5-2.5Z" />
                                  <path d="M16 6 5 17v3h3L19 9" />
                                </svg>
                              </button>
                            )}

                          </div>
                        </div>
                      </div>,
                      document.body
                    )}

                    {/* Panel Color Wheel kustom — portal terpisah, terbuka di samping popup
                        utama (lihat openColorWheel), TIDAK pernah tertumpuk krn di
                        document.body, sama pola dgn popup utama di atas. */}
                    {showColorWheel && createPortal(
                      <div
                        ref={wheelPopupRef}
                        className="fixed z-60 bg-white border border-stone-200/90 rounded-2xl p-3.5 shadow-xl animate-fadeIn"
                        style={{ top: wheelPos.top, left: wheelPos.left, width: 216 }}
                      >
                        <span className="text-[9px] font-extrabold text-stone-400 uppercase tracking-wider block mb-2">
                          {tx("Color Wheel", "Color Wheel")}
                        </span>

                        {/* Kotak Saturation/Value — PERMINTAAN USER: kursor cuma disembunyikan
                            SELAMA ditekan/digeser (draggingHandle), bukan dari awal hover —
                            bulat indikator yang membesar itu sendiri jadi penanda posisi,
                            gantinya kursor. Posisi handle dihitung via calc() (bukan
                            left:X%+transform:-50%) supaya badannya selalu persis di dalam
                            kotak, tidak pernah "nongol" keluar tepi sedikit pun. */}
                        <div
                          ref={svSquareRef}
                          onPointerDown={handleSvPointerDown}
                          className={`relative w-full h-33 rounded-[10px] shadow-inner select-none touch-none ${
                            draggingHandle === "sv" ? "cursor-none" : "cursor-pointer"
                          }`}
                          style={{
                            background: `linear-gradient(to top, #000, transparent), linear-gradient(to right, #fff, transparent), ${hueBg}`,
                          }}
                        >
                          <div
                            className={`absolute rounded-full border-[2.5px] border-white pointer-events-none transition-[width,height] duration-150 ${
                              draggingHandle === "sv" ? "w-6 h-6" : "w-3.5 h-3.5"
                            }`}
                            style={{
                              left: `calc((100% - ${svHandleSize}px) * ${hsv.s / 100})`,
                              top: `calc((100% - ${svHandleSize}px) * ${(100 - hsv.v) / 100})`,
                              backgroundColor: wheelHex,
                              boxShadow: "0 0 0 1px rgba(0,0,0,0.35), 0 1px 3px rgba(0,0,0,0.3)",
                            }}
                          />
                        </div>

                        {/* Slider Hue — sama, handle dijaga tetap di dalam track secara
                            horizontal (vertikal tetap ditengahkan, track-nya memang sengaja
                            lebih tipis dari handle). */}
                        <div
                          ref={hueSliderRef}
                          onPointerDown={handleHuePointerDown}
                          className={`relative mt-3 w-full h-3 rounded-full shadow-inner select-none touch-none ${
                            draggingHandle === "hue" ? "cursor-none" : "cursor-pointer"
                          }`}
                          style={{
                            background:
                              "linear-gradient(to right, #ff0000, #ffff00, #00ff00, #00ffff, #0000ff, #ff00ff, #ff0000)",
                          }}
                        >
                          <div
                            className={`absolute rounded-full bg-white border-2 border-white pointer-events-none transition-[width,height] duration-150 ${
                              draggingHandle === "hue" ? "w-6.5 h-6.5" : "w-4.5 h-4.5"
                            }`}
                            style={{
                              left: `calc((100% - ${hueHandleSize}px) * ${hsv.h / 360})`,
                              top: "50%",
                              transform: "translateY(-50%)",
                              boxShadow: "0 0 0 1.5px rgba(0,0,0,0.25), 0 1px 3px rgba(0,0,0,0.25)",
                            }}
                          />
                        </div>

                        {/* Preview + Hex — PERMINTAAN USER: kode hex cuma muncul di SATU
                            tempat (di sini, popup color wheel), bukan dobel dgn kotak di
                            panel utama. Input inilah satu-satunya tempat ketik manual;
                            customHex dipakai sbg buffer teks (sama seperti input lama)
                            supaya ketikan parsial tidak langsung ketiban ulang oleh wheelHex
                            sebelum genap 6 digit valid. */}
                        <div className="flex items-center gap-2.5 mt-3.5">
                          <span
                            className="w-8.5 h-8.5 rounded-full border-2 border-white shrink-0"
                            style={{ backgroundColor: wheelHex, boxShadow: "0 0 0 1px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.08)" }}
                          />
                          <div className="relative flex-1">
                            <span className="absolute left-0 top-1/2 -translate-y-1/2 text-stone-400 font-mono text-[15px] font-bold pointer-events-none">
                              #
                            </span>
                            <input
                              type="text"
                              value={customHex.replace(/^#/, "")}
                              maxLength={6}
                              onChange={(e) => {
                                // PERMINTAAN USER: warna langsung berubah tiap ketik satu
                                // karakter, tidak perlu tunggu genap 6 digit / Enter. Digit
                                // yang belum diketik di-"isi sementara" dgn 0 di kanan cuma
                                // utk keperluan preview warna — teks yang tampil di kotak
                                // tetap persis apa yang diketik (raw), bukan versi di-pad.
                                const raw = e.target.value.replace(/[^0-9A-Fa-f]/g, "").toUpperCase();
                                const val = `#${raw}`;
                                setCustomHex(val);
                                if (raw.length > 0) {
                                  const padded = raw.padEnd(6, "0");
                                  setThemeColor && setThemeColor(`#${padded}`);
                                  const [r, g, b] = hexToRgb(`#${padded}`);
                                  setHsv(rgbToHsv(r, g, b));
                                }
                              }}
                              onKeyDown={(e) => {
                                // PERMINTAAN USER: tekan Enter = warna itu yang dipakai,
                                // selesai ngetik, DAN popup color wheel ini langsung
                                // ketutup — bukan cuma blur input-nya doang.
                                if (e.key !== "Enter") return;
                                e.preventDefault();
                                const raw = customHex.replace(/^#/, "");
                                if (raw.length > 0) {
                                  setCustomHex(`#${raw.padEnd(6, "0")}`);
                                }
                                e.currentTarget.blur();
                                setShowColorWheel(false);
                              }}
                              className="w-full bg-transparent pl-3.5 font-mono text-[15px] font-extrabold text-stone-900 tracking-wide focus:outline-none"
                            />
                          </div>
                        </div>

                        {/* RGB Fields */}
                        <div className="flex gap-1.5 mt-3">
                          {(["r", "g", "b"] as const).map((channel, idx) => (
                            <div key={channel} className="flex-1">
                              <span className="text-[8.5px] font-extrabold text-stone-400 uppercase tracking-wider text-center block mb-1">
                                {channel}
                              </span>
                              <input
                                type="text"
                                inputMode="numeric"
                                value={Math.round(wheelRgb[idx])}
                                onChange={(e) => {
                                  const raw = e.target.value.replace(/[^0-9]/g, "");
                                  const n = Math.max(0, Math.min(255, raw === "" ? 0 : parseInt(raw, 10)));
                                  const nextRgb: [number, number, number] = [...wheelRgb] as [number, number, number];
                                  nextRgb[idx] = n;
                                  applyHsv(rgbToHsv(nextRgb[0], nextRgb[1], nextRgb[2]));
                                }}
                                className="w-full text-center bg-stone-50 border border-stone-200 rounded-[9px] py-1.5 text-[11.5px] font-mono font-extrabold text-stone-900 focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green"
                              />
                            </div>
                          ))}
                        </div>
                      </div>,
                      document.body
                    )}
                  </div>
                );
              })()}
            </div>

            <div>
              <label className="block text-[11px] font-bold text-stone-600 uppercase tracking-wider mb-1.5">
                {tx("Style Preset", "Preset Gaya")}
              </label>
              <div className="grid grid-cols-2 gap-2">
                {[
                  { id: "auto", name: tx("Automatic", "Otomatis") },
                  { id: "minimalist", name: tx("Simple", "Simpel") },
                  { id: "corporate", name: tx("Professional", "Profesional") },
                  { id: "executive", name: tx("Bold Executive", "Eksekutif Tegas") },
                ].map((pItem) => (
                  <button
                    type="button"
                    key={pItem.id}
                    onClick={() => setStylePreset && setStylePreset(pItem.id)}
                    className={`flex items-center justify-center px-2 py-2 rounded-xl border transition-all cursor-pointer ${
                      stylePreset === pItem.id
                        ? "border-stone-900 bg-stone-50 ring-2 ring-stone-900/10 shadow-sm"
                        : "border-stone-200 bg-white hover:bg-stone-50"
                    }`}
                  >
                    <span className="text-[9px] font-extrabold text-stone-700 truncate w-full text-center">
                      {pItem.name}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Column 3: AI-Driven Include Sections — tinggi kartu ini DIPAKU (height, px, lewat
            templateCardHeight hasil ResizeObserver di atas) ke tinggi kartu "Template & Theme"
            di kolom 2, KONSTAN berapa pun panjang daftar section-nya (termasuk saat masih
            loading/cuma 1 baris spinner, ATAU saat section-nya 9+ item) — BUKAN lewat CSS grid
            stretch biasa (yang terbukti gagal begitu daftarnya panjang: tinggi ALAMI kartu ini
            ikut menentukan tinggi baris grid duluan sebelum stretch diterapkan, jadi kartunya
            malah ikut memanjang, bukan discroll). Dengan height tetap di sini, flex-1 min-h-0
            pada daftar di bawah PASTI mengisi sisa ruang yang tersedia & overflow-y-auto BENAR2
            jadi satu-satunya jalan keluar kalau section-nya banyak; tombol "+ Add" selalu
            nempel di dasar kartu. */}
        <div
          className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm premium-card-hover transition-colors flex flex-col"
          style={templateCardHeight ? { height: templateCardHeight } : undefined}
        >
          <h3 className="font-extrabold text-stone-850 text-sm border-b border-stone-100 pb-2 mb-4 flex items-center justify-between">
            <span>{tx("Include Sections", "Include Sections")}</span>
            <span className="text-[10px] bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-full font-bold border border-emerald-200 flex items-center gap-1">
              <span>✨</span> {tx("AI Suggested", "AI Suggested")}
            </span>
          </h3>

          <div className="space-y-2 flex-1 min-h-0 overflow-y-auto pr-1">
            {sectionsLoading && dynamicSections.length === 0 ? (
              <div className="flex items-center gap-2 py-4 text-stone-400">
                <span className="w-3.5 h-3.5 border-2 border-stone-300 border-t-petro-green rounded-full animate-spin"></span>
                <span className="text-xs font-semibold">
                  {tx(
                    "AI sedang menyusun usulan section...",
                    "AI sedang menyusun usulan section...",
                  )}
                </span>
              </div>
            ) : dynamicSections.length > 0 ? (
              [...dynamicSections]
                .map((sec, originalIdx) => ({ sec, originalIdx }))
                .sort(
                  (a, b) =>
                    (a.sec.order ?? a.originalIdx) -
                    (b.sec.order ?? b.originalIdx),
                )
                .map(({ sec, originalIdx }) => (
                  <label
                    key={sec.key || originalIdx}
                    className="flex items-start gap-2.5 cursor-pointer py-1 select-none hover:bg-stone-50/80 p-1.5 rounded-lg transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={sec.enabled}
                      onChange={() => handleToggleDynamicSection(originalIdx)}
                      className="w-4 h-4 rounded text-petro-green focus:ring-petro-green border-stone-300 mt-0.5"
                    />
                    <div className="flex flex-col text-left">
                      <span className="text-xs font-bold text-stone-800 leading-tight">
                        {sec.title}
                        {sec.recommended === false && (
                          <span className="ml-1.5 text-[9px] font-bold text-stone-400 uppercase tracking-wide">
                            {tx("Opsional", "Optional")}
                          </span>
                        )}
                      </span>
                      {sec.description && (
                        <span className="text-[9.5px] text-stone-400 font-medium leading-tight mt-0.5">
                          {sec.description}
                        </span>
                      )}
                    </div>
                  </label>
                ))
            ) : (
              REPORT_SECTIONS.map((sec) => (
                <label
                  key={sec.key}
                  className="flex items-center gap-2.5 cursor-pointer py-1 select-none"
                >
                  <input
                    type="checkbox"
                    checked={sections[sec.key]}
                    onChange={(e) =>
                      setSections((prev) => ({
                        ...prev,
                        [sec.key]: e.target.checked,
                      }))
                    }
                    className="w-4 h-4 rounded text-petro-green focus:ring-petro-green border-stone-300"
                  />
                  <span className="text-xs font-semibold text-stone-700">
                    {tx(sec.title, sec.title)}
                  </span>
                </label>
              ))
            )}
          </div>

          {/* Add Custom Section Button — shrink-0 supaya baris ini TIDAK ikut ditekan oleh
              flex-1 pada daftar section di atasnya, selalu tetap di dasar kartu. */}
          <div className="flex items-center gap-1.5 border-t border-stone-100 pt-2.5 mt-2.5 shrink-0">
            <input
              type="text"
              value={customSectionInput}
              onChange={(e) => setCustomSectionInput(e.target.value)}
              placeholder={tx("Custom Section Title...", "Judul Bagian Kustom...")}
              className="flex-1 bg-stone-50 border border-stone-200 rounded-lg px-2.5 py-1.5 text-xs text-stone-800 focus:outline-none focus:border-petro-green"
            />
            <button
              type="button"
              onClick={handleAddCustomSection}
              className="px-3 py-1.5 bg-stone-900 hover:bg-stone-800 text-white text-xs font-bold rounded-lg transition-all cursor-pointer shrink-0"
            >
              + {tx("Add", "Tambah")}
            </button>
          </div>
        </div>
      </div>

      {/* Bottom Wide Card: Export Formats & Preferences */}
      <div className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm text-left premium-card-hover transition-colors mt-5">
        <h3 className="font-extrabold text-stone-855 text-sm border-b border-stone-100 pb-2 mb-4">
          {tx(
            "Export Format & Output Options",
            "Export Format & Output Options",
          )}
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <label className="flex items-center gap-3 p-3.5 bg-stone-50 border border-stone-250 rounded-xl cursor-pointer hover:bg-stone-100/50 transition-colors">
            <input
              type="checkbox"
              checked={exportFormats.pdf}
              onChange={(e) =>
                setExportFormats((prev) => ({
                  ...prev,
                  pdf: e.target.checked,
                }))
              }
              className="w-4 h-4 rounded text-petro-green focus:ring-petro-green border-stone-300"
            />
            <div className="flex flex-col text-left">
              <span className="text-xs font-bold text-stone-800">
                {tx("PDF Document", "Dokumen PDF")}
              </span>
              <span className="text-[10px] text-stone-400 font-semibold">
                {tx(
                  "Laporan cetak resmi format A4 dengan Kop Petrokimia & Lampiran Log",
                  "Official printable A4 report with Petrokimia letterhead & Log Attachment",
                )}
              </span>
            </div>
          </label>

          <label className="flex items-center gap-3 p-3.5 bg-stone-50 border border-stone-250 rounded-xl cursor-pointer hover:bg-stone-100/50 transition-colors">
            <input
              type="checkbox"
              checked={exportFormats.pptx}
              onChange={(e) =>
                setExportFormats((prev) => ({
                  ...prev,
                  pptx: e.target.checked,
                }))
              }
              className="w-4 h-4 rounded text-petro-green focus:ring-petro-green border-stone-300"
            />
            <div className="flex flex-col text-left">
              <span className="text-xs font-bold text-stone-800">
                {tx(
                  "PowerPoint Presentation (PPTX)",
                  "Presentasi PowerPoint (PPTX)",
                )}
              </span>
              <span className="text-[10px] text-stone-400 font-semibold">
                {tx(
                  "Slide presentasi eksekutif Widescreen 16:9 dengan grafik & teks visual",
                  "Widescreen 16:9 executive presentation slides with charts & visual text",
                )}
              </span>
            </div>
          </label>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
          <div>
            <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider mb-1.5">
              {tx("Tone", "Tone")}
            </label>
            <select
              value={tone}
              onChange={(e) => setTone(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
            >
              <option value="Professional">
                {tx("Professional", "Professional")}
              </option>
              <option value="Technical">{tx("Technical", "Technical")}</option>
              <option value="Executive">{tx("Executive", "Executive")}</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider mb-1.5">
              {tx("Default Level", "Default Level")}
            </label>
            <select
              value={defaultLevel}
              onChange={(e) => setDefaultLevel(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
            >
              <option value="Standard">{tx("Standard", "Standard")}</option>
              <option value="Detailed">{tx("Detailed", "Detailed")}</option>
              <option value="Summary Only">
                {tx("Summary Only", "Summary Only")}
              </option>
            </select>
          </div>
        </div>
      </div>

      {/* Bottom Nav Bar */}
      <div className="flex justify-between pt-5 border-t border-stone-200/60 mt-8">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white border border-stone-200 hover:bg-stone-50 text-stone-700 font-bold text-sm shadow-sm transition-all duration-200 cursor-pointer"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2.5}
            stroke="currentColor"
            className="w-3.5 h-3.5"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18"
            />
          </svg>
          {tx("Back", "Back")}
        </button>

        <button
          onClick={onNext}
          disabled={sectionsLoading}
          title={
            sectionsLoading
              ? tx(
                  "Please wait until AI finishes suggesting sections for this data",
                  "Mohon tunggu sampai AI selesai mengusulkan section untuk data ini",
                )
              : undefined
          }
          className={`inline-flex items-center gap-2 px-6 py-3 rounded-lg text-white font-bold text-sm shadow transition-all duration-200 group ${
            sectionsLoading
              ? "bg-stone-300 cursor-not-allowed shadow-none"
              : "bg-petro-green hover:bg-petro-green-hover cursor-pointer"
          }`}
        >
          {sectionsLoading ? (
            <>
              <span className="w-3.5 h-3.5 border-2 border-white/50 border-t-white rounded-full animate-spin" />
              {tx("Preparing AI suggestions...", "Menyiapkan usulan AI...")}
            </>
          ) : (
            <>
              {tx("Generate Report", "Generate Report")}
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2.5}
                stroke="currentColor"
                className="w-3.5 h-3.5 transition-transform group-hover:translate-x-1"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3"
                />
              </svg>
            </>
          )}
        </button>
      </div>
    </ScrollReveal>
  );
}
