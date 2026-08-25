import React from "react";
import ScrollReveal from "@/components/ScrollReveal";
import { REPORT_SECTIONS } from "@/utils/reportSections";

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

  // Tutup color picker saat klik di luar
  React.useEffect(() => {
    if (!showColorPicker) return;
    const handler = (e: MouseEvent) => {
      if (colorPickerRef.current && !colorPickerRef.current.contains(e.target as Node)) {
        setShowColorPicker(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showColorPicker]);

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

      {/* 3-Column Top Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 text-left">
        {/* Column 1: Report Metadata & Period */}
        <div className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm space-y-4 premium-card-hover transition-colors">
          <h3 className="font-extrabold text-stone-855 text-sm border-b border-stone-100 pb-2">
            {tx("Report Period & Language", "Report Period & Language")}
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
          </div>
        </div>

        {/* Column 2: Template Kop & Theme Selector — ref di sini dipakai ResizeObserver (lihat
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
                    name: tx("SOC Technical Report", "Laporan Teknis SOC"),
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
                    name: tx("Management Report", "Laporan Manajemen"),
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

            <div>
              <label className="block text-[11px] font-bold text-stone-600 uppercase tracking-wider mb-1">
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
              <label className="block text-[11px] font-bold text-stone-600 uppercase tracking-wider mb-1">
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

            {/* Theme Color — Inline Expandable Luxury Accordion (Never gets cut off or overlaps buttons!) */}
            <div className="space-y-2" ref={colorPickerRef}>
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
                      onClick={() => setShowColorPicker(!showColorPicker)}
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

                    {/* Smooth INLINE Expandable Palette (Never cuts off, cleanly pushes content down!) */}
                    {showColorPicker && (
                      <div className="bg-stone-50/80 border border-stone-200/90 rounded-2xl p-3.5 space-y-3 animate-fadeIn">
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
                          <div className="flex items-center gap-2">
                            {/* Color Wheel Swatch Trigger */}
                            <div
                              className="relative w-9 h-9 rounded-xl shadow-xs border border-stone-300/80 overflow-hidden shrink-0 cursor-pointer group"
                              title={tx("Click to open color wheel", "Klik untuk buka color wheel")}
                            >
                              <input
                                type="color"
                                value={customHex.startsWith("#") ? customHex : "#004D25"}
                                onChange={(e) => {
                                  const val = e.target.value.toUpperCase();
                                  setCustomHex(val);
                                  setThemeColor && setThemeColor(val);
                                }}
                                className="absolute -top-4 -left-4 w-20 h-20 cursor-pointer opacity-0 z-10"
                              />
                              <div
                                className="w-full h-full rounded"
                                style={{ backgroundColor: customHex }}
                              />
                              <div className="absolute inset-0 bg-black/15 opacity-0 group-hover:opacity-100 flex items-center justify-center text-white text-[10px] transition-opacity">
                                🎨
                              </div>
                            </div>

                            {/* Hex Monospace Input */}
                            <div className="relative flex-1">
                              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-stone-400 font-mono text-xs font-bold pointer-events-none">
                                #
                              </span>
                              <input
                                type="text"
                                value={customHex.replace(/^#/, "")}
                                maxLength={6}
                                placeholder="004D25"
                                onChange={(e) => {
                                  const raw = e.target.value.replace(/[^0-9A-Fa-f]/g, "").toUpperCase();
                                  const val = `#${raw}`;
                                  setCustomHex(val);
                                  if (raw.length === 6) {
                                    setThemeColor && setThemeColor(val);
                                  }
                                }}
                                className="w-full bg-white border border-stone-200 rounded-xl pl-7 pr-3 py-2 text-xs font-mono font-extrabold text-stone-850 focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green uppercase tracking-wider shadow-2xs"
                              />
                            </div>

                            {/* Done Button */}
                            <button
                              type="button"
                              onClick={() => {
                                const formatted = customHex.startsWith("#") ? customHex : `#${customHex}`;
                                if (/^#[0-9A-Fa-f]{6}$/.test(formatted)) {
                                  setThemeColor && setThemeColor(formatted.toUpperCase());
                                }
                                setShowColorPicker(false);
                              }}
                              className="px-3.5 py-2 bg-stone-900 hover:bg-black text-white text-xs font-extrabold rounded-xl transition-colors shadow-xs cursor-pointer shrink-0"
                            >
                              OK
                            </button>
                          </div>
                        </div>
                      </div>
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
