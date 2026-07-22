"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Sidebar from "@/components/Sidebar";
import Navbar from "@/components/Navbar";
import ScrollReveal from "@/components/ScrollReveal";
import { t, getLanguage } from "@/utils/i18n";
import Step0Overview from "./components/Step0Overview";
import Step1Upload from "./components/Step1Upload";
import Step2Settings from "./components/Step2Settings";
import Step3AIProcessing from "./components/Step3AIProcessing";
import Step4PreviewEdit from "./components/Step4PreviewEdit";
import Step5Export from "./components/Step5Export";

interface UploadedFile {
  name: string;
  type: string;
  size: string;
  status: "success" | "pending" | "failed";
}

export default function GenerateReportPage() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState<0 | 1 | 2 | 3 | 4 | 5>(0); // 0 = Overview, 1 = Upload, 2 = Settings, 3 = AI Processing, 4 = Preview & Edit, 5 = Export
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [reportId, setReportId] = useState<number | null>(null);

  // ==========================================
  // EFFECT 1: Pengaman Hidrasi (Hydration Guard)
  // ==========================================
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  const tx = (key: string, fallback: string) => (mounted ? t(key) : fallback);

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

  // File States (Empty by default, no dummy data)
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [rawFiles, setRawFiles] = useState<File[]>([]);

  // Form States (Step 2)
  const [title, setTitle] = useState("SOC Executive Summary - July 2026");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [periodAutoDetected, setPeriodAutoDetected] = useState(false);
  const [periodDetecting, setPeriodDetecting] = useState(false);
  const [templateType, setTemplateType] = useState(
    "SOC Executive Summary (Monthly)",
  );
  const [outputFormat, setOutputFormat] = useState("PDF");
  const [language, setLanguage] = useState("English");
  const [includeAI, setIncludeAI] = useState(true);
  const [includeRaw, setIncludeRaw] = useState(true);

  // Sinkronisasi default bahasa laporan dari preferensi personal user (/settings/profile).
  // Bukan lagi dari pengaturan global (/settings/), karena field "language" sudah dipindah
  // ke per-user. Field include_exec_summary/include_charts yang dulu disinkronkan ke sini
  // sudah dihapus total dari backend (dulu memang cross-wire yang tidak nyambung ke apapun),
  // jadi includeAI/includeRaw sekarang cukup pakai default bawaan (true) dan diatur manual
  // oleh user lewat form kalau perlu.
  useEffect(() => {
    const fetchFormDefaults = async () => {
      try {
        const token = localStorage.getItem("token");
        const headers: Record<string, string> = {};
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }
        const res = await fetch(
          "http://localhost:8000/api/v1/settings/profile",
          { headers },
        );
        if (res.ok) {
          const profile = await res.json();
          if (profile.language) {
            setLanguage(profile.language);
          }
        }
      } catch (err) {
        console.error(
          "Gagal memuat preferensi bahasa default untuk form:",
          err,
        );
      }
    };
    fetchFormDefaults();
  }, []);

  // New Figma Form States
  const [tone, setTone] = useState("Professional");
  const [defaultLevel, setDefaultLevel] = useState("Standard");
  const [sections, setSections] = useState<Record<string, boolean>>({
    executiveSummary: true,
    threatOverview: false,
    attackSummary: true,
    vaptSummary: true,
    bandwidthMonitoring: true,
    threatHunting: true,
    conclusionRecommendation: false,
  });
  const [exportFormats, setExportFormats] = useState<Record<string, boolean>>({
    pdf: true,
    pptx: true,
  });

  // Stepper Status (Step 3)
  const [aiStatus, setAiStatus] = useState<
    "pending" | "processing" | "completed"
  >("pending");

  // Report details state (Step 4 & 5)
  const [reportDetails, setReportDetails] = useState<any>(null);
  const [editedSummary, setEditedSummary] = useState<any>({});
  const [activeTab, setActiveTab] = useState<"preview" | "edit" | "charts">(
    "preview",
  );
  const [activePage, setActivePage] = useState("01");
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

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
        return "trend_analysis";
      case "03":
        return "severity_analysis";
      case "04":
        return "risk_assessment";
      case "05":
        return "bandwidth_summary";
      case "06":
        return "recommendations";
      case "07":
        return "conclusion";
      default:
        return "executive_summary";
    }
  };

  // Field "recommendations" di ai_summary itu array of string (bukan satu blok teks), sementara
  // rich text editor kerjanya selalu pakai HTML. Dua fungsi ini menjembatani konversi dua arah:
  // array -> HTML list (buat ditampilkan di editor sebagai bullet list), dan HTML -> array
  // (buat disimpan balik ke backend dengan struktur yang sama seperti sebelumnya).
  const arrayItemsToHtml = (items: string[]): string => {
    if (!items || items.length === 0) return "<ul><li></li></ul>";
    return `<ul>${items.map((item) => `<li>${item}</li>`).join("")}</ul>`;
  };

  const htmlToArrayItems = (html: string): string[] => {
    if (typeof window === "undefined") return [html];
    const doc = new DOMParser().parseFromString(html, "text/html");
    const listItems = doc.querySelectorAll("li");
    if (listItems.length > 0) {
      return Array.from(listItems)
        .map((li) => li.innerHTML.trim())
        .filter(Boolean);
    }
    const paragraphs = doc.querySelectorAll("p");
    if (paragraphs.length > 0) {
      return Array.from(paragraphs)
        .map((p) => p.innerHTML.trim())
        .filter(Boolean);
    }
    const text = doc.body.innerHTML.trim();
    return text ? [text] : [];
  };

  const getPageText = (page: string) => {
    const key = getPageContentKey(page);
    let text = editedSummary[key];
    if (Array.isArray(text)) {
      return arrayItemsToHtml(text);
    }
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
        [key]: htmlToArrayItems(newVal),
      });
    } else {
      setEditedSummary({
        ...editedSummary,
        [key]: newVal,
      });
    }
  };

  // Memanggil backend untuk mendeteksi otomatis rentang tanggal (period) dari isi file yang
  // baru diupload. Kalau ketemu kolom tanggal yang valid, field Report Period di Step 2 langsung
  // terisi otomatis. Kalau tidak ketemu (mis. data cuma punya "bulan" tanpa tahun), field
  // dibiarkan kosong supaya user isi manual sendiri.
  const detectPeriodFromFile = async (file: File) => {
    setPeriodDetecting(true);
    setPeriodAutoDetected(false);
    try {
      const token = localStorage.getItem("token");
      const authHeaders: Record<string, string> = {};
      if (token) {
        authHeaders["Authorization"] = `Bearer ${token}`;
      }

      const fd = new FormData();
      fd.append("file", file);

      const res = await fetch(
        "http://localhost:8000/api/v1/upload/detect-period",
        {
          method: "POST",
          headers: authHeaders,
          body: fd,
        },
      );

      if (res.ok) {
        const data = await res.json();
        if (data.detected && data.period_start && data.period_end) {
          setPeriodStart(data.period_start);
          setPeriodEnd(data.period_end);
          setPeriodAutoDetected(true);
        }
      }
    } catch (err) {
      // Deteksi gagal itu bukan error fatal — user tetap bisa isi periode manual di Step 2.
      console.warn("[PERIOD DETECT] Gagal mendeteksi periode otomatis:", err);
    } finally {
      setPeriodDetecting(false);
    }
  };

  // Handle local file adding
  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const file = e.dataTransfer.files[0];
      setRawFiles((prev) => [...prev, file]);
      const newFile: UploadedFile = {
        name: file.name,
        type: file.name.split(".").pop()?.toUpperCase() || "LOG",
        size: (file.size / (1024 * 1024)).toFixed(2) + " MB",
        status: "success",
      };
      setFiles((prev) => [...prev, newFile]);
      detectPeriodFromFile(file);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setRawFiles((prev) => [...prev, file]);
      const newFile: UploadedFile = {
        name: file.name,
        type: file.name.split(".").pop()?.toUpperCase() || "LOG",
        size: (file.size / (1024 * 1024)).toFixed(2) + " MB",
        status: "success",
      };
      setFiles((prev) => [...prev, newFile]);
      detectPeriodFromFile(file);
    }
  };

  // Submit Settings and Start Upload to Backend
  const handleStartGeneration = async () => {
    if (!periodStart || !periodEnd) {
      setErrorMsg(
        "Periode laporan belum terisi. Silakan isi Report Period secara manual di Step 2.",
      );
      return;
    }

    setCurrentStep(3);
    setLoading(true);
    setErrorMsg("");
    setAiStatus("processing");

    try {
      const token = localStorage.getItem("token");
      const authHeaders: Record<string, string> = {};
      if (token) {
        authHeaders["Authorization"] = `Bearer ${token}`;
      }

      // 1. Kirim berkas log dan preferensi ke backend POST /api/v1/upload/
      const formData = new FormData();
      formData.append("title", title);

      // Map template to backend data_type (firewall, email_security, vapt, dll.)
      let dataType = "firewall";
      if (templateType.includes("Email")) dataType = "email_security";
      else if (
        templateType.includes("Vulnerability") ||
        templateType.includes("VAPT")
      )
        dataType = "vapt";

      formData.append("data_type", dataType);
      formData.append("period_start", periodStart);
      formData.append("period_end", periodEnd);
      formData.append("template_type", templateType);
      formData.append("output_format", outputFormat);
      formData.append("language", language);
      formData.append("include_ai_insights", String(includeAI));
      formData.append("include_raw_data_summary", String(includeRaw));

      // Kirim file asli jika diunggah oleh user, jika tidak gunakan file dummy csv
      if (rawFiles.length > 0) {
        formData.append("file", rawFiles[rawFiles.length - 1]);
      } else {
        const csvContent =
          "tanggal,blocked_traffic\n2026-07-01,1200\n2026-07-02,1500\n2026-07-03,950\n2026-07-04,2100\n2026-07-05,1800\n2026-07-06,1300\n2026-07-07,2400";
        const blob = new Blob([csvContent], { type: "text/csv" });
        formData.append("file", blob, "firewall_data.csv");
      }

      const uploadRes = await fetch("http://localhost:8000/api/v1/upload/", {
        method: "POST",
        headers: authHeaders,
        body: formData,
      });

      if (!uploadRes.ok) {
        throw new Error(
          "Gagal mengunggah konfigurasi laporan siber ke server.",
        );
      }

      const reportData = await uploadRes.json();
      const generatedId = reportData.id;
      setReportId(generatedId);

      // 2. Trigger AI Engine Analysis: POST /api/v1/analysis/generate/{report_id}
      const generateRes = await fetch(
        `http://localhost:8000/api/v1/analysis/generate/${generatedId}`,
        {
          method: "POST",
          headers: authHeaders,
        },
      );

      if (!generateRes.ok) {
        throw new Error("Gagal memicu pemrosesan AI lokal (Ollama).");
      }

      const detailRes = await fetch(
        `http://localhost:8000/api/v1/history/${generatedId}`,
        {
          headers: authHeaders,
        },
      );
      if (detailRes.ok) {
        const details = await detailRes.json();
        setReportDetails(details);
        setEditedSummary(details.ai_summary || {});
      }
      setAiStatus("completed");
      setLoading(false);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || "Terjadi kesalahan tidak terduga.");
      setAiStatus("pending");
      setLoading(false);
    }
  };

  const handleNextStep = () => {
    if (currentStep === 0) setCurrentStep(1);
    else if (currentStep === 1) setCurrentStep(2);
    else if (currentStep === 4) setCurrentStep(5);
  };

  const handleBackStep = () => {
    if (currentStep === 1) setCurrentStep(0);
    else if (currentStep === 2) setCurrentStep(1);
    else if (currentStep === 4) setCurrentStep(2);
    else if (currentStep === 5) setCurrentStep(4);
  };

  const handleProceedToEditor = () => {
    setCurrentStep(4);
  };

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

  const renderStepCircle = (stepNum: number) => {
    if (currentStep > stepNum) {
      return (
        <div className="w-8 h-8 rounded-full bg-petro-green text-white flex items-center justify-center font-bold text-xs shadow-sm border-2 border-petro-green">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-4 h-4"
          >
            <path
              fillRule="evenodd"
              d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z"
              clipRule="evenodd"
            />
          </svg>
        </div>
      );
    } else if (currentStep === stepNum) {
      return (
        <div className="w-8 h-8 rounded-full bg-petro-green text-white flex items-center justify-center font-bold text-xs shadow-sm border-2 border-petro-green">
          {stepNum}
        </div>
      );
    } else {
      return (
        <div className="w-8 h-8 rounded-full bg-white text-stone-400 border border-stone-200 flex items-center justify-center font-bold text-xs shadow-sm">
          {stepNum}
        </div>
      );
    }
  };

  // List Stepper dengan Dukungan Hydration Guard
  const steps = [
    {
      number: 1,
      title: tx("Upload Data", "Upload Data"),
      desc: tx(
        "Upload your security evidence files. Supported formats: PDF, CSV, XLSX",
        "Upload your security evidence files. Supported formats: PDF, CSV, XLSX",
      ),
      icon: (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.8}
          stroke="currentColor"
          className="w-6 h-6 transition-transform duration-300 group-hover:scale-110"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 16.5V9.75m0 0 3 3m-3-3-3 3M6.75 19.5h10.5a2.25 2.25 0 0 0 2.25-2.25V6.75A2.25 2.25 0 0 0 17.25 4.5H6.75A2.25 2.25 0 0 0 4.5 6.75v10.5a2.25 2.25 0 0 0 2.25 2.25Z"
          />
        </svg>
      ),
    },
    {
      number: 2,
      title: tx("Report Settings", "Report Settings"),
      desc: tx(
        "Set period, template, format, and other preferences for your report",
        "Set period, template, format, and other preferences for your report",
      ),
      icon: (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.8}
          stroke="currentColor"
          className="w-6 h-6 transition-transform duration-300 group-hover:scale-110"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-9.75 0h9.75"
          />
        </svg>
      ),
    },
    {
      number: 3,
      title: tx("AI Processing", "AI Processing"),
      desc: tx(
        "Our AI will analyze the data and generate insights, charts, and summary",
        "Our AI will analyze the data and generate insights, charts, and summary",
      ),
      icon: (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.8}
          stroke="currentColor"
          className="w-6 h-6 transition-transform duration-350 group-hover:rotate-12 group-hover:scale-110"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09Z"
          />
        </svg>
      ),
    },
    {
      number: 4,
      title: tx("Preview & Edit", "Preview & Edit"),
      desc: tx(
        "Review AI generated content and make any necessary edits",
        "Review AI generated content and make any necessary edits",
      ),
      icon: (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.8}
          stroke="currentColor"
          className="w-6 h-6 transition-transform duration-300 group-hover:scale-110"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125"
          />
        </svg>
      ),
    },
    {
      number: 5,
      title: tx("Export Report", "Export Report"),
      desc: tx(
        "Export your report to PDF or PowerPoint format",
        "Export your report to PDF or PowerPoint format",
      ),
      icon: (
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.8}
          stroke="currentColor"
          className="w-6 h-6 transition-transform duration-300 group-hover:scale-110"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"
          />
        </svg>
      ),
    },
  ];

  return (
    <div className="min-h-screen bg-petro-bg-warm flex">
      {/* Sidebar Navigation */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 pl-64 flex flex-col min-h-screen">
        <Navbar />

        {/* Main Body */}
        <main className="flex-1 p-8 max-w-6xl mx-auto w-full">
          {/* STEPPER LOGO & METRIC (Only show if step > 0) */}
          {currentStep > 0 && (
            <div className="w-full flex justify-center mb-10">
              <div className="w-full max-w-3xl relative animate-fadeIn">
                {/* ── BACKGROUND CONTINUOUS SEAMLESS TRACK ── */}
                {/* Garis background utuh membentang presisi dari pusat Step 1 ke Step 5 */}
                <div className="absolute top-4 left-4 right-4 h-0.5 bg-stone-200 -translate-y-1/2 z-0">
                  {/* Active Green Progress Line yang meluncur dinamis & smooth tanpa celah */}
                  <div
                    className="h-full bg-petro-green transition-all duration-500 ease-out"
                    style={{
                      width: `${Math.max(0, Math.min(100, ((currentStep - 1) / 4) * 100))}%`,
                    }}
                  />
                </div>

                {/* ── STEP CIRCLES AND LABELS ── */}
                <div className="relative z-10 flex justify-between items-start w-full">
                  {/* Step 1 */}
                  <div className="flex flex-col items-center">
                    <div className="relative z-10">{renderStepCircle(1)}</div>
                    <span className="text-[10px] font-bold text-stone-600 mt-2">
                      {tx("Upload Data", "Upload Data")}
                    </span>
                  </div>

                  {/* Step 2 */}
                  <div className="flex flex-col items-center">
                    <div className="relative z-10">{renderStepCircle(2)}</div>
                    <span className="text-[10px] font-bold text-stone-600 mt-2">
                      {tx("Report Settings", "Report Settings")}
                    </span>
                  </div>

                  {/* Step 3 */}
                  <div className="flex flex-col items-center">
                    <div className="relative z-10">{renderStepCircle(3)}</div>
                    <span className="text-[10px] font-bold text-stone-600 mt-2">
                      {tx("AI Processing", "AI Processing")}
                    </span>
                  </div>

                  {/* Step 4 */}
                  <div className="flex flex-col items-center">
                    <div className="relative z-10">{renderStepCircle(4)}</div>
                    <span className="text-[10px] font-bold text-stone-600 mt-2">
                      {tx("Preview & Edit", "Preview & Edit")}
                    </span>
                  </div>

                  {/* Step 5 */}
                  <div className="flex flex-col items-center">
                    <div className="relative z-10">{renderStepCircle(5)}</div>
                    <span className="text-[10px] font-bold text-stone-600 mt-2">
                      {tx("Export", "Export")}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {currentStep > 0 && <hr className="border-stone-200/60 mb-8" />}

          {/* STEP 0: OVERVIEW / HOW IT WORKS */}
          {currentStep === 0 && (
            <Step0Overview onStart={() => setCurrentStep(1)} tx={tx} />
          )}

          {/* STEP 1: UPLOAD DATA */}
          {currentStep === 1 && (
            <Step1Upload
              files={files}
              onFileDrop={handleFileDrop}
              onFileSelect={handleFileSelect}
              onNext={handleNextStep}
              onBack={handleBackStep}
              tx={tx}
            />
          )}

          {/* STEP 2: REPORT SETTINGS */}
          {currentStep === 2 && (
            <Step2Settings
              periodStart={periodStart}
              setPeriodStart={setPeriodStart}
              periodEnd={periodEnd}
              setPeriodEnd={setPeriodEnd}
              periodAutoDetected={periodAutoDetected}
              periodDetecting={periodDetecting}
              onPeriodManualEdit={() => setPeriodAutoDetected(false)}
              language={language}
              setLanguage={setLanguage}
              exportFormats={exportFormats}
              setExportFormats={setExportFormats}
              sections={sections}
              setSections={setSections}
              tone={tone}
              setTone={setTone}
              defaultLevel={defaultLevel}
              setDefaultLevel={setDefaultLevel}
              onNext={handleStartGeneration}
              onBack={handleBackStep}
              tx={tx}
            />
          )}

          {/* STEP 3: AI PROCESSING */}
          {currentStep === 3 && (
            <Step3AIProcessing
              aiStatus={aiStatus}
              reportDetails={reportDetails}
              errorMsg={errorMsg}
              onBack={handleBackStep}
              onProceed={handleProceedToEditor}
              tx={tx}
            />
          )}

          {/* STEP 4: PREVIEW & EDIT */}
          {currentStep === 4 && (
            <Step4PreviewEdit
              activePage={activePage}
              setActivePage={setActivePage}
              activeTab={activeTab}
              setActiveTab={setActiveTab}
              isSaving={isSaving}
              saveSuccess={saveSuccess}
              language={language}
              periodStart={periodStart}
              periodEnd={periodEnd}
              reportDetails={reportDetails}
              editedSummary={editedSummary}
              getPageText={getPageText}
              getPageTitle={getPageTitle}
              handleTextChange={handleTextChange}
              handleSaveEdits={handleSaveEdits}
              onBack={handleBackStep}
              onNext={handleNextStep}
              tx={tx}
            />
          )}

          {/* STEP 5: EXPORT */}
          {currentStep === 5 && (
            <Step5Export
              reportId={reportId}
              onReset={() => {
                setCurrentStep(0);
                setReportId(null);
                setReportDetails(null);
                setEditedSummary({});
                setAiStatus("pending");
              }}
              tx={tx}
            />
          )}
        </main>
      </div>
    </div>
  );
}
