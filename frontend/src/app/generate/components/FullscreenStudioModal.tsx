"use client";

import React, { useEffect } from "react";
import { REPORT_SECTIONS } from "@/utils/reportSections";
import RichTextEditor from "./RichTextEditor";
import ChartNarasiLayout from "./ChartNarasiLayout";

const LAST_PAGE = REPORT_SECTIONS[REPORT_SECTIONS.length - 1].page;

interface FullscreenStudioModalProps {
  isOpen: boolean;
  onClose: () => void;
  reportTitle: string;
  dataType: string;
  activePage: string;
  setActivePage: (page: string) => void;
  activeTab: "preview" | "edit" | "charts";
  setActiveTab: (tab: "preview" | "edit" | "charts") => void;
  previewFormat: "pdf" | "pptx";
  setPreviewFormat: (format: "pdf" | "pptx") => void;
  zoomLevel: number;
  setZoomLevel: (zoom: number) => void;
  getPageTitle: (page: string) => string;
  getPageText: (page: string) => string;
  handleTextChange: (val: string) => void;
  handleSaveEdits: () => void;
  isSaving: boolean;
  saveSuccess: boolean;
  reportId?: number | null;
  chartCaptions?: string[];
  headerTitle?: string;
  headerSubtitle?: string;
  themeColor?: string;
  inputFile?: string;
  createdAt?: string;
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
  previewFormat,
  setPreviewFormat,
  zoomLevel,
  setZoomLevel,
  getPageTitle,
  getPageText,
  handleTextChange,
  handleSaveEdits,
  isSaving,
  saveSuccess,
  reportId,
  chartCaptions = [],
  headerTitle = "PT PETROKIMIA GRESIK",
  headerSubtitle = "Sistem Otomasi Laporan & Eksekutif Presentasi Berbasis AI",
  themeColor = "green",
  inputFile = "-",
  createdAt,
  tx,
}: FullscreenStudioModalProps) {
  // Keydown listener for Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Theme color map
  const themeMap: Record<string, { primary: string; accent: string }> = {
    green: { primary: "#004D25", accent: "#d9a700" },
    navy: { primary: "#0F172A", accent: "#38BDF8" },
    dark: { primary: "#111827", accent: "#818CF8" },
    gold: { primary: "#78350F", accent: "#F59E0B" },
  };
  const { primary: primaryColor, accent: accentColor } =
    themeMap[themeColor] ?? themeMap.green;

  const textVal = getPageText(activePage);
  const wordCount = textVal ? textVal.trim().split(/\s+/).length : 0;
  const charCount = textVal ? textVal.length : 0;

  return (
    <div className="fixed inset-0 z-50 bg-stone-950 text-stone-100 flex flex-col animate-fadeIn overflow-hidden font-sans select-none">
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
          {/* Format Switcher if Preview */}
          {activeTab === "preview" && (
            <div className="hidden md:inline-flex p-1 bg-stone-950 rounded-xl border border-stone-800 gap-1">
              <button
                onClick={() => setPreviewFormat("pdf")}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-extrabold transition-all cursor-pointer ${
                  previewFormat === "pdf"
                    ? "bg-stone-800 text-white shadow-sm"
                    : "text-stone-400 hover:text-white"
                }`}
              >
                <span className="w-2 h-2 rounded-full bg-red-500" />
                PDF
              </button>
              <button
                onClick={() => setPreviewFormat("pptx")}
                className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-extrabold transition-all cursor-pointer ${
                  previewFormat === "pptx"
                    ? "bg-stone-800 text-white shadow-sm"
                    : "text-stone-400 hover:text-white"
                }`}
              >
                <span className="w-2 h-2 rounded-full bg-amber-500" />
                PPTX
              </button>
            </div>
          )}

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
              {REPORT_SECTIONS.map((sec) => (
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
            {/* 1. PREVIEW MODE */}
            {activeTab === "preview" && (
              <div className="space-y-6">
                {/* PDF Document Canvas */}
                {previewFormat === "pdf" && (
                  <div className="bg-white text-stone-900 rounded-2xl shadow-2xl shadow-black/80 border border-stone-800 p-8 sm:p-12 max-w-3xl mx-auto font-sans text-left space-y-6">
                    {/* Kop Header */}
                    <div
                      className="pb-4 flex justify-between items-center"
                      style={{ borderBottom: `3px solid ${primaryColor}` }}
                    >
                      <div>
                        <h3
                          className="text-2xl font-black tracking-tight m-0"
                          style={{ color: primaryColor }}
                        >
                          {headerTitle}
                        </h3>
                        <p
                          className="text-xs font-extrabold uppercase tracking-wider mt-1"
                          style={{ color: accentColor }}
                        >
                          {headerSubtitle}
                        </p>
                      </div>
                      <img
                        src="/LOGO_PETRO_DANANTARA.png"
                        alt="Logo Petrokimia"
                        className="h-14 w-auto object-contain"
                      />
                    </div>

                    {/* Document Title */}
                    <div>
                      <h2 className="text-3xl font-black text-stone-900 leading-tight">
                        {reportTitle ||
                          tx("Untitled report", "Untitled report")}
                      </h2>
                      <p className="text-xs text-stone-500 font-extrabold uppercase mt-1">
                        Tipe Data: {dataType} | Sumber: {inputFile}
                      </p>
                    </div>

                    {/* Section Box */}
                    <div className="space-y-6 pt-2">
                      <div className="p-6 rounded-2xl border border-stone-200 bg-stone-50/60 shadow-sm">
                        <h4
                          className="text-base font-black pb-3 border-b border-stone-200 flex items-center justify-between"
                          style={{ color: primaryColor }}
                        >
                          <span>
                            {activePage}. {getPageTitle(activePage)}
                          </span>
                          <span className="text-[10px] bg-emerald-100 text-emerald-800 px-2.5 py-0.5 rounded-full font-bold">
                            Focus Mode
                          </span>
                        </h4>
                        <p className="text-xs sm:text-sm text-stone-700 mt-4 font-medium leading-relaxed whitespace-pre-wrap">
                          {getPageText(activePage)}
                        </p>
                      </div>

                      {/* Include Chart 2-Col Layout for Section 02 */}
                      {activePage === "02" && (
                        <div className="p-6 rounded-2xl border border-stone-200 bg-white shadow-sm">
                          <ChartNarasiLayout
                            reportId={reportId}
                            chartCaptions={chartCaptions}
                            tx={tx}
                          />
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* PPTX Widescreen Presentation Slide Canvas */}
                {previewFormat === "pptx" && (
                  <div className="max-w-4xl mx-auto border-2 border-stone-800 rounded-2xl shadow-2xl shadow-black/80 bg-white aspect-[16/9] flex flex-col justify-between text-left p-8 font-sans text-stone-900">
                    <div
                      className="flex justify-between items-start border-b pb-3"
                      style={{ borderColor: `${primaryColor}30` }}
                    >
                      <div>
                        <h3
                          className="text-xl font-black m-0"
                          style={{ color: primaryColor }}
                        >
                          {activePage}. {getPageTitle(activePage)}
                        </h3>
                        <div
                          className="w-20 h-1.5 rounded-full mt-1"
                          style={{ backgroundColor: accentColor }}
                        />
                      </div>
                      <img
                        src="/LOGO_PETRO_DANANTARA.png"
                        alt="Logo Petrokimia"
                        className="h-9 w-auto object-contain"
                      />
                    </div>

                    {activePage === "02" ? (
                      <div className="my-auto overflow-y-auto max-h-[380px] p-2">
                        <ChartNarasiLayout
                          reportId={reportId}
                          chartCaptions={chartCaptions}
                          tx={tx}
                        />
                      </div>
                    ) : (
                      <div className="my-auto flex items-stretch gap-4 pl-3 pr-4 py-4">
                        <div
                          className="w-1.5 rounded-full shrink-0"
                          style={{ backgroundColor: primaryColor }}
                        />
                        <p className="text-sm text-stone-800 font-medium leading-relaxed whitespace-pre-wrap">
                          {getPageText(activePage)}
                        </p>
                      </div>
                    )}

                    <div className="flex justify-between items-center border-t border-stone-200 pt-3 text-xs font-bold text-stone-400">
                      <span>{headerTitle} • Fullscreen Widescreen View</span>
                      <span className="font-extrabold text-stone-700">
                        Slide {activePage} of {LAST_PAGE}
                      </span>
                    </div>
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
                <div className="min-h-[420px] text-stone-900">
                  <RichTextEditor
                    value={textVal}
                    onChange={handleTextChange}
                    tx={tx}
                  />
                </div>
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
                    reportId={reportId}
                    chartCaptions={chartCaptions}
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
