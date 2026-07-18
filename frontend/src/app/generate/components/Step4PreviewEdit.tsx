import React from "react";
import ScrollReveal from "@/components/ScrollReveal";

interface Step4PreviewEditProps {
  activePage: string;
  setActivePage: (page: string) => void;
  activeTab: "preview" | "edit" | "charts";
  setActiveTab: (tab: "preview" | "edit" | "charts") => void;
  isSaving: boolean;
  saveSuccess: boolean;
  language: string;
  periodStart: string;
  periodEnd: string;
  reportDetails: any;
  editedSummary: any;
  getPageText: (page: string) => string;
  getPageTitle: (page: string) => string;
  handleTextChange: (newVal: string) => void;
  handleSaveEdits: () => void;
  onBack: () => void;
  onNext: () => void;
  tx: (key: string, fallback: string) => string;
}

export default function Step4PreviewEdit({
  activePage,
  setActivePage,
  activeTab,
  setActiveTab,
  isSaving,
  saveSuccess,
  language,
  periodStart,
  periodEnd,
  reportDetails,
  editedSummary,
  getPageText,
  getPageTitle,
  handleTextChange,
  handleSaveEdits,
  onBack,
  onNext,
  tx,
}: Step4PreviewEditProps) {
  return (
    <ScrollReveal animation="fadeInUp" className="space-y-6">
      <div className="text-left">
        <h2 className="text-2xl font-extrabold text-stone-900">{tx("Preview & Edit", "Preview & Edit")}</h2>
        <p className="text-sm text-stone-500 font-semibold mt-1">
          {tx("Review AI generated content and make any necessary edits", "Review AI generated content and make any necessary edits")}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 text-left items-start mt-6">
        {/* Left Panel: Pages List */}
        <div className="lg:col-span-3 bg-white rounded-2xl border border-stone-200/80 p-5 shadow-sm space-y-4 premium-card-hover transition-colors">
          <h3 className="font-extrabold text-stone-855 text-sm border-b border-stone-100 pb-2">{tx("Pages", "Pages")}</h3>

          <div className="space-y-1.5">
            {[
              { id: "01", label: "01 Executive Summary" },
              { id: "02", label: "02 Threat Overview" },
              { id: "03", label: "03 Attack Summary" },
              { id: "04", label: "04 VAPT Summary" },
              { id: "05", label: "05 Bandwidth Summary" },
              { id: "06", label: "06 Threat Hunting" },
              { id: "07", label: "07 Conclusion & Rec." },
            ].map((pg) => (
              <button
                key={pg.id}
                onClick={() => setActivePage(pg.id)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                  activePage === pg.id
                    ? "bg-petro-green/10 text-petro-green border border-petro-green/20"
                    : "bg-transparent text-stone-600 hover:bg-stone-50 border border-transparent"
                }`}
              >
                <span className="truncate">{tx(pg.label.substring(3), pg.label.substring(3))}</span>
              </button>
            ))}
          </div>

          {/* Pagination Buttons */}
          <div className="flex justify-between items-center border-t border-stone-100 pt-3 text-[10px] font-bold text-stone-400">
            <button
              disabled={activePage === "01"}
              onClick={() => {
                const prev = String(Number(activePage) - 1).padStart(2, "0");
                setActivePage(prev);
              }}
              className="p-1 hover:text-stone-750 disabled:opacity-30 disabled:pointer-events-none transition-colors cursor-pointer"
            >
              &lt; {tx("Prev", "Prev")}
            </button>
            <span>
              {tx("Page", "Page")} {activePage} {tx("of", "of")} 07
            </span>
            <button
              disabled={activePage === "07"}
              onClick={() => {
                const next = String(Number(activePage) + 1).padStart(2, "0");
                setActivePage(next);
              }}
              className="p-1 hover:text-stone-750 disabled:opacity-30 disabled:pointer-events-none transition-colors cursor-pointer"
            >
              {tx("Next", "Next")} &gt;
            </button>
          </div>
        </div>

        {/* Center Panel: Preview & Edit Workspace */}
        <div className="lg:col-span-6 bg-white rounded-2xl border border-stone-200/80 p-6 shadow-sm space-y-6 premium-card-hover transition-colors">
          {/* Tab Selector */}
          <div className="flex justify-between items-center border-b border-stone-150 pb-2">
            <div className="flex gap-2">
              {(["preview", "edit", "charts"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all capitalize cursor-pointer ${
                    activeTab === tab ? "bg-stone-900 text-white" : "bg-stone-50 text-stone-500 hover:bg-stone-100"
                  }`}
                >
                  {tab === "edit" ? tx("Edit Text", "Edit Text") : tx(tab, tab)}
                </button>
              ))}
            </div>

            {/* Live Save Status */}
            {activeTab === "edit" && (
              <button
                onClick={handleSaveEdits}
                disabled={isSaving}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-petro-green hover:bg-petro-green-hover text-white text-[11px] font-bold rounded-lg shadow-sm transition-all cursor-pointer"
              >
                {isSaving ? (
                  <div className="w-3 h-3 border-2 border-white/35 border-t-white rounded-full animate-spin"></div>
                ) : saveSuccess ? (
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                    <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                  </svg>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                    <path d="M10.75 4.75a.75.75 0 0 0-1.5 0v4.5h-4.5a.75.75 0 0 0 0 1.5h4.5v4.5a.75.75 0 0 0 1.5 0v-4.5h4.5a.75.75 0 0 0 0-1.5h-4.5v-4.5Z" />
                  </svg>
                )}
                {isSaving ? tx("Saving...", "Saving...") : saveSuccess ? tx("Saved!", "Saved!") : tx("Save Changes", "Save Changes")}
              </button>
            )}
          </div>

          {/* Tab Contents */}
          <div className="min-h-[350px]">
            {activeTab === "preview" && (
              <div className="border border-stone-200 rounded-xl p-8 shadow-inner bg-white max-w-lg mx-auto flex flex-col justify-between min-h-[460px]">
                {/* Letter Header */}
                <div>
                  <div className="flex items-center justify-between border-b-2 border-stone-300 pb-3 mb-6">
                    <div className="flex items-center gap-2">
                      <div className="w-7 h-7 rounded-full bg-petro-green flex items-center justify-center text-white font-black text-[10px]">
                        PKG
                      </div>
                      <div className="text-left leading-none">
                        <span className="text-[10px] font-black text-stone-855 tracking-wider">PETROKIMIA GRESIK</span>
                        <br />
                        <span className="text-[6px] font-bold text-stone-400 uppercase tracking-widest">Solusi Agroindustri</span>
                      </div>
                    </div>
                    <span className="text-[8px] font-bold text-stone-450 tracking-wider uppercase">{tx("SOC Executive Summary", "SOC Executive Summary")}</span>
                  </div>

                  {/* Letter Content */}
                  <div className="space-y-4 text-left">
                    <div>
                      <h4 className="text-[9px] text-petro-green font-black uppercase tracking-widest">{tx(getPageTitle(activePage), getPageTitle(activePage))}</h4>
                      <h2 className="text-sm font-black text-stone-855 mt-1">{tx("Monthly Security Operations Summary", "Monthly Security Operations Summary")}</h2>
                      <p className="text-[8px] text-stone-400 font-bold mt-0.5">
                        {tx("Period:", "Period:")} {periodStart} {tx("to", "to")} {periodEnd}
                      </p>
                    </div>

                    <p className="text-xs text-stone-600 font-semibold leading-relaxed whitespace-pre-wrap">{getPageText(activePage)}</p>

                    {/* Highlights on Step 1 */}
                    {activePage === "01" && (
                      <div className="p-3 bg-stone-50 border border-stone-200 rounded-xl text-left mt-5 space-y-1">
                        <h5 className="text-[9px] font-black text-stone-755 uppercase tracking-wider">{tx("Key Highlights", "Key Highlights")}</h5>
                        <div className="grid grid-cols-2 gap-4 pt-1">
                          <div>
                            <span className="text-[8px] text-stone-400 font-semibold uppercase">{tx("Total Alerts", "Total Alerts")}</span>
                            <p className="text-sm font-black text-stone-800">
                              {reportDetails?.total_records_parsed ?? 177} <span className="text-[9px] text-emerald-600 font-bold">+18.2%</span>
                            </p>
                          </div>
                          <div>
                            <span className="text-[8px] text-stone-400 font-semibold uppercase">{tx("Critical Threats", "Critical Threats")}</span>
                            <p className="text-sm font-black text-stone-800">
                              {reportDetails?.threat_count_critical ?? 18} <span className="text-[9px] text-red-650 font-bold">+12.0%</span>
                            </p>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Page Footer */}
                <div className="flex justify-between items-center border-t border-stone-200 pt-3 mt-8 text-[8px] text-stone-400">
                  <span className="font-bold uppercase tracking-wider">{tx("AI Security Reports", "AI Security Reports")}</span>
                  <span className="font-black text-stone-700">{activePage}</span>
                </div>
              </div>
            )}

            {activeTab === "edit" && (
              <div className="space-y-4">
                <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider">{tx("Edit Content Text Area", "Edit Content Text Area")}</label>
                <textarea
                  value={getPageText(activePage)}
                  onChange={(e) => handleTextChange(e.target.value)}
                  className="w-full h-80 bg-stone-50 border border-stone-250 rounded-xl p-4 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all leading-relaxed"
                  placeholder={tx("Type report page narrative contents here...", "Type report page narrative contents here...")}
                />
              </div>
            )}

            {activeTab === "charts" && (
              <div className="border border-stone-200 rounded-xl p-6 bg-stone-50/50 flex flex-col justify-center items-center min-h-[350px]">
                <h4 className="text-xs font-black text-stone-755 uppercase tracking-wider mb-6">{tx("Threats Severity Distribution Chart", "Threats Severity Distribution Chart")}</h4>

                <svg className="w-full max-w-sm h-64" viewBox="0 0 500 240">
                  <line x1="50" y1="30" x2="450" y2="30" stroke="#e5e7eb" strokeWidth="1" strokeDasharray="3 3" />
                  <line x1="50" y1="80" x2="450" y2="80" stroke="#e5e7eb" strokeWidth="1" strokeDasharray="3 3" />
                  <line x1="50" y1="130" x2="450" y2="130" stroke="#e5e7eb" strokeWidth="1" strokeDasharray="3 3" />
                  <line x1="50" y1="180" x2="450" y2="180" stroke="#d1d5db" strokeWidth="1.5" />

                  <text x="35" y="35" className="text-[10px] font-bold fill-stone-400" textAnchor="end">
                    150
                  </text>
                  <text x="35" y="85" className="text-[10px] font-bold fill-stone-400" textAnchor="end">
                    100
                  </text>
                  <text x="35" y="135" className="text-[10px] font-bold fill-stone-400" textAnchor="end">
                    50
                  </text>
                  <text x="35" y="185" className="text-[10px] font-bold fill-stone-400" textAnchor="end">
                    0
                  </text>

                  {/* Critical */}
                  <rect x="80" y={180 - Math.min(150, (reportDetails?.threat_count_critical ?? 18) * 1.2)} width="40" height={Math.min(150, (reportDetails?.threat_count_critical ?? 18) * 1.2)} rx="4" fill="#dc2626" />
                  <text x="100" y={170 - Math.min(150, (reportDetails?.threat_count_critical ?? 18) * 1.2)} className="text-[10px] font-black fill-red-600" textAnchor="middle">
                    {reportDetails?.threat_count_critical ?? 18}
                  </text>
                  <text x="100" y="205" className="text-[9px] font-bold fill-stone-500" textAnchor="middle">
                    {tx("Critical", "Critical")}
                  </text>

                  {/* High */}
                  <rect x="180" y={180 - Math.min(150, (reportDetails?.threat_count_high ?? 56) * 1.2)} width="40" height={Math.min(150, (reportDetails?.threat_count_high ?? 56) * 1.2)} rx="4" fill="#ea580c" />
                  <text x="200" y={170 - Math.min(150, (reportDetails?.threat_count_high ?? 56) * 1.2)} className="text-[10px] font-black fill-amber-600" textAnchor="middle">
                    {reportDetails?.threat_count_high ?? 56}
                  </text>
                  <text x="200" y="205" className="text-[9px] font-bold fill-stone-500" textAnchor="middle">
                    {tx("High", "High")}
                  </text>

                  {/* Medium */}
                  <rect x="280" y={180 - Math.min(150, (reportDetails?.threat_count_medium ?? 103) * 1.2)} width="40" height={Math.min(150, (reportDetails?.threat_count_medium ?? 103) * 1.2)} rx="4" fill="#eab308" />
                  <text x="300" y={170 - Math.min(150, (reportDetails?.threat_count_medium ?? 103) * 1.2)} className="text-[10px] font-black fill-yellow-600" textAnchor="middle">
                    {reportDetails?.threat_count_medium ?? 103}
                  </text>
                  <text x="300" y="205" className="text-[9px] font-bold fill-stone-500" textAnchor="middle">
                    {tx("Medium", "Medium")}
                  </text>

                  {/* Low */}
                  <rect x="380" y={180 - Math.min(150, (reportDetails?.threat_count_low ?? 20) * 1.2)} width="40" height={Math.min(150, (reportDetails?.threat_count_low ?? 20) * 1.2)} rx="4" fill="#3b82f6" />
                  <text x="400" y={170 - Math.min(150, (reportDetails?.threat_count_low ?? 20) * 1.2)} className="text-[10px] font-black fill-blue-600" textAnchor="middle">
                    {reportDetails?.threat_count_low ?? 20}
                  </text>
                  <text x="400" y="205" className="text-[9px] font-bold fill-stone-500" textAnchor="middle">
                    {tx("Low", "Low")}
                  </text>
                </svg>
              </div>
            )}
          </div>
        </div>

        {/* Right Panel: Properties */}
        <div className="lg:col-span-3 bg-white rounded-2xl border border-stone-200/80 p-5 shadow-sm space-y-4 premium-card-hover transition-colors">
          <h3 className="font-extrabold text-stone-855 text-sm border-b border-stone-100 pb-2">{tx("Properties", "Properties")}</h3>

          <div>
            <label className="block text-[10px] font-bold text-stone-500 uppercase tracking-wider mb-1.5">{tx("Language", "Language")}</label>
            <select disabled value={language} className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 text-xs focus:outline-none text-stone-500">
              <option value="English">{tx("English", "English")}</option>
              <option value="Indonesian">{tx("Indonesian", "Indonesian")}</option>
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
