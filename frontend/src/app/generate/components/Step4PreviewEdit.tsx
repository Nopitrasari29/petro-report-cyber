import React from "react";
import ScrollReveal from "@/components/ScrollReveal";
import ReportChartPanel from "./ReportChartPanel";
import ChartNarasiLayout from "./ChartNarasiLayout";
import RichTextEditor from "./RichTextEditor";
import FullscreenStudioModal from "./FullscreenStudioModal";
import { REPORT_SECTIONS } from "@/utils/reportSections";

const LAST_PAGE = REPORT_SECTIONS[REPORT_SECTIONS.length - 1].page;

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
  chartCaptions?: string[];
  headerTitle?: string;
  headerSubtitle?: string;
  themeColor?: string;
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
  chartCaptions = [],
  headerTitle = "PT PETROKIMIA GRESIK",
  headerSubtitle = "Sistem Otomasi Laporan & Eksekutif Presentasi Berbasis AI",
  themeColor = "green",
  getPageText,
  getPageTitle,
  handleTextChange,
  handleSaveEdits,
  onBack,
  onNext,
  tx,
}: Step4PreviewEditProps) {
  const [previewFormat, setPreviewFormat] = React.useState<"pdf" | "pptx">("pdf");
  const [zoomLevel, setZoomLevel] = React.useState<number>(100);
  const [isFullscreen, setIsFullscreen] = React.useState<boolean>(false);

  // Theme color map untuk preview (sama dengan export_pdf.py)
  const themeMap: Record<string, { primary: string; accent: string }> = {
    green: { primary: "#004D25", accent: "#d9a700" },
    navy:  { primary: "#0F172A", accent: "#38BDF8" },
    dark:  { primary: "#111827", accent: "#818CF8" },
    gold:  { primary: "#78350F", accent: "#F59E0B" },
  };
  const { primary: primaryColor, accent: accentColor } = themeMap[themeColor] ?? themeMap.green;

  React.useEffect(() => {
    if (activePage && previewFormat === "pdf") {
      const el = document.getElementById(`step-pdf-section-${activePage}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  }, [activePage, previewFormat]);

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
            {REPORT_SECTIONS.map((sec) => (
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
              {tx("Page", "Page")} {activePage} {tx("of", "of")} {LAST_PAGE}
            </span>
            <button
              disabled={activePage === LAST_PAGE}
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
                title={tx("Fullscreen Edit/Preview Mode", "Mode Layar Penuh Edit/Preview")}
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
              transform: zoomLevel !== 100 ? `scale(${zoomLevel / 100})` : "none",
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

                 {/* MODE 1: PDF DOCUMENT VIEW (A4 Portrait) */}
                {previewFormat === "pdf" && (
                  <div className="border border-stone-300 rounded-lg p-6 shadow-lg bg-white max-w-lg mx-auto flex flex-col justify-between min-h-[580px] animate-fadeIn text-left font-sans max-h-[550px] overflow-y-auto scroll-smooth">
                    <div className="space-y-4">
                      {/* Official PDF Document Header Kop — DINAMIS sesuai pilihan user */}
                      <div
                        className="pb-3 flex justify-between items-center"
                        style={{ borderBottom: `3px solid ${primaryColor}` }}
                      >
                        <div>
                          <h3
                            className="text-base font-black tracking-tight m-0"
                            style={{ color: primaryColor }}
                          >
                            {headerTitle}
                          </h3>
                          <p
                            className="text-[9px] font-extrabold uppercase tracking-wider mt-0.5"
                            style={{ color: accentColor }}
                          >
                            {headerSubtitle}
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
                        {reportDetails?.title || "SOC Executive Summary"}
                      </h2>

                      {/* Metadata Block Table */}
                      <table className="w-full text-[10px] text-stone-600 border-collapse">
                        <tbody>
                          <tr>
                            <td className="font-extrabold text-stone-400 uppercase w-28 py-0.5">Jenis Data:</td>
                            <td className="font-extrabold text-stone-800 uppercase">{reportDetails?.data_type || "FIREWALL"}</td>
                          </tr>
                          <tr>
                            <td className="font-extrabold text-stone-400 uppercase py-0.5">Tanggal Cetak:</td>
                            <td className="font-extrabold text-stone-800">{new Date().toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" })}</td>
                          </tr>
                          <tr>
                            <td className="font-extrabold text-stone-400 uppercase py-0.5">Berkas Sumber:</td>
                            <td className="font-mono font-bold text-stone-700">{reportDetails?.input_file_name || "-"}</td>
                          </tr>
                        </tbody>
                      </table>

                      {/* Confidentiality Notice Alert Box */}
                      <div className="bg-stone-50 border-l-4 border-[#d9a700] p-3 rounded-r-lg text-[9.5px] text-stone-600 leading-relaxed font-medium">
                        <strong className="text-stone-900 font-bold block mb-0.5">Pemberitahuan Kerahasiaan siber:</strong>
                        Dokumen ini berisi rekaman aktivitas operasional keamanan siber internal PT Petrokimia Gresik. Dilarang keras menyebarluaskan isi laporan ini di luar otoritas SOC.
                      </div>

                      {/* Section 1: Executive Summary */}
                      <div id="step-pdf-section-01" className={`p-4 rounded-xl transition-all duration-300 ${activePage === "01" ? "bg-emerald-50/80 border-2 border-petro-green shadow-sm ring-2 ring-emerald-200" : "border border-stone-150"}`}>
                        <h4 className="text-xs font-black text-[#004D25] border-b border-stone-150 pb-1 flex items-center justify-between">
                          <span>1. Ringkasan Eksekutif (Executive Summary)</span>
                          {activePage === "01" && <span className="text-[9px] bg-petro-green text-white px-2 py-0.5 rounded-full font-extrabold">Active Section</span>}
                        </h4>
                        <p className="text-[10px] text-stone-700 mt-2 font-medium leading-relaxed whitespace-pre-wrap">
                          {getPageText("01")}
                        </p>
                      </div>

                      {/* Section 2: Visualisasi Data Analitik — Layout 2-kolom Chart + Narasi */}
                      <div id="step-pdf-section-02" className={`p-4 rounded-xl transition-all duration-300 ${activePage === "02" ? "bg-emerald-50/80 border-2 border-petro-green shadow-sm ring-2 ring-emerald-200" : "border border-stone-150"}`}>
                        <h4
                          className="text-xs font-black border-b border-stone-150 pb-1 mb-3 flex items-center justify-between"
                          style={{ color: primaryColor }}
                        >
                          <span>2. Visualisasi Data & Infografis Analitik</span>
                          {activePage === "02" && <span className="text-[9px] bg-petro-green text-white px-2 py-0.5 rounded-full font-extrabold">Active Section</span>}
                        </h4>
                        {/* 2-kolom: kiri chart, kanan narasi AI per chart */}
                        <ChartNarasiLayout
                          reportId={reportDetails?.id}
                          chartCaptions={chartCaptions}
                          tx={tx}
                        />
                      </div>

                      {/* Section 3: Trend Analysis */}
                      <div id="step-pdf-section-03" className={`p-4 rounded-xl transition-all duration-300 ${activePage === "03" ? "bg-emerald-50/80 border-2 border-petro-green shadow-sm ring-2 ring-emerald-200" : "border border-stone-150"}`}>
                        <h4 className="text-xs font-black text-[#004D25] border-b border-stone-150 pb-1 flex items-center justify-between">
                          <span>3. Analisis Tren Ancaman (Trend Analysis)</span>
                          {activePage === "03" && <span className="text-[9px] bg-petro-green text-white px-2 py-0.5 rounded-full font-extrabold">Active Section</span>}
                        </h4>
                        <p className="text-[10px] text-stone-700 mt-2 font-medium leading-relaxed whitespace-pre-wrap">
                          {getPageText("03")}
                        </p>
                      </div>

                      {/* Section 4: Severity Analysis */}
                      <div id="step-pdf-section-04" className={`p-4 rounded-xl transition-all duration-300 ${activePage === "04" ? "bg-emerald-50/80 border-2 border-petro-green shadow-sm ring-2 ring-emerald-200" : "border border-stone-150"}`}>
                        <h4 className="text-xs font-black text-[#004D25] border-b border-stone-150 pb-1 flex items-center justify-between">
                          <span>4. Analisis Tingkat Keparahan (Severity Analysis)</span>
                          {activePage === "04" && <span className="text-[9px] bg-petro-green text-white px-2 py-0.5 rounded-full font-extrabold">Active Section</span>}
                        </h4>
                        <p className="text-[10px] text-stone-700 mt-2 font-medium leading-relaxed whitespace-pre-wrap">
                          {getPageText("04")}
                        </p>
                      </div>

                      {/* Section 5: Risk Assessment */}
                      <div id="step-pdf-section-05" className={`p-4 rounded-xl transition-all duration-300 ${activePage === "05" ? "bg-emerald-50/80 border-2 border-petro-green shadow-sm ring-2 ring-emerald-200" : "border border-stone-150"}`}>
                        <h4 className="text-xs font-black text-[#004D25] border-b border-stone-150 pb-1 flex items-center justify-between">
                          <span>5. Penilaian Risiko (Risk Assessment)</span>
                          {activePage === "05" && <span className="text-[9px] bg-petro-green text-white px-2 py-0.5 rounded-full font-extrabold">Active Section</span>}
                        </h4>
                        <p className="text-[10px] text-stone-700 mt-2 font-medium leading-relaxed whitespace-pre-wrap">
                          {getPageText("05")}
                        </p>
                      </div>

                      {/* Section 6: Recommendations & Conclusion */}
                      <div id="step-pdf-section-06" className={`p-4 rounded-xl transition-all duration-300 ${activePage === "06" ? "bg-emerald-50/80 border-2 border-petro-green shadow-sm ring-2 ring-emerald-200" : "border border-stone-150"}`}>
                        <h4 className="text-xs font-black text-[#004D25] border-b border-stone-150 pb-1 flex items-center justify-between">
                          <span>6. Kesimpulan & Rekomendasi</span>
                          {activePage === "06" && <span className="text-[9px] bg-petro-green text-white px-2 py-0.5 rounded-full font-extrabold">Active Section</span>}
                        </h4>
                        <p className="text-[10px] text-stone-700 mt-2 font-medium leading-relaxed whitespace-pre-wrap">
                          {getPageText("06")}
                        </p>
                      </div>
                    </div>

                    {/* Page Footer */}
                    <div className="flex justify-between items-center border-t border-stone-200 pt-3 mt-6 text-[8px] text-stone-400">
                      <span className="font-bold uppercase tracking-wider">
                        {tx("PT Petrokimia Gresik • SOC Security Reports", "PT Petrokimia Gresik • SOC Security Reports")}
                      </span>
                    </div>
                  </div>
                )}

                {/* MODE 2: PPTX PRESENTATION SLIDE VIEW (16:9 Landscape Widescreen matching export_ppt.py 1-to-1) */}
                {previewFormat === "pptx" && (
                  <div className="max-w-lg mx-auto border-2 border-stone-300 rounded-2xl shadow-xl bg-white aspect-[16/9] flex flex-col justify-between text-left relative animate-fadeIn overflow-hidden font-sans p-6">
                     {activePage === "01" ? (
                      /* Slide 1: Cover Slide — Dinamis sesuai tema dan kop header */
                      <div className="h-full flex flex-col justify-between relative">
                        {/* Top Accent Bar (warna tema) */}
                        <div
                          className="absolute -top-6 -left-6 -right-6 h-3"
                          style={{ backgroundColor: primaryColor }}
                        />

                        {/* Top Header Logo */}
                        <div className="flex justify-between items-start pt-2">
                          <div />
                          <img
                            src="/LOGO_PETRO_DANANTARA.png"
                            alt="Logo Petrokimia"
                            className="h-9 w-auto object-contain"
                          />
                        </div>

                        {/* Cover Title Box */}
                        <div className="my-auto space-y-2 pl-2">
                          <h4
                            className="text-xs font-black tracking-wide uppercase"
                            style={{ color: primaryColor }}
                          >
                            {headerTitle}
                          </h4>
                          <h2
                            className="text-xl font-black leading-tight"
                            style={{ color: primaryColor }}
                          >
                            {reportDetails?.title || "Executive Summary"}
                          </h2>
                          <p className="text-[10.5px] font-black pt-1" style={{ color: accentColor }}>
                            {headerSubtitle} | Laporan {(reportDetails?.data_type || "DATA").toUpperCase()} |{" "}
                            {new Date().toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" })}
                          </p>
                        </div>

                        {/* Cover Slide Footer */}
                        <div className="flex justify-between items-center border-t border-stone-200 pt-2 text-[8px] font-bold text-stone-400">
                          <span>{headerTitle} • Operations</span>
                          <span className="font-extrabold text-stone-700">Slide 01 of {LAST_PAGE}</span>
                        </div>
                      </div>
                    ) : activePage === "02" ? (
                      /* Slide 2: Visualisasi Chart + Narasi AI — 2-kolom seperti PPTX export */
                      <div className="h-full flex flex-col justify-between relative overflow-y-auto">
                        <div>
                          <div
                            className="flex justify-between items-start border-b pb-2 mb-2"
                            style={{ borderColor: `${primaryColor}30` }}
                          >
                            <div>
                              <h3 className="text-sm font-black m-0" style={{ color: primaryColor }}>
                                Visualisasi Data & Infografis Analitik
                              </h3>
                              <div className="w-12 h-1 rounded mt-1" style={{ backgroundColor: accentColor }} />
                            </div>
                            <img
                              src="/LOGO_PETRO_DANANTARA.png"
                              alt="Logo Petrokimia"
                              className="h-6 w-auto object-contain"
                            />
                          </div>
                          {/* Layout 2-kolom Chart + Narasi AI */}
                          <ChartNarasiLayout
                            reportId={reportDetails?.id}
                            chartCaptions={chartCaptions}
                            tx={tx}
                          />
                        </div>
                        <div className="flex justify-between items-center border-t border-stone-200 pt-2 mt-2 text-[8px] font-bold text-stone-400">
                          <span>{headerTitle} • Operations</span>
                          <span className="font-extrabold text-stone-700">Slide {activePage} of {LAST_PAGE}</span>
                        </div>
                      </div>
                    ) : (
                      /* Content Slide Layout (Slide 3+) */
                      <div className="h-full flex flex-col justify-between relative">
                        {/* Slide Header */}
                        <div
                          className="flex justify-between items-start border-b pb-2"
                          style={{ borderColor: `${primaryColor}20` }}
                        >
                          <div>
                            <h3 className="text-sm font-black m-0" style={{ color: primaryColor }}>
                              {getPageTitle(activePage)}
                            </h3>
                            <div className="w-12 h-1 rounded mt-1" style={{ backgroundColor: accentColor }} />
                          </div>
                          <img
                            src="/LOGO_PETRO_DANANTARA.png"
                            alt="Logo Petrokimia"
                            className="h-6 w-auto object-contain"
                          />
                        </div>

                        {/* Content Box with Left Accent Bar */}
                        <div className="my-auto flex items-stretch gap-3 pl-1 pr-2 py-2 flex-1 overflow-y-auto">
                          <div className="w-1 rounded shrink-0" style={{ backgroundColor: primaryColor }} />
                          <p className="text-[10.5px] text-stone-700 font-medium leading-relaxed whitespace-pre-wrap">
                            {getPageText(activePage)}
                          </p>
                        </div>

                        {/* Content Slide Footer */}
                        <div className="flex justify-between items-center border-t border-stone-200 pt-2 text-[8px] font-bold text-stone-400">
                          <span>{headerTitle} • Operations</span>
                          <span className="font-extrabold text-stone-700">Slide {activePage} of {LAST_PAGE}</span>
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
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-black text-stone-755 uppercase tracking-wider">
                    {tx("Chart Visualization & Insight Narasi", "Chart Visualization & Insight Narasi")}
                  </h4>
                  <span className="text-[10px] bg-amber-50 text-amber-700 px-2 py-0.5 rounded-full font-bold border border-amber-200">
                    💡 AI Chart Captions
                  </span>
                </div>

                {/* Chart + Narasi side-by-side layout */}
                <ChartNarasiLayout
                  reportId={reportDetails?.id}
                  chartCaptions={chartCaptions}
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
      {/* Fullscreen Studio Modal */}
      <FullscreenStudioModal
        isOpen={isFullscreen}
        onClose={() => setIsFullscreen(false)}
        reportTitle={reportDetails?.title}
        dataType={reportDetails?.data_type || "DATA"}
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
        reportId={reportDetails?.id}
        chartCaptions={chartCaptions}
        headerTitle={headerTitle}
        headerSubtitle={headerSubtitle}
        themeColor={themeColor}
        inputFile={reportDetails?.input_file_name || "-"}
        tx={tx}
      />
    </ScrollReveal>
  );
}
