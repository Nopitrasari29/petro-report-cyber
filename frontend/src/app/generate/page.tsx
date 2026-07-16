"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Sidebar from "@/components/Sidebar";
import Navbar from "@/components/Navbar";
import ScrollReveal from "@/components/ScrollReveal";
import { t, getLanguage } from "@/utils/i18n";

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

  // File States (Pre-populated to match Step 1 Mockup)
  const [files, setFiles] = useState<UploadedFile[]>([
    { name: "email_threat_report_july.pdf", type: "PDF", size: "2.45 MB", status: "success" },
    { name: "attack_log_july.csv", type: "CSV", size: "1.23 MB", status: "success" },
    { name: "vapt_result_july.xlsx", type: "XLSX", size: "3.12 MB", status: "success" },
  ]);
  const [rawFiles, setRawFiles] = useState<File[]>([]);

  // Form States (Step 2)
  const [title, setTitle] = useState("SOC Executive Summary - July 2026");
  const [periodStart, setPeriodStart] = useState("2026-07-01");
  const [periodEnd, setPeriodEnd] = useState("2026-07-31");
  const [templateType, setTemplateType] = useState("SOC Executive Summary (Monthly)");
  const [outputFormat, setOutputFormat] = useState("PDF");
  const [language, setLanguage] = useState("English");
  const [includeAI, setIncludeAI] = useState(true);
  const [includeRaw, setIncludeRaw] = useState(true);

  // Fetch settings to sync form defaults
  useEffect(() => {
    const fetchFormDefaults = async () => {
      try {
        const token = localStorage.getItem("token");
        const headers: Record<string, string> = {};
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }
        const res = await fetch("http://localhost:8000/api/v1/settings/", { headers });
        if (res.ok) {
          const settingsData = await res.json();
          // Sinkronisasi bahasa default
          if (settingsData.ai_language) {
            setLanguage(settingsData.ai_language);
          }
          // Sinkronisasi pilihan AI insights & raw data summary
          if (settingsData.include_exec_summary !== undefined) {
            setIncludeAI(settingsData.include_exec_summary);
          }
          if (settingsData.include_charts !== undefined) {
            setIncludeRaw(settingsData.include_charts);
          }
        }
      } catch (err) {
        console.error("Gagal memuat default settings untuk form:", err);
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
    conclusionRecommendation: false
  });
  const [exportFormats, setExportFormats] = useState<Record<string, boolean>>({
    pdf: true,
    pptx: true
  });

  // Stepper Status (Step 3)
  const [aiStatus, setAiStatus] = useState<"pending" | "processing" | "completed">("pending");

  // Report details state (Step 4 & 5)
  const [reportDetails, setReportDetails] = useState<any>(null);
  const [editedSummary, setEditedSummary] = useState<any>({});
  const [activeTab, setActiveTab] = useState<"preview" | "edit" | "charts">("preview");
  const [activePage, setActivePage] = useState("01");
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const getPageTitle = (page: string) => {
    switch(page) {
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
    switch(page) {
      case "01": return "executive_summary";
      case "02": return "trend_analysis";
      case "03": return "severity_analysis";
      case "04": return "risk_assessment";
      case "05": return "bandwidth_summary";
      case "06": return "recommendations";
      case "07": return "conclusion";
      default: return "executive_summary";
    }
  };

  const getPageText = (page: string) => {
    const key = getPageContentKey(page);
    let text = editedSummary[key];
    if (Array.isArray(text)) {
      return text.join("\n\n");
    }
    if (text) return text;
    
    // Fallbacks
    switch(page) {
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
    }
  };

  // Submit Settings and Start Upload to Backend
  const handleStartGeneration = async () => {
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
      else if (templateType.includes("Vulnerability") || templateType.includes("VAPT")) dataType = "vapt";

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
        const csvContent = "tanggal,blocked_traffic\n2026-07-01,1200\n2026-07-02,1500\n2026-07-03,950\n2026-07-04,2100\n2026-07-05,1800\n2026-07-06,1300\n2026-07-07,2400";
        const blob = new Blob([csvContent], { type: "text/csv" });
        formData.append("file", blob, "firewall_data.csv");
      }

      const uploadRes = await fetch("http://localhost:8000/api/v1/upload/", {
        method: "POST",
        headers: authHeaders,
        body: formData,
      });

      if (!uploadRes.ok) {
        throw new Error("Gagal mengunggah konfigurasi laporan siber ke server.");
      }

      const reportData = await uploadRes.json();
      const generatedId = reportData.id;
      setReportId(generatedId);

      // 2. Trigger AI Engine Analysis: POST /api/v1/analysis/generate/{report_id}
      const generateRes = await fetch(`http://localhost:8000/api/v1/analysis/generate/${generatedId}`, {
        method: "POST",
        headers: authHeaders,
      });

      if (!generateRes.ok) {
        throw new Error("Gagal memicu pemrosesan AI lokal (Ollama).");
      }

      const detailRes = await fetch(`http://localhost:8000/api/v1/history/${generatedId}`, {
        headers: authHeaders,
      });
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

  const renderStepCircle = (stepNum: number) => {
    if (currentStep > stepNum) {
      return (
        <div className="w-8 h-8 rounded-full bg-petro-green text-white flex items-center justify-center font-bold text-xs shadow-sm border-2 border-petro-green">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
            <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
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

  return (
    <div className="min-h-screen bg-petro-bg-warm flex">
      {/* Sidebar Navigation */}
      <Sidebar />

      {/* Main Content Area */}
      <div className="flex-1 pl-64 flex flex-col min-h-screen">
        <Navbar />

        {/* Header wizard stepper */}
        <main className="flex-1 p-8 max-w-6xl mx-auto w-full">
          
          {/* STEPPER LOGO & METRIC (Only show if step > 0) */}
          {currentStep > 0 && (
            <div className="w-full flex justify-center mb-10">
              <div className="flex items-center gap-12 w-full max-w-3xl">
                {/* Step 1 */}
                <div className="flex flex-col items-center relative flex-1">
                  {renderStepCircle(1)}
                  <span className="text-[10px] font-bold text-stone-600 mt-2">{t("Upload Data")}</span>
                  <div className={`absolute left-[calc(50%+16px)] top-4 w-[calc(100%-32px)] h-0.5 ${
                    currentStep >= 2 ? "bg-petro-green" : "bg-stone-200"
                  }`}></div>
                </div>

                {/* Step 2 */}
                <div className="flex flex-col items-center relative flex-1">
                  {renderStepCircle(2)}
                  <span className="text-[10px] font-bold text-stone-600 mt-2">{t("Report Settings")}</span>
                  <div className={`absolute left-[calc(50%+16px)] top-4 w-[calc(100%-32px)] h-0.5 ${
                    currentStep >= 3 ? "bg-petro-green" : "bg-stone-200"
                  }`}></div>
                </div>

                {/* Step 3 */}
                <div className="flex flex-col items-center relative flex-1">
                  {renderStepCircle(3)}
                  <span className="text-[10px] font-bold text-stone-600 mt-2">{t("AI Processing")}</span>
                  <div className={`absolute left-[calc(50%+16px)] top-4 w-[calc(100%-32px)] h-0.5 ${
                    currentStep >= 4 ? "bg-petro-green" : "bg-stone-200"
                  }`}></div>
                </div>

                {/* Step 4 */}
                <div className="flex flex-col items-center relative flex-1">
                  {renderStepCircle(4)}
                  <span className="text-[10px] font-bold text-stone-600 mt-2">{t("Preview & Edit")}</span>
                  <div className={`absolute left-[calc(50%+16px)] top-4 w-[calc(100%-32px)] h-0.5 ${
                    currentStep >= 5 ? "bg-petro-green" : "bg-stone-200"
                  }`}></div>
                </div>

                {/* Step 5 */}
                <div className="flex flex-col items-center flex-1">
                  {renderStepCircle(5)}
                  <span className="text-[10px] font-bold text-stone-600 mt-2">{t("Export")}</span>
                </div>
              </div>
            </div>
          )}

          {currentStep > 0 && <hr className="border-stone-200/60 mb-8" />}

          {/* STEP 0: OVERVIEW / HOW IT WORKS */}
          {currentStep === 0 && (
            <ScrollReveal animation="fadeInUp" delay={100} className="space-y-6">
              <div className="text-left">
                <h2 className="text-2xl font-extrabold text-stone-900">Generate Report</h2>
                <p className="text-sm text-stone-500 font-medium mt-1">Upload your security data and let AI generate comprehensive SOC reports automatically.</p>
              </div>

              <div className="bg-white rounded-2xl border border-stone-200/80 p-8 shadow-sm text-left mt-6 premium-card-hover">
                <h3 className="font-extrabold text-stone-900 text-lg mb-6">How It Works</h3>
                
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
                  {/* Timeline (left 7 cols) */}
                  <div className="lg:col-span-7 flex flex-col">
                    {/* Item 1 */}
                    <div className="flex items-start gap-4">
                      <div className="flex flex-col items-center shrink-0">
                        <div className="w-8 h-8 rounded-full bg-petro-green text-white border-2 border-petro-green flex items-center justify-center font-bold text-xs shadow-sm">
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                            <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                          </svg>
                        </div>
                        <div className="w-0.5 h-12 bg-petro-green"></div>
                      </div>
                      <div className="flex-1 flex justify-between items-center py-1">
                        <div className="text-left">
                          <h4 className="font-bold text-stone-850 text-sm">Upload your data sources</h4>
                          <p className="text-[10px] text-stone-450 mt-1">Upload your security evidence files. Supported formats: PDF, CSV, XLSX</p>
                        </div>
                        <span className="px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-250 text-emerald-600 font-bold text-[10px]">Complete</span>
                      </div>
                    </div>

                    {/* Item 2 */}
                    <div className="flex items-start gap-4">
                      <div className="flex flex-col items-center shrink-0">
                        <div className="w-8 h-8 rounded-full bg-petro-green text-white border-2 border-petro-green flex items-center justify-center font-bold text-xs shadow-sm">
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                            <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                          </svg>
                        </div>
                        <div className="w-0.5 h-12 bg-petro-green"></div>
                      </div>
                      <div className="flex-1 flex justify-between items-center py-1">
                        <div className="text-left">
                          <h4 className="font-bold text-stone-850 text-sm">Configure report settings</h4>
                          <p className="text-[10px] text-stone-450 mt-1">Set period, template, format, and other preferences for your report</p>
                        </div>
                        <span className="px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-255 text-emerald-600 font-bold text-[10px]">Complete</span>
                      </div>
                    </div>

                    {/* Item 3 */}
                    <div className="flex items-start gap-4">
                      <div className="flex flex-col items-center shrink-0">
                        <div className="w-8 h-8 rounded-full bg-white text-petro-green border-2 border-petro-green flex items-center justify-center font-bold text-xs shadow-sm">
                          3
                        </div>
                        <div className="w-0.5 h-12 bg-stone-250"></div>
                      </div>
                      <div className="flex-1 flex justify-between items-center py-1">
                        <div className="text-left">
                          <h4 className="font-bold text-stone-850 text-sm">AI processing</h4>
                          <p className="text-[10px] text-stone-450 mt-1">Our AI will analyze the data and generate insights, charts, and summary</p>
                        </div>
                        <span className="px-2.5 py-1 rounded-full bg-stone-100 border border-stone-200 text-stone-450 font-bold text-[10px]">Pending</span>
                      </div>
                    </div>

                    {/* Item 4 */}
                    <div className="flex items-start gap-4">
                      <div className="flex flex-col items-center shrink-0">
                        <div className="w-8 h-8 rounded-full bg-white text-stone-400 border border-stone-200 flex items-center justify-center font-bold text-xs shadow-sm">
                          4
                        </div>
                        <div className="w-0.5 h-12 bg-stone-200"></div>
                      </div>
                      <div className="flex-1 flex justify-between items-center py-1">
                        <div className="text-left">
                          <h4 className="font-bold text-stone-455 text-sm">Preview & edit</h4>
                          <p className="text-[10px] text-stone-450 mt-1">Review AI generated content and make any necessary edits</p>
                        </div>
                        <span className="px-2.5 py-1 rounded-full bg-stone-100 border border-stone-200 text-stone-450 font-bold text-[10px]">Pending</span>
                      </div>
                    </div>

                    {/* Item 5 */}
                    <div className="flex items-start gap-4">
                      <div className="flex flex-col items-center shrink-0">
                        <div className="w-8 h-8 rounded-full bg-white text-stone-400 border border-stone-200 flex items-center justify-center font-bold text-xs shadow-sm">
                          5
                        </div>
                      </div>
                      <div className="flex-1 flex justify-between items-center py-1">
                        <div className="text-left">
                          <h4 className="font-bold text-stone-455 text-sm">Export report</h4>
                          <p className="text-[10px] text-stone-450 mt-1">Export your report to PDF or PowerPoint format</p>
                        </div>
                        <span className="px-2.5 py-1 rounded-full bg-stone-100 border border-stone-200 text-stone-450 font-bold text-[10px]">Pending</span>
                      </div>
                    </div>
                  </div>

                  {/* Right Laptop Illustration (right 5 cols) */}
                  <div className="lg:col-span-5 flex flex-col items-center justify-center pl-0 lg:pl-8 border-t lg:border-t-0 lg:border-l border-stone-150 py-6">
                    <img src="/soc-logo.png" alt="SOC Report" className="w-full max-w-[280px] object-contain h-auto" />
                    <p className="mt-8 text-xs font-bold text-stone-750 tracking-wide uppercase">Processing Pipeline</p>
                    <p className="text-[10px] text-stone-450 mt-1 leading-snug text-center max-w-[200px] font-semibold">Fully automated monthly SOC reporting workflow.</p>
                  </div>
                </div>
              </div>

              {/* Start Button */}
              <div className="pt-6 border-t border-stone-200/60 mt-8 flex flex-col items-center gap-4">
                <button
                  onClick={() => setCurrentStep(1)}
                  className="w-full max-w-xl inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-petro-green hover:bg-petro-green-hover text-white font-extrabold text-sm shadow-md transition-all duration-200"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
                    <path d="M6.3 2.841A1.5 1.5 0 0 0 4 4.11v11.78a1.5 1.5 0 0 0 2.3 1.269l9.324-5.89a1.5 1.5 0 0 0 0-2.538L6.3 2.84Z" />
                  </svg>
                  Start Processing
                </button>
                
                <Link
                  href="/"
                  className="text-stone-500 hover:text-petro-green font-bold text-xs transition-colors flex items-center gap-1.5"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3 h-3">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
                  </svg>
                  Back to Home Page
                </Link>
              </div>
            </ScrollReveal>
          )}

          {/* STEP 1: UPLOAD DATA */}
          {currentStep === 1 && (
            <ScrollReveal animation="fadeInUp" delay={100} className="space-y-6">
              <div className="text-left">
                <h2 className="text-2xl font-extrabold text-stone-900">Upload Data</h2>
                <p className="text-sm text-stone-500 font-medium mt-1">Upload the security evidence files you want to include in this report</p>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Drag & Drop Area */}
                <div className="lg:col-span-2 space-y-6">
                  <div
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={handleFileDrop}
                    className="h-80 border-2 border-dashed border-stone-200 hover:border-petro-green/60 rounded-2xl bg-white flex flex-col items-center justify-center cursor-pointer transition-all p-6 group premium-card-hover"
                  >
                    <div className="w-16 h-16 rounded-full bg-petro-green-light flex items-center justify-center text-petro-green group-hover:scale-105 transition-all duration-300">
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-8 h-8">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0 3 3m-3-3-3 3M6.75 19.5h10.5a2.25 2.25 0 0 0 2.25-2.25V6.75A2.25 2.25 0 0 0 17.25 4.5H6.75A2.25 2.25 0 0 0 4.5 6.75v10.5a2.25 2.25 0 0 0 2.25 2.25Z" />
                      </svg>
                    </div>
                    <p className="mt-4 font-bold text-stone-880 text-sm">Drag & drop your files here</p>
                    <p className="text-xs text-stone-400 mt-1 font-semibold">or</p>
                    
                    <label className="mt-3 px-5 py-2.5 rounded-lg bg-petro-green hover:bg-petro-green-hover text-white font-bold text-xs shadow-sm cursor-pointer transition-colors">
                      Choose File
                      <input type="file" onChange={handleFileSelect} className="hidden" />
                    </label>
                    
                    <p className="text-[10px] text-stone-450 mt-4 font-medium">Supported format: PDF, CSV, XLSX</p>
                    <p className="text-[9px] text-stone-400 font-medium">Maximum file size: 100 MB per file</p>
                  </div>

                  {/* Uploaded Files Table */}
                  <div className="bg-white rounded-2xl border border-stone-200/80 p-5 shadow-sm premium-card-hover">
                    <h3 className="font-bold text-stone-850 text-sm border-b border-stone-100 pb-3">Uploaded Files ({files.length})</h3>
                    <div className="mt-3 divide-y divide-stone-100">
                      {files.map((file, idx) => (
                        <div key={idx} className="py-3 flex items-center justify-between text-sm">
                          <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-lg bg-red-50 flex items-center justify-center text-red-650 font-bold text-xs border border-red-100">
                              {file.type}
                            </div>
                            <div className="flex flex-col text-left">
                              <span className="font-bold text-stone-800 text-xs leading-none">{file.name}</span>
                              <span className="text-[10px] text-stone-450 font-semibold mt-1">{file.type}</span>
                            </div>
                          </div>
                          <div className="flex items-center gap-5">
                            <span className="text-xs font-semibold text-stone-500">{file.size}</span>
                            <span className="w-5 h-5 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600">
                              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                                <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                              </svg>
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Right Summary Column */}
                <div className="space-y-6">
                  <div className="bg-white border border-stone-200/80 rounded-2xl p-5 shadow-sm text-left premium-card-hover">
                    <h3 className="font-bold text-stone-900 text-sm border-b border-stone-100 pb-3">Upload Summary</h3>
                    <div className="mt-4 flex items-baseline gap-2">
                      <span className="text-3xl font-extrabold text-petro-green">{files.length}</span>
                      <span className="text-xs font-bold text-stone-500">Files Uploaded</span>
                    </div>
                    <div className="mt-4 space-y-2">
                      {files.map((file, idx) => (
                        <div key={idx} className="flex items-center gap-2 text-xs font-medium text-stone-600">
                          <span className="text-emerald-600">✓</span>
                          <span>{file.name}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="bg-white border border-stone-200/80 rounded-2xl p-5 shadow-sm text-left premium-card-hover">
                    <h3 className="font-bold text-stone-900 text-sm border-b border-stone-100 pb-3">Estimated AI Accuracy</h3>
                    <div className="mt-4 flex items-center gap-4">
                      {/* Circular Progress Ring */}
                      <div className="relative w-12 h-12 shrink-0">
                        <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                          <path
                            className="text-stone-100"
                            strokeWidth="3.5"
                            stroke="currentColor"
                            fill="none"
                            d="M18 2.0845
                              a 15.9155 15.9155 0 0 1 0 31.831
                              a 15.9155 15.9155 0 0 1 0 -31.831"
                          />
                          <path
                            className="text-petro-green"
                            strokeDasharray="94, 100"
                            strokeWidth="3.5"
                            strokeLinecap="round"
                            stroke="currentColor"
                            fill="none"
                            d="M18 2.0845
                              a 15.9155 15.9155 0 0 1 0 31.831
                              a 15.9155 15.9155 0 0 1 0 -31.831"
                          />
                        </svg>
                      </div>
                      <div>
                        <div className="text-lg font-black text-stone-850">94%</div>
                        <div className="text-[10px] text-stone-450 font-bold mt-0.5">Based on data quality</div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Bottom Nav Bar */}
              <div className="flex justify-between pt-5 border-t border-stone-200/60 mt-8">
                <button
                  onClick={handleBackStep}
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white border border-stone-200 hover:bg-stone-50 text-stone-700 font-bold text-sm shadow-sm transition-all duration-200"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
                  </svg>
                  Back
                </button>                <button
                  onClick={handleNextStep}
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-petro-green hover:bg-petro-green-hover text-white font-bold text-sm shadow transition-all duration-200 group"
                >
                  {t("Next: Settings")}
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5 transition-transform group-hover:translate-x-1">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                  </svg>
                </button>
              </div>
            </ScrollReveal>
          )}

          {/* STEP 2: REPORT SETTINGS */}
          {currentStep === 2 && (
            <ScrollReveal animation="fadeInUp" delay={100} className="space-y-6">
              <div className="text-left">
                <h2 className="text-2xl font-extrabold text-stone-900">{t("Report Settings")}</h2>
                <p className="text-sm text-stone-500 font-semibold mt-1">{t("Configure the settings for your SOC report")}</p>
              </div>

              {/* 3-Column Top Cards */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 text-left">
                
                {/* Column 1: Report Metadata & Period */}
                <div className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm space-y-4 premium-card-hover">
                  <h3 className="font-extrabold text-stone-850 text-sm border-b border-stone-100 pb-2">{t("Report")}</h3>
                  
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider mb-1.5">{t("Report Period")}</label>
                      <div className="grid grid-cols-2 gap-2">
                        <input
                          type="date"
                          value={periodStart}
                          onChange={(e) => setPeriodStart(e.target.value)}
                          className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
                        />
                        <input
                          type="date"
                          value={periodEnd}
                          onChange={(e) => setPeriodEnd(e.target.value)}
                          className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider mb-1.5">{t("Language")}</label>
                      <select
                        value={language}
                        onChange={(e) => setLanguage(e.target.value)}
                        className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
                      >
                        <option value="English">English</option>
                        <option value="Indonesian">Indonesian</option>
                      </select>
                    </div>
                  </div>
                </div>

                {/* Column 2: Output Options */}
                <div className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm space-y-4 premium-card-hover">
                  <h3 className="font-extrabold text-stone-850 text-sm border-b border-stone-100 pb-2">{t("Output")}</h3>
                  
                  <div>
                    <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider mb-3">{t("Export Format")}</label>
                    <div className="space-y-3">
                      <label className="flex items-center gap-3 p-3 bg-stone-50 border border-stone-250 rounded-xl cursor-pointer hover:bg-stone-100/50 transition-colors">
                        <input
                          type="checkbox"
                          checked={exportFormats.pdf}
                          onChange={(e) => setExportFormats(prev => ({ ...prev, pdf: e.target.checked }))}
                          className="w-4 h-4 rounded text-petro-green focus:ring-petro-green border-stone-300"
                        />
                        <div className="flex flex-col text-left">
                          <span className="text-xs font-bold text-stone-800">PDF</span>
                          <span className="text-[9px] text-stone-400 font-semibold">{t("Standard printable document")}</span>
                        </div>
                      </label>

                      <label className="flex items-center gap-3 p-3 bg-stone-50 border border-stone-250 rounded-xl cursor-pointer hover:bg-stone-100/50 transition-colors">
                        <input
                          type="checkbox"
                          checked={exportFormats.pptx}
                          onChange={(e) => setExportFormats(prev => ({ ...prev, pptx: e.target.checked }))}
                          className="w-4 h-4 rounded text-petro-green focus:ring-petro-green border-stone-300"
                        />
                        <div className="flex flex-col text-left">
                          <span className="text-xs font-bold text-stone-800">PowerPoint (PPTX)</span>
                          <span className="text-[9px] text-stone-400 font-semibold">{t("Presentation slides layout")}</span>
                        </div>
                      </label>
                    </div>
                  </div>
                </div>

                {/* Column 3: Include Sections Checkboxes */}
                <div className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm space-y-4 premium-card-hover">
                  <h3 className="font-extrabold text-stone-850 text-sm border-b border-stone-100 pb-2">{t("Include Sections")}</h3>
                  
                  <div className="space-y-2 max-h-[180px] overflow-y-auto pr-1">
                    {[
                      { key: "executiveSummary", label: "Executive Summary" },
                      { key: "threatOverview", label: "Threat Overview" },
                      { key: "attackSummary", label: "Attack Summary" },
                      { key: "vaptSummary", label: "VAPT Summary" },
                      { key: "bandwidthMonitoring", label: "Bandwidth Monitoring" },
                      { key: "threatHunting", label: "Threat Hunting" },
                      { key: "conclusionRecommendation", label: "Conclusion & Recommendation" }
                    ].map((sec) => (
                      <label key={sec.key} className="flex items-center gap-2.5 cursor-pointer py-0.5 select-none">
                        <input
                          type="checkbox"
                          checked={sections[sec.key]}
                          onChange={(e) => setSections(prev => ({ ...prev, [sec.key]: e.target.checked }))}
                          className="w-4 h-4 rounded text-petro-green focus:ring-petro-green border-stone-300"
                        />
                        <span className="text-xs font-semibold text-stone-700">{t(sec.label)}</span>
                      </label>
                    ))}
                  </div>
                </div>

              </div>

              {/* Bottom Wide Card: Additional Preferences */}
              <div className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm text-left premium-card-hover">
                <h3 className="font-extrabold text-stone-855 text-sm border-b border-stone-100 pb-2 mb-4">{t("Additional Preferences")}</h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div>
                    <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider mb-1.5">{t("Tone")}</label>
                    <select
                      value={tone}
                      onChange={(e) => setTone(e.target.value)}
                      className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
                    >
                      <option value="Professional">{t("Professional")}</option>
                      <option value="Technical">{t("Technical")}</option>
                      <option value="Executive">{t("Executive")}</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider mb-1.5">{t("Default Level")}</label>
                    <select
                      value={defaultLevel}
                      onChange={(e) => setDefaultLevel(e.target.value)}
                      className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2.5 text-xs focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all"
                    >
                      <option value="Standard">{t("Standard")}</option>
                      <option value="Detailed">{t("Detailed")}</option>
                      <option value="Summary Only">{t("Summary Only")}</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Bottom Nav Bar */}
              <div className="flex justify-between pt-5 border-t border-stone-200/60 mt-8">
                <button
                  onClick={handleBackStep}
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white border border-stone-200 hover:bg-stone-50 text-stone-700 font-bold text-sm shadow-sm transition-all duration-200"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
                  </svg>
                  {t("Back")}
                </button>

                <button
                  onClick={handleStartGeneration}
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-petro-green hover:bg-petro-green-hover text-white font-bold text-sm shadow transition-all duration-200 group"
                >
                  {t("Next Export")}
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5 transition-transform group-hover:translate-x-1">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                  </svg>
                </button>
              </div>
            </ScrollReveal>
          )}          {/* STEP 3: AI PROCESSING */}
          {currentStep === 3 && (
            <ScrollReveal animation="fadeInUp" delay={100} className="space-y-6">
              <div className="text-left">
                <h2 className="text-2xl font-extrabold text-stone-900">{t("AI Processing")}</h2>
                <p className="text-sm text-stone-500 font-semibold mt-1">{t("Our AI is analyzing your data and generating insights")}</p>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 text-left items-start mt-6">
                
                {/* Left Column (60% width): Processing Progress */}
                <div className="lg:col-span-7 bg-white rounded-2xl border border-stone-200/80 p-6 shadow-sm space-y-6 premium-card-hover">
                  <div>
                    <div className="flex justify-between items-center mb-2">
                      <h3 className="font-extrabold text-stone-855 text-sm">{t("Processing Progress")}</h3>
                      <span className="text-xs font-bold text-petro-green">
                        {aiStatus === "completed" ? "100%" : "68%"}
                      </span>
                    </div>
                    {/* Progress Bar */}
                    <div className="w-full h-3 bg-stone-100 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-petro-green transition-all duration-500" 
                        style={{ width: aiStatus === "completed" ? "100%" : "68%" }}
                      ></div>
                    </div>
                  </div>

                  {/* Checklist */}
                  <div className="space-y-4">
                    {/* Item 1 */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="w-5 h-5 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center">
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-emerald-600">
                            <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                          </svg>
                        </span>
                        <span className="text-xs font-bold text-stone-700">{t("Reading uploaded files")}</span>
                      </div>
                      <span className="text-[10px] text-emerald-600 font-bold">{t("Completed")}</span>
                    </div>

                    {/* Item 2 */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="w-5 h-5 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center">
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-emerald-600">
                            <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                          </svg>
                        </span>
                        <span className="text-xs font-bold text-stone-700">{t("Extracting and structuring data")}</span>
                      </div>
                      <span className="text-[10px] text-emerald-600 font-bold">{t("Completed")}</span>
                    </div>

                    {/* Item 3 */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="w-5 h-5 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center">
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-emerald-600">
                            <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                          </svg>
                        </span>
                        <span className="text-xs font-bold text-stone-700">{t("Detecting security threats")}</span>
                      </div>
                      <span className="text-[10px] text-emerald-600 font-bold">{t("Completed")}</span>
                    </div>

                    {/* Item 4 */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {aiStatus === "completed" ? (
                          <span className="w-5 h-5 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-emerald-600">
                              <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                            </svg>
                          </span>
                        ) : (
                          <span className="w-5 h-5 rounded-full bg-amber-50 border border-amber-200 flex items-center justify-center">
                            <div className="w-2.5 h-2.5 border-2 border-stone-200 border-t-amber-500 rounded-full animate-spin"></div>
                          </span>
                        )}
                        <span className="text-xs font-bold text-stone-700">{t("Generating executive summary")}</span>
                      </div>
                      <span className={`text-[10px] font-bold ${aiStatus === "completed" ? "text-emerald-600" : "text-amber-600"}`}>
                        {aiStatus === "completed" ? t("Completed") : t("In Progress")}
                      </span>
                    </div>

                    {/* Item 5 */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {aiStatus === "completed" ? (
                          <span className="w-5 h-5 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-emerald-600">
                              <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                            </svg>
                          </span>
                        ) : (
                          <span className="w-5 h-5 rounded-full bg-stone-50 border border-stone-200 flex items-center justify-center"></span>
                        )}
                        <span className={`text-xs font-bold ${aiStatus === "completed" ? "text-stone-700" : "text-stone-400"}`}>{t("Creating charts and visualizations")}</span>
                      </div>
                      <span className={`text-[10px] font-bold ${aiStatus === "completed" ? "text-emerald-600" : "text-stone-400"}`}>
                        {aiStatus === "completed" ? t("Completed") : t("Waiting")}
                      </span>
                    </div>

                    {/* Item 6 */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {aiStatus === "completed" ? (
                          <span className="w-5 h-5 rounded-full bg-emerald-50 border border-emerald-250 flex items-center justify-center">
                            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-emerald-600">
                              <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                            </svg>
                          </span>
                        ) : (
                          <span className="w-5 h-5 rounded-full bg-stone-50 border border-stone-200 flex items-center justify-center"></span>
                        )}
                        <span className={`text-xs font-bold ${aiStatus === "completed" ? "text-stone-700" : "text-stone-400"}`}>{t("Preparing report content")}</span>
                      </div>
                      <span className={`text-[10px] font-bold ${aiStatus === "completed" ? "text-emerald-600" : "text-stone-400"}`}>
                        {aiStatus === "completed" ? t("Completed") : t("Waiting")}
                      </span>
                    </div>
                  </div>

                  {/* Warning Alert */}
                  <div className="bg-emerald-50/50 border border-emerald-100 rounded-xl p-4 flex gap-3 text-left">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5 text-emerald-650 shrink-0 mt-0.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                    </svg>
                    <div>
                      <p className="text-xs font-bold text-stone-800">{t("Please don't close or refresh this page")}</p>
                      <p className="text-[10px] text-stone-500 font-semibold mt-0.5">{t("This process may take a few minutes as our local LLM analyzes log data.")}</p>
                    </div>
                  </div>
                </div>

                {/* Right Column (40% width): AI Insights Preview */}
                <div className="lg:col-span-5 bg-white rounded-2xl border border-stone-200/80 p-6 shadow-sm space-y-4 premium-card-hover">
                  <h3 className="font-extrabold text-stone-855 text-sm border-b border-stone-100 pb-2">{t("AI Insights Preview")}</h3>
                  
                  <div className="space-y-3">
                    {/* Critical */}
                    <div className="flex items-center justify-between p-3.5 bg-red-50/50 border border-red-100 rounded-xl">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-red-600 animate-pulse"></span>
                        <span className="text-xs font-bold text-stone-750">Critical</span>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-black text-red-600">{reportDetails?.threat_count_critical ?? 18}</div>
                        <div className="text-[9px] text-red-650/80 font-bold mt-0.5">+12% vs last month</div>
                      </div>
                    </div>

                    {/* High */}
                    <div className="flex items-center justify-between p-3.5 bg-amber-50/40 border border-amber-100 rounded-xl">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
                        <span className="text-xs font-bold text-stone-750">High</span>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-black text-amber-600">{reportDetails?.threat_count_high ?? 56}</div>
                        <div className="text-[9px] text-amber-600/80 font-bold mt-0.5">+9% vs last month</div>
                      </div>
                    </div>

                    {/* Medium */}
                    <div className="flex items-center justify-between p-3.5 bg-yellow-50/30 border border-yellow-100 rounded-xl">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-yellow-400"></span>
                        <span className="text-xs font-bold text-stone-750">Medium</span>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-black text-yellow-600">{reportDetails?.threat_count_medium ?? 103}</div>
                        <div className="text-[9px] text-yellow-650/80 font-bold mt-0.5">+5% vs last month</div>
                      </div>
                    </div>
                  </div>

                  {/* Summary Grid stats */}
                  <div className="grid grid-cols-2 gap-4 border-t border-stone-100 pt-4 text-center">
                    <div className="p-3 bg-stone-50 border border-stone-150 rounded-xl">
                      <div className="text-[9px] text-stone-400 font-bold uppercase tracking-wider">Total Alerts</div>
                      <div className="text-base font-black text-stone-800 mt-1">{reportDetails?.total_records_parsed ?? 177}</div>
                    </div>
                    <div className="p-3 bg-stone-50 border border-stone-150 rounded-xl">
                      <div className="text-[9px] text-stone-400 font-bold uppercase tracking-wider">Total Incidents</div>
                      <div className="text-base font-black text-stone-800 mt-1">
                        {reportDetails 
                          ? (reportDetails.threat_count_critical + reportDetails.threat_count_high + reportDetails.threat_count_medium)
                          : 26
                        }
                      </div>
                    </div>
                  </div>
                </div>

              </div>

              {/* Status information or Error messages */}
              {errorMsg && (
                <div className="bg-red-50 border border-red-200 text-red-750 px-4 py-3 rounded-xl text-xs font-medium text-left">
                  <strong>Error:</strong> {errorMsg}
                </div>
              )}

              {/* Bottom Nav Bar */}
              <div className="pt-6 border-t border-stone-200/60 mt-8 flex flex-col items-end gap-2">
                <p className="text-[10px] text-stone-500 font-bold">Estimated time: 2 - 5 minutes</p>
                
                <div className="flex justify-between items-center w-full">
                  <button
                    onClick={handleBackStep}
                    disabled={aiStatus === "processing"}
                    className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white border border-stone-200 hover:bg-stone-50 text-stone-700 font-bold text-sm shadow-sm transition-all duration-200 disabled:opacity-50"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
                    </svg>
                    Back
                  </button>                  {aiStatus === "completed" ? (
                    <button
                      onClick={handleProceedToEditor}
                      className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-petro-green hover:bg-petro-green-hover text-white font-bold text-sm shadow transition-all duration-200 group"
                    >
                      {t("View Preview & Edit")}
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5 transition-transform group-hover:translate-x-1">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                      </svg>
                    </button>
                  ) : (
                    <button
                      disabled
                      className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-petro-green text-white font-bold text-sm shadow cursor-not-allowed"
                    >
                      <svg className="animate-spin h-3.5 w-3.5 text-white mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      {t("Processing......")}
                    </button>
                  )}
                </div>
              </div>
            </ScrollReveal>
          )}

          {/* STEP 4: PREVIEW & EDIT */}
          {currentStep === 4 && (
            <ScrollReveal animation="fadeInUp" delay={100} className="space-y-6">
              <div className="text-left">
                <h2 className="text-2xl font-extrabold text-stone-900">{t("Preview & Edit")}</h2>
                <p className="text-sm text-stone-500 font-semibold mt-1">{t("Review AI generated content and make any necessary edits")}</p>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 text-left items-start mt-6">
                
                {/* Left Panel: Pages List */}
                <div className="lg:col-span-3 bg-white rounded-2xl border border-stone-200/80 p-5 shadow-sm space-y-4 premium-card-hover">
                  <h3 className="font-extrabold text-stone-855 text-sm border-b border-stone-100 pb-2">{t("Pages")}</h3>
                  
                  <div className="space-y-1.5">
                    {[
                      { id: "01", label: "01 Executive Summary" },
                      { id: "02", label: "02 Threat Overview" },
                      { id: "03", label: "03 Attack Summary" },
                      { id: "04", label: "04 VAPT Summary" },
                      { id: "05", label: "05 Bandwidth Summary" },
                      { id: "06", label: "06 Threat Hunting" },
                      { id: "07", label: "07 Conclusion & Rec." }
                    ].map((pg) => (
                      <button
                        key={pg.id}
                        onClick={() => setActivePage(pg.id)}
                        className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-xs font-bold transition-all ${
                          activePage === pg.id
                            ? "bg-petro-green/10 text-petro-green border border-petro-green/20"
                            : "bg-transparent text-stone-600 hover:bg-stone-50 border border-transparent"
                        }`}
                      >
                        <span className="truncate">{t(pg.label.substring(3))}</span>
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
                      className="p-1 hover:text-stone-750 disabled:opacity-30 disabled:pointer-events-none transition-colors"
                    >
                      &lt; {t("Prev")}
                    </button>
                    <span>{t("Page")} {activePage} {t("of")} 07</span>
                    <button 
                      disabled={activePage === "07"}
                      onClick={() => {
                        const next = String(Number(activePage) + 1).padStart(2, "0");
                        setActivePage(next);
                      }}
                      className="p-1 hover:text-stone-750 disabled:opacity-30 disabled:pointer-events-none transition-colors"
                    >
                      {t("Next")} &gt;
                    </button>
                  </div>
                </div>

                {/* Center Panel: Preview & Edit Workspace */}
                <div className="lg:col-span-6 bg-white rounded-2xl border border-stone-200/80 p-6 shadow-sm space-y-6 premium-card-hover">
                  
                  {/* Tab Selector */}
                  <div className="flex justify-between items-center border-b border-stone-150 pb-2">
                    <div className="flex gap-2">
                      {(["preview", "edit", "charts"] as const).map((tab) => (
                        <button
                          key={tab}
                          onClick={() => setActiveTab(tab)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all capitalize ${
                            activeTab === tab
                              ? "bg-stone-900 text-white"
                              : "bg-stone-50 text-stone-500 hover:bg-stone-100"
                          }`}
                        >
                          {tab === "edit" ? t("Edit Text") : t(tab)}
                        </button>
                      ))}
                    </div>

                    {/* Live Save Status */}
                    {activeTab === "edit" && (
                      <button
                        onClick={handleSaveEdits}
                        disabled={isSaving}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-petro-green hover:bg-petro-green-hover text-white text-[11px] font-bold rounded-lg shadow-sm transition-all"
                      >
                        {isSaving ? (
                          <div className="w-3 h-3 border-2 border-white/35 border-t-white rounded-full animate-spin"></div>
                        ) : saveSuccess ? (
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                            <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                          </svg>
                        ) : (
                          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                            <path d="M10.75 4.75a.75.75 0 0 0-1.5 0v4.5h-4.5a.75.75 0 0 0 0 1.5h4.5v4.5a.75.75 0 0 0 1.5 0v-4.5h4.5a.75.75 0 0 0 0-1.5h-4.5v-4.5Z" />
                          </svg>
                        )}
                        {isSaving ? t("Saving...") : saveSuccess ? t("Saved!") : t("Save Changes")}
                      </button>
                    )}
                  </div>

                  {/* Tab Contents */}
                  <div className="min-h-[350px]">
                    {activeTab === "preview" && (
                      <div className="border border-stone-200 rounded-xl p-8 shadow-inner bg-white max-w-lg mx-auto flex flex-col justify-between min-h-[460px]">
                        {/* Letter Header */}
                        <div>
                          <div className="flex items-center justify-between border-b-2 border-stone-300 pb-3 mb-6">
                            <div className="flex items-center gap-2">
                              <div className="w-7 h-7 rounded-full bg-petro-green flex items-center justify-center text-white font-black text-[10px]">
                                PKG
                              </div>
                              <div className="text-left leading-none">
                                <span className="text-[10px] font-black text-stone-850 tracking-wider">PETROKIMIA GRESIK</span>
                                <br />
                                <span className="text-[6px] font-bold text-stone-400 uppercase tracking-widest">Solusi Agroindustri</span>
                              </div>
                            </div>
                            <span className="text-[8px] font-bold text-stone-450 tracking-wider uppercase">{t("SOC Executive Summary")}</span>
                          </div>

                          {/* Letter Content */}
                          <div className="space-y-4 text-left">
                            <div>
                              <h4 className="text-[9px] text-petro-green font-black uppercase tracking-widest">{t(getPageTitle(activePage))}</h4>
                              <h2 className="text-sm font-black text-stone-855 mt-1">{t("Monthly Security Operations Summary")}</h2>
                              <p className="text-[8px] text-stone-400 font-bold mt-0.5">{t("Period:")} {periodStart} {t("to")} {periodEnd}</p>
                            </div>

                            <p className="text-xs text-stone-600 font-semibold leading-relaxed whitespace-pre-wrap">
                              {getPageText(activePage)}
                            </p>

                            {/* Highlights on Step 1 */}
                            {activePage === "01" && (
                              <div className="p-3 bg-stone-50 border border-stone-200 rounded-xl text-left mt-5 space-y-1">
                                <h5 className="text-[9px] font-black text-stone-750 uppercase tracking-wider">{t("Key Highlights")}</h5>
                                <div className="grid grid-cols-2 gap-4 pt-1">
                                  <div>
                                    <span className="text-[8px] text-stone-400 font-semibold uppercase">{t("Total Alerts")}</span>
                                    <p className="text-sm font-black text-stone-800">{reportDetails?.total_records_parsed ?? 177} <span className="text-[9px] text-emerald-600 font-bold">+18.2%</span></p>
                                  </div>
                                  <div>
                                    <span className="text-[8px] text-stone-400 font-semibold uppercase">{t("Critical Threats")}</span>
                                    <p className="text-sm font-black text-stone-800">{reportDetails?.threat_count_critical ?? 18} <span className="text-[9px] text-red-650 font-bold">+12.0%</span></p>
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>

                        {/* Page Footer */}
                        <div className="flex justify-between items-center border-t border-stone-200 pt-3 mt-8 text-[8px] text-stone-400">
                          <span className="font-bold uppercase tracking-wider">{t("AI Security Reports")}</span>
                          <span className="font-black text-stone-700">{activePage}</span>
                        </div>
                      </div>
                    )}

                    {activeTab === "edit" && (
                      <div className="space-y-4">
                        <label className="block text-xs font-bold text-stone-600 uppercase tracking-wider">{t("Edit Content Text Area")}</label>
                        <textarea
                          value={getPageText(activePage)}
                          onChange={(e) => handleTextChange(e.target.value)}
                          className="w-full h-80 bg-stone-50 border border-stone-250 rounded-xl p-4 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-petro-green/20 focus:border-petro-green transition-all leading-relaxed"
                          placeholder={t("Type report page narrative contents here...")}
                        />
                      </div>
                    )}                    {activeTab === "charts" && (
                      <div className="border border-stone-200 rounded-xl p-6 bg-stone-50/50 flex flex-col justify-center items-center min-h-[350px]">
                        <h4 className="text-xs font-black text-stone-755 uppercase tracking-wider mb-6">{t("Threats Severity Distribution Chart")}</h4>
                        
                        <svg className="w-full max-w-sm h-64" viewBox="0 0 500 240">
                          <line x1="50" y1="30" x2="450" y2="30" stroke="#e5e7eb" strokeWidth="1" strokeDasharray="3 3" />
                          <line x1="50" y1="80" x2="450" y2="80" stroke="#e5e7eb" strokeWidth="1" strokeDasharray="3 3" />
                          <line x1="50" y1="130" x2="450" y2="130" stroke="#e5e7eb" strokeWidth="1" strokeDasharray="3 3" />
                          <line x1="50" y1="180" x2="450" y2="180" stroke="#d1d5db" strokeWidth="1.5" />
                          
                          <text x="35" y="35" className="text-[10px] font-bold fill-stone-400" textAnchor="end">150</text>
                          <text x="35" y="85" className="text-[10px] font-bold fill-stone-400" textAnchor="end">100</text>
                          <text x="35" y="135" className="text-[10px] font-bold fill-stone-400" textAnchor="end">50</text>
                          <text x="35" y="185" className="text-[10px] font-bold fill-stone-400" textAnchor="end">0</text>

                          {/* Critical */}
                          <rect x="80" y={180 - Math.min(150, (reportDetails?.threat_count_critical ?? 18) * 1.2)} width="40" height={Math.min(150, (reportDetails?.threat_count_critical ?? 18) * 1.2)} rx="4" fill="#dc2626" />
                          <text x="100" y={170 - Math.min(150, (reportDetails?.threat_count_critical ?? 18) * 1.2)} className="text-[10px] font-black fill-red-600" textAnchor="middle">{reportDetails?.threat_count_critical ?? 18}</text>
                          <text x="100" y="205" className="text-[9px] font-bold fill-stone-500" textAnchor="middle">{t("Critical")}</text>

                          {/* High */}
                          <rect x="180" y={180 - Math.min(150, (reportDetails?.threat_count_high ?? 56) * 1.2)} width="40" height={Math.min(150, (reportDetails?.threat_count_high ?? 56) * 1.2)} rx="4" fill="#ea580c" />
                          <text x="200" y={170 - Math.min(150, (reportDetails?.threat_count_high ?? 56) * 1.2)} className="text-[10px] font-black fill-amber-600" textAnchor="middle">{reportDetails?.threat_count_high ?? 56}</text>
                          <text x="200" y="205" className="text-[9px] font-bold fill-stone-500" textAnchor="middle">{t("High")}</text>

                          {/* Medium */}
                          <rect x="280" y={180 - Math.min(150, (reportDetails?.threat_count_medium ?? 103) * 1.2)} width="40" height={Math.min(150, (reportDetails?.threat_count_medium ?? 103) * 1.2)} rx="4" fill="#eab308" />
                          <text x="300" y={170 - Math.min(150, (reportDetails?.threat_count_medium ?? 103) * 1.2)} className="text-[10px] font-black fill-yellow-600" textAnchor="middle">{reportDetails?.threat_count_medium ?? 103}</text>
                          <text x="300" y="205" className="text-[9px] font-bold fill-stone-500" textAnchor="middle">{t("Medium")}</text>

                          {/* Low */}
                          <rect x="380" y={180 - Math.min(150, (reportDetails?.threat_count_low ?? 20) * 1.2)} width="40" height={Math.min(150, (reportDetails?.threat_count_low ?? 20) * 1.2)} rx="4" fill="#3b82f6" />
                          <text x="400" y={170 - Math.min(150, (reportDetails?.threat_count_low ?? 20) * 1.2)} className="text-[10px] font-black fill-blue-600" textAnchor="middle">{reportDetails?.threat_count_low ?? 20}</text>
                          <text x="400" y="205" className="text-[9px] font-bold fill-stone-500" textAnchor="middle">{t("Low")}</text>
                        </svg>
                      </div>
                    )}
                  </div>
                </div>

                {/* Right Panel: Properties */}
                <div className="lg:col-span-3 bg-white rounded-2xl border border-stone-200/80 p-5 shadow-sm space-y-4 premium-card-hover">
                  <h3 className="font-extrabold text-stone-850 text-sm border-b border-stone-100 pb-2">{t("Properties")}</h3>
                  
                  <div>
                    <label className="block text-[10px] font-bold text-stone-500 uppercase tracking-wider mb-1.5">{t("Language")}</label>
                    <select
                      value={language}
                      disabled
                      className="w-full bg-stone-50 border border-stone-200 rounded-xl px-3 py-2 text-xs focus:outline-none text-stone-500"
                    >
                      <option value="English">{t("English")}</option>
                      <option value="Indonesian">{t("Indonesian")}</option>
                    </select>
                  </div>
                </div>

              </div>

              {/* Bottom Nav Bar */}
              <div className="flex justify-between pt-5 border-t border-stone-200/60 mt-8">
                <button
                  onClick={handleBackStep}
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white border border-stone-200 hover:bg-stone-50 text-stone-700 font-bold text-sm shadow-sm transition-all duration-200"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
                  </svg>
                  {t("Back")}
                </button>

                <button
                  onClick={handleNextStep}
                  className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-petro-green hover:bg-petro-green-hover text-white font-bold text-sm shadow transition-all duration-200 group"
                >
                  {t("Next Export")}
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5 transition-transform group-hover:translate-x-1">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
                  </svg>
                </button>
              </div>
            </ScrollReveal>
          )}

          {/* STEP 5: EXPORT */}
          {currentStep === 5 && (
            <ScrollReveal animation="scaleIn" delay={100} className="space-y-6 max-w-xl mx-auto">
              <div className="bg-white rounded-2xl border border-stone-200/80 p-8 shadow-sm text-center space-y-6">
                
                {/* Success Checkmark Circle */}
                <div className="w-16 h-16 rounded-full bg-emerald-50 border border-emerald-100 flex items-center justify-center mx-auto">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-8 h-8 text-emerald-600 animate-bounce">
                    <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12Zm13.36-1.814a.75.75 0 1 0-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 0 0-1.06 1.06l2.5 2.5a.75.75 0 0 0 1.14-.059l4.14-5.795Z" clipRule="evenodd" />
                  </svg>
                </div>

                <div className="space-y-2">
                  <h2 className="text-xl font-extrabold text-stone-900">{t("Report Generated Successfully!")}</h2>
                  <p className="text-xs text-stone-500 font-semibold">{t("Your SOC Security report is now ready for download.")}</p>
                </div>

                {/* Big Cards for Download */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4">
                  {/* PDF Download */}
                  <button
                    onClick={() => window.open(`http://localhost:8000/api/v1/history/${reportId}/pdf`, "_blank")}
                    className="flex flex-col items-center justify-center p-5 bg-white border border-stone-200 rounded-2xl premium-card-hover group text-center space-y-3 w-full cursor-pointer"
                  >
                    <div className="w-10 h-10 rounded-xl bg-red-50 flex items-center justify-center text-red-650 font-black text-xs">
                      PDF
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs font-extrabold text-stone-800">{t("Download PDF")}</div>
                      <div className="text-[9px] text-stone-400 font-bold">{t("Standard Document Format")}</div>
                    </div>
                  </button>

                  {/* PPTX Download */}
                  <button
                    onClick={() => window.open(`http://localhost:8000/api/v1/history/${reportId}/pptx`, "_blank")}
                    className="flex flex-col items-center justify-center p-5 bg-white border border-stone-200 rounded-2xl premium-card-hover group text-center space-y-3 w-full cursor-pointer"
                  >
                    <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center text-amber-600 font-black text-xs">
                      PPTX
                    </div>
                    <div className="space-y-1">
                      <div className="text-xs font-extrabold text-stone-800">{t("Download PPTX")}</div>
                      <div className="text-[9px] text-stone-400 font-bold">{t("Presentation Slide Deck")}</div>
                    </div>
                  </button>
                </div>

                {/* Reset button to start over */}
                <div className="pt-6 border-t border-stone-100 flex justify-center">
                  <button
                    onClick={() => {
                      setCurrentStep(0);
                      setReportId(null);
                      setReportDetails(null);
                      setEditedSummary({});
                      setAiStatus("pending");
                    }}
                    className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl border border-stone-200 hover:bg-stone-50 text-stone-700 font-bold text-xs shadow-sm transition-all"
                  >
                    {t("Generate Another Report")}
                  </button>
                </div>

              </div>
            </ScrollReveal>
          )}
        </main>
      </div>
    </div>
  );
}
