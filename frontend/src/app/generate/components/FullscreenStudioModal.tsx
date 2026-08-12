"use client";

import React, { useEffect, useRef } from "react";
import { getPageByNumber, type ReportPage } from "@/utils/reportSections";
import type { ReportBlock, VisualStyle } from "@/utils/reportTheme";
import RichTextEditor from "./RichTextEditor";
import ChartNarasiLayout from "./ChartNarasiLayout";
import ReportBlockRenderer from "@/components/ReportBlockRenderer";

interface FullscreenStudioModalProps {
  isOpen: boolean;
  onClose: () => void;
  reportTitle: string;
  dataType: string;
  activePage: string;
  setActivePage: (page: string) => void;
  activeTab: "preview" | "edit" | "charts";
  setActiveTab: (tab: "preview" | "edit" | "charts") => void;
  zoomLevel: number;
  setZoomLevel: (zoom: number) => void;
  getPageTitle: (page: string) => string;
  getPageText: (page: string) => string;
  handleTextChange: (val: string) => void;
  handleSaveEdits: () => void;
  isSaving: boolean;
  saveSuccess: boolean;
  pages: ReportPage[];
  blocks: ReportBlock[];
  visualStyle?: VisualStyle;
  blocksLoading: boolean;
  blocksError: string;
  inputFile?: string;
  tx: (key: string, fallback: string) => string;
}

