"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Sidebar from "@/components/Sidebar";
import Navbar from "@/components/Navbar";
import ScrollReveal from "@/components/ScrollReveal";
import { t, getLanguage } from "@/utils/i18n";

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
  const [typeFilter, setTypeFilter] = useState("All Types");
  const [periodFilter, setPeriodFilter] = useState("Select Periods");
  const [userFilter, setUserFilter] = useState("All Users");

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

      // Fetch all reports to calculate stats and perform flexible filtering
      const res = await fetch("http://localhost:8000/api/v1/history/?limit=200", {
        headers,
      });

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

  useEffect(() => {
    fetchReports();
  }, []);

  // Delete Action handler
  const handleDelete = async (id: number) => {
    if (!confirm("Apakah Anda yakin ingin menghapus laporan ini dari riwayat?")) {
      return;
    }
    try {
      const token = localStorage.getItem("token");
      const headers: Record<string, string> = {};
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const res = await fetch(`http://localhost:8000/api/v1/history/${id}`, {
        method: "DELETE",
        headers,
      });

      if (!res.ok) {
        throw new Error("Gagal menghapus laporan.");
      }

      // Refresh list
      fetchReports();
    } catch (err: any) {
      alert(err.message || "Gagal menghapus laporan.");
    }
  };

  // Helper formatting dates
  const formatPeriod = (start: string, end: string) => {
    if (!start || !end) return "July 2026";
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
      case "approved":
        return {
          label: "Completed",
          classes: "bg-emerald-50 text-emerald-600 border border-emerald-200",
        };
      case "analyzed":
      case "in review":
        return {
          label: "In Review",
          classes: "bg-amber-50 text-amber-600 border border-amber-250",
        };
      case "draft":
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
          label: status || "Draft",
          classes: "bg-stone-50 text-stone-600 border border-stone-200",
        };
    }
  };

  // DataType mapping to display label
  const getDataTypeLabel = (dataType: string) => {
    switch (dataType?.toLowerCase()) {
      case "firewall":
        return "SOC Report";
      case "vapt":
        return "Threat Trend";
      case "email_security":
        return "Threat Hunting";
      case "ids_ips":
        return "IDS/IPS Report";
      default:
        return dataType || "SOC Report";
    }
  };

  // Dynamic Statistics Calculation
  const totalCount = reports.length;
  const approvedCount = reports.filter(r => r.status === "completed").length;
  const inReviewCount = reports.filter(r => r.status === "analyzed" || r.status === "parsed").length;
  const draftCount = reports.filter(r => r.status === "draft").length;
  const exportedCount = approvedCount; // Statically equal to approved for demo consistency

  const approvedPercent = totalCount ? ((approvedCount / totalCount) * 100).toFixed(1) : "0.0";
  const inReviewPercent = totalCount ? ((inReviewCount / totalCount) * 100).toFixed(1) : "0.0";
  const draftPercent = totalCount ? ((draftCount / totalCount) * 100).toFixed(1) : "0.0";
  const exportedPercent = totalCount ? ((exportedCount / totalCount) * 100).toFixed(1) : "0.0";

  // Filtered reports
  const filteredReports = reports.filter((item) => {
    // Search filter
    const matchesSearch =
      item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      getDataTypeLabel(item.data_type).toLowerCase().includes(searchQuery.toLowerCase()) ||
      item.created_by_name?.toLowerCase().includes(searchQuery.toLowerCase());

    // Status filter
    let matchesStatus = true;
    if (statusFilter !== "All Statuses") {
      const statusDetails = getStatusDetails(item.status);
      matchesStatus = statusDetails.label.toLowerCase() === statusFilter.toLowerCase();
    }

    // Type filter
    let matchesType = true;
    if (typeFilter !== "All Types") {
      matchesType = getDataTypeLabel(item.data_type).toLowerCase() === typeFilter.toLowerCase();
    }

    // User filter
    let matchesUser = true;
    if (userFilter !== "All Users") {
      matchesUser = item.created_by_name === userFilter;
    }

    return matchesSearch && matchesStatus && matchesType && matchesUser;
  });

  // Unique list of creators for filter dropdown
  const creators = Array.from(new Set(reports.map(r => r.created_by_name).filter(Boolean)));

  // Pagination logic
  const indexOfLastRow = currentPage * rowsPerPage;
  const indexOfFirstRow = indexOfLastRow - rowsPerPage;
  const currentRows = filteredReports.slice(indexOfFirstRow, indexOfLastRow);
  const totalPages = Math.ceil(filteredReports.length / rowsPerPage) || 1;

  const handleExportList = () => {
    // Mock export list as CSV
    const headers = "Report Name,Period,Report Type,Created By,Status,Created At\n";
    const rows = filteredReports
      .map(
        (r) =>
          `"${r.title}","${formatPeriod(r.period_start, r.period_end)}","${getDataTypeLabel(
            r.data_type
          )}","${r.created_by_name || "Rafika"}","${getStatusDetails(r.status).label}","${formatDateString(
            r.created_at
          )}"`
      )
      .join("\n");
    
    const blob = new Blob([headers + rows], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.setAttribute("href", url);
    a.setAttribute("download", `soc_reports_history_${new Date().toISOString().slice(0, 10)}.csv`);
    a.click();
  };

  const handleDownloadPDF = (id: number) => {
    window.open(`http://localhost:8000/api/v1/history/${id}/pdf`, "_blank");
  };

  return (
    <div className="min-h-screen bg-petro-bg-warm flex">
      {/* Sidebar Navigation */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 pl-64 flex flex-col min-h-screen">
        <Navbar />

        {/* Main Body */}
        <main className="flex-1 p-8 max-w-6xl mx-auto w-full space-y-8">
          {/* Header section */}
          <div className="flex justify-between items-center animate-fadeInUp">
            <div className="text-left">
              <h2 className="text-2xl font-extrabold text-stone-900">{t("Report History")}</h2>
              <p className="text-sm text-stone-500 font-medium mt-1">
                {t("View, search, and manage all generated SOC reports.")}
              </p>
            </div>
            <button
              onClick={handleExportList}
              className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-petro-green hover:bg-petro-green-hover text-white font-extrabold text-sm shadow-md hover:shadow-lg transition-all duration-200 group"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
              </svg>
              {t("Export List")}
            </button>
          </div>

          {/* Error Message */}
          {errorMsg && (
            <div className="bg-red-50 border border-red-200 text-red-750 px-4 py-3 rounded-xl text-xs font-medium text-left">
              <strong>Error:</strong> {t(errorMsg)}
            </div>
          )}

          {/* Summary Stats Cards Grid */}
          <ScrollReveal animation="fadeInUp" delay={100}>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              {/* Total Reports */}
              <div className="bg-white border border-stone-200/80 rounded-2xl p-5 shadow-sm text-left flex flex-col justify-between premium-card-hover cursor-pointer">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="p-1.5 rounded-lg bg-stone-50 border border-stone-100 text-stone-500">
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                      </svg>
                    </span>
                    <span className="text-[10px] font-extrabold text-stone-500 uppercase tracking-wider">{t("Total Reports")}</span>
                  </div>
                  <div className="text-2xl font-black text-stone-850 mt-3">{totalCount}</div>
                </div>
                <div className="text-[10px] text-stone-400 font-bold mt-2">{t("All time")}</div>
              </div>

              {/* Approved */}
              <div className="bg-white border border-stone-200/80 rounded-2xl p-5 shadow-sm text-left flex flex-col justify-between premium-card-hover cursor-pointer">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="p-1.5 rounded-lg bg-emerald-50 border border-emerald-100 text-emerald-650">
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                      </svg>
                    </span>
                    <span className="text-[10px] font-extrabold text-stone-500 uppercase tracking-wider">{t("Approved")}</span>
                  </div>
                  <div className="text-2xl font-black text-stone-850 mt-3">{approvedCount}</div>
                </div>
                <div className="text-[10px] text-emerald-600 font-bold mt-2">{approvedPercent}% {t("of total")}</div>
              </div>

              {/* In Review */}
              <div className="bg-white border border-stone-200/80 rounded-2xl p-5 shadow-sm text-left flex flex-col justify-between premium-card-hover cursor-pointer">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="p-1.5 rounded-lg bg-sky-50 border border-sky-100 text-sky-655">
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                      </svg>
                    </span>
                    <span className="text-[10px] font-extrabold text-stone-500 uppercase tracking-wider">{t("In Review")}</span>
                  </div>
                  <div className="text-2xl font-black text-stone-850 mt-3">{inReviewCount}</div>
                </div>
                <div className="text-[10px] text-sky-600 font-bold mt-2">{inReviewPercent}% {t("of total")}</div>
              </div>

              {/* Draft */}
              <div className="bg-white border border-stone-200/80 rounded-2xl p-5 shadow-sm text-left flex flex-col justify-between premium-card-hover cursor-pointer">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="p-1.5 rounded-lg bg-amber-50 border border-amber-100 text-amber-600">
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125" />
                      </svg>
                    </span>
                    <span className="text-[10px] font-extrabold text-stone-500 uppercase tracking-wider">{t("Draft")}</span>
                  </div>
                  <div className="text-2xl font-black text-stone-850 mt-3">{draftCount}</div>
                </div>
                <div className="text-[10px] text-amber-600 font-bold mt-2">{draftPercent}% {t("of total")}</div>
              </div>

              {/* Exported */}
              <div className="bg-white border border-stone-200/80 rounded-2xl p-5 shadow-sm text-left flex flex-col justify-between premium-card-hover cursor-pointer">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="p-1.5 rounded-lg bg-purple-50 border border-purple-100 text-purple-600">
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 8.25H7.5a2.25 2.25 0 0 0-2.25 2.25v9a2.25 2.25 0 0 0 2.25 2.25h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25H15M9 12l3 3m0 0 3-3m-3 3V2.25" />
                      </svg>
                    </span>
                    <span className="text-[10px] font-extrabold text-stone-500 uppercase tracking-wider">{t("Exported")}</span>
                  </div>
                  <div className="text-2xl font-black text-stone-850 mt-3">{exportedCount}</div>
                </div>
                <div className="text-[10px] text-purple-600 font-bold mt-2">{exportedPercent}% {t("of total")}</div>
              </div>
            </div>
          </ScrollReveal>

          {/* Filters & Table Card Wrapper */}
          <ScrollReveal animation="fadeInUp" delay={200}>
            <div className="bg-white rounded-2xl border border-stone-200/80 shadow-sm overflow-hidden flex flex-col">
            {/* Filter Bar */}
            <div className="p-5 border-b border-stone-150 flex flex-wrap items-center justify-between gap-4">
              <div className="flex flex-wrap items-center gap-3 flex-1 min-w-[280px]">
                {/* Search query input */}
                <div className="relative flex-1 min-w-[240px]">
                  <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-stone-400">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-4 h-4">
                      <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.604 10.604Z" />
                    </svg>
                  </span>
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => {
                      setSearchQuery(e.target.value);
                      setCurrentPage(1);
                    }}
                    placeholder={t("Search report title, period, keyword....")}
                    className="w-full pl-9 pr-4 py-2 border border-stone-200 rounded-xl text-xs font-semibold focus:outline-none focus:border-petro-green text-stone-800 placeholder-stone-400 transition-colors"
                  />
                </div>

                {/* Status selector */}
                <div className="relative">
                  <select
                    value={statusFilter}
                    onChange={(e) => {
                      setStatusFilter(e.target.value);
                      setCurrentPage(1);
                    }}
                    className="appearance-none pl-3 pr-8 py-2 border border-stone-200 rounded-xl text-xs font-bold text-stone-700 bg-white focus:outline-none focus:border-petro-green cursor-pointer transition-colors"
                  >
                    <option value="All Statuses">{t("All Statuses")}</option>
                    <option value="Completed">{t("Completed")}</option>
                    <option value="Draft">{t("Draft")}</option>
                    <option value="In Review">{t("In Review")}</option>
                    <option value="Failed">{t("Failed")}</option>
                  </select>
                  <span className="absolute inset-y-0 right-0 pr-2.5 flex items-center pointer-events-none text-stone-500">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                    </svg>
                  </span>
                </div>

                {/* Report Type selector */}
                <div className="relative">
                  <select
                    value={typeFilter}
                    onChange={(e) => {
                      setTypeFilter(e.target.value);
                      setCurrentPage(1);
                    }}
                    className="appearance-none pl-3 pr-8 py-2 border border-stone-200 rounded-xl text-xs font-bold text-stone-700 bg-white focus:outline-none focus:border-petro-green cursor-pointer transition-colors"
                  >
                    <option value="All Types">{t("All Types")}</option>
                    <option value="SOC Report">{t("SOC Report")}</option>
                    <option value="Threat Trend">{t("Threat Trend")}</option>
                    <option value="Threat Hunting">{t("Threat Hunting")}</option>
                    <option value="IDS/IPS Report">{t("IDS/IPS Report")}</option>
                  </select>
                  <span className="absolute inset-y-0 right-0 pr-2.5 flex items-center pointer-events-none text-stone-500">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                    </svg>
                  </span>
                </div>

                {/* Period selector */}
                <div className="relative">
                  <select
                    value={periodFilter}
                    onChange={(e) => {
                      setPeriodFilter(e.target.value);
                      setCurrentPage(1);
                    }}
                    className="appearance-none pl-3 pr-8 py-2 border border-stone-200 rounded-xl text-xs font-bold text-stone-700 bg-white focus:outline-none focus:border-petro-green cursor-pointer transition-colors"
                  >
                    <option>Select Periods</option>
                    <option>June 2026</option>
                    <option>July 2026</option>
                  </select>
                  <span className="absolute inset-y-0 right-0 pr-2 flex items-center pointer-events-none text-stone-500">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                    </svg>
                  </span>
                </div>

                {/* Generated By selector */}
                <div className="relative">
                  <select
                    value={userFilter}
                    onChange={(e) => {
                      setUserFilter(e.target.value);
                      setCurrentPage(1);
                    }}
                    className="appearance-none pl-3 pr-8 py-2 border border-stone-200 rounded-xl text-xs font-bold text-stone-700 bg-white focus:outline-none focus:border-petro-green cursor-pointer transition-colors"
                  >
                    <option value="All Users">{t("All Users")}</option>
                    {creators.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                  <span className="absolute inset-y-0 right-0 pr-2.5 flex items-center pointer-events-none text-stone-500">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                    </svg>
                  </span>
                </div>
              </div>

              {/* Action buttons on the right */}
              <button className="flex items-center gap-2 px-3 py-2 bg-stone-50 hover:bg-stone-100 border border-stone-200 text-stone-700 font-extrabold text-xs rounded-xl transition-colors shadow-sm">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.2} stroke="currentColor" className="w-3.5 h-3.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 0 1-.659 1.591l-5.432 5.432a2.25 2.25 0 0 0-.659 1.591v2.927a2.25 2.25 0 0 1-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 0 0-.659-1.591L3.659 7.409A2.25 2.25 0 0 1 3 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0 1 12 3Z" />
                </svg>
                {t("Filters")}
              </button>
            </div>

            {/* Table Area */}
            {loading ? (
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="bg-stone-50/70 border-b border-stone-150 text-stone-500 font-extrabold text-[11px] uppercase tracking-wider text-left">
                      <th className="py-4 px-6">{t("Report Name")}</th>
                      <th className="py-4 px-6">{t("Period")}</th>
                      <th className="py-4 px-6">{t("Report Type")}</th>
                      <th className="py-4 px-6">{t("Created By")}</th>
                      <th className="py-4 px-6">{t("Status")}</th>
                      <th className="py-4 px-6">{t("Created At")}</th>
                      <th className="py-4 px-6 text-center">{t("Action")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100">
                    {Array.from({ length: 6 }).map((_, i) => (
                      <tr key={i}>
                        <td className="py-4 px-6"><div className="skeleton h-3.5 w-48 rounded" /></td>
                        <td className="py-4 px-6"><div className="skeleton h-3 w-28 rounded" /></td>
                        <td className="py-4 px-6"><div className="skeleton h-3 w-24 rounded" /></td>
                        <td className="py-4 px-6"><div className="skeleton h-3 w-20 rounded" /></td>
                        <td className="py-4 px-6"><div className="skeleton h-5 w-16 rounded-full" /></td>
                        <td className="py-4 px-6"><div className="skeleton h-3 w-24 rounded" /></td>
                        <td className="py-4 px-6">
                          <div className="flex justify-center gap-2">
                            <div className="skeleton h-6 w-6 rounded-lg" />
                            <div className="skeleton h-6 w-6 rounded-lg" />
                            <div className="skeleton h-6 w-6 rounded-lg" />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : filteredReports.length === 0 ? (
              <div className="p-20 text-center text-stone-400 font-bold text-sm">
                {t("No reports found matching filters.")}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="bg-stone-50/70 border-b border-stone-150 text-stone-500 font-extrabold text-[11px] uppercase tracking-wider text-left">
                      <th className="py-4 px-6">{t("Report Name")}</th>
                      <th className="py-4 px-6">{t("Period")}</th>
                      <th className="py-4 px-6">{t("Report Type")}</th>
                      <th className="py-4 px-6">{t("Created By")}</th>
                      <th className="py-4 px-6">{t("Status")}</th>
                      <th className="py-4 px-6">{t("Created At")}</th>
                      <th className="py-4 px-6 text-center">{t("Action")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-stone-100 text-stone-700 text-xs font-bold">
                    {currentRows.map((item, rowIdx) => {
                      const statusDetails = getStatusDetails(item.status);
                      return (
                        <tr
                          key={item.id}
                          className="group hover:bg-stone-50/70 transition-all duration-200 animate-fadeInUp"
                          style={{ animationDelay: `${rowIdx * 40}ms` }}
                        >
                          <td className="py-4 px-6 font-black text-stone-850 text-left group-hover:text-petro-green transition-colors duration-200">{item.title}</td>
                          <td className="py-4 px-6 text-left">{formatPeriod(item.period_start, item.period_end)}</td>
                          <td className="py-4 px-6 text-left">{t(getDataTypeLabel(item.data_type))}</td>
                          <td className="py-4 px-6 text-left">{item.created_by_name || "Rafika"}</td>
                          <td className="py-4 px-6 text-left">
                            <span className={`px-3 py-1 rounded-full font-bold text-[10px] whitespace-nowrap inline-flex items-center gap-1.5 ${statusDetails.classes}`}>
                              {item.status === "draft" || item.status === "analyzed" ? (
                                <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
                              ) : null}
                              {t(statusDetails.label)}
                            </span>
                          </td>
                          <td className="py-4 px-6 text-left text-stone-450">{formatDateString(item.created_at)}</td>
                          <td className="py-4 px-6 text-center flex items-center justify-center gap-2">
                            {/* View Action */}
                            <Link
                              href={`/history/${item.id}`}
                              className="p-1.5 rounded-lg border border-stone-200 bg-white hover:bg-stone-50 text-stone-600 hover:text-stone-800 transition-colors shadow-sm"
                              title={t("View Preview")}
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.2} stroke="currentColor" className="w-3.5 h-3.5">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.43 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z" />
                                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
                              </svg>
                            </Link>

                            {/* Download Action */}
                            <button
                              onClick={() => handleDownloadPDF(item.id)}
                              className="p-1.5 rounded-lg border border-stone-200 bg-white hover:bg-stone-50 text-stone-600 hover:text-stone-800 transition-colors shadow-sm"
                              title={t("Download PDF")}
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.2} stroke="currentColor" className="w-3.5 h-3.5">
                                <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3" />
                              </svg>
                            </button>

                            {/* Edit Action */}
                            <Link
                              href={`/history/${item.id}?edit=true`}
                              className="p-1.5 rounded-lg border border-stone-200 bg-white hover:bg-stone-50 text-stone-600 hover:text-stone-800 transition-colors shadow-sm"
                              title={t("Edit Report")}
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.2} stroke="currentColor" className="w-3.5 h-3.5">
                                <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125" />
                              </svg>
                            </Link>

                            {/* Delete Action */}
                            <button
                              onClick={() => handleDelete(item.id)}
                              className="p-1.5 rounded-lg border border-red-100 bg-red-50 hover:bg-red-100 text-red-650 hover:text-red-700 transition-colors shadow-sm"
                              title={t("Delete Report")}
                            >
                              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.2} stroke="currentColor" className="w-3.5 h-3.5">
                                <path strokeLinecap="round" strokeLinejoin="round" d="m14.74 9-.346 9m-4.788 0L9 9m12 6a2.25 2.25 0 0 1-2.25 2.25h-9a2.25 2.25 0 0 1-2.25-2.25V5.25c0-.54.384-1.006.917-1.096A48.24 48.24 0 0 1 12 3c2.78 0 5.518.232 8.161.68.525.09.917.556.917 1.096V15Z" />
                              </svg>
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination Footer */}
            {!loading && filteredReports.length > 0 && (
              <div className="p-5 border-t border-stone-150 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs font-bold text-stone-500">
                <span>
                  {t("Showing")} {indexOfFirstRow + 1} {t("to")} {Math.min(indexOfLastRow, filteredReports.length)} {t("of")} {filteredReports.length} {t("reports")}
                </span>

                <div className="flex items-center gap-6">
                  {/* Rows per page selector */}
                  <div className="flex items-center gap-2">
                    <span>{t("Rows per page")}</span>
                    <div className="relative">
                      <select
                        value={rowsPerPage}
                        onChange={(e) => {
                          setRowsPerPage(Number(e.target.value));
                          setCurrentPage(1);
                        }}
                        className="appearance-none pl-3 pr-7 py-1.5 border border-stone-200 rounded-lg text-stone-700 bg-white focus:outline-none focus:border-petro-green cursor-pointer transition-colors"
                      >
                        <option value={5}>5</option>
                        <option value={10}>10</option>
                        <option value={20}>20</option>
                        <option value={50}>50</option>
                      </select>
                      <span className="absolute inset-y-0 right-0 pr-2 flex items-center pointer-events-none text-stone-500">
                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
                          <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                        </svg>
                      </span>
                    </div>
                  </div>

                  {/* Page selector buttons */}
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                      disabled={currentPage === 1}
                      className="w-8 h-8 rounded-lg border border-stone-200 flex items-center justify-center bg-white text-stone-500 hover:bg-stone-50 disabled:opacity-50 transition-colors"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
                      </svg>
                    </button>

                    {Array.from({ length: totalPages }).map((_, i) => {
                      const pageNum = i + 1;
                      return (
                        <button
                          key={pageNum}
                          onClick={() => setCurrentPage(pageNum)}
                          className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold transition-all ${
                            currentPage === pageNum
                              ? "bg-petro-green text-white"
                              : "border border-stone-200 bg-white text-stone-600 hover:bg-stone-50"
                          }`}
                        >
                          {pageNum}
                        </button>
                      );
                    })}

                    <button
                      onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                      disabled={currentPage === totalPages}
                      className="w-8 h-8 rounded-lg border border-stone-200 flex items-center justify-center bg-white text-stone-500 hover:bg-stone-50 disabled:opacity-50 transition-colors"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
                        <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </ScrollReveal>
        </main>
      </div>
    </div>
  );
}
