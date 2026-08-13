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
  themeColor = "auto",
  setThemeColor,
  stylePreset = "auto",
  setStylePreset,
  tone,
  setTone,
  defaultLevel,
  setDefaultLevel,
  onNext,
  onBack,
  tx,
}: Step2SettingsProps) {
  const [customSectionInput, setCustomSectionInput] = React.useState("");

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

          <div className="space-y-3">
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

            <div>
              <label className="block text-[11px] font-bold text-stone-600 uppercase tracking-wider mb-1.5">
                {tx("Theme Color", "Warna Tema")}
              </label>
              <div className="grid grid-cols-5 gap-1.5">
                {[
                  {
                    id: "auto",
                    name: tx("Automatic", "Otomatis"),
                    color: "",
                    style: {
                      background:
                        "conic-gradient(from 0deg, #004D25, #0F172A, #111827, #78350F, #004D25)",
                    },
                  },
                  {
                    id: "green",
                    name: tx("Corporate Green", "Hijau Korporat"),
                    color: "bg-[#004D25]",
                  },
                  {
                    id: "navy",
                    name: tx("Slate Navy", "Navy Gelap"),
                    color: "bg-[#0F172A]",
                  },
                  {
                    id: "dark",
                    name: tx("Cyber Dark", "Gelap Siber"),
                    color: "bg-[#111827]",
                  },
                  {
                    id: "gold",
                    name: tx("Amber Gold", "Emas Amber"),
                    color: "bg-[#78350F]",
                  },
                ].map((tItem) => (
                  <button
                    type="button"
                    key={tItem.id}
                    onClick={() => setThemeColor && setThemeColor(tItem.id)}
                    title={
                      tItem.id === "auto"
                        ? tx(
                            "Warna diacak otomatis tiap generate (bisa jatuh ke tema apa saja, termasuk hijau)",
                            "Color is randomly picked each time you generate (could land on any theme, including green)",
                          )
                        : tItem.name
                    }
                    className={`flex flex-col items-center justify-center p-1.5 rounded-xl border transition-all cursor-pointer ${
                      themeColor === tItem.id
                        ? "border-stone-900 bg-stone-50 ring-2 ring-stone-900/10 shadow-sm"
                        : "border-stone-200 bg-white hover:bg-stone-50"
                    }`}
                  >
                    <span
                      className={`w-4 h-4 rounded-full shadow-sm mb-1 ${tItem.color}`}
                      style={tItem.style}
                    ></span>
                    <span className="text-[9px] font-extrabold text-stone-700 truncate w-full text-center">
                      {tItem.name.split(" ")[0]}
                    </span>
                  </button>
                ))}
              </div>
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
