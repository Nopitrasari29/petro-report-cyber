"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Sidebar from "@/components/Sidebar";
import Navbar from "@/components/Navbar";
import ScrollReveal from "@/components/ScrollReveal";
import { t, getLanguage } from "@/utils/i18n";
import { API_BASE_URL } from "@/utils/api";
import {
  REPORT_SECTIONS,
  getSectionTitle,
  getSectionContentKey,
} from "@/utils/reportSections";
import Step0Overview from "./components/Step0Overview";
import Step1Upload from "./components/Step1Upload";
import Step2Settings from "./components/Step2Settings";
import Step3AIProcessing from "./components/Step3AIProcessing";
import Step4PreviewEdit from "./components/Step4PreviewEdit";
import Step5Export from "./components/Step5Export";
import TitlePromptModal from "./components/TitlePromptModal";

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
          `${API_BASE_URL}/api/v1/settings/profile`,
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

  const [tone, setTone] = useState("Professional");
  const [defaultLevel, setDefaultLevel] = useState("Standard");
  // Key di sini HARUS sama persis dengan key di REPORT_SECTIONS/ai_summary backend
  // (executive_summary, trend_analysis, dst) — bukan nama dekoratif seperti sebelumnya
  // ("vaptSummary", "bandwidthMonitoring") yang tidak berhubungan dengan section sungguhan
  // apapun, dan gara-gara itu checkbox ini dulu gak pernah benar-benar dikirim/dipakai.
  const [sections, setSections] = useState<Record<string, boolean>>(
    Object.fromEntries(REPORT_SECTIONS.map((s) => [s.key, true])),
  );
  const [exportFormats, setExportFormats] = useState<Record<string, boolean>>({
    pdf: false,
    pptx: false,
  });

  // Stepper Status (Step 3)
  const [aiStatus, setAiStatus] = useState<
    "pending" | "processing" | "completed"
  >("pending");
  // Progress "68%" & checklist yang selalu "Completed" dulu ternyata statis — gak mencerminkan
  // proses beneran sama sekali. processingStep melacak 3 tahap ASYNC NYATA yang benar-benar
  // bisa diamati dari frontend (upload+parse, analisis AI, ambil hasil akhir) — bukan 6 langkah
  // karangan yang gak bisa dibedakan satu sama lain dari sisi frontend.
  const [processingStep, setProcessingStep] = useState<
    "idle" | "uploading" | "analyzing" | "fetching" | "done"
  >("idle");
  const [processingStartedAt, setProcessingStartedAt] = useState<number | null>(
    null,
  );
  // Estimasi waktu dari RIWAYAT laporan milik user sendiri (rata-rata processing_time_sec
  // laporan yang sudah pernah selesai) — bukan angka "2-5 menit" yang di-hardcode tanpa
  // dasar apapun. null berarti belum ada riwayat sama sekali (user belum pernah generate
  // laporan sebelumnya) — di kondisi ini UI fallback ke pesan generik, bukan angka palsu.
  const [estimatedSeconds, setEstimatedSeconds] = useState<number | null>(null);

  // Progress token LIVE dari background job Ollama (di-poll dari GET /analysis/{id}/progress
  // tiap 2 detik selama status="processing") + perkiraan total token dari riwayat laporan user
  // (rata-rata tokens_generated laporan yang sudah selesai). Dua angka ini dipakai Step3 buat
  // menghitung kecepatan generate token asli dan sisa waktu yang genuinely bereaksi terhadapnya
  // — mirip ETA download yang dihitung dari bytes/detik yang benar-benar terukur, bukan animasi.
  const [tokensGenerated, setTokensGenerated] = useState<number | null>(null);
  const [expectedTotalTokens, setExpectedTotalTokens] = useState<number | null>(null);

  // Report details state (Step 4 & 5)
  const [reportDetails, setReportDetails] = useState<any>(null);
  const [editedSummary, setEditedSummary] = useState<any>({});
  const [activeTab, setActiveTab] = useState<"preview" | "edit" | "charts">(
    "preview",
  );
  const [activePage, setActivePage] = useState("01");
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const getPageTitle = getSectionTitle;
  const getPageContentKey = getSectionContentKey;

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

    // Belum ada konten AI untuk section ini (mis. field itu belum di-generate atau report
    // masih diproses) — tampilkan placeholder jujur, BUKAN narasi karangan yang kelihatan
    // seperti hasil analisis sungguhan padahal isinya sama untuk semua laporan.
    return tx(
      "Content not yet available for this section.",
      "Content not yet available for this section.",
    );
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
        `${API_BASE_URL}/api/v1/upload/detect-period`,
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

  // Handle local file adding — backend sekarang menerima BEBERAPA file sekaligus (digabung
  // jadi satu daftar data di server), jadi file baru ditambahkan ke daftar, bukan mengganti.
  const acceptNewFiles = (fileList: FileList) => {
    const newFiles = Array.from(fileList);
    if (newFiles.length === 0) return;

    const isFirstBatch = rawFiles.length === 0;

    setRawFiles((prev) => [...prev, ...newFiles]);
    setFiles((prev) => [
      ...prev,
      ...newFiles.map((file) => ({
        name: file.name,
        type: file.name.split(".").pop()?.toUpperCase() || "LOG",
        size: (file.size / (1024 * 1024)).toFixed(2) + " MB",
        status: "success" as const,
      })),
    ]);

    // Auto-deteksi periode cuma dari batch PERTAMA — kalau sudah ada file lain sebelumnya,
    // membiarkan deteksi otomatis menimpa periode yang mungkin sudah disesuaikan user secara
    // manual bisa lebih membingungkan daripada membantu. User tetap bisa edit manual di Step 2.
    if (isFirstBatch) {
      detectPeriodFromFile(newFiles[0]);
    }
  };

  const handleRemoveFile = (index: number) => {
    setRawFiles((prev) => prev.filter((_, i) => i !== index));
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      acceptNewFiles(e.dataTransfer.files);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      acceptNewFiles(e.target.files);
    }
    // Reset supaya user bisa pilih file yang sama lagi kalau perlu (browser tidak nge-trigger
    // onChange kalau value input tidak berubah dari sebelumnya).
    e.target.value = "";
  };

  // Ambil rata-rata processing_time_sec dari laporan-laporan user yang sudah pernah selesai,
  // buat dasar estimasi waktu yang genuinely berdasar data — bukan tebakan statis. Gagal/tidak
  // ada riwayat sama sekali dianggap wajar (user baru), bukan error yang perlu ditampilkan.
  const fetchEstimatedSeconds = async (): Promise<number | null> => {
    try {
      const token = localStorage.getItem("token");
      const authHeaders: Record<string, string> = {};
      if (token) authHeaders["Authorization"] = `Bearer ${token}`;

      const res = await fetch(
        `${API_BASE_URL}/api/v1/history/?limit=10&status=analyzed`,
        { headers: authHeaders },
      );
      if (!res.ok) return null;

      const reports = await res.json();
      const durations: number[] = (Array.isArray(reports) ? reports : [])
        .map((r: any) => r.processing_time_sec)
        .filter((v: any) => typeof v === "number" && v > 0);

      if (durations.length === 0) return null;
      return Math.round(
        durations.reduce((sum, v) => sum + v, 0) / durations.length,
      );
    } catch {
      return null;
    }
  };

  // Submit Settings and Start Upload to Backend
  const handleStartGeneration = async () => {
    if (!periodStart || !periodEnd) {
      setErrorMsg(
        "Periode laporan belum terisi. Silakan isi Report Period secara manual di Step 2."
      );
      return;
    }

    const hasExportFormat = exportFormats.pdf || exportFormats.pptx;
    const hasSection = Object.values(sections).some((val) => val === true);

    if (!hasExportFormat) {
      alert(
        tx(
          "Silakan pilih setidaknya satu format export (PDF atau PowerPoint).",
          "Silakan pilih setidaknya satu format export (PDF atau PowerPoint).",
        ),
      );
      return;
    }
    if (!hasSection) {
      alert(
        tx(
          "Silakan pilih setidaknya satu section laporan untuk dimasukkan.",
          "Silakan pilih setidaknya satu section laporan untuk dimasukkan.",
        ),
      );
      return;
    }

    setCurrentStep(3);
    setLoading(true);
    setErrorMsg("");
    setAiStatus("processing");
    setProcessingStep("uploading");
    setProcessingStartedAt(Date.now());
    setEstimatedSeconds(null);
    setTokensGenerated(null);
    setExpectedTotalTokens(null);
    fetchEstimatedSeconds().then(setEstimatedSeconds);

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
      // outputFormat lama selalu "PDF" statis (gak pernah diubah UI manapun) — sekarang
      // dihitung dari checkbox Export Format yang beneran dipilih user di Report Settings.
      const selectedFormats = [
        exportFormats.pdf && "PDF",
        exportFormats.pptx && "PPTX",
      ].filter(Boolean);
      formData.append(
        "output_format",
        selectedFormats.length > 0 ? selectedFormats.join("+") : outputFormat,
      );
      formData.append("language", language);
      formData.append("include_ai_insights", String(includeAI));
      formData.append("include_raw_data_summary", String(includeRaw));
      formData.append("included_sections", JSON.stringify(sections));

      // Step1Upload menonaktifkan tombol Next selama belum ada file, jadi ini seharusnya
      // tidak pernah kejadian lewat alur normal — tapi kalau sampai kejadian (state gak
      // sinkron dsb.), lebih baik gagal jelas daripada diam-diam kirim data CSV karangan
      // seolah-olah itu file asli milik user.
      if (rawFiles.length === 0) {
        throw new Error(
          "Tidak ada file yang diupload. Silakan kembali ke Step 1 dan upload file terlebih dahulu.",
        );
      }
      // Kirim SEMUA file (backend menggabungkan datanya jadi satu) — FormData mendukung
      // banyak entri dengan nama field yang sama, FastAPI mem-parsingnya sebagai List[UploadFile].
      rawFiles.forEach((file) => formData.append("files", file));

      const uploadRes = await fetch(`${API_BASE_URL}/api/v1/upload/`, {
        method: "POST",
        headers: authHeaders,
        body: formData,
      });

      if (!uploadRes.ok) {
        let detail = "Gagal mengunggah konfigurasi laporan siber ke server.";
        if (uploadRes.status === 401) {
          detail = "Sesi login Anda telah kedaluwarsa. Silakan login kembali.";
        } else {
          try {
            const errData = await uploadRes.json();
            detail = errData.detail || detail;
          } catch {}
        }
        throw new Error(detail);
      }

      const reportData = await uploadRes.json();
      const generatedId = reportData.id;
      setReportId(generatedId);
      setProcessingStep("analyzing");

      // 2. Trigger AI Engine Analysis: POST /api/v1/analysis/generate/{report_id}
      // Endpoint ini sekarang langsung kembali (job Ollama jalan di background), jadi lanjut
      // polling progress token-nya secara live di bawah — bukan lagi 1 fetch yang nge-block
      // browser selama 3-10 menit.
      const generateRes = await fetch(
        `${API_BASE_URL}/api/v1/analysis/generate/${generatedId}`,
        {
          method: "POST",
          headers: authHeaders,
        },
      );

      if (!generateRes.ok) {
        let detail = "Gagal memicu pemrosesan AI lokal (Ollama).";
        try {
          const errData = await generateRes.json();
          detail = errData.detail || detail;
        } catch {}
        throw new Error(detail);
      }

      // 2b. Poll progress asli tiap 2 detik sampai job selesai (analyzed) atau gagal (failed).
      // tokens_generated & expected_total_tokens dipakai Step3 buat menghitung sisa waktu yang
      // genuinely bereaksi ke kecepatan generate token — bukan cuma angka tetap dari riwayat.
      let finalStatus = "processing";
      // Jaring pengaman sisi frontend — backend sendiri sudah punya OLLAMA_TIMEOUT_SECONDS=600,
      // ditambah buffer supaya tidak polling selamanya kalau ada yang benar-benar macet.
      const pollDeadline = Date.now() + 900 * 1000;
      while (finalStatus === "processing") {
        if (Date.now() > pollDeadline) {
          throw new Error(
            "Proses analisis AI melebihi batas waktu yang wajar. Silakan cek status Ollama dan coba lagi.",
          );
        }
        await new Promise((resolve) => setTimeout(resolve, 2000));
        const progRes = await fetch(
          `${API_BASE_URL}/api/v1/analysis/${generatedId}/progress`,
          { headers: authHeaders },
        );
        if (!progRes.ok) continue; // hiccup jaringan sesaat — coba lagi tick berikutnya
        const prog = await progRes.json();
        finalStatus = prog.status;
        setTokensGenerated(prog.tokens_generated ?? 0);
        setExpectedTotalTokens(prog.expected_total_tokens ?? null);
      }

      if (finalStatus === "failed") {
        throw new Error(
          "Proses analisis AI gagal karena kesalahan tak terduga di server. Silakan coba lagi.",
        );
      }

      setProcessingStep("fetching");
      const detailRes = await fetch(
        `${API_BASE_URL}/api/v1/history/${generatedId}`,
        {
          headers: authHeaders,
        },
      );
      if (detailRes.ok) {
        const details = await detailRes.json();
        setReportDetails(details);
        setEditedSummary(details.ai_summary || {});
      }
      setProcessingStep("done");
      setAiStatus("completed");
      setLoading(false);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(err.message || "Terjadi kesalahan tidak terduga.");
      setAiStatus("pending");
      setProcessingStep("idle");
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

  const [showTitlePrompt, setShowTitlePrompt] = useState(false);

  const handleConfirmTitle = async (newTitle: string) => {
    setTitle(newTitle);
    setShowTitlePrompt(false);
    if (reportId) {
      try {
        const token = localStorage.getItem("token");
        const authHeaders: Record<string, string> = {
          "Content-Type": "application/json",
        };
        if (token) authHeaders["Authorization"] = `Bearer ${token}`;
        await fetch(`${API_BASE_URL}/api/v1/analysis/${reportId}`, {
          method: "PUT",
          headers: authHeaders,
          body: JSON.stringify({ title: newTitle }),
        });
      } catch (e) {
        console.error(e);
      }
    }
    handleNextStep();
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
        `${API_BASE_URL}/api/v1/analysis/${reportId}`,
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
      <div className="flex-1 pl-0 md:pl-64 flex flex-col min-h-screen">
        <Navbar />

        {/* Main Body */}
        <main className="flex-1 p-4 sm:p-6 md:p-8 max-w-6xl mx-auto w-full">
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
              rawFiles={rawFiles}
              onFileDrop={handleFileDrop}
              onFileSelect={handleFileSelect}
              onFileRemove={handleRemoveFile}
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
              processingStep={processingStep}
              processingStartedAt={processingStartedAt}
              estimatedSeconds={estimatedSeconds}
              tokensGenerated={tokensGenerated}
              expectedTotalTokens={expectedTotalTokens}
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
              onNext={() => setShowTitlePrompt(true)}
              tx={tx}
            />
          )}

          <TitlePromptModal
            isOpen={showTitlePrompt}
            initialTitle={title}
            onConfirm={handleConfirmTitle}
            onClose={() => setShowTitlePrompt(false)}
            tx={tx}
          />

          {/* STEP 5: EXPORT */}
          {currentStep === 5 && (
            <Step5Export
              reportId={reportId}
              exportFormats={exportFormats}
              onReset={() => {
                setCurrentStep(0);
                setReportId(null);
                setReportDetails(null);
                setEditedSummary({});
                setAiStatus("pending");
                setProcessingStep("idle");
                setProcessingStartedAt(null);
              }}
              tx={tx}
            />
          )}
        </main>
      </div>
    </div>
  );
}
