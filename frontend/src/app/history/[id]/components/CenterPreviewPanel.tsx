import { useState, useEffect } from "react";
import { t } from "@/utils/i18n";
import ChartNarasiLayout from "@/app/generate/components/ChartNarasiLayout";
import RichTextEditor from "@/app/generate/components/RichTextEditor";
import FullscreenStudioModal from "@/app/generate/components/FullscreenStudioModal";
import ReportBlockRenderer from "@/components/ReportBlockRenderer";
import { fetchReportBlocks } from "@/utils/reportBlocksApi";
import type { ReportBlock } from "@/utils/reportTheme";

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

  // Blocks yang SAMA PERSIS dipakai backend untuk merender PDF/PPTX (build_report_blocks) —
  // supaya tab Preview ini dijamin menampilkan section & angka yang sama dengan file yang
  // benar-benar diunduh, bukan implementasi tampilan yang dikarang terpisah.
  const [blocks, setBlocks] = useState<ReportBlock[]>([]);
  const [blocksLoading, setBlocksLoading] = useState(true);
  const [blocksError, setBlocksError] = useState("");

  useEffect(() => {
    if (!report?.id) return;
    let cancelled = false;
    setBlocksLoading(true);
    setBlocksError("");
    const token =
      typeof window !== "undefined" ? localStorage.getItem("token") : null;
    fetchReportBlocks(report.id, token)
      .then((b) => {
        if (!cancelled) setBlocks(b);
      })
      .catch((err) => {
        if (!cancelled) setBlocksError(err.message || "Gagal memuat preview.");
      })
      .finally(() => {
        if (!cancelled) setBlocksLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [report?.id]);

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

  const chartCaptions: string[] = Array.isArray(
    report?.ai_summary?.chart_captions,
  )
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

              {/* Loading / error states — sama utk kedua mode */}
              {blocksLoading && (
                <div className="max-w-2xl mx-auto flex items-center justify-center gap-2 py-16 text-stone-400">
                  <div className="w-4 h-4 border-2 border-stone-300 border-t-petro-green rounded-full animate-spin" />
                  <span className="text-xs font-bold">
                    {tx("Memuat preview...", "Memuat preview...")}
                  </span>
                </div>
              )}
              {!blocksLoading && blocksError && (
                <div className="max-w-2xl mx-auto bg-red-50 border border-red-200 text-red-700 text-xs font-medium p-4 rounded-xl">
                  {blocksError}
                </div>
              )}

              {/* MODE 1: PDF DOCUMENT VIEW — tumpukan halaman, isi PERSIS sama dgn build_report_blocks */}
              {!blocksLoading && !blocksError && previewFormat === "pdf" && (
                <div className="max-w-2xl mx-auto space-y-4">
                  {blocks.map((block, i) => (
                    <ReportBlockRenderer key={i} block={block} />
                  ))}
                </div>
              )}

              {/* MODE 2: PPTX SLIDE VIEW — tiap block jadi 1 "slide" 16:9, tumpukan bisa di-scroll */}
              {!blocksLoading && !blocksError && previewFormat === "pptx" && (
                <div className="max-w-2xl mx-auto space-y-6">
                  {blocks.map((block, i) => (
                    <div
                      key={i}
                      className="aspect-video rounded-2xl border-2 border-stone-300 shadow-xl overflow-y-auto"
                    >
                      <ReportBlockRenderer block={block} />
                    </div>
                  ))}
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
                  {tx(
                    "Chart Visualization & Insight Narasi",
                    "Chart Visualization & Insight Narasi",
                  )}
                </h5>
                <span className="text-[10px] bg-amber-50 text-amber-700 px-2.5 py-0.5 rounded-full font-bold border border-amber-200">
                  💡 AI Chart Captions
                </span>
              </div>
              <ChartNarasiLayout
                reportId={report.id}
                chartCaptions={chartCaptions}
                tx={tx}
              />
            </div>
          )}
        </div>
      </div>

      {/* Shared Fullscreen Studio Modal */}
      <FullscreenStudioModal
        isOpen={isFullscreen}
        onClose={() => setIsFullscreen(false)}
        reportTitle={report?.title || tx("Untitled report", "Untitled report")}
        dataType={report?.data_type || tx("Unknown", "Unknown")}
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
