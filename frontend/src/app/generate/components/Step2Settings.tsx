import React from "react";
import ScrollReveal from "@/components/ScrollReveal";

interface Step2SettingsProps {
  periodStart: string;
  setPeriodStart: (val: string) => void;
  periodEnd: string;
  setPeriodEnd: (val: string) => void;
  language: string;
  setLanguage: (val: string) => void;
  exportFormats: Record<string, boolean>;
  setExportFormats: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
  sections: Record<string, boolean>;
  setSections: React.Dispatch<React.SetStateAction<Record<string, boolean>>>;
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
  language,
  setLanguage,
  exportFormats,
  setExportFormats,
  sections,
  setSections,
  tone,
  setTone,
  defaultLevel,
  setDefaultLevel,
  onNext,
  onBack,
  tx,
}: Step2SettingsProps) {
  return (
    <ScrollReveal animation="fadeInUp" className="space-y-6">
      <div className="text-left">
        <h2 className="text-2xl font-extrabold text-stone-900">{tx("Report Settings", "Report Settings")}</h2>
        <p className="text-sm text-stone-500 font-semibold mt-1">
          {tx("Configure the settings for your SOC report", "Configure the settings for your SOC report")}
        </p>
      </div>

      {/* 3-Column Top Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 text-left">
        {/* Column 1: Report Metadata & Period */}
        <div className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm space-y-4 premium-card-hover transition-colors">
          <h3 className="font-extrabold text-stone-855 text-sm border-b border-stone-100 pb-2">{tx("Report", "Report")}</h3>

          <div className="space-y-3">
            <div>
              <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider mb-1.5">{tx("Report Period", "Report Period")}</label>
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="date"
                  value={periodStart}
                  onChange={(e) => setPeriodStart(e.target.value)}
                  className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
                />
                <input
                  type="date"
                  value={periodEnd}
                  onChange={(e) => setPeriodEnd(e.target.value)}
                  className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider mb-1.5">{tx("Language", "Language")}</label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
              >
                <option value="English">{tx("English", "English")}</option>
                <option value="Indonesian">{tx("Indonesian", "Indonesian")}</option>
              </select>
            </div>
          </div>
        </div>

        {/* Column 2: Output Options */}
        <div className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm space-y-4 premium-card-hover transition-colors">
          <h3 className="font-extrabold text-stone-850 text-sm border-b border-stone-100 pb-2">{tx("Output", "Output")}</h3>

          <div>
            <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider mb-3">{tx("Export Format", "Export Format")}</label>
            <div className="space-y-3">
              <label className="flex items-center gap-3 p-3 bg-stone-50 border border-stone-250 rounded-xl cursor-pointer hover:bg-stone-100/50 transition-colors">
                <input
                  type="checkbox"
                  checked={exportFormats.pdf}
                  onChange={(e) => setExportFormats((prev) => ({ ...prev, pdf: e.target.checked }))}
                  className="w-4 h-4 rounded text-petro-green focus:ring-petro-green border-stone-300"
                />
                <div className="flex flex-col text-left">
                  <span className="text-xs font-bold text-stone-800">PDF</span>
                  <span className="text-[9px] text-stone-400 font-semibold">{tx("Standard printable document", "Standard printable document")}</span>
                </div>
              </label>

              <label className="flex items-center gap-3 p-3 bg-stone-50 border border-stone-250 rounded-xl cursor-pointer hover:bg-stone-100/50 transition-colors">
                <input
                  type="checkbox"
                  checked={exportFormats.pptx}
                  onChange={(e) => setExportFormats((prev) => ({ ...prev, pptx: e.target.checked }))}
                  className="w-4 h-4 rounded text-petro-green focus:ring-petro-green border-stone-300"
                />
                <div className="flex flex-col text-left">
                  <span className="text-xs font-bold text-stone-800">PowerPoint (PPTX)</span>
                  <span className="text-[9px] text-stone-400 font-semibold">{tx("Presentation slides layout", "Presentation slides layout")}</span>
                </div>
              </label>
            </div>
          </div>
        </div>

        {/* Column 3: Include Sections Checkboxes */}
        <div className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm space-y-4 premium-card-hover transition-colors">
          <h3 className="font-extrabold text-stone-850 text-sm border-b border-stone-100 pb-2">{tx("Include Sections", "Include Sections")}</h3>

          <div className="space-y-2 max-h-[180px] overflow-y-auto pr-1">
            {[
              { key: "executiveSummary", label: "Executive Summary" },
              { key: "threatOverview", label: "Threat Overview" },
              { key: "attackSummary", label: "Attack Summary" },
              { key: "vaptSummary", label: "VAPT Summary" },
              { key: "bandwidthMonitoring", label: "Bandwidth Monitoring" },
              { key: "threatHunting", label: "Threat Hunting" },
              { key: "conclusionRecommendation", label: "Conclusion & Recommendation" },
            ].map((sec) => (
              <label key={sec.key} className="flex items-center gap-2.5 cursor-pointer py-0.5 select-none">
                <input
                  type="checkbox"
                  checked={sections[sec.key]}
                  onChange={(e) => setSections((prev) => ({ ...prev, [sec.key]: e.target.checked }))}
                  className="w-4 h-4 rounded text-petro-green focus:ring-petro-green border-stone-300"
                />
                <span className="text-xs font-semibold text-stone-700">{tx(sec.label, sec.label)}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom Wide Card: Additional Preferences */}
      <div className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm text-left premium-card-hover transition-colors">
        <h3 className="font-extrabold text-stone-855 text-sm border-b border-stone-100 pb-2 mb-4">{tx("Additional Preferences", "Additional Preferences")}</h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider mb-1.5">{tx("Tone", "Tone")}</label>
            <select
              value={tone}
              onChange={(e) => setTone(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
            >
              <option value="Professional">{tx("Professional", "Professional")}</option>
              <option value="Technical">{tx("Technical", "Technical")}</option>
              <option value="Executive">{tx("Executive", "Executive")}</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider mb-1.5">{tx("Default Level", "Default Level")}</label>
            <select
              value={defaultLevel}
              onChange={(e) => setDefaultLevel(e.target.value)}
              className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
            >
              <option value="Standard">{tx("Standard", "Standard")}</option>
              <option value="Detailed">{tx("Detailed", "Detailed")}</option>
              <option value="Summary Only">{tx("Summary Only", "Summary Only")}</option>
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
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
          </svg>
          {tx("Back", "Back")}
        </button>

        <button
          onClick={onNext}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-petro-green hover:bg-petro-green-hover text-white font-bold text-sm shadow transition-all duration-200 group cursor-pointer"
        >
          {tx("Next Export", "Next Export")}
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5 transition-transform group-hover:translate-x-1">
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
          </svg>
        </button>
      </div>
    </ScrollReveal>
  );
}
