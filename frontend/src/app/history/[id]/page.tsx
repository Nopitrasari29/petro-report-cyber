"use client";

import { useState, useEffect, use } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import Sidebar from "@/components/Sidebar";
import Navbar from "@/components/Navbar";
import { t, getLanguage } from "@/utils/i18n";
import PagesSidebar from "./components/PagesSidebar";
import CenterPreviewPanel from "./components/CenterPreviewPanel";
import PropertiesPanel from "./components/PropertiesPanel";

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

export default function ReportDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);
  const tx = (key: string, fallback: string) => (mounted ? t(key) : fallback);

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
  const [activeTab, setActiveTab] = useState<"preview" | "edit" | "charts">(
    "preview",
  );
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

        const res = await fetch(
          `http://localhost:8000/api/v1/history/${reportId}`,
          {
            headers,
          },
        );

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
      case "01":
        return "Executive Summary";
      case "02":
        return "Threat Overview";
      case "03":
        return "Attack Summary";
      case "04":
        return "VAPT Summary";
      case "05":
        return "Bandwidth Summary";
      case "06":
        return "Threat Hunting";
      case "07":
        return "Conclusion & Recommendation";
      default:
        return "Executive Summary";
    }
  };

  const getPageContentKey = (page: string) => {
    switch (page) {
      case "01":
        return "executive_summary";
      case "02":
        return "threat_overview";
      case "03":
        return "attack_summary";
      case "04":
        return "vapt_summary";
      case "05":
        return "bandwidth_monitoring";
      case "06":
        return "threat_hunting";
      case "07":
        return "conclusion_recommendation";
      default:
        return "executive_summary";
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
      case "01":
        return "Executive Summary:\n\nDuring this monthly operational cycle, the security posture of Petrokimia Gresik has been monitored continuously. Overall security alert levels remained within stable parameters, with a small increase in traffic volume matching seasonal operations. Threat mitigation filters blocked multiple scanning attempts automatically, maintaining corporate uptime.";
      case "02":
        return "Threat Overview:\n\nThe most prevalent threat vectors observed were brute force login attempts and automated port scanning. Most security sensors operated within SLA, successfully blocking unauthorized probes on external interfaces.";
      case "03":
        return "Attack Summary:\n\nSeverity analysis shows a concentration of Low to Medium threats. Critical issues were restricted to known testing ranges and external scans which were mitigated by standard perimeter firewalls.";
      case "04":
        return "VAPT Summary:\n\nThe regular vulnerability scan showed no critical unpatched network vulnerabilities. A few high-level web service exposures were flagged and scheduled for remediation.";
      case "05":
        return "Bandwidth Summary:\n\nDaily bandwidth monitoring shows normal business traffic peaks. Security bandwidth consumption by tunnels and SIEM log forwarding was optimized within acceptable limits.";
      case "06":
        return "Threat Hunting:\n\nProactive threat hunting focused on outdated SSL/TLS handshakes and internal segment anomalous queries. No active compromises or lateral movements were detected.";
      case "07":
        return "Conclusion & Recommendation:\n\nWe recommend updating firewall filtering rules for known malicious scanning subnets and proceeding with patch deployment for external staging environments.";
      default:
        return "Content not available.";
    }
  };

  const handleTextChange = (newVal: string) => {
    const key = getPageContentKey(activePage);
    const originalVal = editedSummary[key];
    if (Array.isArray(originalVal)) {
      setEditedSummary({
        ...editedSummary,
        [key]: newVal.split("\n").filter((line) => line.trim() !== ""),
      });
    } else {
      setEditedSummary({
        ...editedSummary,
        [key]: newVal,
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
        "Content-Type": "application/json",
      };
      if (token) {
        authHeaders["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch(
        `http://localhost:8000/api/v1/analysis/${reportId}`,
        {
          method: "PUT",
          headers: authHeaders,
          body: JSON.stringify({
            ai_summary: editedSummary,
          }),
        },
      );
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

  const handleDownloadFile = async (format: "pdf" | "pptx") => {
    if (!reportId) return;
    const token = typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
      alert("Token akses tidak ditemukan. Silakan login ulang.");
      return;
    }

    try {
      const url = `http://localhost:8000/api/v1/history/${reportId}/${format}`;
      const res = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        let detail = `Gagal mengunduh file ${format.toUpperCase()}.`;
        try {
          const data = await res.json();
          detail = data.detail || detail;
        } catch {}
        alert(detail);
        return;
      }

      const blob = await res.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = `soc_report_${reportId}.${format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);
    } catch (err: any) {
      alert(err.message || "Terjadi kesalahan saat mengunduh file.");
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-petro-bg-warm flex">
        <Sidebar />
        <div className="flex-1 pl-64 flex flex-col min-h-screen">
          <Navbar />
          <main className="flex-1 flex flex-col items-center justify-center text-stone-500 gap-3">
            <svg
              className="animate-spin h-8 w-8 text-petro-green"
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
            <span className="text-xs font-bold">
              {tx("Loading report details...", "Loading report details...")}
            </span>
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
              <strong>Error:</strong> {errorMsg || "Laporan tidak ditemukan."}
            </div>
            <Link
              href="/history"
              className="mt-4 inline-flex items-center gap-2 text-stone-600 hover:text-petro-green font-bold text-xs"
            >
              {tx("Back to History", "Back to History")}
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
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={3}
                stroke="currentColor"
                className="w-3 h-3"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18"
                />
              </svg>
              {tx("Back to History", "Back to History")}
            </Link>
          </div>

          {/* Header Row */}
          <div className="flex justify-between items-center">
            <div className="text-left">
              <h2 className="text-2xl font-extrabold text-stone-900">
                {report.title}
              </h2>
              {/* Metadata Info Bar */}
              <div className="flex flex-wrap gap-5 text-[10px] font-bold text-stone-500 mt-2">
                <span className="flex items-center gap-1.5">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={2.5}
                    stroke="currentColor"
                    className="w-3.5 h-3.5 text-stone-400"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5m-9-6h.008v.008H12v-.008ZM12 15h.008v.008H12V15Zm0 2.25h.008v.008H12v-.008ZM9.75 15h.008v.008H9.75V15Zm0 2.25h.008v.008H9.75v-.008ZM7.5 15h.008v.008H7.5V15Zm0 2.25h.008v.008H7.5v-.008Zm6.75-4.5h.008v.008h-.008v-.008Zm0 2.25h.008v.008h-.008V15Zm0 2.25h.008v.008h-.008v-.008Zm2.25-4.5h.008v.008H16.5v-.008Zm0 2.25h.008v.008H16.5V15Z"
                    />
                  </svg>
                  {tx("Period:", "Period:")}{" "}
                  <strong>
                    {formatDateString(report.period_start)} -{" "}
                    {formatDateString(report.period_end)}
                  </strong>
                </span>
                <span className="flex items-center gap-1.5">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={2.5}
                    stroke="currentColor"
                    className="w-3.5 h-3.5 text-stone-400"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
                    />
                  </svg>
                  {tx("Generated On:", "Generated On:")}{" "}
                  <strong>{formatDateString(report.created_at)}</strong>
                </span>
                <span className="flex items-center gap-1.5">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={2.5}
                    stroke="currentColor"
                    className="w-3.5 h-3.5 text-stone-400"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
                    />
                  </svg>
                  {tx("Format:", "Format:")}{" "}
                  <strong>{report.output_format || "PDF"}</strong>
                </span>
                <span className="flex items-center gap-1.5">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={2.5}
                    stroke="currentColor"
                    className="w-3.5 h-3.5 text-stone-400"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z"
                    />
                  </svg>
                  {tx("Size:", "Size:")} <strong>27.5 MB</strong>
                </span>
              </div>
            </div>

            {/* Download PDF & PPTX action buttons */}
            <div className="flex items-center gap-2.5">
              <button
                onClick={() => handleDownloadFile("pdf")}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-petro-green hover:bg-petro-green-hover text-white font-extrabold text-xs shadow-md transition-all cursor-pointer"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2.5}
                  stroke="currentColor"
                  className="w-4 h-4"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"
                  />
                </svg>
                {tx("Download PDF", "Download PDF")}
              </button>

              <button
                onClick={() => handleDownloadFile("pptx")}
                className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-600 text-white font-extrabold text-xs shadow-md transition-all cursor-pointer"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2.5}
                  stroke="currentColor"
                  className="w-4 h-4"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"
                  />
                </svg>
                {tx("Download PPTX", "Download PPTX")}
              </button>
            </div>
          </div>

          {/* 3-Panel Split Layout */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mt-4">
            {/* Left Sidebar Panel - Pages Navigation */}
            <PagesSidebar
              activePage={activePage}
              setActivePage={setActivePage}
              getPageTitle={getPageTitle}
            />

            {/* Center Area - Tabs & Content Preview */}
            <CenterPreviewPanel
              activeTab={activeTab}
              setActiveTab={setActiveTab}
              activePage={activePage}
              report={report}
              getPageTitle={getPageTitle}
              getPageText={getPageText}
              handleTextChange={handleTextChange}
              handleSaveEdits={handleSaveEdits}
              isSaving={isSaving}
              saveSuccess={saveSuccess}
            />

            {/* Right Panel - Properties */}
            <PropertiesPanel report={report} />
          </div>
        </main>
      </div>
    </div>
  );
}
