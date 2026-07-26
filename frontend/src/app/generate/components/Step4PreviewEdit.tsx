import React from "react";
import ScrollReveal from "@/components/ScrollReveal";
import ReportChartPanel from "./ReportChartPanel";
import RichTextEditor from "./RichTextEditor";
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

  React.useEffect(() => {
    if (activePage && previewFormat === "pdf") {
      const el = document.getElementById(`step-pdf-section-${activePage}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    }
  }, [activePage, previewFormat]);

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
                  <div className="border border-stone-300 rounded-lg p-6 shadow-lg bg-white max-w-lg mx-auto flex flex-col justify-between min-h-[580px] animate-fadeIn text-left font-sans max-h-[550px] overflow-y-auto scroll-smooth">
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

                      {/* Section 2: Visualisasi Data Analitik */}
                      <div id="step-pdf-section-02" className={`p-4 rounded-xl transition-all duration-300 ${activePage === "02" ? "bg-emerald-50/80 border-2 border-petro-green shadow-sm ring-2 ring-emerald-200" : "border border-stone-150"}`}>
                        <h4 className="text-xs font-black text-[#004D25] border-b border-stone-150 pb-1 mb-2 flex items-center justify-between">
                          <span>2. Visualisasi Data Analitik</span>
                          {activePage === "02" && <span className="text-[9px] bg-petro-green text-white px-2 py-0.5 rounded-full font-extrabold">Active Section</span>}
                        </h4>
                        <ReportChartPanel reportId={reportDetails?.id} tx={tx} />
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
                            {reportDetails?.title || "SOC Executive Summary"}
                          </h2>
                          <p className="text-[10.5px] font-black text-[#d9a700] pt-1">
                            Sistem Otomasi Report SOC | Laporan {(reportDetails?.data_type || "FIREWALL").toUpperCase()} | {new Date().toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" })}
                          </p>
                        </div>

                        {/* Cover Slide Footer */}
                        <div className="flex justify-between items-center border-t border-stone-200 pt-2 text-[8px] font-bold text-stone-400">
                          <span>PT Petrokimia Gresik • SOC Operations</span>
                          <span className="font-extrabold text-stone-700">Slide 01 of {LAST_PAGE}</span>
                        </div>
                      </div>
                    ) : activePage === "02" ? (
                      /* Slide 2: Visualisasi Chart Slide */
                      <div className="h-full flex flex-col justify-between relative overflow-y-auto">
                        <div>
                          <div className="flex justify-between items-start border-b border-stone-150 pb-2 mb-2">
                            <div>
                              <h3 className="text-sm font-black text-[#004D25] m-0">
                                Visualisasi Data Analitik
                              </h3>
                              <div className="w-12 h-1 bg-[#d9a700] rounded mt-1"></div>
                            </div>
                            <img
                              src="/LOGO_PETRO_DANANTARA.png"
                              alt="Logo Petrokimia"
                              className="h-6 w-auto object-contain"
                            />
                          </div>
                          <ReportChartPanel reportId={reportDetails?.id} tx={tx} />
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
