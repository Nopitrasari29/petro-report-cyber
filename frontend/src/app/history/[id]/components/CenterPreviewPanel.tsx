import { useState, useEffect, useCallback } from "react";
import { useTx } from "@/hooks/useTx";
import ChartNarasiLayout from "@/app/generate/components/ChartNarasiLayout";
import RichTextEditor from "@/app/generate/components/RichTextEditor";
import FullscreenStudioModal from "@/app/generate/components/FullscreenStudioModal";
import ReportBlockRenderer from "@/components/ReportBlockRenderer";
import DataQualityPanel from "./DataQualityPanel";
import type { ReportBlock, VisualStyle } from "@/utils/reportTheme";
import { getPageByNumber, type ReportPage } from "@/utils/reportSections";
import type { ReportDetails } from "@/types/report";

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
  pages: ReportPage[];
  blocks: ReportBlock[];
  visualStyle?: VisualStyle;
  blocksLoading: boolean;
  blocksError: string;
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
  pages,
  blocks,
  visualStyle,
  blocksLoading,
  blocksError,
}: CenterPreviewPanelProps) {
  const [zoomLevel, setZoomLevel] = useState<number>(100);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  // useCallback (bukan arrow function inline di JSX) — BUG NYATA YANG DIPERBAIKI: FullscreenStudioModal
  // menaruh requestFullscreen()/exitFullscreen() di useEffect yang depends on [isOpen, onClose]. Prop
  // onClose inline dibuat ULANG tiap render CenterPreviewPanel (mis. tiap kali activePage/activeTab
  // berubah krn klik halaman lain di panel Pages) — identity baru memicu effect itu jalan ulang: cleanup
  // lama memanggil exitFullscreen(), lalu requestFullscreen() baru DITOLAK browser krn bukan lagi respons
  // langsung dari user gesture, dan "fullscreenchange" yang terpicu dari exit tadi langsung menutup modal.
  // Referensi stabil di sini menghentikan effect itu re-run tiap klik halaman.
  const closeFullscreen = useCallback(() => setIsFullscreen(false), []);
  // Tab "Quality" SENGAJA dipisah dari activeTab (preview/edit/charts) - state itu juga
  // dipakai FullscreenStudioModal di bawah yang tidak didesain utk tampilan tabel kualitas
  // data, jadi diberi state lokal sendiri alih-alih memperluas kontrak activeTab bersama.
  const [showQuality, setShowQuality] = useState(false);
  const { tx } = useTx();
  const isActivePageEditable = getPageByNumber(pages, activePage)?.editable ?? false;
  // Preview cuma render 1 block aktif (bukan seluruh dokumen ditumpuk) — pages 1:1 urutan
  // dengan blocks (lihat buildPagesFromBlocks), jadi indexnya tinggal activePage - 1.
  const activeBlock = blocks[Number(activePage) - 1];

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

  return (
    <div className="lg:col-span-9 bg-white dark:bg-stone-900 border border-stone-200/85 dark:border-stone-700/80 rounded-2xl shadow-sm flex flex-col h-[520px] overflow-hidden">
      {/* Tab Navigation header */}
      <div className="bg-white dark:bg-stone-900 border-b border-stone-100 dark:border-stone-800 px-5 flex items-center justify-between">
        <div className="flex gap-4">
          {["preview", "edit", "charts"].map((tab) => (
            <button
              key={tab}
              onClick={() => {
                setActiveTab(tab as any);
                setShowQuality(false);
              }}
              className={`py-3.5 font-bold text-xs capitalize relative transition-colors ${
                !showQuality && activeTab === tab
                  ? "text-stone-900 dark:text-stone-100 border-b-2 border-petro-green font-black"
                  : "text-stone-400 dark:text-stone-500 hover:text-stone-700 dark:hover:text-stone-300"
              }`}
            >
              {tab === "edit" ? tx("Edit Text", "Edit Text") : tx(tab, tab)}
            </button>
          ))}
          {/* Tab Quality — lihat catatan showQuality di atas kenapa dipisah dari activeTab */}
          <button
            onClick={() => setShowQuality(true)}
            className={`py-3.5 font-bold text-xs relative transition-colors ${
              showQuality
                ? "text-stone-900 dark:text-stone-100 border-b-2 border-petro-green font-black"
                : "text-stone-400 dark:text-stone-500 hover:text-stone-700 dark:hover:text-stone-300"
            }`}
          >
            {tx("Kualitas Data", "Data Quality")}
          </button>
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
        {showQuality && report?.id && <DataQualityPanel reportId={report.id} />}
        <div
          className="transition-transform duration-200 ease-out"
          style={{
            display: showQuality ? "none" : undefined,
            transform: zoomLevel !== 100 ? `scale(${zoomLevel / 100})` : "none",
            transformOrigin: "top center",
          }}
        >
          {/* PREVIEW TAB */}
          {activeTab === "preview" && (
            <div className="space-y-4">
              {/* Loading / error states */}
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

              {/* Cuma 1 halaman aktif yang ditampilkan (bukan seluruh dokumen ditumpuk) —
                  dibungkus rasio 16:9 (ukuran slide asli, 13.333x7.5in — PDF & PPTX SAMA-SAMA
                  dirender sebagai "slide" berukuran identik, lihat _page() di export_pdf.py
                  dan SLIDE_W/SLIDE_H di export_ppt.py). Toggle PDF/PPTX sebelumnya di sini
                  dihapus — preview-nya 1 komponen yang sama utk kedua format, tidak pernah
                  benar-benar meniru file yang diunduh secara berbeda. */}
              {!blocksLoading && !blocksError && activeBlock && (
                <div className="max-w-2xl mx-auto">
                  {/* BUG DIPERBAIKI (dilaporkan user): `h-auto` (kotak tumbuh melebihi 16:9)
                      dibalik lagi — bikin rasio kotak berubah-ubah antar halaman, padahal file
                      PPT/PDF sungguhan SELALU 16:9 tetap. `overflow-y-auto` dikembalikan ke
                      kotak ini SENDIRI (bukan cuma di panel luar) supaya bentuknya SELALU
                      persis 16:9 & konten yang kepanjangan di-scroll di dalam kotaknya, bukan
                      bikin kotaknya melar. */}
                  <div className="aspect-video overflow-y-auto bg-white border border-stone-300 shadow-sm">
                    <ReportBlockRenderer block={activeBlock} visualStyle={visualStyle} />
                  </div>
                </div>
              )}
              {!blocksLoading && !blocksError && !activeBlock && (
                <div className="max-w-2xl mx-auto text-center text-stone-400 text-xs font-bold py-16">
                  {tx("No page selected.", "Tidak ada halaman yang dipilih.")}
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
                {isActivePageEditable ? (
                  <RichTextEditor
                    value={getPageText(activePage)}
                    onChange={handleTextChange}
                    tx={tx}
                  />
                ) : (
                  <div className="flex-1 bg-stone-50 border border-stone-200 text-stone-500 text-xs font-medium p-6 rounded-xl text-center flex items-center justify-center">
                    {tx(
                      "This section is generated automatically from your data — there's no free-form text to edit here.",
                      "Bagian ini dibuat otomatis dari data laporan — tidak ada teks bebas untuk diedit di sini.",
                    )}
                  </div>
                )}
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
                blocks={blocks}
                visualStyle={visualStyle}
                blocksLoading={blocksLoading}
                blocksError={blocksError}
                tx={tx}
              />
            </div>
          )}
        </div>
      </div>

      {/* Shared Fullscreen Studio Modal */}
      <FullscreenStudioModal
        isOpen={isFullscreen}
        onClose={closeFullscreen}
        reportTitle={report?.title || tx("Untitled report", "Untitled report")}
        dataType={report?.data_type || tx("Unknown", "Unknown")}
        activePage={activePage}
        setActivePage={setActivePage}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
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
        visualStyle={visualStyle}
        blocksLoading={blocksLoading}
        blocksError={blocksError}
        inputFile={report?.input_file_name || "-"}
        tx={tx}
      />
    </div>
  );
}
