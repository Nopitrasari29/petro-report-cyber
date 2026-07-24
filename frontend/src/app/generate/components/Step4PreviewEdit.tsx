import React from "react";
import ScrollReveal from "@/components/ScrollReveal";
import ReportChartPanel from "./ReportChartPanel";
import RichTextEditor from "./RichTextEditor";

// Mendeteksi apakah suatu string konten itu HTML (hasil rich text editor) atau teks polos
// (AI-generated asli / laporan lama sebelum editor ini ada). Dipakai biar tab Preview bisa
// nampilin dua-duanya dengan benar tanpa nge-render tag mentah sebagai teks literal.
const looksLikeHtml = (value: string) => /<[a-zA-Z][^>]*>/.test(value);

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
  const [previewFormat, setPreviewFormat] = React.useState<"pdf" | "pptx">("pdf");

  return (
    <ScrollReveal animation="fadeInUp" className="space-y-6">
      <div className="text-left">
        <h2 className="text-2xl font-extrabold text-stone-900">
          {tx("Preview & Edit", "Preview & Edit")}
        </h2>
        <p className="text-sm text-stone-500 font-semibold mt-1">
          {tx(
            "Review AI generated content and make any necessary edits",
            "Review AI generated content and make any necessary edits",
          )}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 text-left items-start mt-6">
        {/* Left Panel: Pages List */}
        <div className="lg:col-span-3 bg-white rounded-2xl border border-stone-200/80 p-5 shadow-sm space-y-4 premium-card-hover transition-colors">
          <h3 className="font-extrabold text-stone-855 text-sm border-b border-stone-100 pb-2">
            {tx("Pages", "Pages")}
          </h3>

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
                <span className="truncate">
                  {tx(pg.label.substring(3), pg.label.substring(3))}
                </span>
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
                    activeTab === tab
                      ? "bg-stone-900 text-white"
                      : "bg-stone-50 text-stone-500 hover:bg-stone-100"
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
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className="w-3.5 h-3.5"
                  >
                    <path
                      fillRule="evenodd"
                      d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z"
                      clipRule="evenodd"
                    />
                  </svg>
                ) : (
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 20 20"
                    fill="currentColor"
                    className="w-3.5 h-3.5"
                  >
                    <path d="M10.75 4.75a.75.75 0 0 0-1.5 0v4.5h-4.5a.75.75 0 0 0 0 1.5h4.5v4.5a.75.75 0 0 0 1.5 0v-4.5h4.5a.75.75 0 0 0 0-1.5h-4.5v-4.5Z" />
                  </svg>
                )}
                {isSaving
                  ? tx("Saving...", "Saving...")
                  : saveSuccess
                    ? tx("Saved!", "Saved!")
                    : tx("Save Changes", "Save Changes")}
              </button>
            )}
          </div>

          {/* Tab Contents */}
          <div className="min-h-[350px]">
            {activeTab === "preview" && (
              <div className="space-y-4">
                {/* Format Preview Toggle (PDF Document / PPTX Slide) */}
                <div className="flex justify-center">
                  <div className="inline-flex p-1 bg-stone-100/90 rounded-xl border border-stone-200 shadow-inner gap-1">
                    <button
                      onClick={() => setPreviewFormat("pdf")}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-extrabold transition-all cursor-pointer ${
                        previewFormat === "pdf"
                          ? "bg-white text-stone-900 shadow-sm"
                          : "text-stone-500 hover:text-stone-800"
                      }`}
                    >
                      <span className="w-2 h-2 rounded-full bg-red-500"></span>
                      {tx("PDF Document View", "PDF Document View")}
                    </button>
                    <button
                      onClick={() => setPreviewFormat("pptx")}
                      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-extrabold transition-all cursor-pointer ${
                        previewFormat === "pptx"
                          ? "bg-white text-stone-900 shadow-sm"
                          : "text-stone-500 hover:text-stone-800"
                      }`}
                    >
                      <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                      {tx("PPTX Slide View", "PPTX Slide View")}
                    </button>
                  </div>
                </div>

                {/* MODE 1: PDF DOCUMENT VIEW (A4 Portrait) */}
                {previewFormat === "pdf" && (
                  <div className="border border-stone-200/90 rounded-xl p-6 shadow-md bg-white max-w-lg mx-auto flex flex-col justify-between min-h-[480px] animate-fadeIn">
                    <div>
                      {/* Document Kop */}
                      <div className="flex items-center justify-between border-b-2 border-stone-300 pb-3 mb-5">
                        <div className="flex items-center gap-2">
                          <img
                            src="/LOGO_PETRO_DANANTARA.png"
                            alt="Petrokimia Danantara Logo"
                            className="h-9 w-auto object-contain"
                          />
                        </div>
                        <span className="text-[9px] font-black text-amber-600 tracking-wider uppercase">
                          {tx("SOC Executive Summary", "SOC Executive Summary")}
                        </span>
                      </div>

                      {/* Document Body */}
                      <div className="space-y-4 text-left">
                        <div>
                          <h4 className="text-[10px] text-petro-green font-black uppercase tracking-widest">
                            {tx(getPageTitle(activePage), getPageTitle(activePage))}
                          </h4>
                          <h2 className="text-sm font-black text-stone-855 mt-0.5">
                            {tx(
                              "Monthly Security Operations Summary",
                              "Monthly Security Operations Summary",
                            )}
                          </h2>
                          <p className="text-[8px] text-stone-400 font-bold mt-0.5">
                            {tx("Period:", "Period:")} {periodStart || "2026-07-01"}{" "}
                            {tx("to", "to")} {periodEnd || "2026-07-31"}
                          </p>
                        </div>

                        {looksLikeHtml(getPageText(activePage)) ? (
                          <div
                            className="text-xs text-stone-600 font-semibold leading-relaxed rte-preview"
                            dangerouslySetInnerHTML={{
                              __html: getPageText(activePage),
                            }}
                          />
                        ) : (
                          <p className="text-xs text-stone-600 font-semibold leading-relaxed whitespace-pre-wrap">
                            {getPageText(activePage)}
                          </p>
                        )}

                        {/* Highlights on Page 01 */}
                        {activePage === "01" && (
                          <div className="p-3 bg-stone-50 border border-stone-200 rounded-xl text-left mt-4 space-y-1">
                            <h5 className="text-[9px] font-black text-stone-755 uppercase tracking-wider">
                              {tx("Key Highlights", "Key Highlights")}
                            </h5>
                            <div className="grid grid-cols-2 gap-4 pt-1">
                              <div>
                                <span className="text-[8px] text-stone-400 font-semibold uppercase">
                                  {tx("Total Alerts", "Total Alerts")}
                                </span>
                                <p className="text-sm font-black text-stone-800">
                                  {reportDetails?.total_records_parsed ?? 0}
                                </p>
                              </div>
                              <div>
                                <span className="text-[8px] text-stone-400 font-semibold uppercase">
                                  {tx("Critical Threats", "Critical Threats")}
                                </span>
                                <p className="text-sm font-black text-stone-800">
                                  {reportDetails?.threat_count_critical ?? 0}
                                </p>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Page Footer */}
                    <div className="flex justify-between items-center border-t border-stone-200 pt-3 mt-6 text-[8px] text-stone-400">
                      <span className="font-bold uppercase tracking-wider">
                        {tx("PT Petrokimia Gresik • SOC Security Reports", "PT Petrokimia Gresik • SOC Security Reports")}
                      </span>
                      <span className="font-black text-stone-700">
                        Page {activePage} of 07
                      </span>
                    </div>
                  </div>
                )}

                {/* MODE 2: PPTX PRESENTATION SLIDE VIEW (16:9 Landscape Widescreen) */}
                {previewFormat === "pptx" && (
                  <div className="border-2 border-stone-300 rounded-2xl shadow-xl bg-white max-w-lg mx-auto overflow-hidden aspect-[16/9] flex flex-col justify-between text-left relative animate-fadeIn">
                    {activePage === "01" ? (
                      /* Cover Slide Layout */
                      <div className="h-full bg-gradient-to-br from-[#004D25] via-[#047857] to-[#013219] p-6 text-white flex flex-col justify-between relative">
                        <div className="flex justify-between items-start">
                          <div className="bg-white/95 backdrop-blur px-2.5 py-1 rounded-lg shadow-sm">
                            <img
                              src="/LOGO_PETRO_DANANTARA.png"
                              alt="Petrokimia Danantara Logo"
                              className="h-7 w-auto object-contain"
                            />
                          </div>
                          <span className="px-2 py-0.5 bg-amber-400/20 text-amber-300 border border-amber-300/30 text-[9px] font-black uppercase tracking-widest rounded-full">
                            PPTX PRESENTATION SLIDE
                          </span>
                        </div>

                        <div className="my-auto space-y-2">
                          <h2 className="text-base font-black text-white leading-tight tracking-wide">
                            MONTHLY SECURITY OPERATIONS SUMMARY
                          </h2>
                          <p className="text-[10px] text-stone-200 font-semibold">
                            PT Petrokimia Gresik • SOC Security Operations
                          </p>
                          <p className="text-[9px] text-amber-300 font-bold">
                            Period: {periodStart || "2026-07-01"} to {periodEnd || "2026-07-31"}
                          </p>
                        </div>

                        <div className="flex justify-between items-center border-t border-white/20 pt-2 text-[8px] text-stone-300">
                          <span>Confidential • Internal SOC Use Only</span>
                          <span className="font-bold">Slide 01 of 07</span>
                        </div>
                      </div>
                    ) : (
                      /* Content Slide Layout */
                      <div className="h-full flex flex-col justify-between bg-stone-50">
                        {/* Slide Top Bar */}
                        <div className="bg-[#004D25] text-white px-5 py-2.5 flex items-center justify-between">
                          <h3 className="text-xs font-black tracking-wide uppercase">
                            {activePage} {getPageTitle(activePage)}
                          </h3>
                          <div className="bg-white px-2 py-0.5 rounded shadow-sm">
                            <img
                              src="/LOGO_PETRO_DANANTARA.png"
                              alt="Petrokimia Danantara Logo"
                              className="h-5 w-auto object-contain"
                            />
                          </div>
                        </div>

                        {/* Slide Content Body */}
                        <div className="p-5 flex-1 overflow-y-auto space-y-3">
                          {looksLikeHtml(getPageText(activePage)) ? (
                            <div
                              className="text-[10px] text-stone-700 font-semibold leading-relaxed rte-preview"
                              dangerouslySetInnerHTML={{
                                __html: getPageText(activePage),
                              }}
                            />
                          ) : (
                            <p className="text-[10px] text-stone-700 font-semibold leading-relaxed whitespace-pre-wrap">
                              {getPageText(activePage)}
                            </p>
                          )}

                          {/* Threat Breakdown Bar on Slide */}
                          <div className="bg-white border border-stone-200 p-3 rounded-xl">
                            <span className="text-[9px] font-black text-stone-800 uppercase tracking-wide block mb-2">
                              Threat Severity Summary
                            </span>
                            <div className="grid grid-cols-4 gap-2 text-center text-[8px] font-bold">
                              <div className="bg-red-50 text-red-700 p-1.5 rounded border border-red-150">
                                <span className="block text-[10px] font-black">
                                  {reportDetails?.threat_count_critical ?? 0}
                                </span>
                                Critical
                              </div>
                              <div className="bg-amber-50 text-amber-700 p-1.5 rounded border border-amber-150">
                                <span className="block text-[10px] font-black">
                                  {reportDetails?.threat_count_high ?? 0}
                                </span>
                                High
                              </div>
                              <div className="bg-yellow-50 text-yellow-700 p-1.5 rounded border border-yellow-150">
                                <span className="block text-[10px] font-black">
                                  {reportDetails?.threat_count_medium ?? 0}
                                </span>
                                Medium
                              </div>
                              <div className="bg-emerald-50 text-emerald-700 p-1.5 rounded border border-emerald-150">
                                <span className="block text-[10px] font-black">
                                  {reportDetails?.threat_count_low ?? 0}
                                </span>
                                Low
                              </div>
                            </div>
                          </div>
                        </div>

                        {/* Slide Footer */}
                        <div className="px-5 py-2 border-t border-stone-200 bg-white flex items-center justify-between text-[8px] text-stone-500 font-semibold">
                          <span>PT Petrokimia Gresik • SOC Security Operations</span>
                          <span className="font-bold text-stone-800">
                            Slide {activePage} of 07
                          </span>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {activeTab === "edit" && (
              <div className="space-y-4">
                <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider">
                  {tx("Edit Content", "Edit Content")}
                </label>
                <RichTextEditor
                  value={getPageText(activePage)}
                  onChange={handleTextChange}
                  tx={tx}
                />
              </div>
            )}

            {activeTab === "charts" && (
              <div>
                <h4 className="text-xs font-black text-stone-755 uppercase tracking-wider mb-4">
                  {tx("Chart Visualization", "Chart Visualization")}
                </h4>
                <ReportChartPanel reportId={reportDetails?.id} tx={tx} />
              </div>
            )}
          </div>
        </div>

        {/* Right Panel: Properties */}
        <div className="lg:col-span-3 bg-white rounded-2xl border border-stone-200/80 p-5 shadow-sm space-y-4 premium-card-hover transition-colors">
          <h3 className="font-extrabold text-stone-855 text-sm border-b border-stone-100 pb-2">
            {tx("Properties", "Properties")}
          </h3>

          <div>
            <label className="block text-[10px] font-bold text-stone-500 uppercase tracking-wider mb-1.5">
              {tx("Language", "Language")}
            </label>
            <select
              disabled
              value={language}
              className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 text-xs focus:outline-none text-stone-500"
            >
              <option value="English">{tx("English", "English")}</option>
              <option value="Indonesian">
                {tx("Indonesian", "Indonesian")}
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
          {tx("Next Export", "Next Export")}
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
