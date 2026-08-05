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
  tone,
  setTone,
  defaultLevel,
  setDefaultLevel,
  onNext,
  onBack,
  tx,
}: Step2SettingsProps) {
  const [customSectionInput, setCustomSectionInput] = React.useState("");

  const handleAddCustomSection = () => {
    if (!customSectionInput.trim() || !setDynamicSections) return;
    const newKey = `custom_${Date.now()}`;
    const newItem: DynamicSectionItem = {
      key: newKey,
      title: customSectionInput.trim(),
      description: "Section kustom pengguna",
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
      <div className="text-left">
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

        {/* Column 2: Template Kop & Theme Selector */}
        <div className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm space-y-4 premium-card-hover transition-colors">
          <h3 className="font-extrabold text-stone-850 text-sm border-b border-stone-100 pb-2 flex items-center justify-between">
            <span>{tx("Template & Theme", "Template & Theme")}</span>
            <span className="text-[10px] bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full font-bold border border-amber-200">
              Custom Kop
            </span>
          </h3>

          <div className="space-y-3">
            <div>
              <label className="block text-[11px] font-bold text-stone-600 uppercase tracking-wider mb-1">
                Kop Header Title
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
                Kop Subtitle
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
                Theme Color
              </label>
              <div className="grid grid-cols-4 gap-2">
                {[
                  {
                    id: "green",
                    name: "Corporate Green",
                    color: "bg-[#004D25]",
                  },
                  { id: "navy", name: "Slate Navy", color: "bg-[#0F172A]" },
                  { id: "dark", name: "Cyber Dark", color: "bg-[#111827]" },
                  { id: "gold", name: "Amber Gold", color: "bg-[#78350F]" },
                ].map((tItem) => (
                  <button
                    type="button"
                    key={tItem.id}
                    onClick={() => setThemeColor && setThemeColor(tItem.id)}
                    className={`flex flex-col items-center justify-center p-2 rounded-xl border transition-all cursor-pointer ${
                      themeColor === tItem.id
                        ? "border-stone-900 bg-stone-50 ring-2 ring-stone-900/10 shadow-sm"
                        : "border-stone-200 bg-white hover:bg-stone-50"
                    }`}
                  >
                    <span
                      className={`w-4 h-4 rounded-full ${tItem.color} shadow-sm mb-1`}
                    ></span>
                    <span className="text-[9px] font-extrabold text-stone-700 truncate w-full text-center">
                      {tItem.name.split(" ")[0]}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Column 3: AI-Driven Include Sections */}
        <div className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm space-y-4 premium-card-hover transition-colors">
          <h3 className="font-extrabold text-stone-850 text-sm border-b border-stone-100 pb-2 flex items-center justify-between">
            <span>{tx("Include Sections", "Include Sections")}</span>
            <span className="text-[10px] bg-emerald-50 text-emerald-700 px-2 py-0.5 rounded-full font-bold border border-emerald-200 flex items-center gap-1">
              <span>✨</span> AI Suggested
            </span>
          </h3>

          <div className="space-y-2 max-h-[160px] overflow-y-auto pr-1">
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

          {/* Add Custom Section Button */}
          <div className="flex items-center gap-1.5 border-t border-stone-100 pt-2.5">
            <input
              type="text"
              value={customSectionInput}
              onChange={(e) => setCustomSectionInput(e.target.value)}
              placeholder="Custom Section Title..."
              className="flex-1 bg-stone-50 border border-stone-200 rounded-lg px-2.5 py-1.5 text-xs text-stone-800 focus:outline-none focus:border-petro-green"
            />
            <button
              type="button"
              onClick={handleAddCustomSection}
              className="px-3 py-1.5 bg-stone-900 hover:bg-stone-800 text-white text-xs font-bold rounded-lg transition-all cursor-pointer shrink-0"
            >
              + Add
            </button>
          </div>
        </div>
      </div>

      {/* Bottom Wide Card: Export Formats & Preferences */}
      <div className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm text-left premium-card-hover transition-colors">
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
                PDF Document
              </span>
              <span className="text-[10px] text-stone-400 font-semibold">
                Laporan cetak resmi format A4 dengan Kop Petrokimia & Lampiran
                Log
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
                PowerPoint Presentation (PPTX)
              </span>
              <span className="text-[10px] text-stone-400 font-semibold">
                Slide presentasi eksekutif Widescreen 16:9 dengan grafik & teks
                visual
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
          className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-petro-green hover:bg-petro-green-hover text-white font-bold text-sm shadow transition-all duration-200 group cursor-pointer"
        >
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
        </button>
      </div>
    </ScrollReveal>
  );
}
