"use client";

import { useState, useEffect, use } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import Sidebar from "@/components/Sidebar";
import Navbar from "@/components/Navbar";
import { t, getLanguage } from "@/utils/i18n";

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

export default function ReportDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const resolvedParams = use(params);
  const reportId = resolvedParams?.id;

  const [report, setReport] = useState<ReportDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");

  const [lang, setLang] = useState("English");
  useEffect(() => {
    setLang(getLanguage());
    const handleLangChange = () => {
      setLang(getLanguage());
    };
    window.addEventListener("ui_language_changed", handleLangChange);
    return () => {
      window.removeEventListener("ui_language_changed", handleLangChange);
    };
  }, []);

  // Editor states
  const [editedSummary, setEditedSummary] = useState<Record<string, any>>({});
  const [activeTab, setActiveTab] = useState<"preview" | "edit" | "charts">("preview");
  const [activePage, setActivePage] = useState("01");
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Initialize and check for ?edit=true search param
  useEffect(() => {
    if (searchParams.get("edit") === "true") {
      setActiveTab("edit");
    }
  }, [searchParams]);

  // Load report detail on mount
  useEffect(() => {
    if (!reportId) return;

    const loadReportDetails = async () => {
      setLoading(true);
      setErrorMsg("");
      try {
        const token = localStorage.getItem("token");
        const headers: Record<string, string> = {};
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }

        const res = await fetch(`http://localhost:8000/api/v1/history/${reportId}`, {
          headers,
        });

        if (res.status === 401 || res.status === 403) {
          router.push("/login");
          return;
        }

        if (!res.ok) {
          throw new Error("Gagal mengambil detail riwayat laporan.");
        }

        const data = await res.json();
        setReport(data);
        setEditedSummary(data.ai_summary || {});
      } catch (err: any) {
        console.error(err);
        setErrorMsg(err.message || "Terjadi kesalahan koneksi.");
      } finally {
        setLoading(false);
      }
    };

    loadReportDetails();
  }, [reportId]);

  // Formatting date string
  const formatDateString = (dtStr: string) => {
    if (!dtStr) return "-";
    const d = new Date(dtStr);
    return d.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  };

  // Sections navigation mapping
  const getPageTitle = (page: string) => {
    switch (page) {
      case "01": return "Executive Summary";
      case "02": return "Threat Overview";
      case "03": return "Attack Summary";
      case "04": return "VAPT Summary";
      case "05": return "Bandwidth Summary";
      case "06": return "Threat Hunting";
      case "07": return "Conclusion & Recommendation";
      default: return "Executive Summary";
    }
  };

  const getPageContentKey = (page: string) => {
    switch (page) {
      case "01": return "executive_summary";
      case "02": return "threat_overview";
      case "03": return "attack_summary";
      case "04": return "vapt_summary";
      case "05": return "bandwidth_monitoring";
      case "06": return "threat_hunting";
      case "07": return "conclusion_recommendation";
      default: return "executive_summary";
    }
  };

  // Get active text
  const getPageText = (page: string) => {
    const key = getPageContentKey(page);
    const text = editedSummary[key];
    if (Array.isArray(text)) return text.join("\n");
    if (text) return text;
    
    // Fallbacks
    switch (page) {
      case "01": return "Executive Summary:\n\nDuring this monthly operational cycle, the security posture of Petrokimia Gresik has been monitored continuously. Overall security alert levels remained within stable parameters, with a small increase in traffic volume matching seasonal operations. Threat mitigation filters blocked multiple scanning attempts automatically, maintaining corporate uptime.";
      case "02": return "Threat Overview:\n\nThe most prevalent threat vectors observed were brute force login attempts and automated port scanning. Most security sensors operated within SLA, successfully blocking unauthorized probes on external interfaces.";
      case "03": return "Attack Summary:\n\nSeverity analysis shows a concentration of Low to Medium threats. Critical issues were restricted to known testing ranges and external scans which were mitigated by standard perimeter firewalls.";
      case "04": return "VAPT Summary:\n\nThe regular vulnerability scan showed no critical unpatched network vulnerabilities. A few high-level web service exposures were flagged and scheduled for remediation.";
      case "05": return "Bandwidth Summary:\n\nDaily bandwidth monitoring shows normal business traffic peaks. Security bandwidth consumption by tunnels and SIEM log forwarding was optimized within acceptable limits.";
      case "06": return "Threat Hunting:\n\nProactive threat hunting focused on outdated SSL/TLS handshakes and internal segment anomalous queries. No active compromises or lateral movements were detected.";
      case "07": return "Conclusion & Recommendation:\n\nWe recommend updating firewall filtering rules for known malicious scanning subnets and proceeding with patch deployment for external staging environments.";
      default: return "Content not available.";
    }
  };

  const handleTextChange = (newVal: string) => {
    const key = getPageContentKey(activePage);
    const originalVal = editedSummary[key];
    if (Array.isArray(originalVal)) {
      setEditedSummary({
        ...editedSummary,
        [key]: newVal.split("\n").filter(line => line.trim() !== "")
      });
    } else {
      setEditedSummary({
        ...editedSummary,
        [key]: newVal
      });
    }
  };

  // Save manual modifications back to db
  const handleSaveEdits = async () => {
    if (!reportId) return;
    setIsSaving(true);
    setSaveSuccess(false);
    try {
      const token = localStorage.getItem("token");
      const authHeaders: Record<string, string> = {
        "Content-Type": "application/json"
      };
      if (token) {
        authHeaders["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch(`http://localhost:8000/api/v1/analysis/${reportId}`, {
        method: "PUT",
        headers: authHeaders,
        body: JSON.stringify({
          ai_summary: editedSummary
        })
      });
      if (res.ok) {
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 2000);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDownloadPDF = () => {
    window.open(`http://localhost:8000/api/v1/history/${reportId}/pdf`, "_blank");
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-petro-bg-warm flex">
        <Sidebar />
        <div className="flex-1 pl-64 flex flex-col min-h-screen">
          <Navbar />
          <main className="flex-1 flex flex-col items-center justify-center text-stone-500 gap-3">
            <svg className="animate-spin h-8 w-8 text-petro-green" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span className="text-xs font-bold">{t("Loading report details...")}</span>
          </main>
        </div>
      </div>
    );
  }

  if (errorMsg || !report) {
    return (
      <div className="min-h-screen bg-petro-bg-warm flex">
        <Sidebar />
        <div className="flex-1 pl-64 flex flex-col min-h-screen">
          <Navbar />
          <main className="flex-1 p-8 max-w-4xl mx-auto w-full text-center">
            <div className="bg-red-50 border border-red-200 text-red-750 px-4 py-3 rounded-xl text-xs font-medium text-left">
              <strong>Error:</strong> {t(errorMsg || "Laporan tidak ditemukan.")}
            </div>
            <Link
              href="/history"
              className="mt-4 inline-flex items-center gap-2 text-stone-600 hover:text-petro-green font-bold text-xs"
            >
              {t("Back to History")}
            </Link>
          </main>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-petro-bg-warm flex">
      {/* Sidebar Navigation */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 pl-64 flex flex-col min-h-screen">
        <Navbar />

        {/* Main Body */}
        <main className="flex-1 p-8 max-w-6xl mx-auto w-full space-y-6">
          {/* Breadcrumb back navigation */}
          <div className="text-left">
            <Link
              href="/history"
              className="text-stone-400 hover:text-stone-600 font-bold text-[10px] tracking-wide flex items-center gap-1.5 transition-colors uppercase"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor" className="w-3 h-3">
                <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
              </svg>
              {t("Back to History")}
            </Link>
          </div>

          {/* Header Row */}
          <div className="flex justify-between items-center">
            <div className="text-left">
              <h2 className="text-2xl font-extrabold text-stone-900">{report.title}</h2>
              {/* Metadata Info Bar */}
              <div className="flex flex-wrap gap-5 text-[10px] font-bold text-stone-500 mt-2">
                <span className="flex items-center gap-1.5">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5 text-stone-400">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5m-9-6h.008v.008H12v-.008ZM12 15h.008v.008H12V15Zm0 2.25h.008v.008H12v-.008ZM9.75 15h.008v.008H9.75V15Zm0 2.25h.008v.008H9.75v-.008ZM7.5 15h.008v.008H7.5V15Zm0 2.25h.008v.008H7.5v-.008Zm6.75-4.5h.008v.008h-.008v-.008Zm0 2.25h.008v.008h-.008V15Zm0 2.25h.008v.008h-.008v-.008Zm2.25-4.5h.008v.008H16.5v-.008Zm0 2.25h.008v.008H16.5V15Z" />
                  </svg>
                  {t("Period:")} <strong>{formatDateString(report.period_start)} - {formatDateString(report.period_end)}</strong>
                </span>
                <span className="flex items-center gap-1.5">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5 text-stone-400">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                  </svg>
                  {t("Generated On:")} <strong>{formatDateString(report.created_at)}</strong>
                </span>
                <span className="flex items-center gap-1.5">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5 text-stone-400">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                  </svg>
                  {t("Format:")} <strong>{report.output_format || "PDF"}</strong>
                </span>
                <span className="flex items-center gap-1.5">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5 text-stone-400">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
                  </svg>
                  {t("Size:")} <strong>27.5 MB</strong>
                </span>
              </div>
            </div>
            
            {/* Download PDF button */}
            <button
              onClick={handleDownloadPDF}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-petro-green hover:bg-petro-green-hover text-white font-extrabold text-sm shadow-md transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              {t("Download")}
            </button>
          </div>

          {/* 3-Panel Split Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mt-4">
            
            {/* Left Sidebar Panel - Pages Navigation */}
            <div className="lg:col-span-3 bg-white border border-stone-200/85 rounded-2xl p-4 shadow-sm flex flex-col justify-between h-[520px]">
              <div>
                <h3 className="font-extrabold text-stone-900 text-sm border-b border-stone-100 pb-3 flex justify-between items-center cursor-pointer">
                  <span>{t("Pages")}</span>
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-stone-500">
                    <path fillRule="evenodd" d="M14.77 12.79a.75.75 0 0 1-1.06-.02L10 8.832 6.29 12.77a.75.75 0 1 1-1.08-1.04l4.25-4.5a.75.75 0 0 1 1.08 0l4.25 4.5a.75.75 0 0 1-.02 1.06Z" clipRule="evenodd" />
                  </svg>
                </h3>
                
                <div className="mt-4 space-y-2">
                  {["01", "02", "03", "04", "05", "06", "07"].map((page) => (
                    <button
                      key={page}
                      onClick={() => setActivePage(page)}
                      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border transition-all text-left ${
                        activePage === page
                           ? "bg-stone-50 border-stone-200 text-stone-900 font-extrabold shadow-sm"
                           : "border-transparent text-stone-500 hover:bg-stone-50/50 hover:text-stone-700 font-bold"
                      }`}
                    >
                      <span className="text-[10px] uppercase font-black text-stone-400">{page}</span>
                      <span className="text-[11px] truncate">{t(getPageTitle(page))}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Sidebar Pagination Footer */}
              <div className="flex justify-between items-center pt-3 border-t border-stone-100">
                <button
                  onClick={() => setActivePage((prev) => String(Math.max(Number(prev) - 1, 1)).padStart(2, "0"))}
                  disabled={activePage === "01"}
                  className="p-2 rounded-xl border border-stone-200 hover:bg-stone-50 disabled:opacity-40 transition-colors bg-white shadow-sm"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-stone-600">
                    <path fillRule="evenodd" d="M11.78 5.22a.75.75 0 0 1 0 1.06L8.06 10l3.72 3.72a.75.75 0 1 1-1.06 1.06l-4.25-4.25a.75.75 0 0 1 0-1.06l4.25-4.25a.75.75 0 0 1 1.06 0Z" clipRule="evenodd" />
                  </svg>
                </button>
                <span className="text-[10px] font-black text-stone-500">
                  {t("Page")} {Number(activePage)} {t("of")} 7
                </span>
                <button
                  onClick={() => setActivePage((prev) => String(Math.min(Number(prev) + 1, 7)).padStart(2, "0"))}
                  disabled={activePage === "07"}
                  className="p-2 rounded-xl border border-stone-200 hover:bg-stone-50 disabled:opacity-40 transition-colors bg-white shadow-sm"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-stone-600">
                    <path fillRule="evenodd" d="M8.22 5.22a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.75.75 0 0 1-1.06-1.06L11.94 10 8.22 6.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Center Area - Tabs & Content Preview */}
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
                      {tab === "edit" ? t("Edit Text") : t(tab)}
                    </button>
                  ))}
                </div>
                
                {/* 100% Zoom badge */}
                <div className="flex items-center gap-1.5">
                  <span className="px-2 py-1 bg-white border border-stone-200 text-stone-500 font-extrabold text-[10px] rounded-lg shadow-sm flex items-center gap-1 cursor-pointer">
                    100%
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={3} stroke="currentColor" className="w-2.5 h-2.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                    </svg>
                  </span>
                  <span className="p-1 bg-white border border-stone-200 text-stone-500 rounded-lg shadow-sm cursor-pointer hover:bg-stone-50">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.2} stroke="currentColor" className="w-3.5 h-3.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75v4.5m0-4.5h-4.5m4.5 0L15 9m5.25 11.25v-4.5m0 4.5h-4.5m4.5 0-5.25-5.25" />
                    </svg>
                  </span>
                </div>
              </div>

              {/* Tab Contents */}
              <div className="flex-1 overflow-y-auto p-6 bg-[#EFECE5]/60">
                
                {/* PREVIEW TAB */}
                {activeTab === "preview" && (
                  <div className="max-w-[420px] mx-auto bg-white border border-stone-200/80 rounded-lg shadow p-6 min-h-[580px] text-left relative flex flex-col justify-between">
                    <div>
                      {/* Document Kop */}
                      <div className="flex justify-between items-start border-b border-stone-150 pb-4">
                        <img src="/soc-logo.png" alt="Petrokimia Logo" className="w-20 h-auto object-contain" />
                        <span className="text-[10px] font-black text-amber-500 uppercase tracking-widest mt-1">
                          {t("SOC Executive Summary")}
                        </span>
                      </div>
                      
                      {/* Document Title */}
                      <h4 className="text-lg font-black text-stone-850 mt-6 leading-tight">
                        {t("Monthly Security Operations Summary")}
                      </h4>
                      <p className="text-[10px] text-amber-600 font-extrabold mt-1">July 2026</p>
                      
                      {/* Section heading & Narrative content */}
                      <div className="mt-6">
                        <h5 className="text-xs font-black text-stone-850 border-b border-stone-100 pb-1.5 capitalize">
                          {t(getPageTitle(activePage))}
                        </h5>
                        <p className="text-[10px] text-stone-600 mt-3 font-semibold leading-relaxed whitespace-pre-wrap">
                          {getPageText(activePage)}
                        </p>
                      </div>

                      {/* Key Highlights box on page 01 */}
                      {activePage === "01" && (
                        <div className="mt-6 bg-stone-50/80 border border-stone-200/60 rounded-xl p-4">
                          <h6 className="text-[10px] font-black text-stone-800 uppercase tracking-wide">{t("Key Highlights")}</h6>
                          <div className="grid grid-cols-2 gap-3 mt-3">
                            <div className="bg-white border border-stone-150 p-2.5 rounded-lg">
                              <span className="text-[8px] font-bold text-stone-400 uppercase flex items-center gap-1">
                                <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse"></span>
                                {t("Total Reports")}
                              </span>
                              <div className="text-base font-black text-stone-850 mt-1">{report.total_records_parsed ?? 26}</div>
                              <span className="text-[8px] text-emerald-600 font-bold mt-1 block">18.2% {t("vs last month")}</span>
                            </div>
                            <div className="bg-white border border-stone-150 p-2.5 rounded-lg">
                              <span className="text-[8px] font-bold text-stone-400 uppercase flex items-center gap-1">
                                <span className="w-1.5 h-1.5 rounded-full bg-red-600"></span>
                                {t("Critical Incidents")}
                              </span>
                              <div className="text-base font-black text-stone-850 mt-1">{report.threat_count_critical ?? 18}</div>
                              <span className="text-[8px] text-red-650/80 font-bold mt-1 block">12.0% {t("vs last month")}</span>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Footer Kop */}
                    <div className="flex justify-between items-center text-[8px] font-bold text-stone-400 border-t border-stone-100 pt-4 mt-8">
                      <span>{t("AI Security Reports")}</span>
                      <span>{t("Page")} {activePage}</span>
                    </div>
                  </div>
                )}

                {/* EDIT TEXT TAB */}
                {activeTab === "edit" && (
                  <div className="w-full h-full flex flex-col justify-between text-left space-y-4">
                    <div className="flex-1 min-h-[300px] flex flex-col">
                      <label className="text-[11px] font-black text-stone-700 uppercase tracking-wider mb-2">
                        {t("Modify Section Narrative AI")} ({t(getPageTitle(activePage))})
                      </label>
                      <textarea
                        value={getPageText(activePage)}
                        onChange={(e) => handleTextChange(e.target.value)}
                        className="w-full flex-1 p-4 border border-stone-200 rounded-2xl focus:outline-none focus:border-petro-green text-xs font-semibold leading-relaxed text-stone-800 shadow-sm"
                        placeholder={t("Write dynamic logs narration...")}
                      />
                    </div>
                    
                    {/* Action buttons save edits */}
                    <div className="flex items-center gap-4">
                      <button
                        onClick={handleSaveEdits}
                        disabled={isSaving}
                        className="px-5 py-2.5 rounded-xl bg-petro-green hover:bg-petro-green-hover text-white font-extrabold text-xs shadow-md transition-colors flex items-center gap-2 disabled:opacity-60"
                      >
                        {isSaving ? (
                          <>
                            <svg className="animate-spin h-3.5 w-3.5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            {t("Saving...")}
                          </>
                        ) : (
                          t("Save Changes")
                        )}
                      </button>

                      {saveSuccess && (
                        <span className="text-xs text-emerald-600 font-extrabold flex items-center gap-1 animate-fade-in">
                          ✓ {t("Saved Successfully!")}
                        </span>
                      )}
                    </div>
                  </div>
                )}

                {/* CHARTS TAB */}
                {activeTab === "charts" && (
                  <div className="w-full max-w-[450px] mx-auto bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm text-left">
                    <h5 className="font-extrabold text-stone-855 text-xs border-b border-stone-100 pb-3 uppercase tracking-wide">
                      {t("Severity Threat Incidents Distribution")}
                    </h5>
                    
                    {/* Beautiful SVG charts representation */}
                    <div className="mt-6 flex flex-col items-center">
                      <div className="w-full h-48 flex items-end justify-around border-b border-l border-stone-200/80 pb-2 pl-2">
                        {/* Critical bar */}
                        <div className="flex flex-col items-center w-12 group">
                          <span className="text-[10px] font-black text-red-600 mb-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            {report.threat_count_critical ?? 18}
                          </span>
                          <div
                            style={{ height: `${Math.min((report.threat_count_critical ?? 18) * 3, 130)}px` }}
                            className="w-7 bg-red-500 rounded-t-md hover:bg-red-600 transition-all cursor-pointer shadow-sm"
                          ></div>
                          <span className="text-[9px] font-bold text-stone-500 mt-2">{t("Critical")}</span>
                        </div>

                        {/* High bar */}
                        <div className="flex flex-col items-center w-12 group">
                          <span className="text-[10px] font-black text-amber-600 mb-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            {report.threat_count_high ?? 56}
                          </span>
                          <div
                            style={{ height: `${Math.min((report.threat_count_high ?? 56) * 1.5, 130)}px` }}
                            className="w-7 bg-amber-500 rounded-t-md hover:bg-amber-600 transition-all cursor-pointer shadow-sm"
                          ></div>
                          <span className="text-[9px] font-bold text-stone-500 mt-2">{t("High")}</span>
                        </div>

                        {/* Medium bar */}
                        <div className="flex flex-col items-center w-12 group">
                          <span className="text-[10px] font-black text-yellow-600 mb-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            {report.threat_count_medium ?? 102}
                          </span>
                          <div
                            style={{ height: `${Math.min((report.threat_count_medium ?? 102) * 0.8, 130)}px` }}
                            className="w-7 bg-yellow-400 rounded-t-md hover:bg-yellow-500 transition-all cursor-pointer shadow-sm"
                          ></div>
                          <span className="text-[9px] font-bold text-stone-500 mt-2">{t("Medium")}</span>
                        </div>

                        {/* Low bar */}
                        <div className="flex flex-col items-center w-12 group">
                          <span className="text-[10px] font-black text-emerald-600 mb-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            {report.threat_count_low ?? 210}
                          </span>
                          <div
                            style={{ height: `${Math.min((report.threat_count_low ?? 210) * 0.4, 130)}px` }}
                            className="w-7 bg-emerald-500 rounded-t-md hover:bg-emerald-600 transition-all cursor-pointer shadow-sm"
                          ></div>
                          <span className="text-[9px] font-bold text-stone-500 mt-2">{t("Low")}</span>
                        </div>
                      </div>
                    </div>

                    {/* Chart legends */}
                    <div className="grid grid-cols-2 gap-4 mt-6 text-[10px] font-bold text-stone-600 border-t border-stone-100 pt-4">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-red-500 shrink-0"></span>
                        <span>{t("Critical")}: {report.threat_count_critical ?? 18}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-amber-500 shrink-0"></span>
                        <span>{t("High")}: {report.threat_count_high ?? 56}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-yellow-400 shrink-0"></span>
                        <span>{t("Medium")}: {report.threat_count_medium ?? 102}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-emerald-50 shrink-0"></span>
                        <span>{t("Low")}: {report.threat_count_low ?? 210}</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Right Panel - Properties */}
            <div className="lg:col-span-3 bg-white border border-stone-200/85 rounded-2xl p-4 shadow-sm h-[520px]">
              <h3 className="font-extrabold text-stone-900 text-sm border-b border-stone-100 pb-3 flex justify-between items-center cursor-pointer">
                <span>{t("Properties")}</span>
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-stone-500">
                  <path fillRule="evenodd" d="M14.77 12.79a.75.75 0 0 1-1.06-.02L10 8.832 6.29 12.77a.75.75 0 1 1-1.08-1.04l4.25-4.5a.75.75 0 0 1 1.08 0l4.25 4.5a.75.75 0 0 1-.02 1.06Z" clipRule="evenodd" />
                </svg>
              </h3>
              
              <div className="mt-4 space-y-4 text-left">
                <div className="flex flex-col gap-1.5">
                  <label className="text-[10px] font-black text-stone-500 uppercase tracking-wider">{t("Language")}</label>
                  <div className="relative">
                    <select
                      value={report.language || "English"}
                      disabled
                      className="appearance-none w-full pl-3 pr-8 py-2 border border-stone-200 rounded-xl text-xs font-bold text-stone-700 bg-stone-50 cursor-not-allowed"
                    >
                      <option>{t("English")}</option>
                      <option>{t("Indonesian")}</option>
                    </select>
                    <span className="absolute inset-y-0 right-0 pr-2.5 flex items-center pointer-events-none text-stone-400">
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                      </svg>
                    </span>
                  </div>
                </div>
              </div>
            </div>

          </div>
        </main>
      </div>
    </div>
  );
}
