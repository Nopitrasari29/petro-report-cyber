"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Sidebar from "@/components/Sidebar";
import Navbar from "@/components/Navbar";
import ScrollReveal from "@/components/ScrollReveal";
import { t, getLanguage } from "@/utils/i18n";
import { API_BASE_URL } from "@/utils/api";
import { sanitizeFilename, downloadBlobAsFile } from "@/utils/downloadFile";
import HistoryStatsCards from "./components/HistoryStatsCards";
import HistoryFilterBar from "./components/HistoryFilterBar";
import HistoryTable from "./components/HistoryTable";
import { ToastContainer } from "@/components/ToastModal";

interface ReportItem {
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
}

export default function ReportHistoryPage() {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);
  const tx = (key: string, fallback: string) => (mounted ? t(key) : fallback);

  const router = useRouter();
  const [reports, setReports] = useState<ReportItem[]>([]);
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

  // Filters & Search State
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("All Statuses");
  const [periodFilter, setPeriodFilter] = useState("Select Periods");
  const [sortOrder, setSortOrder] = useState("newest");

  // Pagination State
  const [currentPage, setCurrentPage] = useState(1);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  // Load Report History from Backend
  const fetchReports = async () => {
    setLoading(true);
    setErrorMsg("");
    try {
      const token = localStorage.getItem("token");
      const headers: Record<string, string> = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      // Fix #10: Server-side filtering — kirim parameter ke backend, bukan filter semua di client
      // Backend sudah mendukung ?search=&status=&skip=&limit= secara native
      const params = new URLSearchParams();
      params.set("limit", "100"); // Dynamic page load limit
      if (searchQuery) params.set("search", searchQuery);
      if (statusFilter && statusFilter !== "All Statuses") {
        // Map UI label ke backend status value (RCA-22: Konsistensi label Approved/Completed)
        const statusMap: Record<string, string> = {
          Completed: "analyzed",
          Approved: "analyzed",
          "In Review": "processing",
          Draft: "draft",
          Failed: "failed",
        };
        const backendStatus = statusMap[statusFilter];
        if (backendStatus) params.set("status", backendStatus);
      }

      const res = await fetch(
        `${API_BASE_URL}/api/v1/history/?${params.toString()}`,
        { headers },
      );

      if (res.status === 401 || res.status === 403) {
        router.push("/login");
        return;
      }

      if (!res.ok) {
        throw new Error("Gagal mengambil data riwayat laporan.");
      }

      const data = await res.json();
      setReports(data);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || "Terjadi kesalahan koneksi.");
    } finally {
      setLoading(false);
    }
  };

  // Fix #10: Re-fetch dari server setiap kali search query atau status filter berubah
  // Debounce 300ms untuk search supaya tidak hit API tiap keystroke
  useEffect(() => {
    const timer = setTimeout(() => {
      fetchReports();
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, statusFilter]);

  useEffect(() => {
    fetchReports();
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const urlSearch = params.get("search");
      if (urlSearch) {
        setSearchQuery(urlSearch);
      }
    }
  }, []);

  // Toast notification state
  const [toasts, setToasts] = useState<
    Array<{
      id: string;
      type: "success" | "error" | "info" | "warning";
      message: string;
    }>
  >([]);
  const addToast = (
    message: string,
    type: "success" | "error" | "info" | "warning" = "info",
  ) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  };
  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Delete Action handler
  const handleDelete = async (id: number) => {
    try {
      const token = localStorage.getItem("token");
      const headers: Record<string, string> = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch(`${API_BASE_URL}/api/v1/history/${id}`, {
        method: "DELETE",
        headers,
      });

      if (!res.ok) {
        throw new Error("Gagal menghapus laporan.");
      }

      addToast("Laporan berhasil dihapus dari riwayat.", "success");
      fetchReports();
    } catch (err: any) {
      addToast(err.message || "Gagal menghapus laporan.", "error");
    }
  };

  // Bulk Delete Action handler
  const handleBulkDelete = async (ids: number[]) => {
    try {
      const token = localStorage.getItem("token");
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch(`${API_BASE_URL}/api/v1/history/bulk-delete`, {
        method: "POST",
        headers,
        body: JSON.stringify(ids),
      });

      if (!res.ok) {
        throw new Error("Gagal menghapus beberapa laporan.");
      }

      addToast(`${ids.length} laporan berhasil dihapus.`, "success");
      fetchReports();
    } catch (err: any) {
      addToast(err.message || "Gagal menghapus beberapa laporan.", "error");
    }
  };

  // Retry AI Action handler
  const handleRetry = async (id: number) => {
    try {
      const token = localStorage.getItem("token");
      const headers: Record<string, string> = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch(`${API_BASE_URL}/api/v1/history/${id}/retry`, {
        method: "POST",
        headers,
      });

      if (!res.ok) {
        throw new Error("Gagal memicu ulang analisis AI.");
      }

      addToast("Analisis AI berhasil dipicu ulang di background.", "info");
      fetchReports();
    } catch (err: any) {
      addToast(err.message || "Gagal memicu ulang analisis AI.", "error");
    }
  };

  // Helper formatting dates
  const formatPeriod = (start: string, end: string) => {
    if (!start || !end) return "-";
    const parseMonthYear = (dateStr: string) => {
      const d = new Date(dateStr);
      return d.toLocaleDateString("en-US", { month: "long", year: "numeric" });
    };
    const startStr = parseMonthYear(start);
    const endStr = parseMonthYear(end);
    return startStr === endStr ? startStr : `${startStr} - ${endStr}`;
  };

  const formatDateString = (dtStr: string) => {
    if (!dtStr) return "-";
    const d = new Date(dtStr);
    return d.toLocaleDateString("en-GB", {
      day: "numeric",
      month: "long",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // Status mapping to display label & styling
  const getStatusDetails = (status: string) => {
    switch (status?.toLowerCase()) {
      case "completed":
      case "analyzed":
      case "approved":
        return {
          label: "Completed",
          classes: "bg-emerald-50 text-emerald-600 border border-emerald-200",
        };
      case "processing":
      case "in review":
        return {
          label: "In Review",
          classes: "bg-amber-50 text-amber-600 border border-amber-250",
        };
      case "draft":
      case "parsed":
        return {
          label: "Draft",
          classes: "bg-blue-50 text-blue-600 border border-blue-200",
        };
      case "failed":
        return {
          label: "Failed",
          classes: "bg-red-50 text-red-600 border border-red-200",
        };
      default:
        return {
          label: status || "Completed",
          classes: "bg-emerald-50 text-emerald-600 border border-emerald-200",
        };
    }
  };

  // Template/DataType mapping to dynamic display label
  const getDataTypeLabel = (item: any) => {
    if (!item) return tx("Unknown", "Unknown");
    if (typeof item === "string") {
      switch (item.toLowerCase()) {
        case "firewall":
          return "SOC Report";
        case "vapt":
          return "Threat Trend";
        case "email_security":
          return "Threat Hunting";
        case "ids_ips":
          return "IDS/IPS Report";
        default:
          return item || tx("Unknown", "Unknown");
      }
    }
    if (item.template_type) {
      const t = item.template_type.toLowerCase();
      if (t.includes("soc")) return "SOC Report";
      if (t.includes("threat")) return "Threat Trend";
      if (t.includes("email") || t.includes("phish")) return "Threat Hunting";
      if (t.includes("ids") || t.includes("ips")) return "IDS/IPS Report";
      return item.template_type;
    }
    switch (item.data_type?.toLowerCase()) {
      case "firewall":
        return "SOC Report";
      case "vapt":
        return "Threat Trend";
      case "email_security":
        return "Threat Hunting";
      case "ids_ips":
        return "IDS/IPS Report";
      default:
        return item.data_type || tx("Unknown", "Unknown");
    }
  };

  // Dynamic Statistics Calculation
  const totalCount = reports.length;
  const approvedCount = reports.filter(
    (r) =>
      r.status === "completed" ||
      r.status === "analyzed" ||
      r.status === "approved",
  ).length;
  const inReviewCount = reports.filter(
    (r) => r.status === "processing" || r.status === "in review",
  ).length;
  const draftCount = reports.filter(
    (r) => r.status === "draft" || r.status === "parsed",
  ).length;
  const exportedCount = reports.filter(
    (r) =>
      typeof r.output_format === "string" &&
      (r.output_format.includes("PDF") || r.output_format.includes("PPTX")),
  ).length;

  const approvedPercent = totalCount
    ? ((approvedCount / totalCount) * 100).toFixed(1)
    : "0.0";
  const inReviewPercent = totalCount
    ? ((inReviewCount / totalCount) * 100).toFixed(1)
    : "0.0";
  const draftPercent = totalCount
    ? ((draftCount / totalCount) * 100).toFixed(1)
    : "0.0";
  const exportedPercent = totalCount
    ? ((exportedCount / totalCount) * 100).toFixed(1)
    : "0.0";

  // Dynamic Period options extracted directly from user's report data
  const periodOptions = Array.from(
    new Set(
      reports
        .map((r) => formatPeriod(r.period_start, r.period_end))
        .filter((p) => p && p !== "N/A"),
    ),
  );

  // Filtered reports
  const filteredReports = reports.filter((item) => {
    // Search filter
    const searchLower = searchQuery.toLowerCase();
    const matchesSearch =
      !searchQuery ||
      item.title.toLowerCase().includes(searchLower) ||
      getDataTypeLabel(item).toLowerCase().includes(searchLower) ||
      (item.template_type &&
        item.template_type.toLowerCase().includes(searchLower)) ||
      (item.data_type && item.data_type.toLowerCase().includes(searchLower)) ||
      (item.status && item.status.toLowerCase().includes(searchLower)) ||
      getStatusDetails(item.status).label.toLowerCase().includes(searchLower) ||
      formatPeriod(item.period_start, item.period_end)
        .toLowerCase()
        .includes(searchLower) ||
      formatDateString(item.created_at).toLowerCase().includes(searchLower);

    // Status filter
    let matchesStatus = true;
    if (statusFilter !== "All Statuses") {
      const statusDetails = getStatusDetails(item.status);
      matchesStatus =
        statusDetails.label.toLowerCase() === statusFilter.toLowerCase();
    }

    // Period filter
    let matchesPeriod = true;
    if (
      periodFilter &&
      periodFilter !== "Select Periods" &&
      periodFilter !== "All Periods"
    ) {
      const pFormatted = formatPeriod(
        item.period_start,
        item.period_end,
      ).toLowerCase();
      const pTarget = periodFilter.toLowerCase();
      matchesPeriod =
        pFormatted.includes(pTarget) || pTarget.includes(pFormatted);
    }

    return matchesSearch && matchesStatus && matchesPeriod;
  });

  // Sorting reports based on sortOrder
  const sortedReports = [...filteredReports].sort((a, b) => {
    if (sortOrder === "oldest") {
      return (
        new Date(a.created_at || 0).getTime() -
        new Date(b.created_at || 0).getTime()
      );
    }
    if (sortOrder === "title_asc") {
      return (a.title || "").localeCompare(b.title || "");
    }
    if (sortOrder === "title_desc") {
      return (b.title || "").localeCompare(a.title || "");
    }
    // Default: newest
    return (
      new Date(b.created_at || 0).getTime() -
      new Date(a.created_at || 0).getTime()
    );
  });

  // Pagination logic
  const indexOfLastRow = currentPage * rowsPerPage;
  const indexOfFirstRow = indexOfLastRow - rowsPerPage;
  const currentRows = sortedReports.slice(indexOfFirstRow, indexOfLastRow);
  const totalPages = Math.ceil(sortedReports.length / rowsPerPage) || 1;

  const handleExportList = () => {
    // Export current filtered report set as CSV
    const headers =
      "Report Name,Period,Report Type,Created By,Status,Created At\n";
    const rows = filteredReports
      .map(
        (r) =>
          `"${r.title}","${formatPeriod(r.period_start, r.period_end)}","${getDataTypeLabel(
            r,
          )}","${r.created_by_name || tx("Analyst", "Analyst")}","${getStatusDetails(r.status).label}","${formatDateString(
            r.created_at,
          )}"`,
      )
      .join("\n");

    const blob = new Blob([headers + rows], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.setAttribute("href", url);
    a.setAttribute(
      "download",
      `soc_reports_history_${new Date().toISOString().slice(0, 10)}.csv`,
    );
    a.click();
  };

  const handleDownloadFile = async (id: number, format: "pdf" | "pptx") => {
    const token =
      typeof window !== "undefined" ? localStorage.getItem("token") : null;
    if (!token) {
      alert("Token akses tidak ditemukan. Silakan login ulang.");
      return;
    }

    try {
      const url = `${API_BASE_URL}/api/v1/history/${id}/${format}`;
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
      const reportTitle = reports.find((r) => r.id === id)?.title;
      const filenameBase = sanitizeFilename(reportTitle, `soc_report_${id}`);
      await downloadBlobAsFile(blob, `${filenameBase}.${format}`);
    } catch (err: any) {
      alert(err.message || "Terjadi kesalahan saat mengunduh file.");
    }
  };

  return (
    <div className="min-h-screen bg-petro-bg-warm flex">
      {/* Sidebar Navigation */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 pl-0 md:pl-64 flex flex-col min-h-screen">
        <Navbar />

        {/* Header Title Bar */}
        <main className="flex-1 p-4 sm:p-6 md:p-8 max-w-7xl mx-auto w-full space-y-6">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="text-left">
              <h1 className="text-2xl font-extrabold text-stone-900 tracking-tight">
                {tx("Report History", "Report History")}
              </h1>
              <p className="text-xs text-stone-500 font-semibold mt-1">
                {tx(
                  "Manage, search, preview, and download previously generated SOC reports.",
                  "Manage, search, preview, and download previously generated SOC reports.",
                )}
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={handleExportList}
                className="px-4 py-2.5 bg-white border border-stone-200 hover:bg-stone-50 text-stone-700 font-bold text-xs rounded-xl shadow-sm transition-all flex items-center gap-2 cursor-pointer"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                  className="w-4 h-4 text-stone-500"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"
                  />
                </svg>
                {tx("Export CSV", "Export CSV")}
              </button>

              <Link
                href="/generate"
                className="px-4 py-2.5 bg-petro-green hover:bg-petro-green-hover text-white font-bold text-xs rounded-xl shadow-md transition-all flex items-center gap-2"
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
                    d="M12 4.5v15m7.5-7.5h-15"
                  />
                </svg>
                {tx("New Report", "New Report")}
              </Link>
            </div>
          </div>

          {/* Metric Stats Cards Row */}
          <ScrollReveal animation="fadeInUp" delay={100}>
            <HistoryStatsCards
              totalCount={totalCount}
              approvedCount={approvedCount}
              inReviewCount={inReviewCount}
              draftCount={draftCount}
              exportedCount={exportedCount}
              approvedPercent={approvedPercent}
              inReviewPercent={inReviewPercent}
              draftPercent={draftPercent}
              exportedPercent={exportedPercent}
            />
          </ScrollReveal>

          {/* Table Container Card */}
          <ScrollReveal animation="fadeInUp" delay={200}>
            <div className="bg-white rounded-2xl border border-stone-200/80 shadow-sm overflow-hidden flex flex-col">
              <HistoryFilterBar
                searchQuery={searchQuery}
                setSearchQuery={setSearchQuery}
                statusFilter={statusFilter}
                setStatusFilter={setStatusFilter}
                periodFilter={periodFilter}
                setPeriodFilter={setPeriodFilter}
                periodOptions={periodOptions}
                sortOrder={sortOrder}
                setSortOrder={setSortOrder}
                setCurrentPage={setCurrentPage}
              />

              <HistoryTable
                loading={loading}
                filteredReports={filteredReports}
                currentRows={currentRows}
                rowsPerPage={rowsPerPage}
                setRowsPerPage={setRowsPerPage}
                currentPage={currentPage}
                setCurrentPage={setCurrentPage}
                totalPages={totalPages}
                indexOfFirstRow={indexOfFirstRow}
                indexOfLastRow={indexOfLastRow}
                getStatusDetails={getStatusDetails}
                formatPeriod={formatPeriod}
                getDataTypeLabel={getDataTypeLabel}
                formatDateString={formatDateString}
                handleDownloadFile={handleDownloadFile}
                handleDelete={handleDelete}
                handleBulkDelete={handleBulkDelete}
                handleRetry={handleRetry}
              />
            </div>
          </ScrollReveal>
        </main>
      </div>
      <ToastContainer toasts={toasts} onClose={removeToast} />
    </div>
  );
}
