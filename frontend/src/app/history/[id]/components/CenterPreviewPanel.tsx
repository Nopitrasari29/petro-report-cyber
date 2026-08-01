import { useState, useEffect } from "react";
import { t } from "@/utils/i18n";
import { REPORT_SECTIONS } from "@/utils/reportSections";
import ChartNarasiLayout from "@/app/generate/components/ChartNarasiLayout";
import RichTextEditor from "@/app/generate/components/RichTextEditor";
import FullscreenStudioModal from "@/app/generate/components/FullscreenStudioModal";

const LAST_PAGE = REPORT_SECTIONS[REPORT_SECTIONS.length - 1].page;

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
  setActivePage?: (page: string) => void;
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
  setActivePage = () => {},
  report,
  getPageTitle,
  getPageText,
  handleTextChange,
  handleSaveEdits,
  isSaving,
  saveSuccess,
}: CenterPreviewPanelProps) {
  const [previewFormat, setPreviewFormat] = useState<"pdf" | "pptx">("pdf");
  const [zoomLevel, setZoomLevel] = useState<number>(100);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (activePage && previewFormat === "pdf") {
      const el = document.getElementById(`pdf-section-${activePage}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  }, [activePage, previewFormat]);

  // Listener tombol Escape untuk melepaskan mode Fullscreen
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isFullscreen) {
        setIsFullscreen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isFullscreen]);

  const chartCaptions: string[] = Array.isArray(report?.ai_summary?.chart_captions)
    ? report.ai_summary.chart_captions
    : [];

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

        {/* Zoom Selector & Fullscreen Button */}
        <div className="flex items-center gap-2 py-2">
          {/* Zoom Dropdown Selector */}
          <div className="relative inline-flex items-center bg-stone-100 hover:bg-stone-200 rounded-xl px-2.5 py-1 text-[11px] font-extrabold text-stone-700 transition-colors border border-stone-200 shadow-sm">
            <select
              value={zoomLevel}
              onChange={(e) => setZoomLevel(Number(e.target.value))}
              className="bg-transparent text-[11px] font-bold text-stone-700 appearance-none pr-5 py-0.5 outline-none cursor-pointer"
            >
              <option value={50}>50%</option>
              <option value={75}>75%</option>
              <option value={100}>100%</option>
              <option value={125}>125%</option>
              <option value={150}>150%</option>
              <option value={200}>200%</option>
            </select>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="w-3 h-3 absolute right-2 pointer-events-none text-stone-500"
            >
              <path
                fillRule="evenodd"
                d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z"
                clipRule="evenodd"
              />
            </svg>
          </div>

          {/* Fullscreen Toggle Button */}
          <button
            onClick={() => setIsFullscreen(true)}
            title={tx("Fullscreen Edit/Preview", "Layar Penuh Edit/Preview")}
            className="p-1.5 rounded-xl bg-white text-stone-600 hover:bg-stone-100 border border-stone-200 shadow-sm transition-all cursor-pointer"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
              className="w-3.5 h-3.5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15"
              />
            </svg>
          </button>
        </div>
      </div>

      {/* Tab Contents Container dengan Zoom scale */}
      <div className="flex-1 overflow-y-auto p-6 bg-[#EFECE5]/60 scroll-smooth">
        <div
          className="transition-transform duration-200 ease-out"
          style={{
            transform: zoomLevel !== 100 ? `scale(${zoomLevel / 100})` : "none",
            transformOrigin: "top center",
          }}
        >
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
              <div className="max-w-[540px] mx-auto bg-white border border-stone-300 rounded-lg shadow-lg p-6 min-h-[620px] text-left relative flex flex-col justify-between animate-fadeIn font-sans">
                <div className="space-y-4">
                  {/* Official PDF Document Header Kop */}
                  <div className="border-b-3 border-[#004D25] pb-3 flex justify-between items-center">
                    <div>
                      <h3 className="text-base font-black text-[#004D25] tracking-tight m-0">
                        PT PETROKIMIA GRESIK
                      </h3>
                      <p className="text-[9px] font-extrabold text-[#d9a700] uppercase tracking-wider mt-0.5">
                        Sistem Otomasi Report Bulanan SOC Berbasis AI
                      </p>
                    </div>
                    <img
                      src="/LOGO_PETRO_DANANTARA.png"
                      alt="Logo Petrokimia"
                      className="h-10 w-auto object-contain"
                    />
                  </div>

                  {/* Document Title */}
                  <h2 className="text-lg font-black text-stone-900 leading-tight">
                    {report.title || "SOC Executive Summary"}
                  </h2>

                  {/* Metadata Block Table */}
                  <table className="w-full text-[10px] text-stone-600 border-collapse">
                    <tbody>
                      <tr>
                        <td className="font-extrabold text-stone-400 uppercase w-28 py-0.5">Jenis Data:</td>
                        <td className="font-extrabold text-stone-800 uppercase">{report.data_type || "FIREWALL"}</td>
                      </tr>
                      <tr>
                        <td className="font-extrabold text-stone-400 uppercase py-0.5">Tanggal Cetak:</td>
                        <td className="font-extrabold text-stone-800">{report.created_at ? new Date(report.created_at).toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" }) : "22 Juli 2026"}</td>
                      </tr>
                      <tr>
                        <td className="font-extrabold text-stone-400 uppercase py-0.5">Berkas Sumber:</td>
                        <td className="font-mono font-bold text-stone-700">{report.input_file_name || "-"}</td>
                      </tr>
                    </tbody>
                  </table>

                  {/* Confidentiality Notice Alert Box */}
                  <div className="bg-stone-50 border-l-4 border-[#d9a700] p-3 rounded-r-lg text-[9.5px] text-stone-600 leading-relaxed font-medium">
                    <strong className="text-stone-900 font-bold block mb-0.5">Pemberitahuan Kerahasiaan siber:</strong>
                    Dokumen ini berisi rekaman aktivitas operasional keamanan siber internal PT Petrokimia Gresik. Dilarang keras menyebarluaskan isi laporan ini di luar otoritas SOC.
                  </div>

                  {/* Section 1: Executive Summary */}
                  <div id="pdf-section-01" className={`p-4 rounded-xl transition-all duration-300 ${activePage === "01" ? "bg-emerald-50/80 border-2 border-petro-green shadow-sm ring-2 ring-emerald-200" : "border border-stone-150"}`}>
                    <h4 className="text-xs font-black text-[#004D25] border-b border-stone-150 pb-1 flex items-center justify-between">
                      <span>1. Ringkasan Eksekutif (Executive Summary)</span>
                      {activePage === "01" && <span className="text-[9px] bg-petro-green text-white px-2 py-0.5 rounded-full font-extrabold">Active Section</span>}
                    </h4>
                    <p className="text-[10px] text-stone-700 mt-2 font-medium leading-relaxed whitespace-pre-wrap">
                      {getPageText("01")}
                    </p>
                  </div>

                  {/* Section 2: Visualisasi Data & Infografis Analitik */}
                  <div id="pdf-section-02" className={`p-4 rounded-xl transition-all duration-300 ${activePage === "02" ? "bg-emerald-50/80 border-2 border-petro-green shadow-sm ring-2 ring-emerald-200" : "border border-stone-150"}`}>
                    <h4 className="text-xs font-black text-[#004D25] border-b border-stone-150 pb-1 mb-3 flex items-center justify-between">
                      <span>2. Visualisasi Data & Infografis Analitik</span>
                      {activePage === "02" && <span className="text-[9px] bg-petro-green text-white px-2 py-0.5 rounded-full font-extrabold">Active Section</span>}
                    </h4>
                    <ChartNarasiLayout reportId={report.id} chartCaptions={chartCaptions} tx={tx} />
                  </div>

                  {/* Section 3: Trend Analysis */}
                  <div id="pdf-section-03" className={`p-4 rounded-xl transition-all duration-300 ${activePage === "03" ? "bg-emerald-50/80 border-2 border-petro-green shadow-sm ring-2 ring-emerald-200" : "border border-stone-150"}`}>
                    <h4 className="text-xs font-black text-[#004D25] border-b border-stone-150 pb-1 flex items-center justify-between">
                      <span>3. Analisis Tren Ancaman (Trend Analysis)</span>
                      {activePage === "03" && <span className="text-[9px] bg-petro-green text-white px-2 py-0.5 rounded-full font-extrabold">Active Section</span>}
                    </h4>
                    <p className="text-[10px] text-stone-700 mt-2 font-medium leading-relaxed whitespace-pre-wrap">
                      {getPageText("03")}
                    </p>
                  </div>

                  {/* Section 4: Severity Analysis */}
                  <div id="pdf-section-04" className={`p-4 rounded-xl transition-all duration-300 ${activePage === "04" ? "bg-emerald-50/80 border-2 border-petro-green shadow-sm ring-2 ring-emerald-200" : "border border-stone-150"}`}>
                    <h4 className="text-xs font-black text-[#004D25] border-b border-stone-150 pb-1 flex items-center justify-between">
                      <span>4. Analisis Tingkat Keparahan (Severity Analysis)</span>
                      {activePage === "04" && <span className="text-[9px] bg-petro-green text-white px-2 py-0.5 rounded-full font-extrabold">Active Section</span>}
                    </h4>
                    <p className="text-[10px] text-stone-700 mt-2 font-medium leading-relaxed whitespace-pre-wrap">
                      {getPageText("04")}
                    </p>
                  </div>

                  {/* Section 5: Risk Assessment */}
                  <div id="pdf-section-05" className={`p-4 rounded-xl transition-all duration-300 ${activePage === "05" ? "bg-emerald-50/80 border-2 border-petro-green shadow-sm ring-2 ring-emerald-200" : "border border-stone-150"}`}>
                    <h4 className="text-xs font-black text-[#004D25] border-b border-stone-150 pb-1 flex items-center justify-between">
                      <span>5. Penilaian Risiko (Risk Assessment)</span>
                      {activePage === "05" && <span className="text-[9px] bg-petro-green text-white px-2 py-0.5 rounded-full font-extrabold">Active Section</span>}
                    </h4>
                    <p className="text-[10px] text-stone-700 mt-2 font-medium leading-relaxed whitespace-pre-wrap">
                      {getPageText("05")}
                    </p>
                  </div>

                  {/* Section 6: Recommendations & Conclusion */}
                  <div id="pdf-section-06" className={`p-4 rounded-xl transition-all duration-300 ${activePage === "06" ? "bg-emerald-50/80 border-2 border-petro-green shadow-sm ring-2 ring-emerald-200" : "border border-stone-150"}`}>
                    <h4 className="text-xs font-black text-[#004D25] border-b border-stone-150 pb-1 flex items-center justify-between">
                      <span>6. Kesimpulan & Rekomendasi</span>
                      {activePage === "06" && <span className="text-[9px] bg-petro-green text-white px-2 py-0.5 rounded-full font-extrabold">Active Section</span>}
                    </h4>
                    <p className="text-[10px] text-stone-700 mt-2 font-medium leading-relaxed whitespace-pre-wrap">
                      {getPageText("06")}
                    </p>
                  </div>
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

            {/* MODE 2: PPTX SLIDE VIEW (16:9 Landscape Widescreen matching export_ppt.py 1-to-1) */}
            {previewFormat === "pptx" && (
              <div className="max-w-[540px] mx-auto border-2 border-stone-300 rounded-2xl shadow-xl bg-white aspect-[16/9] flex flex-col justify-between text-left relative animate-fadeIn overflow-hidden font-sans p-6">
                {activePage === "01" ? (
                  /* Slide 1: Cover Slide (Matching python-pptx cover 1-to-1) */
                  <div className="h-full flex flex-col justify-between relative">
                    {/* Top Green Accent Bar */}
                    <div className="absolute -top-6 -left-6 -right-6 h-3 bg-[#004D25]"></div>

                    {/* Top Header Logo */}
                    <div className="flex justify-between items-start pt-2">
                      <div></div>
                      <img
                        src="/LOGO_PETRO_DANANTARA.png"
                        alt="Logo Petrokimia"
                        className="h-9 w-auto object-contain"
                      />
                    </div>

                    {/* Cover Title Box */}
                    <div className="my-auto space-y-2 pl-2">
                      <h4 className="text-xs font-black text-[#004D25] tracking-wide uppercase">
                        PT PETROKIMIA GRESIK
                      </h4>
                      <h2 className="text-xl font-black text-[#004D25] leading-tight">
                        {report.title || "SOC Executive Summary"}
                      </h2>
                      <p className="text-[10.5px] font-black text-[#d9a700] pt-1">
                        Sistem Otomasi Report SOC | Laporan {(report.data_type || "FIREWALL").toUpperCase()} | {report.created_at ? new Date(report.created_at).toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" }) : "22 Juli 2026"}
                      </p>
                    </div>

                    {/* Cover Slide Footer */}
                    <div className="flex justify-between items-center border-t border-stone-200 pt-2 text-[8px] font-bold text-stone-400">
                      <span>PT Petrokimia Gresik • SOC Operations</span>
                      <span className="font-extrabold text-stone-700">Slide 01 of {LAST_PAGE}</span>
                    </div>
                  </div>
                ) : activePage === "02" ? (
                  /* Slide 2: Visualisasi Chart + Narasi AI Slide */
                  <div className="h-full flex flex-col justify-between relative overflow-y-auto">
                    <div>
                      <div className="flex justify-between items-start border-b border-stone-150 pb-2 mb-2">
                        <div>
                          <h3 className="text-sm font-black text-[#004D25] m-0">
                            Visualisasi Data & Infografis Analitik
                          </h3>
                          <div className="w-12 h-1 bg-[#d9a700] rounded mt-1"></div>
                        </div>
                        <img
                          src="/LOGO_PETRO_DANANTARA.png"
                          alt="Logo Petrokimia"
                          className="h-6 w-auto object-contain"
                        />
                      </div>
                      <ChartNarasiLayout reportId={report.id} chartCaptions={chartCaptions} tx={tx} />
                    </div>
                    <div className="flex justify-between items-center border-t border-stone-200 pt-2 mt-2 text-[8px] font-bold text-stone-400">
                      <span>PT Petrokimia Gresik • SOC Operations</span>
                      <span className="font-extrabold text-stone-700">Slide {activePage} of {LAST_PAGE}</span>
                    </div>
                  </div>
                ) : (
                  /* Content Slide Layout (Slide 3+: Executive Summary, Trend, Severity, Risk, Recommendations) */
                  <div className="h-full flex flex-col justify-between relative">
                    {/* Slide Header */}
                    <div className="flex justify-between items-start border-b border-stone-150 pb-2">
                      <div>
                        <h3 className="text-sm font-black text-[#004D25] m-0">
                          {getPageTitle(activePage)}
                        </h3>
                        <div className="w-12 h-1 bg-[#d9a700] rounded mt-1"></div>
                      </div>
                      <img
                        src="/LOGO_PETRO_DANANTARA.png"
                        alt="Logo Petrokimia"
                        className="h-6 w-auto object-contain"
                      />
                    </div>

                    {/* Content Box with Left Accent Bar */}
                    <div className="my-auto flex items-stretch gap-3 pl-1 pr-2 py-2 flex-1 overflow-y-auto">
                      <div className="w-1 bg-[#004D25] rounded shrink-0"></div>
                      <p className="text-[10.5px] text-stone-700 font-medium leading-relaxed whitespace-pre-wrap">
                        {getPageText(activePage)}
                      </p>
                    </div>

                    {/* Content Slide Footer */}
                    <div className="flex justify-between items-center border-t border-stone-200 pt-2 text-[8px] font-bold text-stone-400">
                      <span>PT Petrokimia Gresik • SOC Operations</span>
                      <span className="font-extrabold text-stone-700">Slide {activePage} of {LAST_PAGE}</span>
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
              <RichTextEditor
                value={getPageText(activePage)}
                onChange={handleTextChange}
                tx={tx}
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
          <div className="w-full text-left space-y-4">
            <div className="flex items-center justify-between">
              <h5 className="font-extrabold text-stone-855 text-xs uppercase tracking-wide">
                {tx("Chart Visualization & Insight Narasi", "Chart Visualization & Insight Narasi")}
              </h5>
              <span className="text-[10px] bg-amber-50 text-amber-700 px-2.5 py-0.5 rounded-full font-bold border border-amber-200">
                💡 AI Chart Captions
              </span>
            </div>
            <ChartNarasiLayout reportId={report.id} chartCaptions={chartCaptions} tx={tx} />
          </div>
        )}
        </div>
      </div>

      {/* Shared Fullscreen Studio Modal */}
      <FullscreenStudioModal
        isOpen={isFullscreen}
        onClose={() => setIsFullscreen(false)}
        reportTitle={report?.title || "SOC Executive Summary"}
        dataType={report?.data_type || "DATA"}
        activePage={activePage}
        setActivePage={setActivePage}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        previewFormat={previewFormat}
        setPreviewFormat={setPreviewFormat}
        zoomLevel={zoomLevel}
        setZoomLevel={setZoomLevel}
        getPageTitle={getPageTitle}
        getPageText={getPageText}
        handleTextChange={handleTextChange}
        handleSaveEdits={handleSaveEdits}
        isSaving={isSaving}
        saveSuccess={saveSuccess}
        reportId={report?.id}
        chartCaptions={chartCaptions}
        headerTitle="PT PETROKIMIA GRESIK"
        headerSubtitle="Sistem Otomasi Laporan & Eksekutif Presentasi Berbasis AI"
        themeColor="green"
        inputFile={report?.input_file_name || "-"}
        tx={tx}
      />
    </div>
  );
}
