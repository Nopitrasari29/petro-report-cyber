import React from "react";
import ScrollReveal from "@/components/ScrollReveal";
import ReportChartPanel from "./ReportChartPanel";
import ChartNarasiLayout from "./ChartNarasiLayout";
import RichTextEditor from "./RichTextEditor";
import FullscreenStudioModal from "./FullscreenStudioModal";
import EditableReportTitle from "@/components/EditableReportTitle";
import ReportBlockRenderer from "@/components/ReportBlockRenderer";
import { fetchReportBlocks } from "@/utils/reportBlocksApi";
import type { ReportBlock } from "@/utils/reportTheme";
import type { ReportPage } from "@/utils/reportSections";

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
  reportTitle?: string;
  editedSummary: any;
  pages: ReportPage[];
  headerTitle?: string;
  headerSubtitle?: string;
  themeColor?: string;
  getPageText: (page: string) => string;
  getPageTitle: (page: string) => string;
  handleTextChange: (newVal: string) => void;
  handleSaveEdits: () => void;
  onBack: () => void;
  onNext: () => void;
  onRenameTitle: (newTitle: string) => void | Promise<void>;
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
  reportTitle = "",
  editedSummary,
  pages,
  headerTitle = "PT PETROKIMIA GRESIK",
  headerSubtitle = "Sistem Otomasi Laporan & Eksekutif Presentasi Berbasis AI",
  themeColor = "green",
  getPageText,
  getPageTitle,
  handleTextChange,
  handleSaveEdits,
  onBack,
  onNext,
  onRenameTitle,
  tx,
}: Step4PreviewEditProps) {
  const [previewFormat, setPreviewFormat] = React.useState<"pdf" | "pptx">(
    "pdf",
  );
  const [zoomLevel, setZoomLevel] = React.useState<number>(100);
  const [isFullscreen, setIsFullscreen] = React.useState<boolean>(false);

  // Blocks yang SAMA PERSIS dipakai backend untuk merender PDF/PPTX (build_report_blocks) —
  // supaya tab Preview ini dijamin menampilkan section & angka yang sama dengan file yang
  // benar-benar diunduh, bukan implementasi tampilan yang dikarang terpisah.
  const [blocks, setBlocks] = React.useState<ReportBlock[]>([]);
  const [blocksLoading, setBlocksLoading] = React.useState(true);
  const [blocksError, setBlocksError] = React.useState("");

  React.useEffect(() => {
    const reportId = reportDetails?.id;
    if (!reportId) return;
    let cancelled = false;
    setBlocksLoading(true);
    setBlocksError("");
    const token =
      typeof window !== "undefined" ? localStorage.getItem("token") : null;
    fetchReportBlocks(reportId, token)
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
  }, [reportDetails?.id]);

  // Listener tombol Escape untuk keluar dari mode Fullscreen
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isFullscreen) {
        setIsFullscreen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isFullscreen]);

  return (
    <ScrollReveal animation="fadeInUp" className="space-y-6">
      <div className="text-left">
        <EditableReportTitle
          title={
            reportTitle ||
            reportDetails?.title ||
            tx("Untitled report", "Untitled report")
          }
          onSave={onRenameTitle}
          className="text-2xl font-extrabold text-stone-900"
          tx={tx}
        />
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
            {pages.map((sec) => (
              <button
                key={sec.page}
                onClick={() => setActivePage(sec.page)}
                className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                  activePage === sec.page
                    ? "bg-petro-green/10 text-petro-green border border-petro-green/30 font-black shadow-sm"
                    : "bg-transparent text-stone-600 hover:bg-stone-50 border border-transparent"
                }`}
              >
                <span className="truncate">{tx(sec.title, sec.title)}</span>
                {activePage === sec.page && (
                  <span className="w-2 h-2 rounded-full bg-petro-green"></span>
                )}
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
              {tx("Page", "Page")} {activePage} {tx("of", "of")} {pages[pages.length - 1].page}
            </span>
            <button
              disabled={activePage === pages[pages.length - 1].page}
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

        {/* Center Panel: Preview & Edit Workspace (Expanded to 9 cols after removing Properties panel) */}
        <div className="lg:col-span-9 bg-white rounded-2xl border border-stone-200/80 p-6 shadow-sm space-y-6 premium-card-hover transition-colors">
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

            {/* Live Save Status, Zoom Selector, & Fullscreen Button */}
            <div className="flex items-center gap-2.5">
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

              {/* Zoom Dropdown Selector */}
              <div className="relative inline-flex items-center bg-stone-100/90 hover:bg-stone-200/80 rounded-xl px-2.5 py-1 text-xs font-extrabold text-stone-700 transition-colors border border-stone-200/80 shadow-sm">
                <select
                  value={zoomLevel}
                  onChange={(e) => setZoomLevel(Number(e.target.value))}
                  className="bg-transparent text-xs font-bold text-stone-700 appearance-none pr-5 py-0.5 outline-none cursor-pointer"
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
                  className="w-3.5 h-3.5 absolute right-2 pointer-events-none text-stone-500"
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
                title={tx(
                  "Fullscreen Edit/Preview Mode",
                  "Mode Layar Penuh Edit/Preview",
                )}
                className="p-1.5 rounded-xl bg-white text-stone-600 hover:bg-stone-100 hover:text-stone-900 border border-stone-200/80 shadow-sm transition-all cursor-pointer"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                  className="w-4 h-4"
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

          {/* Tab Contents Container dengan Zoom Transform */}
          <div
            className="min-h-[350px] transition-transform duration-200 ease-out"
            style={{
              transform:
                zoomLevel !== 100 ? `scale(${zoomLevel / 100})` : "none",
              transformOrigin: "top center",
            }}
          >
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

                {/* Loading / error states — sama utk kedua mode */}
                {blocksLoading && (
                  <div className="max-w-lg mx-auto flex items-center justify-center gap-2 py-16 text-stone-400">
                    <div className="w-4 h-4 border-2 border-stone-300 border-t-petro-green rounded-full animate-spin" />
                    <span className="text-xs font-bold">
                      {tx("Memuat preview...", "Memuat preview...")}
                    </span>
                  </div>
                )}
                {!blocksLoading && blocksError && (
                  <div className="max-w-lg mx-auto bg-red-50 border border-red-200 text-red-700 text-xs font-medium p-4 rounded-xl">
                    {blocksError}
                  </div>
                )}

                {/* MODE 1: PDF DOCUMENT VIEW — tumpukan halaman, isi PERSIS sama dgn build_report_blocks */}
                {!blocksLoading && !blocksError && previewFormat === "pdf" && (
                  <div className="max-w-lg mx-auto space-y-4">
                    {blocks.map((block, i) => (
                      <ReportBlockRenderer key={i} block={block} />
                    ))}
                  </div>
                )}

                {/* MODE 2: PPTX SLIDE VIEW — tiap block jadi 1 "slide" 16:9, tumpukan bisa di-scroll */}
                {!blocksLoading && !blocksError && previewFormat === "pptx" && (
                  <div className="max-w-lg mx-auto space-y-6">
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
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-black text-stone-755 uppercase tracking-wider">
                    {tx(
                      "Chart Visualization & Insight Narasi",
                      "Chart Visualization & Insight Narasi",
                    )}
                  </h4>
                  <span className="text-[10px] bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full font-bold border border-amber-200">
                    💡 AI Chart Captions
                  </span>
                </div>

                {/* Chart + Narasi — blocks yang sama persis dengan tab Preview & file export */}
                <ChartNarasiLayout
                  blocks={blocks}
                  blocksLoading={blocksLoading}
                  blocksError={blocksError}
                  tx={tx}
                />
              </div>
            )}
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
          {tx("Proceed to Export", "Proceed to Export")}
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
      {/* Fullscreen Studio Modal */}
      <FullscreenStudioModal
        isOpen={isFullscreen}
        onClose={() => setIsFullscreen(false)}
        reportTitle={
          reportTitle ||
          reportDetails?.title ||
          tx("Untitled report", "Untitled report")
        }
        dataType={reportDetails?.data_type || tx("Unknown", "Unknown")}
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
        pages={pages}
        blocks={blocks}
        blocksLoading={blocksLoading}
        blocksError={blocksError}
        headerTitle={headerTitle}
        headerSubtitle={headerSubtitle}
        themeColor={themeColor}
        inputFile={reportDetails?.input_file_name || "-"}
        tx={tx}
      />
    </ScrollReveal>
  );
}
