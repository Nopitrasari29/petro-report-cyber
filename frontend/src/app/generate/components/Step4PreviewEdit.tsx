import React from "react";
import ScrollReveal from "@/components/ScrollReveal";
import ChartNarasiLayout from "./ChartNarasiLayout";
import RichTextEditor from "./RichTextEditor";
import FullscreenStudioModal from "./FullscreenStudioModal";
import EditableReportTitle from "@/components/EditableReportTitle";
import ReportBlockRenderer from "@/components/ReportBlockRenderer";
import type { ReportBlock, VisualStyle } from "@/utils/reportTheme";
import { getPageByNumber, type ReportPage } from "@/utils/reportSections";

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
  blocks: ReportBlock[];
  visualStyle?: VisualStyle;
  blocksLoading: boolean;
  blocksError: string;
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
  blocks,
  visualStyle,
  blocksLoading,
  blocksError,
  getPageText,
  getPageTitle,
  handleTextChange,
  handleSaveEdits,
  onBack,
  onNext,
  onRenameTitle,
  tx,
}: Step4PreviewEditProps) {
  const [zoomLevel, setZoomLevel] = React.useState<number>(100);
  const [isFullscreen, setIsFullscreen] = React.useState<boolean>(false);
  // useCallback (bukan arrow function inline di JSX) — lihat catatan panjang di CenterPreviewPanel.tsx:
  // referensi onClose yang berubah tiap render (mis. tiap klik halaman lain) memicu useEffect
  // fullscreen di FullscreenStudioModal jalan ulang & modalnya diam-diam tertutup sendiri.
  const closeFullscreen = React.useCallback(() => setIsFullscreen(false), []);

  // Sinkronisasi tinggi panel "Pages" MENGIKUTI tinggi kartu Preview (bukan sebaliknya) —
  // BUG NYATA YANG DIPERBAIKI (dilaporkan user, disertai screenshot): CSS grid/flex `stretch`
  // biasa SELALU menyamakan ke yang PALING TINGGI di antara 2 kolom — kalau daftar Pages
  // (bisa 12+ halaman) lebih tinggi dari kotak Preview, itu malah menarik kartu Preview ikut
  // lebih tinggi dari kontennya sendiri (nyisa area putih kosong di bawah kotak preview).
  // Grid/flex TIDAK punya cara murni CSS untuk bilang "tinggi kolom A mengikuti kolom B doang,
  // B jangan ikut ditarik" — makanya di sini tinggi kartu Preview diukur lewat ResizeObserver
  // (elemen ini SENGAJA diberi `self-start` di JSX supaya tidak pernah ikut ditarik lebih
  // tinggi oleh stretch, jadi angka yang terukur SELALU tinggi natural kontennya sendiri),
  // lalu dipakai sebagai `max-height` utk kartu Pages — daftar di dalamnya scroll sendiri
  // (lihat min-h-0 di bawah) kalau tidak muat, alih-alih memaksa baris jadi lebih tinggi.
  const previewCardRef = React.useRef<HTMLDivElement>(null);
  const [previewCardHeight, setPreviewCardHeight] = React.useState<number | undefined>(
    undefined,
  );
  React.useEffect(() => {
    const el = previewCardRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        // entry.contentRect TIDAK termasuk padding & border (p-6 + border kartu ini ~50px) —
        // BUG DITEMUKAN saat pengujian: tanpa borderBoxSize, kartu Pages jadi ~50px lebih
        // pendek dari kartu Preview yang sebenarnya (cuma menyamai area KONTEN Preview,
        // bukan tinggi kotak penuhnya). borderBoxSize memberi tinggi kotak penuh yang benar.
        const borderBoxSize = entry.borderBoxSize?.[0];
        setPreviewCardHeight(
          borderBoxSize ? borderBoxSize.blockSize : entry.contentRect.height,
        );
      }
    });
    ro.observe(el, { box: "border-box" });
    return () => ro.disconnect();
  }, []);

  const isActivePageEditable = getPageByNumber(pages, activePage)?.editable ?? false;
  // Preview cuma render 1 block aktif (bukan seluruh dokumen ditumpuk) — pages 1:1 urutan
  // dengan blocks (lihat buildPagesFromBlocks), jadi indexnya tinggal activePage - 1.
  const activeBlock = blocks[Number(activePage) - 1];

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

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 text-left mt-6 items-start">
        {/* Left Panel: Pages List — tinggi kartu ini DIPAKU (height, dua arah: meregang kalau
            lebih pendek dari Preview, kepotong+scroll kalau lebih panjang) ke tinggi kartu
            Preview yang terukur lewat ResizeObserver di atas (lihat previewCardHeight),
            BUKAN lewat CSS grid stretch biasa (yang justru menarik Preview ikut lebih tinggi
            kalau daftar Pages lebih panjang — lihat catatan panjang di deklarasi
            previewCardHeight). Pagination di-mt-auto supaya tetap di dasar kartu. */}
        <div
          className="lg:col-span-3 bg-white rounded-2xl border border-stone-200/80 p-5 shadow-sm premium-card-hover transition-colors flex flex-col min-h-0"
          style={previewCardHeight ? { height: previewCardHeight } : undefined}
        >
          <h3 className="font-extrabold text-stone-855 text-sm border-b border-stone-100 pb-2 mb-4">
            {tx("Pages", "Pages")}
          </h3>

          {pages.length === 0 && (
            <div className="flex items-center gap-2 text-stone-400 text-xs font-bold py-4">
              <div className="w-3.5 h-3.5 border-2 border-stone-300 border-t-petro-green rounded-full animate-spin" />
              {tx("Memuat halaman...", "Memuat halaman...")}
            </div>
          )}

          {/* min-h-0 SENGAJA — tanpa ini, flexbox tetap memaksa div ini setinggi KONTENnya
              (daftar 12+ halaman) walau parent-nya sudah dibatasi max-height, mengabaikan
              overflow-y-auto di bawah sama sekali. Dengan min-h-0, div ini bisa menyusut
              lebih pendek dari kontennya & scroll-y beneran aktif begitu tidak muat. */}
          <div className="space-y-1.5 flex-1 min-h-0 overflow-y-auto">
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

          {/* Pagination Buttons — mt-auto memaku baris ini ke dasar kartu (bukan langsung
              menempel di bawah daftar), supaya kalau kartu jadi tinggi (stretch), pagination
              tetap di posisi paling bawah, bukan mengambang di tengah. */}
          <div className="flex justify-between items-center border-t border-stone-100 pt-3 mt-4 text-[10px] font-bold text-stone-400">
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
              {tx("Page", "Page")} {activePage} {tx("of", "of")} {pages.length > 0 ? pages[pages.length - 1].page : "01"}
            </span>
            <button
              disabled={pages.length === 0 || activePage === pages[pages.length - 1].page}
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

        {/* Center Panel: Preview & Edit Workspace (Expanded to 9 cols after removing Properties panel).
            ref di sini dipakai ResizeObserver (lihat previewCardHeight di atas) — grid diberi
            `items-start` supaya kartu ini SELALU tampil setinggi kontennya sendiri (tidak
            pernah ikut diregangkan lebih tinggi oleh kartu Pages), jadi angka yang terukur di
            sini selalu tinggi natural yang benar utk dijadikan acuan tinggi kartu Pages. */}
        <div
          ref={previewCardRef}
          className="lg:col-span-9 bg-white rounded-2xl border border-stone-200/80 p-6 shadow-sm space-y-6 premium-card-hover transition-colors"
        >
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
                {/* Loading / error states */}
                {blocksLoading && (
                  <div className="flex items-center justify-center gap-2 py-16 text-stone-400">
                    <div className="w-4 h-4 border-2 border-stone-300 border-t-petro-green rounded-full animate-spin" />
                    <span className="text-xs font-bold">
                      {tx("Memuat preview...", "Memuat preview...")}
                    </span>
                  </div>
                )}
                {!blocksLoading && blocksError && (
                  <div className="bg-red-50 border border-red-200 text-red-700 text-xs font-medium p-4 rounded-xl">
                    {blocksError}
                  </div>
                )}

                {/* Cuma 1 halaman aktif yang ditampilkan (bukan seluruh dokumen ditumpuk) —
                    dibungkus rasio 16:9 (ukuran slide asli, 13.333x7.5in — PDF & PPTX SAMA-SAMA
                    dirender sebagai "slide" berukuran identik, lihat _page() di export_pdf.py
                    dan SLIDE_W/SLIDE_H di export_ppt.py). SEBELUMNYA ada toggle "PDF Document
                    View / PPTX Slide View" di sini — dihapus karena preview ini SATU komponen
                    yang sama utk kedua format (ReportBlockRenderer), tidak pernah benar-benar
                    meniru salah satu file yang diunduh secara berbeda, jadi togglenya cuma
                    kosmetik tanpa bedanya sama sekali. Sebelumnya dibatasi max-w-lg (~512px)
                    walau kolom ini bisa jauh lebih lebar — dilepas SUPAYA kotak preview mengisi
                    lebar kolom yang tersedia (rasio 16:9 tetap sama, cuma skalanya membesar
                    mengikuti ruang asli, bukan dipaksa kecil lalu isinya di-scroll).

                    BUG DIPERBAIKI (dilaporkan user): sempat dicoba `h-auto` (kotak tumbuh lebih
                    tinggi kalau konten butuh lebih banyak ruang) supaya tidak ada yang terpotong
                    — tapi itu bikin RASIO kotak berubah-ubah per halaman (kadang 16:9, kadang
                    lebih tinggi), padahal file PPT/PDF sungguhan SELALU 13.333x7.5in (16:9)
                    tetap, tidak pernah "memanjang" mengikuti isi. Preview harus konsisten meniru
                    bentuk asli itu. Sekarang `aspect-video` TANPA `h-auto` (tinggi kotak SELALU
                    persis 16:9, tidak pernah berubah bentuk) + `overflow-y-auto` — konten yang
                    kepanjangan untuk muat di 16:9 di-scroll DI DALAM kotak (bukan bikin kotaknya
                    sendiri melar), karena preview React ini tidak meniru logika auto-shrink font
                    milik export_pdf.py/export_ppt.py yang sungguhan. */}
                {!blocksLoading && !blocksError && activeBlock && (
                  <div className="w-full">
                    <div className="aspect-video overflow-y-auto bg-white border border-stone-300 shadow-sm">
                      <ReportBlockRenderer block={activeBlock} visualStyle={visualStyle} />
                    </div>
                  </div>
                )}
                {!blocksLoading && !blocksError && !activeBlock && (
                  <div className="text-center text-stone-400 text-xs font-bold py-16">
                    {tx("No page selected.", "Tidak ada halaman yang dipilih.")}
                  </div>
                )}
              </div>
            )}

            {activeTab === "edit" && (
              <div className="space-y-4">
                {isActivePageEditable ? (
                  <>
                    <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider">
                      {tx("Edit Content", "Edit Content")}
                    </label>
                    <RichTextEditor
                      value={getPageText(activePage)}
                      onChange={handleTextChange}
                      tx={tx}
                    />
                  </>
                ) : (
                  <div className="max-w-lg mx-auto bg-stone-50 border border-stone-200 text-stone-500 text-xs font-medium p-6 rounded-xl text-center">
                    {tx(
                      "This section is generated automatically from your data — there's no free-form text to edit here.",
                      "Bagian ini dibuat otomatis dari data laporan — tidak ada teks bebas untuk diedit di sini.",
                    )}
                  </div>
                )}
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
                  visualStyle={visualStyle}
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
        onClose={closeFullscreen}
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
        inputFile={reportDetails?.input_file_name || "-"}
        tx={tx}
      />
    </ScrollReveal>
  );
}
