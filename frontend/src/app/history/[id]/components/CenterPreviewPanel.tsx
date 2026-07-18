import { t } from "@/utils/i18n";

interface ReportDetails {
  id: number;
  title: string;
  data_type: string;
  status: string;
  input_file_name: string;
  period_start: string;
  period_end: string;
  template_type: string;
  output_format: string;
  language: string;
  ai_confidence: number;
  created_by_name: string;
  threat_count_critical: number;
  threat_count_high: number;
  threat_count_medium: number;
  threat_count_low: number;
  total_records_parsed: number;
  created_at: string;
  ai_summary: Record<string, any>;
}

interface CenterPreviewPanelProps {
  activeTab: "preview" | "edit" | "charts";
  setActiveTab: (tab: "preview" | "edit" | "charts") => void;
  activePage: string;
  report: ReportDetails;
  getPageTitle: (page: string) => string;
  getPageText: (page: string) => string;
  handleTextChange: (newVal: string) => void;
  handleSaveEdits: () => void;
  isSaving: boolean;
  saveSuccess: boolean;
}

export default function CenterPreviewPanel({
  activeTab,
  setActiveTab,
  activePage,
  report,
  getPageTitle,
  getPageText,
  handleTextChange,
  handleSaveEdits,
  isSaving,
  saveSuccess,
}: CenterPreviewPanelProps) {
  return (
    <div className="lg:col-span-6 bg-white border border-stone-200/85 rounded-2xl shadow-sm flex flex-col h-[520px] overflow-hidden">
      
      {/* Tab Navigation header */}
      <div className="bg-white border-b border-stone-100 px-5 flex items-center justify-between">
        <div className="flex gap-4">
          {["preview", "edit", "charts"].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab as any)}
              className={`py-3.5 font-bold text-xs capitalize relative transition-colors ${
                activeTab === tab
                  ? "text-stone-900 border-b-2 border-petro-green font-black"
                  : "text-stone-400 hover:text-stone-700"
              }`}
            >
              {tab === "edit" ? t("Edit Text") : t(tab)}
            </button>
          ))}
        </div>
        
        {/* 100% Zoom badge */}
        <div className="flex items-center gap-1.5">
          <span className="px-2 py-1 bg-white border border-stone-200 text-stone-500 font-extrabold text-[10px] rounded-lg shadow-sm flex items-center gap-1 cursor-pointer">
            100%
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor" className="w-2.5 h-2.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
            </svg>
          </span>
          <span className="p-1 bg-white border border-stone-200 text-stone-500 rounded-lg shadow-sm cursor-pointer hover:bg-stone-50">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.2} stroke="currentColor" className="w-3.5 h-3.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75v4.5m0-4.5h-4.5m4.5 0L15 9m5.25 11.25v-4.5m0 4.5h-4.5m4.5 0-5.25-5.25" />
            </svg>
          </span>
        </div>
      </div>

      {/* Tab Contents */}
      <div className="flex-1 overflow-y-auto p-6 bg-[#EFECE5]/60">
        
        {/* PREVIEW TAB */}
        {activeTab === "preview" && (
          <div className="max-w-[420px] mx-auto bg-white border border-stone-200/80 rounded-lg shadow p-6 min-h-[580px] text-left relative flex flex-col justify-between">
            <div>
              {/* Document Kop */}
              <div className="flex justify-between items-start border-b border-stone-150 pb-4">
                <img src="/soc-logo.png" alt="Petrokimia Logo" className="w-20 h-auto object-contain" />
                <span className="text-[10px] font-black text-amber-500 uppercase tracking-widest mt-1">
                  {t("SOC Executive Summary")}
                </span>
              </div>
              
              {/* Document Title */}
              <h4 className="text-lg font-black text-stone-855 mt-6 leading-tight">
                {t("Monthly Security Operations Summary")}
              </h4>
              <p className="text-[10px] text-amber-605 font-extrabold mt-1">July 2026</p>
              
              {/* Section heading & Narrative content */}
              <div className="mt-6">
                <h5 className="text-xs font-black text-stone-855 border-b border-stone-100 pb-1.5 capitalize">
                  {t(getPageTitle(activePage))}
                </h5>
                <p className="text-[10px] text-stone-600 mt-3 font-semibold leading-relaxed whitespace-pre-wrap">
                  {getPageText(activePage)}
                </p>
              </div>

              {/* Key Highlights box on page 01 */}
              {activePage === "01" && (
                <div className="mt-6 bg-stone-50/80 border border-stone-200/60 rounded-xl p-4">
                  <h6 className="text-[10px] font-black text-stone-800 uppercase tracking-wide">{t("Key Highlights")}</h6>
                  <div className="grid grid-cols-2 gap-3 mt-3">
                    <div className="bg-white border border-stone-150 p-2.5 rounded-lg">
                      <span className="text-[8px] font-bold text-stone-400 uppercase flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse"></span>
                        {t("Total Reports")}
                      </span>
                      <div className="text-base font-black text-stone-850 mt-1">{report.total_records_parsed ?? 26}</div>
                      <span className="text-[8px] text-emerald-600 font-bold mt-1 block">18.2% {t("vs last month")}</span>
                    </div>
                    <div className="bg-white border border-stone-150 p-2.5 rounded-lg">
                      <span className="text-[8px] font-bold text-stone-400 uppercase flex items-center gap-1">
                        <span className="w-1.5 h-1.5 rounded-full bg-red-600"></span>
                        {t("Critical Incidents")}
                      </span>
                      <div className="text-base font-black text-stone-850 mt-1">{report.threat_count_critical ?? 18}</div>
                      <span className="text-[8px] text-red-650/80 font-bold mt-1 block">12.0% {t("vs last month")}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Footer Kop */}
            <div className="flex justify-between items-center text-[8px] font-bold text-stone-400 border-t border-stone-100 pt-4 mt-8">
              <span>{t("AI Security Reports")}</span>
              <span>{t("Page")} {activePage}</span>
            </div>
          </div>
        )}

        {/* EDIT TEXT TAB */}
        {activeTab === "edit" && (
          <div className="w-full h-full flex flex-col justify-between text-left space-y-4">
            <div className="flex-1 min-h-[300px] flex flex-col">
              <label className="text-[11px] font-black text-stone-700 uppercase tracking-wider mb-2">
                {t("Modify Section Narrative AI")} ({t(getPageTitle(activePage))})
              </label>
              <textarea
                value={getPageText(activePage)}
                onChange={(e) => handleTextChange(e.target.value)}
                className="w-full flex-1 p-4 border border-stone-200 rounded-2xl focus:outline-none focus:border-petro-green text-xs font-semibold leading-relaxed text-stone-800 shadow-sm bg-white"
                placeholder={t("Write dynamic logs narration...")}
              />
            </div>
            
            {/* Action buttons save edits */}
            <div className="flex items-center gap-4">
              <button
                onClick={handleSaveEdits}
                disabled={isSaving}
                className="px-5 py-2.5 rounded-xl bg-petro-green hover:bg-petro-green-hover text-white font-extrabold text-xs shadow-md transition-colors flex items-center gap-2 disabled:opacity-60 cursor-pointer"
              >
                {isSaving ? (
                  <>
                    <svg className="animate-spin h-3.5 w-3.5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    {t("Saving...")}
                  </>
                ) : (
                  t("Save Changes")
                )}
              </button>

              {saveSuccess && (
                <span className="text-xs text-emerald-600 font-extrabold flex items-center gap-1 animate-fade-in">
                  ✓ {t("Saved Successfully!")}
                </span>
              )}
            </div>
          </div>
        )}

        {/* CHARTS TAB */}
        {activeTab === "charts" && (
          <div className="w-full max-w-[450px] mx-auto bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm text-left">
            <h5 className="font-extrabold text-stone-855 text-xs border-b border-stone-100 pb-3 uppercase tracking-wide">
              {t("Severity Threat Incidents Distribution")}
            </h5>
            
            {/* Beautiful SVG charts representation */}
            <div className="mt-6 flex flex-col items-center">
              <div className="w-full h-48 flex items-end justify-around border-b border-l border-stone-200/80 pb-2 pl-2">
                {/* Critical bar */}
                <div className="flex flex-col items-center w-12 group">
                  <span className="text-[10px] font-black text-red-600 mb-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    {report.threat_count_critical ?? 18}
                  </span>
                  <div
                    style={{ height: `${Math.min((report.threat_count_critical ?? 18) * 3, 130)}px` }}
                    className="w-7 bg-red-500 rounded-t-md hover:bg-red-600 transition-all cursor-pointer shadow-sm"
                  ></div>
                  <span className="text-[9px] font-bold text-stone-500 mt-2">{t("Critical")}</span>
                </div>

                {/* High bar */}
                <div className="flex flex-col items-center w-12 group">
                  <span className="text-[10px] font-black text-amber-600 mb-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    {report.threat_count_high ?? 56}
                  </span>
                  <div
                    style={{ height: `${Math.min((report.threat_count_high ?? 56) * 1.5, 130)}px` }}
                    className="w-7 bg-amber-500 rounded-t-md hover:bg-amber-600 transition-all cursor-pointer shadow-sm"
                  ></div>
                  <span className="text-[9px] font-bold text-stone-500 mt-2">{t("High")}</span>
                </div>

                {/* Medium bar */}
                <div className="flex flex-col items-center w-12 group">
                  <span className="text-[10px] font-black text-yellow-600 mb-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    {report.threat_count_medium ?? 102}
                  </span>
                  <div
                    style={{ height: `${Math.min((report.threat_count_medium ?? 102) * 0.8, 130)}px` }}
                    className="w-7 bg-yellow-400 rounded-t-md hover:bg-yellow-500 transition-all cursor-pointer shadow-sm"
                  ></div>
                  <span className="text-[9px] font-bold text-stone-500 mt-2">{t("Medium")}</span>
                </div>

                {/* Low bar */}
                <div className="flex flex-col items-center w-12 group">
                  <span className="text-[10px] font-black text-emerald-600 mb-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    {report.threat_count_low ?? 210}
                  </span>
                  <div
                    style={{ height: `${Math.min((report.threat_count_low ?? 210) * 0.4, 130)}px` }}
                    className="w-7 bg-emerald-500 rounded-t-md hover:bg-emerald-600 transition-all cursor-pointer shadow-sm"
                  ></div>
                  <span className="text-[9px] font-bold text-stone-500 mt-2">{t("Low")}</span>
                </div>
              </div>
            </div>

            {/* Chart legends */}
            <div className="grid grid-cols-2 gap-4 mt-6 text-[10px] font-bold text-stone-600 border-t border-stone-100 pt-4">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500 shrink-0"></span>
                <span>{t("Critical")}: {report.threat_count_critical ?? 18}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500 shrink-0"></span>
                <span>{t("High")}: {report.threat_count_high ?? 56}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-yellow-400 shrink-0"></span>
                <span>{t("Medium")}: {report.threat_count_medium ?? 102}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-50 shrink-0"></span>
                <span>{t("Low")}: {report.threat_count_low ?? 210}</span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