export default function FullscreenStudioModal({
  isOpen,
  onClose,
  reportTitle,
  dataType,
  activePage,
  setActivePage,
  activeTab,
  setActiveTab,
  zoomLevel,
  setZoomLevel,
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
  inputFile = "-",
  tx,
}: FullscreenStudioModalProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const LAST_PAGE = pages.length > 0 ? pages[pages.length - 1].page : "01";
  const isActivePageEditable = getPageByNumber(pages, activePage)?.editable ?? false;
  // Preview cuma render 1 block aktif (bukan seluruh dokumen ditumpuk) — pages 1:1 urutan
  // dengan blocks (lihat buildPagesFromBlocks), jadi indexnya tinggal activePage - 1.
  const activeBlock = blocks[Number(activePage) - 1];

  // Fallback keydown listener for Escape — dipakai kalau browser TIDAK mendukung Fullscreen
  // API (requestFullscreen di bawah gagal/tidak tersedia), jadi modal ini masih bisa ditutup.
  // Kalau Fullscreen API sungguhan aktif, Escape sudah ditangani otomatis oleh browser lewat
  // listener "fullscreenchange" di bawah, jadi dua-duanya aman dipanggil bersamaan.
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Fullscreen API browser yang sesungguhnya (bukan cuma overlay CSS position:fixed seperti
  // sebelumnya) — supaya "Fullscreen Edit/Preview Mode" benar-benar keluar dari chrome browser,
  // bukan sekadar menutupi viewport. Kalau exit dipicu dari luar (tombol Esc bawaan browser,
  // atau user keluar fullscreen lewat OS), fullscreenchange menyinkronkan balik ke onClose().
  useEffect(() => {
    if (!isOpen) return;
    const el = containerRef.current;
    if (el?.requestFullscreen) {
      el.requestFullscreen().catch(() => {});
    }
    const handleFullscreenChange = () => {
      if (!document.fullscreenElement) {
        onClose();
      }
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
      if (document.fullscreenElement) {
        document.exitFullscreen().catch(() => {});
      }
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const textVal = getPageText(activePage);
  const wordCount = textVal ? textVal.trim().split(/\s+/).length : 0;
  const charCount = textVal ? textVal.length : 0;

  return (
    <div
      ref={containerRef}
      role="dialog"
      aria-modal="true"
      aria-label={tx("Report Studio", "Report Studio")}
      className="fixed inset-0 z-50 bg-stone-950 text-stone-100 flex flex-col animate-fadeIn overflow-hidden font-sans select-none"
    >
      {/* Top Header Bar - Studio Style */}
      <header className="h-16 bg-stone-900/90 backdrop-blur-xl border-b border-stone-800 px-6 flex items-center justify-between shrink-0 shadow-lg">
        {/* Left: Report Info & Brand */}
        <div className="flex items-center gap-4 min-w-0">
          <div className="flex items-center gap-2.5 px-3 py-1.5 bg-emerald-950/80 border border-emerald-500/30 rounded-xl text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-xs font-black tracking-wide uppercase">
              Focus Studio
            </span>
          </div>

          <div className="hidden sm:flex flex-col text-left truncate">
            <h1 className="text-sm font-extrabold text-white truncate max-w-xs md:max-w-md">
              {reportTitle || tx("Untitled report", "Untitled report")}
            </h1>
            <p className="text-[10px] text-stone-400 font-bold uppercase tracking-wider">
              {dataType} • {inputFile}
            </p>
          </div>
        </div>

        {/* Center: Segmented Control Tabs */}
        <div className="flex items-center bg-stone-950/80 p-1 rounded-xl border border-stone-800 shadow-inner">
          {(["preview", "edit", "charts"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-1.5 rounded-lg text-xs font-extrabold transition-all cursor-pointer capitalize ${
                activeTab === tab
                  ? "bg-petro-green text-white shadow-md shadow-petro-green/20"
                  : "text-stone-400 hover:text-stone-200 hover:bg-stone-800/50"
              }`}
            >
              {tab === "edit" ? tx("Edit Text", "Edit Text") : tx(tab, tab)}
            </button>
          ))}
        </div>

        {/* Right Action Tools: Save + Zoom + Close */}
        <div className="flex items-center gap-3">
          {/* Save Button */}
          {activeTab === "edit" && (
            <button
              onClick={handleSaveEdits}
              disabled={isSaving}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 bg-petro-green hover:bg-petro-green-hover text-white text-xs font-black rounded-xl shadow-lg shadow-petro-green/20 transition-all cursor-pointer disabled:opacity-50"
            >
              {isSaving ? (
                <div className="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
              ) : saveSuccess ? (
                <svg
                  className="w-4 h-4 text-white"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                >
                  <path
                    fillRule="evenodd"
                    d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z"
                    clipRule="evenodd"
                  />
                </svg>
              ) : (
                <svg
                  className="w-4 h-4 text-white"
                  viewBox="0 0 20 20"
                  fill="currentColor"
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

          {/* Zoom Level Selector */}
          <div className="relative inline-flex items-center bg-stone-800 hover:bg-stone-700/80 rounded-xl px-3 py-1.5 text-xs font-bold text-stone-200 transition-colors border border-stone-700">
            <select
              value={zoomLevel}
              onChange={(e) => setZoomLevel(Number(e.target.value))}
              className="bg-transparent text-xs font-extrabold text-stone-100 appearance-none pr-5 py-0.5 outline-none cursor-pointer"
            >
              <option value={50} className="bg-stone-900">
                50%
              </option>
              <option value={75} className="bg-stone-900">
                75%
              </option>
              <option value={100} className="bg-stone-900">
                100%
              </option>
              <option value={125} className="bg-stone-900">
                125%
              </option>
              <option value={150} className="bg-stone-900">
                150%
              </option>
              <option value={200} className="bg-stone-900">
                200%
              </option>
            </select>
            <svg
              className="w-3.5 h-3.5 absolute right-2.5 pointer-events-none text-stone-400"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M5.22 8.22a.75.75 0 0 1 1.06 0L10 11.94l3.72-3.72a.75.75 0 1 1 1.06 1.06l-4.25 4.25a.75.75 0 0 1-1.06 0L5.22 9.28a.75.75 0 0 1 0-1.06Z"
                clipRule="evenodd"
              />
            </svg>
          </div>

          {/* Close Studio Modal */}
          <button
            onClick={onClose}
            className="p-2 rounded-xl bg-stone-800 hover:bg-red-500/20 hover:text-red-400 text-stone-300 transition-colors cursor-pointer border border-stone-700"
            title={tx("Exit Fullscreen (Esc)", "Keluar Layar Penuh (Esc)")}
          >
            <svg
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              strokeWidth={2.2}
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 18L18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>
      </header>

      {/* Main Studio Body: Left Pages Sidebar + Center Canvas */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Pages Navigation Sidebar */}
        <aside className="w-64 bg-stone-900/80 border-r border-stone-800/80 p-4 shrink-0 hidden md:flex flex-col justify-between select-none">
          <div className="space-y-3">
            <h3 className="text-xs font-black text-stone-400 uppercase tracking-wider px-2">
              {tx("Pages & Sections", "Halaman & Section")}
            </h3>

            <div className="space-y-1">
              {pages.map((sec) => (
                <button
                  key={sec.page}
                  onClick={() => setActivePage(sec.page)}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer text-left ${
                    activePage === sec.page
                      ? "bg-petro-green/20 text-petro-green border border-petro-green/40 font-black shadow-sm"
                      : "text-stone-400 hover:bg-stone-800/60 hover:text-stone-200 border border-transparent"
                  }`}
                >
                  <span className="truncate">
                    {sec.page}. {tx(sec.title, sec.title)}
                  </span>
                  {activePage === sec.page && (
                    <span className="w-2 h-2 rounded-full bg-petro-green shrink-0" />
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Quick Page Prev/Next Bar */}
          <div className="flex items-center justify-between border-t border-stone-800 pt-3 text-xs font-bold text-stone-400">
            <button
              disabled={activePage === "01"}
              onClick={() => {
                const prev = String(Number(activePage) - 1).padStart(2, "0");
                setActivePage(prev);
              }}
              className="p-1 hover:text-white disabled:opacity-30 disabled:pointer-events-none cursor-pointer"
            >
              &lt; {tx("Prev", "Prev")}
            </button>
            <span>
              {activePage} / {LAST_PAGE}
            </span>
            <button
              disabled={activePage === LAST_PAGE}
              onClick={() => {
                const next = String(Number(activePage) + 1).padStart(2, "0");
                setActivePage(next);
              }}
              className="p-1 hover:text-white disabled:opacity-30 disabled:pointer-events-none cursor-pointer"
            >
              {tx("Next", "Next")} &gt;
            </button>
          </div>
        </aside>

        {/* Center Main Canvas Area */}
        <main className="flex-1 bg-stone-950 p-6 md:p-10 overflow-y-auto flex flex-col items-center justify-start scroll-smooth">
          <div
            className="w-full max-w-5xl transition-transform duration-200 ease-out"
            style={{
              transform:
                zoomLevel !== 100 ? `scale(${zoomLevel / 100})` : "none",
              transformOrigin: "top center",
            }}
          >
            {/* 1. PREVIEW MODE — blocks yang SAMA PERSIS dipakai backend untuk merender
                PDF/PPTX (build_report_blocks), identik dengan tab Preview non-fullscreen,
                supaya Focus Studio tidak lagi menampilkan struktur karangan terpisah. */}
            {activeTab === "preview" && (
              <div className="space-y-4">
                {blocksLoading && (
                  <div className="max-w-lg mx-auto flex items-center justify-center gap-2 py-16 text-stone-400">
                    <div className="w-4 h-4 border-2 border-stone-700 border-t-petro-green rounded-full animate-spin" />
                    <span className="text-xs font-bold">
                      {tx("Memuat preview...", "Memuat preview...")}
                    </span>
                  </div>
                )}
                {!blocksLoading && blocksError && (
                  <div className="max-w-lg mx-auto bg-red-950/40 border border-red-500/30 text-red-300 text-xs font-medium p-4 rounded-xl">
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
                  <div className="max-w-3xl mx-auto">
                    {/* BUG DIPERBAIKI (dilaporkan user): `h-auto` (kotak tumbuh melebihi 16:9
                        kalau konten butuh) dibalik lagi — itu bikin rasio kotak berubah-ubah
                        antar halaman, padahal file PPT/PDF sungguhan SELALU 16:9 tetap (lihat
                        catatan di atas). `aspect-video` tanpa `h-auto` = tinggi kotak SELALU
                        persis 16:9; `overflow-y-auto` di kotak INI SENDIRI (bukan cuma di
                        <main> pembungkus) supaya konten yang kepanjangan untuk 16:9 di-scroll
                        di dalam kotaknya, bukan meluber keluar bentuk kotak atau bikin kotaknya
                        melar. Kotak berukuran tetap (16:9 dalam max-w-3xl) jadi scroll ganda
                        dgn <main> nyaris tidak pernah kejadian dalam praktiknya. */}
                    <div className="aspect-video overflow-y-auto bg-white border border-stone-800 shadow-2xl shadow-black/80">
                      <ReportBlockRenderer block={activeBlock} visualStyle={visualStyle} />
                    </div>
                  </div>
                )}
                {!blocksLoading && !blocksError && !activeBlock && (
                  <div className="max-w-lg mx-auto text-center text-stone-500 text-xs font-bold py-16">
                    {tx("No page selected.", "Tidak ada halaman yang dipilih.")}
                  </div>
                )}
              </div>
            )}

            {/* 2. EDIT TEXT MODE — Studio Full Focus Editor */}
            {activeTab === "edit" && (
              <div className="bg-white rounded-3xl p-8 sm:p-10 shadow-2xl shadow-black/70 border border-stone-800 text-stone-900 text-left space-y-6 max-w-4xl mx-auto">
                <div className="flex flex-wrap items-center justify-between border-b border-stone-150 pb-4 gap-2">
                  <div>
                    <span className="text-[10px] font-black uppercase tracking-wider text-emerald-700 bg-emerald-50 border border-emerald-200 px-3 py-1 rounded-full">
                      ✏️ Studio Rich Text Editor
                    </span>
                    <h2 className="text-xl font-black text-stone-900 mt-2">
                      {activePage}. {getPageTitle(activePage)}
                    </h2>
                  </div>

                  <div className="flex items-center gap-4 text-xs font-bold text-stone-400">
                    <span>
                      {wordCount} {tx("words", "kata")}
                    </span>
                    <span>•</span>
                    <span>
                      {charCount} {tx("chars", "karakter")}
                    </span>
                  </div>
                </div>

                {/* Expanded Rich Text Editor Canvas */}
                {isActivePageEditable ? (
                  <div className="min-h-[420px] text-stone-900">
                    <RichTextEditor
                      value={textVal}
                      onChange={handleTextChange}
                      tx={tx}
                    />
                  </div>
                ) : (
                  <div className="bg-stone-50 border border-stone-200 text-stone-500 text-xs font-medium p-6 rounded-xl text-center">
                    {tx(
                      "This section is generated automatically from your data — there's no free-form text to edit here.",
                      "Bagian ini dibuat otomatis dari data laporan — tidak ada teks bebas untuk diedit di sini.",
                    )}
                  </div>
                )}
              </div>
            )}

            {/* 3. CHARTS MODE */}
            {activeTab === "charts" && (
              <div className="space-y-6 max-w-5xl mx-auto text-left">
                <div className="flex items-center justify-between bg-stone-900 p-5 rounded-2xl border border-stone-800">
                  <div>
                    <h3 className="text-sm font-black text-white uppercase tracking-wider">
                      {tx(
                        "Chart Visualization & Insight Narasi",
                        "Chart Visualization & Insight Narasi",
                      )}
                    </h3>
                    <p className="text-xs text-stone-400 mt-0.5 font-medium">
                      {tx(
                        "Visualisasi grafik beserta narasi analisis AI berdampingan.",
                        "Visualisasi grafik beserta narasi analisis AI berdampingan.",
                      )}
                    </p>
                  </div>
                  <span className="text-xs bg-amber-950/80 text-amber-300 border border-amber-500/40 px-3 py-1 rounded-full font-bold">
                    💡 AI Chart Captions
                  </span>
                </div>

                <div className="bg-white p-6 rounded-3xl shadow-2xl border border-stone-800">
                  <ChartNarasiLayout
                    blocks={blocks}
                    visualStyle={visualStyle}
                    blocksLoading={blocksLoading}
                    blocksError={blocksError}
                    tx={tx}
                  />
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
