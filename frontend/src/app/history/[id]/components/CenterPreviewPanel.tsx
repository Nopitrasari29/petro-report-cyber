import { useState, useEffect } from "react";
import { t } from "@/utils/i18n";
import ReportChartPanel from "@/app/generate/components/ReportChartPanel";

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
  const [previewFormat, setPreviewFormat] = useState<"pdf" | "pptx">("pdf");
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);
  const tx = (key: string, fallback: string) => (mounted ? t(key) : fallback);

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
              {tab === "edit" ? tx("Edit Text", "Edit Text") : tx(tab, tab)}
            </button>
          ))}
        </div>

        {/* 100% Zoom badge */}
        <div className="flex items-center gap-1.5">
          <span className="px-2 py-1 bg-white border border-stone-200 text-stone-500 font-extrabold text-[10px] rounded-lg shadow-sm flex items-center gap-1 cursor-pointer">
            100%
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={3}
              stroke="currentColor"
              className="w-2.5 h-2.5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="m19.5 8.25-7.5 7.5-7.5-7.5"
              />
            </svg>
          </span>
          <span className="p-1 bg-white border border-stone-200 text-stone-500 rounded-lg shadow-sm cursor-pointer hover:bg-stone-50">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2.2}
              stroke="currentColor"
              className="w-3.5 h-3.5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75v4.5m0-4.5h-4.5m4.5 0L15 9m5.25 11.25v-4.5m0 4.5h-4.5m4.5 0-5.25-5.25"
              />
            </svg>
          </span>
        </div>
      </div>

      {/* Tab Contents */}
      <div className="flex-1 overflow-y-auto p-6 bg-[#EFECE5]/60">
        {/* PREVIEW TAB */}
        {activeTab === "preview" && (
          <div className="space-y-4">
            {/* Format Preview Toggle (PDF / PPTX) */}
            <div className="flex justify-center">
              <div className="inline-flex p-1 bg-white rounded-xl border border-stone-200/80 shadow-sm gap-1">
                <button
                  onClick={() => setPreviewFormat("pdf")}
                  className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-[11px] font-extrabold transition-all cursor-pointer ${
                    previewFormat === "pdf"
                      ? "bg-petro-green text-white shadow-sm"
                      : "text-stone-500 hover:text-stone-800"
                  }`}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-red-400"></span>
                  {tx("PDF Document View", "PDF Document View")}
                </button>
                <button
                  onClick={() => setPreviewFormat("pptx")}
                  className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-[11px] font-extrabold transition-all cursor-pointer ${
                    previewFormat === "pptx"
                      ? "bg-petro-green text-white shadow-sm"
                      : "text-stone-500 hover:text-stone-800"
                  }`}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
                  {tx("PPTX Slide View", "PPTX Slide View")}
                </button>
              </div>
            </div>

            {/* MODE 1: PDF DOCUMENT VIEW */}
            {previewFormat === "pdf" && (
              <div className="max-w-[420px] mx-auto bg-white border border-stone-200/80 rounded-lg shadow p-6 min-h-[580px] text-left relative flex flex-col justify-between animate-fadeIn">
                <div>
                  {/* Document Kop */}
                  <div className="flex justify-between items-center border-b border-stone-150 pb-4">
                    <img
                      src="/LOGO_PETRO_DANANTARA.png"
                      alt="Petrokimia Danantara Logo"
                      className="h-9 w-auto object-contain"
                    />
                    <span className="text-[10px] font-black text-amber-600 uppercase tracking-widest">
                      {tx("SOC Executive Summary", "SOC Executive Summary")}
                    </span>
                  </div>

                  {/* Document Title */}
                  <h4 className="text-base font-black text-stone-855 mt-5 leading-tight">
                    {tx(
                      "Monthly Security Operations Summary",
                      "Monthly Security Operations Summary",
                    )}
                  </h4>
                  <p className="text-[10px] text-amber-605 font-extrabold mt-1">
                    {report.period_start || "July 2026"} to {report.period_end || "July 2026"}
                  </p>

                  {/* Section heading & Narrative content */}
                  <div className="mt-5">
                    <h5 className="text-xs font-black text-stone-855 border-b border-stone-100 pb-1.5 capitalize">
                      {tx(getPageTitle(activePage), getPageTitle(activePage))}
                    </h5>
                    <p className="text-[10px] text-stone-600 mt-3 font-semibold leading-relaxed whitespace-pre-wrap">
                      {getPageText(activePage)}
                    </p>
                  </div>

                  {/* Key Highlights box on page 01 */}
                  {activePage === "01" && (
                    <div className="mt-5 bg-stone-50/80 border border-stone-200/60 rounded-xl p-4">
                      <h6 className="text-[10px] font-black text-stone-800 uppercase tracking-wide">
                        {tx("Key Highlights", "Key Highlights")}
                      </h6>
                      <div className="grid grid-cols-2 gap-3 mt-3">
                        <div className="bg-white border border-stone-150 p-2.5 rounded-lg">
                          <span className="text-[8px] font-bold text-stone-400 uppercase flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse"></span>
                            {tx("Total Reports", "Total Reports")}
                          </span>
                          <div className="text-base font-black text-stone-850 mt-1">
                            {report.total_records_parsed ?? 0}
                          </div>
                        </div>
                        <div className="bg-white border border-stone-150 p-2.5 rounded-lg">
                          <span className="text-[8px] font-bold text-stone-400 uppercase flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-red-600"></span>
                            {tx("Critical Incidents", "Critical Incidents")}
                          </span>
                          <div className="text-base font-black text-stone-850 mt-1">
                            {report.threat_count_critical ?? 0}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Threat Severity Chart in Preview */}
                  {(activePage === "02" || activePage === "03" || activePage === "04" || activePage === "05") && (
                    <div className="mt-5 bg-stone-50/80 border border-stone-200/60 rounded-xl p-4">
                      <h6 className="text-[10px] font-black text-stone-800 uppercase tracking-wide border-b border-stone-200/60 pb-2">
                        {tx("Severity Threat Incidents Breakdown", "Severity Threat Incidents Breakdown")}
                      </h6>
                      <div className="mt-4 flex items-end justify-around h-28 border-b border-stone-200 pb-2">
                        <div className="flex flex-col items-center">
                          <span className="text-[9px] font-black text-red-600 mb-1">{report.threat_count_critical ?? 0}</span>
                          <div style={{ height: `${Math.min((report.threat_count_critical ?? 0) * 2.5, 70)}px` }} className="w-6 bg-red-500 rounded-t shadow-sm"></div>
                          <span className="text-[8px] font-bold text-stone-500 mt-1">Crit</span>
                        </div>
                        <div className="flex flex-col items-center">
                          <span className="text-[9px] font-black text-amber-600 mb-1">{report.threat_count_high ?? 0}</span>
                          <div style={{ height: `${Math.min((report.threat_count_high ?? 0) * 1.2, 70)}px` }} className="w-6 bg-amber-500 rounded-t shadow-sm"></div>
                          <span className="text-[8px] font-bold text-stone-500 mt-1">High</span>
                        </div>
                        <div className="flex flex-col items-center">
                          <span className="text-[9px] font-black text-yellow-600 mb-1">{report.threat_count_medium ?? 0}</span>
                          <div style={{ height: `${Math.min((report.threat_count_medium ?? 0) * 0.6, 70)}px` }} className="w-6 bg-yellow-400 rounded-t shadow-sm"></div>
                          <span className="text-[8px] font-bold text-stone-500 mt-1">Med</span>
                        </div>
                        <div className="flex flex-col items-center">
                          <span className="text-[9px] font-black text-emerald-600 mb-1">{report.threat_count_low ?? 0}</span>
                          <div style={{ height: `${Math.min((report.threat_count_low ?? 0) * 0.3, 70)}px` }} className="w-6 bg-emerald-500 rounded-t shadow-sm"></div>
                          <span className="text-[8px] font-bold text-stone-500 mt-1">Low</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>

                {/* Footer Kop */}
                <div className="flex justify-between items-center text-[8px] font-bold text-stone-400 border-t border-stone-100 pt-4 mt-6">
                  <span>{tx("PT Petrokimia Gresik • SOC Security Reports", "PT Petrokimia Gresik • SOC Security Reports")}</span>
                  <span>
                    {tx("Page", "Page")} {activePage}
                  </span>
                </div>
              </div>
            )}

            {/* MODE 2: PPTX SLIDE VIEW */}
            {previewFormat === "pptx" && (
              <div className="max-w-[420px] mx-auto border-2 border-stone-300 rounded-xl shadow-lg bg-white overflow-hidden aspect-[16/9] flex flex-col justify-between text-left relative animate-fadeIn">
                {activePage === "01" ? (
                  /* Cover Slide */
                  <div className="h-full bg-gradient-to-br from-[#004D25] via-[#047857] to-[#013219] p-5 text-white flex flex-col justify-between relative">
                    <div className="flex justify-between items-start">
                      <div className="bg-white/95 backdrop-blur px-2 py-0.5 rounded shadow-sm">
                        <img
                          src="/LOGO_PETRO_DANANTARA.png"
                          alt="Petrokimia Danantara Logo"
                          className="h-6 w-auto object-contain"
                        />
                      </div>
                      <span className="px-2 py-0.5 bg-amber-400/20 text-amber-300 text-[8px] font-black uppercase tracking-widest rounded-full">
                        PPTX SLIDE
                      </span>
                    </div>

                    <div className="my-auto space-y-1">
                      <h2 className="text-sm font-black text-white leading-snug tracking-wide">
                        MONTHLY SECURITY OPERATIONS SUMMARY
                      </h2>
                      <p className="text-[9px] text-stone-200 font-semibold">
                        PT Petrokimia Gresik • SOC Security Operations
                      </p>
                      <p className="text-[8px] text-amber-300 font-bold">
                        Period: {report.period_start || "July 2026"} to {report.period_end || "July 2026"}
                      </p>
                    </div>

                    <div className="flex justify-between items-center border-t border-white/20 pt-1.5 text-[7px] text-stone-300">
                      <span>Internal SOC Use Only</span>
                      <span className="font-bold">Slide 01 of 07</span>
                    </div>
                  </div>
                ) : (
                  /* Content Slide */
                  <div className="h-full flex flex-col justify-between bg-stone-50">
                    <div className="bg-[#004D25] text-white px-4 py-2 flex items-center justify-between">
                      <h3 className="text-[11px] font-black tracking-wide uppercase truncate">
                        {activePage} {getPageTitle(activePage)}
                      </h3>
                      <div className="bg-white px-1.5 py-0.5 rounded shrink-0">
                        <img
                          src="/LOGO_PETRO_DANANTARA.png"
                          alt="Petrokimia Danantara Logo"
                          className="h-4 w-auto object-contain"
                        />
                      </div>
                    </div>

                    <div className="p-4 flex-1 overflow-y-auto space-y-2">
                      <p className="text-[9px] text-stone-700 font-semibold leading-relaxed whitespace-pre-wrap">
                        {getPageText(activePage)}
                      </p>

                      <div className="bg-white border border-stone-200 p-2 rounded-lg">
                        <span className="text-[8px] font-black text-stone-800 uppercase tracking-wide block mb-1">
                          Threat Severity Breakdown
                        </span>
                        <div className="grid grid-cols-4 gap-1 text-center text-[7px] font-bold">
                          <div className="bg-red-50 text-red-700 p-1 rounded">
                            <span className="block text-[9px] font-black">{report.threat_count_critical ?? 18}</span> Crit
                          </div>
                          <div className="bg-amber-50 text-amber-700 p-1 rounded">
                            <span className="block text-[9px] font-black">{report.threat_count_high ?? 56}</span> High
                          </div>
                          <div className="bg-yellow-50 text-yellow-700 p-1 rounded">
                            <span className="block text-[9px] font-black">{report.threat_count_medium ?? 102}</span> Med
                          </div>
                          <div className="bg-emerald-50 text-emerald-700 p-1 rounded">
                            <span className="block text-[9px] font-black">{report.threat_count_low ?? 210}</span> Low
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="px-4 py-1.5 border-t border-stone-200 bg-white flex items-center justify-between text-[7px] text-stone-500 font-semibold">
                      <span>PT Petrokimia Gresik • SOC Operations</span>
                      <span className="font-bold text-stone-800">Slide {activePage} of 07</span>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* EDIT TEXT TAB */}
        {activeTab === "edit" && (
          <div className="w-full h-full flex flex-col justify-between text-left space-y-4">
            <div className="flex-1 min-h-[300px] flex flex-col">
              <label className="text-[11px] font-black text-stone-700 uppercase tracking-wider mb-2">
                {tx(
                  "Modify Section Narrative AI",
                  "Modify Section Narrative AI",
                )}{" "}
                ({tx(getPageTitle(activePage), getPageTitle(activePage))})
              </label>
              <textarea
                value={getPageText(activePage)}
                onChange={(e) => handleTextChange(e.target.value)}
                className="w-full flex-1 p-4 border border-stone-200 rounded-2xl focus:outline-none focus:border-petro-green text-xs font-semibold leading-relaxed text-stone-800 shadow-sm bg-white"
                placeholder={tx(
                  "Write dynamic logs narration...",
                  "Write dynamic logs narration...",
                )}
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
                    <svg
                      className="animate-spin h-3.5 w-3.5 text-white"
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                    >
                      <circle
                        className="opacity-25"
                        cx="12"
                        cy="12"
                        r="10"
                        stroke="currentColor"
                        strokeWidth="4"
                      ></circle>
                      <path
                        className="opacity-75"
                        fill="currentColor"
                        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                      ></path>
                    </svg>
                    {tx("Saving...", "Saving...")}
                  </>
                ) : (
                  tx("Save Changes", "Save Changes")
                )}
              </button>

              {saveSuccess && (
                <span className="text-xs text-emerald-600 font-extrabold flex items-center gap-1 animate-fade-in">
                  ✓ {tx("Saved Successfully!", "Saved Successfully!")}
                </span>
              )}
            </div>
          </div>
        )}

        {/* CHARTS TAB */}
        {activeTab === "charts" && (
          <div className="w-full text-left">
            <h5 className="font-extrabold text-stone-855 text-xs mb-3 uppercase tracking-wide">
              {tx("Chart Visualization", "Chart Visualization")}
            </h5>
            <ReportChartPanel reportId={report.id} tx={tx} />
          </div>
        )}
      </div>
    </div>
  );
}
