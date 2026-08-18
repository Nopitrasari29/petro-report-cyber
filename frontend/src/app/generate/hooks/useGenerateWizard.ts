import { useState, useEffect, useRef } from "react";
import { getLanguage } from "@/utils/i18n";
import { useTx } from "@/hooks/useTx";
import { API_BASE_URL, authHeaders, getToken } from "@/utils/api";
import { setNavGuardMessage } from "@/utils/navGuard";
import { REPORT_SECTIONS, buildPagesFromBlocks, getPageByNumber } from "@/utils/reportSections";
import { fetchReportBlocks } from "@/utils/reportBlocksApi";
import { arrayItemsToHtml, htmlToArrayItems } from "@/utils/richTextArrayBridge";
import { DEFAULT_VISUAL_STYLE, type ReportBlock, type VisualStyle } from "@/utils/reportTheme";
import type { DynamicSectionItem } from "../components/Step2Settings";

interface UploadedFile {
  name: string;
  type: string;
  size: string;
  status: "success" | "pending" | "failed";
}

// Job AI di server TETAP jalan di background walau tab di-refresh/ditutup (background task
// tidak dibatalkan) — tapi sebelum ini, reportId cuma disimpan di useState React, jadi refresh
// di tengah Step 3 (AI Processing) membuat frontend kehilangan jejaknya SEPENUHNYA: user harus
// cari manual ke History, padahal job-nya sendiri baik-baik saja. Disimpan ke sessionStorage
// (bukan localStorage — sengaja per-tab/per-sesi browser, bukan lintas sesi) supaya bisa
// dipulihkan begitu halaman dimuat ulang.
const ACTIVE_REPORT_ID_KEY = "petro_generate_active_report_id";

// Seluruh state & logic wizard Generate Report (sebelumnya semuanya ada langsung di
// generate/page.tsx, ~1200 baris dalam 1 fungsi komponen) — dipindah ke sini SUPAYA page.tsx
// tinggal berisi komposisi JSX (Sidebar/Navbar/stepper/Step0..Step5), sementara "otak" wizard
// (state, effect, handler fetch) hidup di 1 tempat yang bisa dibaca terpisah dari tampilannya.
// TIDAK ada logika yang diubah di sini — murni salinan persis dari page.tsx, cuma dipindah &
// dikembalikan lewat 1 objek hasil hook ini.
export function useGenerateWizard() {
  const [currentStep, setCurrentStep] = useState<0 | 1 | 2 | 3 | 4 | 5>(0); // 0 = Overview, 1 = Upload, 2 = Settings, 3 = AI Processing, 4 = Preview & Edit, 5 = Export
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [reportId, setReportId] = useState<number | null>(null);

  const { tx } = useTx();

  // lang sendiri tidak pernah dibaca di mana pun — satu-satunya tujuannya adalah memaksa
  // re-render lewat setLang() begitu event "ui_language_changed" ditembak, supaya tx() (yang
  // membaca getLanguage() langsung tiap render) ikut menghasilkan teks baru. Pola yang sama
  // dipakai di beberapa halaman lain di aplikasi ini.
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

  // BUG DIPERBAIKI: kalau user ganti file dengan cepat (hapus file A, pilih file B sebelum
  // request deteksi periode/usulan section utk file A selesai), respons file A yang telat
  // datang bisa menimpa balik pengaturan (headerTitle/domainType/dynamicSections) yang sudah
  // benar utk file B. Ref ini menyimpan AbortController permintaan yang SEDANG berjalan,
  // dibatalkan setiap kali permintaan baru dimulai sebelum yang lama selesai.
  const periodAbortRef = useRef<AbortController | null>(null);
  const sectionsAbortRef = useRef<AbortController | null>(null);

  // Form States (Step 2)
  const [title, setTitle] = useState("");
  const [periodStart, setPeriodStart] = useState("");
  const [periodEnd, setPeriodEnd] = useState("");
  const [periodAutoDetected, setPeriodAutoDetected] = useState(false);
  const [periodDetecting, setPeriodDetecting] = useState(false);
  const [templateType, setTemplateType] = useState("");
  const [outputFormat, setOutputFormat] = useState("PDF");
  const [language, setLanguage] = useState("English");

  // Sinkronisasi default bahasa laporan dari preferensi personal user (/settings/profile).
  // Bukan lagi dari pengaturan global (/settings/), karena field "language" sudah dipindah
  // ke per-user. Field include_exec_summary/include_charts, dan belakangan includeAI/
  // includeRaw juga, yang dulu disinkronkan ke sini sudah dihapus total dari backend (tidak
  // pernah ada kontrol UI-nya sama sekali, cross-wire yang tidak nyambung ke apapun).
  useEffect(() => {
    const fetchFormDefaults = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/settings/profile`, {
          headers: authHeaders(),
        });
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

  const [headerTitle, setHeaderTitle] = useState("PT PETROKIMIA GRESIK");
  const [headerSubtitle, setHeaderSubtitle] = useState(
    "Sistem Otomasi Laporan & Eksekutif Presentasi Berbasis AI",
  );
  const [themeColor, setThemeColor] = useState("green");
  const [stylePreset, setStylePreset] = useState("auto");
  const [domainType, setDomainType] = useState("general");
  const [dynamicSections, setDynamicSections] = useState<DynamicSectionItem[]>(
    [],
  );
  const [sectionsLoading, setSectionsLoading] = useState(false);

  const [tone, setTone] = useState("Professional");
  const [defaultLevel, setDefaultLevel] = useState("Standard");
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

  // Peringatan sebelum keluar selagi AI masih memproses (diminta user, disertai screenshot
  // Step 5 yang sebelumnya tidak punya jalan balik sama sekali — masalah terkait: pindah ke
  // menu lain di tengah proses tanpa peringatan). 2 lapis:
  // 1) Navigasi DI DALAM aplikasi (klik Sidebar/menu Navbar) — lihat utils/navGuard.ts,
  //    Sidebar.tsx & Navbar.tsx membaca pesan ini lewat confirmNavAway() saat link diklik.
  // 2) Menutup/refresh tab atau pindah ke URL LUAR aplikasi — event browser native
  //    "beforeunload" di bawah.
  // CATATAN JUJUR (bukan disembunyikan, cuma pesannya disesuaikan supaya tidak salah info):
  // proses AI di server TIDAK BENAR-BENAR berhenti kalau halaman ini ditinggalkan (job
  // background tetap jalan, bisa dipulihkan lewat sessionStorage — lihat effect
  // recoverInProgressReport di bawah) — makanya pesannya bilang "tetap berjalan tapi Anda
  // perlu kembali ke sini", BUKAN "akan berhenti", supaya tidak menyesatkan pengguna.
  useEffect(() => {
    setNavGuardMessage(
      aiStatus === "processing"
        ? tx(
            "Analisis AI masih berjalan. Proses TETAP berjalan di server walau Anda pindah halaman, tapi Anda perlu kembali ke halaman ini nanti untuk melihat hasilnya. Yakin ingin keluar?",
            "AI analysis is still running. The process will keep running on the server even if you leave, but you'll need to come back to this page later to see the result. Leave anyway?",
          )
        : null,
    );
    return () => setNavGuardMessage(null);
  }, [aiStatus, tx]);

  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (aiStatus !== "processing") return;
      // Browser modern TIDAK mengizinkan teks kustom di dialog ini lagi (alasan anti-abuse) —
      // pesan yang benar-benar tampil ("Leave site? Changes you made may not be saved" dsb)
      // sepenuhnya ditentukan browser, apa pun isi returnValue di sini. Baris ini cuma
      // memicu dialognya muncul, bukan mengatur teksnya.
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [aiStatus]);

  // Progress token LIVE dari background job Ollama (di-poll dari GET /analysis/{id}/progress
  // tiap 2 detik selama status="processing") + perkiraan total token dari riwayat laporan user
  // (rata-rata tokens_generated laporan yang sudah selesai). Dua angka ini dipakai Step3 buat
  // menghitung kecepatan generate token asli dan sisa waktu yang genuinely bereaksi terhadapnya
  // — mirip ETA download yang dihitung dari bytes/detik yang benar-benar terukur, bukan animasi.
  const [tokensGenerated, setTokensGenerated] = useState<number | null>(null);
  const [expectedTotalTokens, setExpectedTotalTokens] = useState<number | null>(
    null,
  );

  // Report details state (Step 4 & 5)
  const [reportDetails, setReportDetails] = useState<any>(null);
  const [editedSummary, setEditedSummary] = useState<any>({});
  const [activeTab, setActiveTab] = useState<"preview" | "edit" | "charts">(
    "preview",
  );
  const [activePage, setActivePage] = useState("01");
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Blocks yang SAMA PERSIS dipakai backend untuk merender PDF/PPTX (build_report_blocks) —
  // dipindah ke sini (sebelumnya di-fetch terpisah & diam-diam berpotensi beda di Step4PreviewEdit
  // vs FullscreenStudioModal) supaya "pages" di bawah bisa dihitung dari struktur laporan ASLI,
  // bukan lagi 6 field ai_summary yang terpisah dari apa yang benar-benar tampil di Preview.
  const [blocks, setBlocks] = useState<ReportBlock[]>([]);
  const [visualStyle, setVisualStyle] = useState<VisualStyle>(DEFAULT_VISUAL_STYLE);
  // Warna TERRESOLVE dari backend (resolve_theme_color) — BEDA dari `themeColor` di atas, yang
  // itu cuma pilihan mentah user di picker Step 2 (bisa "auto"). Kalau user pilih "Automatic",
  // warna sungguhan baru DIKUNCI acak sekali saat analisis AI berhasil (lihat resolved_theme_color
  // di pick_visual_style()) — preview Step 4 harus baca hasil kunci itu dari sini, BUKAN
  // `themeColor` mentah (yang tetap "auto" selamanya di state picker, bukan warna sungguhan).
  const [resolvedThemeColor, setResolvedThemeColor] = useState("green");
  const [blocksLoading, setBlocksLoading] = useState(true);
  const [blocksError, setBlocksError] = useState("");

  useEffect(() => {
    const reportIdForBlocks = reportDetails?.id;
    if (!reportIdForBlocks) return;
    let cancelled = false;
    setBlocksLoading(true);
    setBlocksError("");
    fetchReportBlocks(reportIdForBlocks, getToken())
      .then(({ blocks: b, visualStyle: vs, themeColor: tc }) => {
        if (!cancelled) {
          setBlocks(b);
          setVisualStyle(vs);
          setResolvedThemeColor(tc);
        }
      })
      .catch((err) => {
        if (!cancelled) setBlocksError(err.message || "Gagal memuat preview.");
      })
      .finally(() => {
        if (!cancelled) setBlocksLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reportDetails?.id]);

  // Daftar halaman LENGKAP — sekarang 1:1 dengan block ASLI laporan (Cover, Latar Belakang,
  // Ringkasan Eksekutif, tiap chart/tabel, dst), urutan & judulnya PERSIS sama dengan tab
  // Preview & file PDF/PPTX yang diunduh. Dihitung ulang tiap kali blocks/editedSummary berubah.
  const pages = buildPagesFromBlocks(blocks, editedSummary, reportDetails?.included_sections);
  const getPageTitle = (page: string) => getPageByNumber(pages, page)?.title ?? "";
  const getPageContentKey = (page: string) => getPageByNumber(pages, page)?.key ?? null;

  const getPageText = (page: string) => {
    const key = getPageContentKey(page);
    if (!key) return "";
    const placeholder = tx(
      "Content not yet available for this section.",
      "Content not yet available for this section.",
    );

    if (key.startsWith("section:")) {
      const idx = Number(key.split(":")[1]);
      const sec = (editedSummary?.sections || [])[idx];
      return sec?.content || placeholder;
    }
    if (key.startsWith("chart_caption:")) {
      const idx = Number(key.split(":")[1]);
      return editedSummary?.chart_captions?.[idx] || placeholder;
    }

    let text = editedSummary[key];
    if (Array.isArray(text)) {
      return arrayItemsToHtml(text);
    }
    if (text) return text;

    // Belum ada konten AI untuk section ini (mis. field itu belum di-generate atau report
    // masih diproses) — tampilkan placeholder jujur, BUKAN narasi karangan yang kelihatan
    // seperti hasil analisis sungguhan padahal isinya sama untuk semua laporan.
    return placeholder;
  };

  const handleTextChange = (newVal: string) => {
    const key = getPageContentKey(activePage);
    if (!key) return;

    if (key.startsWith("section:")) {
      const idx = Number(key.split(":")[1]);
      const sectionsArr = Array.isArray(editedSummary?.sections)
        ? [...editedSummary.sections]
        : [];
      sectionsArr[idx] = { ...(sectionsArr[idx] || {}), content: newVal };
      setEditedSummary({ ...editedSummary, sections: sectionsArr });
      return;
    }
    if (key.startsWith("chart_caption:")) {
      const idx = Number(key.split(":")[1]);
      const captionsArr = Array.isArray(editedSummary?.chart_captions)
        ? [...editedSummary.chart_captions]
        : [];
      captionsArr[idx] = newVal;
      setEditedSummary({ ...editedSummary, chart_captions: captionsArr });
      return;
    }

    const originalVal = editedSummary[key];
    if (Array.isArray(originalVal)) {
      setEditedSummary({
        ...editedSummary,
        [key]: htmlToArrayItems(newVal, key === "recommendations"),
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
  //
  // SENGAJA dipisah dari usulan section AI (suggestSectionsFromFile di bawah) dan ditembak
  // BERSAMAAN (bukan salah satu menunggu yang lain) — deteksi periode ini murni parsing biasa
  // (cepat, hitungan detik), sedangkan usulan section AI bisa beberapa menit. Kalau digabung
  // jadi satu permintaan, field periode yang harusnya sudah bisa terisi duluan ikut tertahan
  // menunggu AI selesai.
  const detectPeriodFromFile = async (file: File) => {
    // Batalkan permintaan file SEBELUMNYA yang mungkin masih berjalan sebelum mulai yang baru.
    periodAbortRef.current?.abort();
    const controller = new AbortController();
    periodAbortRef.current = controller;

    setPeriodDetecting(true);
    setPeriodAutoDetected(false);
    try {
      const fd = new FormData();
      fd.append("file", file);

      const res = await fetch(`${API_BASE_URL}/api/v1/upload/detect-period`, {
        method: "POST",
        headers: authHeaders(),
        body: fd,
        signal: controller.signal,
      });

      if (res.ok) {
        const data = await res.json();
        if (data.detected && data.period_start && data.period_end) {
          setPeriodStart(data.period_start);
          setPeriodEnd(data.period_end);
          setPeriodAutoDetected(true);
        }
      }
    } catch (err: any) {
      if (err?.name === "AbortError") return; // dibatalkan krn file diganti — bukan error
      // Deteksi gagal itu bukan error fatal — user tetap bisa isi periode manual di Step 2.
      console.warn("[PERIOD DETECT] Gagal mendeteksi periode otomatis:", err);
    } finally {
      // Cuma reset loading state kalau ini masih permintaan TERKINI (belum digantikan
      // permintaan file lain yang lebih baru) — kalau sudah digantikan, biarkan permintaan
      // baru itu yang mengontrol status loading-nya sendiri.
      if (periodAbortRef.current === controller) {
        setPeriodDetecting(false);
      }
    }
  };

  // Usulan section AI + deteksi domain/kop header — bagian yang LAMBAT (bisa beberapa menit,
  // lihat section_suggester.py), sengaja dipanggil terpisah dari detectPeriodFromFile di atas.
  const suggestSectionsFromFile = async (file: File) => {
    // Batalkan permintaan file SEBELUMNYA yang mungkin masih berjalan sebelum mulai yang baru
    // (request ini bisa beberapa menit krn panggilan AI, jauh lebih rawan kena race ini).
    sectionsAbortRef.current?.abort();
    const controller = new AbortController();
    sectionsAbortRef.current = controller;

    setSectionsLoading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      // BUG DIPERBAIKI (dilaporkan user): tanpa ini, usulan Kop Subtitle/judul section dari
      // AI SELALU Bahasa Indonesia terlepas dari bahasa yang akan dipilih user di Step 2 —
      // endpoint ini dipanggil sebelum Step 2 dibuka, jadi kirim default bahasa user SAAT INI
      // (dari preferensi profil, lihat efek fetchFormDefaults di atas) sebagai perkiraan
      // terbaik yang tersedia di titik ini.
      fd.append("language", language);

      const res = await fetch(`${API_BASE_URL}/api/v1/upload/suggest-sections`, {
        method: "POST",
        headers: authHeaders(),
        body: fd,
        signal: controller.signal,
      });

      if (res.ok) {
        const data = await res.json();
        if (data.header_title) setHeaderTitle(data.header_title);
        if (data.header_subtitle) setHeaderSubtitle(data.header_subtitle);
        if (data.domain_type) setDomainType(data.domain_type);
        if (data.suggested_sections && Array.isArray(data.suggested_sections)) {
          setDynamicSections(data.suggested_sections);
        }
      }
    } catch (err: any) {
      if (err?.name === "AbortError") return; // dibatalkan krn file diganti — bukan error
      // Gagal itu bukan error fatal — fallback preset section tetap dipakai backend saat generate.
      console.warn("[SECTION SUGGEST] Gagal menyusun usulan section:", err);
    } finally {
      if (sectionsAbortRef.current === controller) {
        setSectionsLoading(false);
      }
    }
  };

  // BUG DIPERBAIKI: label "Maksimum 100MB per file" di Step 1 sebelumnya cuma teks - tidak
  // ada pengecekan nyata di frontend, jadi file oversized lolos ditampilkan "sukses" masuk
  // daftar sampai baru ketahuan gagal di submit akhir (backend memang sudah menegakkan batas
  // ini, jadi bukan celah keamanan - murni gap UX, feedback yang telat).
  const MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024;
  const ALLOWED_EXTENSIONS = [".csv", ".json", ".xlsx", ".xls", ".pdf"];

  // Handle local file adding — backend sekarang menerima BEBERAPA file sekaligus (digabung
  // jadi satu daftar data di server), jadi file baru ditambahkan ke daftar, bukan mengganti.
  const acceptNewFiles = (fileList: FileList) => {
    const allFiles = Array.from(fileList);
    if (allFiles.length === 0) return;

    // RCA-D02: Validasi format/ekstensi berkas di sisi klien
    const invalidExtFiles = allFiles.filter((f) => {
      const ext = "." + (f.name.split(".").pop() || "").toLowerCase();
      return !ALLOWED_EXTENSIONS.includes(ext);
    });

    if (invalidExtFiles.length > 0) {
      setErrorMsg(
        `${tx("Format berkas berikut tidak didukung (hanya .csv, .json, .xlsx, .xls, .pdf):", "The following file formats are not supported (only .csv, .json, .xlsx, .xls, .pdf):")} ${invalidExtFiles.map((f) => f.name).join(", ")}.`,
      );
    }

    const validExtFiles = allFiles.filter((f) => {
      const ext = "." + (f.name.split(".").pop() || "").toLowerCase();
      return ALLOWED_EXTENSIONS.includes(ext);
    });

    const oversized = validExtFiles.filter((f) => f.size > MAX_UPLOAD_SIZE_BYTES);
    const newFiles = validExtFiles.filter((f) => f.size <= MAX_UPLOAD_SIZE_BYTES);
    if (oversized.length > 0) {
      setErrorMsg(
        `${tx("File berikut melebihi batas maksimum 100MB dan tidak ditambahkan:", "The following files exceed the 100MB limit and were not added:")} ${oversized.map((f) => f.name).join(", ")}.`,
      );
    }
    if (newFiles.length === 0) return;

    // Validasi konsistensi format jika sudah ada berkas sebelumnya atau upload multi-file
    const combinedFiles = [...rawFiles, ...newFiles];
    if (combinedFiles.length > 1) {
      const exts = new Set(
        combinedFiles.map((f) => "." + (f.name.split(".").pop() || "").toLowerCase()),
      );
      if (exts.size > 1) {
        setErrorMsg(
          tx(
            "Semua berkas yang diunggah harus memiliki format/ekstensi yang sama (contoh: semua .csv atau semua .xlsx).",
            "All uploaded files must share the same format/extension (e.g. all .csv or all .xlsx).",
          ),
        );
        return;
      }
    }

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
      // Ditembak BERSAMAAN (bukan salah satu menunggu yang lain) — lihat komentar di
      // masing-masing fungsi kenapa keduanya sengaja dipisah jadi 2 permintaan independen.
      detectPeriodFromFile(newFiles[0]);
      suggestSectionsFromFile(newFiles[0]);
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
      const res = await fetch(
        `${API_BASE_URL}/api/v1/history/?limit=10&status=analyzed`,
        { headers: authHeaders() },
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

  // Ditandai true oleh handleCancelGeneration (tombol "Batalkan Proses") — dicek di loop
  // polling di bawah supaya pembatalan yang disengaja TIDAK ditampilkan sebagai "gagal karena
  // kesalahan tak terduga" (pesan generik utk kegagalan asli), karena di server keduanya
  // sama-sama berakhir sbg status "failed" — cuma sisi frontend ini yang tahu bedanya.
  const cancelRequestedRef = useRef(false);

  // Poll progress asli tiap 2 detik sampai job selesai (analyzed) atau gagal (failed), lalu
  // ambil detail hasil akhirnya. Dipisah jadi fungsi sendiri supaya bisa dipanggil ulang oleh
  // handleRetryAnalysis TANPA mengulang upload file / membuat report baru dari nol.
  const pollAndFetchResult = async (generatedId: number) => {
    let finalStatus = "processing";
    // Jaring pengaman sisi frontend — dinaikkan dari 15 ke 25 menit karena generation sekarang
    // bisa lebih lama saat user memilih banyak section dinamis (PART A3 menambah muatan yang
    // harus ditulis model dalam satu panggilan yang sama).
    const pollDeadline = Date.now() + 1500 * 1000;
    while (finalStatus === "processing") {
      if (cancelRequestedRef.current) return; // handleCancelGeneration sudah atur state sendiri
      if (Date.now() > pollDeadline) {
        throw new Error(
          "Proses analisis AI melebihi batas waktu yang wajar di sisi frontend. Proses TETAP " +
            'berjalan di server — klik "Coba Lagi" untuk memeriksa status terbaru tanpa mengulang dari awal.',
        );
      }
      await new Promise((resolve) => setTimeout(resolve, 2000));
      const progRes = await fetch(
        `${API_BASE_URL}/api/v1/analysis/${generatedId}/progress`,
        { headers: authHeaders() },
      );
      if (!progRes.ok) continue; // hiccup jaringan sesaat — coba lagi tick berikutnya
      const prog = await progRes.json();
      finalStatus = prog.status;
      setTokensGenerated(prog.tokens_generated ?? 0);
      setExpectedTotalTokens(prog.expected_total_tokens ?? null);
    }

    if (cancelRequestedRef.current) return; // dibatalkan tepat saat tick terakhir — bukan gagal

    if (finalStatus === "failed") {
      throw new Error(
        "Proses analisis AI gagal karena kesalahan tak terduga di server. Silakan coba lagi.",
      );
    }

    setProcessingStep("fetching");
    const detailRes = await fetch(
      `${API_BASE_URL}/api/v1/history/${generatedId}`,
      {
        headers: authHeaders(),
      },
    );
    if (detailRes.ok) {
      const details = await detailRes.json();
      setReportDetails(details);
      setEditedSummary(details.ai_summary || {});
      if (!title && details.title) {
        setTitle(details.title);
      }
    }
    setProcessingStep("done");
    setAiStatus("completed");
  };

  // Pemulihan setelah refresh di tengah Step 3 (AI Processing) — job AI di server TETAP jalan
  // di background walau tab sempat di-refresh/ditutup (tidak dibatalkan), tapi frontend dulu
  // kehilangan jejak reportId-nya sepenuhnya begitu reload (cuma di useState). Status laporan
  // yang tersimpan di sessionStorage (ACTIVE_REPORT_ID_KEY) dicek dulu ke server SEBELUM
  // diputuskan mau dipulihkan — kalau ternyata sudah tidak "processing" lagi (analyzed/failed/
  // sudah tidak ada), sessionStorage-nya dibuang saja, biarkan wizard mulai normal dari Step 0
  // (kasus itu di luar scope fix ini — cukup tangani hilangnya jejak proses yang MASIH berjalan,
  // yang paling merugikan karena bisa makan beberapa menit).
  useEffect(() => {
    const savedId = Number(sessionStorage.getItem(ACTIVE_REPORT_ID_KEY));
    if (!savedId) return;

    const recoverInProgressReport = async () => {
      try {
        const res = await fetch(
          `${API_BASE_URL}/api/v1/history/${savedId}`,
          { headers: authHeaders() },
        );
        if (!res.ok) {
          sessionStorage.removeItem(ACTIVE_REPORT_ID_KEY);
          return;
        }
        const details = await res.json();
        if (details.status !== "processing") {
          sessionStorage.removeItem(ACTIVE_REPORT_ID_KEY);
          return;
        }
        setReportId(savedId);
        setCurrentStep(3);
        setAiStatus("processing");
        setProcessingStep("analyzing");
        setProcessingStartedAt(Date.now());
        await pollAndFetchResult(savedId);
      } catch {
        sessionStorage.removeItem(ACTIVE_REPORT_ID_KEY);
      }
    };
    recoverInProgressReport();
  }, []);

  // Retry setelah timeout/gagal — TIDAK upload ulang file / bikin report baru. Cek dulu status
  // TERKINI di server (job background sebelumnya tidak ikut dibatalkan saat frontend menyerah,
  // jadi bisa jadi sudah selesai atau masih berjalan), baru putuskan: langsung tampilkan hasil,
  // lanjut polling saja, atau trigger analisis baru (kalau memang sudah "failed" di server).
  const handleRetryAnalysis = async () => {
    if (!reportId) return;
    cancelRequestedRef.current = false;
    setErrorMsg("");
    setAiStatus("processing");
    setProcessingStep("analyzing");
    setLoading(true);

    try {
      const statusRes = await fetch(
        `${API_BASE_URL}/api/v1/history/${reportId}`,
        {
          headers: authHeaders(),
        },
      );
      if (statusRes.ok) {
        const details = await statusRes.json();
        if (details.status === "analyzed") {
          setReportDetails(details);
          setEditedSummary(details.ai_summary || {});
          if (!title && details.title) {
            setTitle(details.title);
          }
          setProcessingStep("done");
          setAiStatus("completed");
          setLoading(false);
          return;
        }
        if (details.status === "processing") {
          await pollAndFetchResult(reportId);
          setLoading(false);
          return;
        }
      }

      // Status "failed" (atau tidak diketahui) — trigger ulang analisisnya dari server.
      const generateRes = await fetch(
        `${API_BASE_URL}/api/v1/analysis/generate/${reportId}`,
        { method: "POST", headers: authHeaders() },
      );
      if (!generateRes.ok) {
        let detail = "Gagal memicu ulang pemrosesan AI lokal (Ollama).";
        try {
          const errData = await generateRes.json();
          detail = errData.detail || detail;
        } catch {}
        throw new Error(detail);
      }
      await pollAndFetchResult(reportId);
      setLoading(false);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(
        err.message ||
          tx("Terjadi kesalahan tidak terduga.", "An unexpected error occurred."),
      );
      setAiStatus("pending");
      setProcessingStep("idle");
      setLoading(false);
    }
  };

  // Tombol "Batalkan Proses" (Step 3) — dipanggil SENGAJA oleh user, beda dari sekadar pindah
  // halaman (yang TETAP membiarkan job jalan di background, lihat catatan navGuard di atas).
  // TIDAK benar-benar menghentikan panggilan Ollama yang sedang jalan di server (lihat catatan
  // panjang di endpoint /cancel, backend/analysis.py) — tapi melepas kunci global SEKARANG JUGA
  // (server menandai laporan "failed") supaya user bisa langsung mulai generate laporan lain
  // tanpa menunggu. cancelRequestedRef mencegah pollAndFetchResult yang mungkin masih jalan
  // menampilkan pesan "gagal karena kesalahan tak terduga" (generik) padahal ini pembatalan
  // yang disengaja.
  const handleCancelGeneration = async () => {
    if (!reportId) return;
    cancelRequestedRef.current = true;
    try {
      await fetch(`${API_BASE_URL}/api/v1/analysis/${reportId}/cancel`, {
        method: "POST",
        headers: authHeaders(),
      });
    } catch (err) {
      console.warn("Gagal memberi tahu server soal pembatalan (tetap dianggap dibatalkan di sisi ini):", err);
    }
    sessionStorage.removeItem(ACTIVE_REPORT_ID_KEY);
    setLoading(false);
    setAiStatus("pending");
    setProcessingStep("idle");
    setErrorMsg(tx("Proses dibatalkan.", "Process cancelled."));
  };

  // Submit Settings and Start Upload to Backend
  const handleStartGeneration = async () => {
    cancelRequestedRef.current = false;
    if (!periodStart || !periodEnd) {
      setErrorMsg(
        tx(
          "Periode laporan belum terisi. Silakan isi Report Period secara manual di Step 2.",
          "Report period is not filled in. Please fill in the Report Period manually in Step 2.",
        ),
      );
      return;
    }

    const hasExportFormat = exportFormats.pdf || exportFormats.pptx;
    const hasSection = Object.values(sections).some((val) => val === true);

    // BUG DIPERBAIKI: dulu pakai alert() bawaan browser (blocking) - file ini sudah punya
    // errorMsg + render-nya sendiri (dipakai persis di atas utk validasi periode), jadi
    // konsisten pakai itu juga alih-alih import sistem toast baru cuma utk 2 titik ini.
    if (!hasExportFormat) {
      setErrorMsg(
        tx(
          "Silakan pilih setidaknya satu format export (PDF atau PowerPoint).",
          "Silakan pilih setidaknya satu format export (PDF atau PowerPoint).",
        ),
      );
      return;
    }
    if (!hasSection) {
      setErrorMsg(
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
      // 1. Kirim berkas log dan preferensi ke backend POST /api/v1/upload/
      const formData = new FormData();
      formData.append("title", title);

      // Map domain yang sudah dideteksi AI dari isi file (domainType, diisi oleh
      // suggestSectionsFromFile) ke data_type yang dipahami backend. `templateType` TIDAK
      // dipakai lagi di sini — tidak ada UI mana pun di wizard ini yang pernah mengisinya,
      // jadi sebelumnya data_type selalu jatuh ke default "firewall" untuk SEMUA domain.
      const domainToDataType: Record<string, string> = {
        financial: "keuangan",
        kpi_hr: "kpi_hr",
        soc_security: "firewall",
        procurement: "procurement",
      };
      const dataType = domainToDataType[domainType] || "operasional";

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
      formData.append("header_title", headerTitle);
      formData.append("header_subtitle", headerSubtitle);
      formData.append("theme_color", themeColor);
      formData.append("style_preset", stylePreset);
      formData.append("domain_type", domainType);
      formData.append("tone", tone);
      formData.append("default_level", defaultLevel);

      if (dynamicSections.length > 0) {
        // Kirim HANYA section yang dicentang user (bukan seluruh kandidat usulan AI),
        // beserta urutannya — backend memakai ini utk menyusun ai_summary["sections"].
        const selectedSections = dynamicSections.filter((s) => s.enabled);
        formData.append("included_sections", JSON.stringify(selectedSections));
      } else {
        formData.append("included_sections", JSON.stringify(sections));
      }

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
        headers: authHeaders(),
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
      sessionStorage.setItem(ACTIVE_REPORT_ID_KEY, String(generatedId));
      setProcessingStep("analyzing");

      // 2. Trigger AI Engine Analysis: POST /api/v1/analysis/generate/{report_id}
      // Endpoint ini sekarang langsung kembali (job Ollama jalan di background), jadi lanjut
      // polling progress token-nya secara live di bawah — bukan lagi 1 fetch yang nge-block
      // browser selama 3-10 menit.
      const generateRes = await fetch(
        `${API_BASE_URL}/api/v1/analysis/generate/${generatedId}`,
        {
          method: "POST",
          headers: authHeaders(),
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

      // 2b. Poll progress asli tiap 2 detik sampai job selesai (analyzed) atau gagal (failed) —
      // tokens_generated & expected_total_tokens dipakai Step3 buat menghitung sisa waktu yang
      // genuinely bereaksi ke kecepatan generate token — bukan cuma angka tetap dari riwayat.
      // pollAndFetchResult sendiri sudah men-set aiStatus="completed" & processingStep="done".
      await pollAndFetchResult(generatedId);
      setLoading(false);
    } catch (err: any) {
      console.error(err);
      setErrorMsg(
        err.message ||
          tx("Terjadi kesalahan tidak terduga.", "An unexpected error occurred."),
      );
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

  // BUG DIPERBAIKI (dilaporkan user): sebelumnya step 3 (AI Processing) tidak punya tujuan
  // "Back" SAMA SEKALI (tombol Back di Step3AIProcessing jadi tidak berfungsi kalau diklik
  // saat aiStatus bukan "processing"), dan step 4 (Preview & Edit) balik LONCAT ke step 2
  // (Report Settings), melewati step 3 begitu saja. Sekarang murni linear: tiap step balik
  // ke step SEBELUMNYA persis satu langkah, konsisten dgn urutan stepper di atas.
  const handleBackStep = () => {
    if (currentStep === 1) setCurrentStep(0);
    else if (currentStep === 2) setCurrentStep(1);
    else if (currentStep === 3) setCurrentStep(2);
    else if (currentStep === 4) setCurrentStep(3);
    else if (currentStep === 5) setCurrentStep(4);
  };

  const handleProceedToEditor = () => {
    setCurrentStep(4);
  };

  // Rename inline (pensil di judul, Step 4) — murni simpan nama, tidak memindah step apa pun.
  // BUG DIPERBAIKI (kerapian): dulu title (state form Step 2, dibutuhkan SEBELUM laporan ada
  // krn dikirim di body upload) dan reportDetails.title (title laporan yang SUDAH ada di
  // server) di-setState manual berpasangan di sini - 2 tempat yang harus selalu diingat
  // disinkronkan bareng. Sekarang cuma reportDetails yang di-update di sini; title (dipakai
  // utk TAMPILAN setelah laporan ada) ikut sinkron otomatis lewat useEffect di bawah begitu
  // reportDetails.title berubah - 1 sumber kebenaran (reportDetails.title) setelah laporan ada,
  // title tetap independen HANYA sebelum reportId ada (state form Step 2 yang belum terkirim).
  const handleRenameTitle = async (newTitle: string) => {
    const prevDetails = reportDetails;
    setReportDetails((prev: any) =>
      prev ? { ...prev, title: newTitle } : prev,
    );
    if (!reportId) return;
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/analysis/${reportId}`, {
        method: "PUT",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({ title: newTitle }),
      });
      if (!res.ok) throw new Error("Gagal menyimpan nama laporan.");
    } catch (e) {
      console.error(e);
      setReportDetails(prevDetails);
    }
  };

  // Sinkronisasi SATU ARAH: title (dipakai utk tampilan/form) mengikuti reportDetails.title
  // begitu laporan sudah ada di server - reportDetails.title jadi sumber kebenaran setelah itu,
  // title tidak lagi perlu di-set manual berpasangan di setiap titik yang mengubah judul.
  useEffect(() => {
    if (reportDetails?.title) {
      setTitle(reportDetails.title);
    }
  }, [reportDetails?.title]);

  const handleSaveEdits = async () => {
    if (!reportId) return;
    setIsSaving(true);
    setSaveSuccess(false);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/analysis/${reportId}`, {
        method: "PUT",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          ai_summary: editedSummary,
        }),
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

  // Reset penuh ke Step 0 (tombol "Buat Laporan Baru" di Step 5) — sebelumnya inline di JSX
  // onReset={() => {...}}, dipindah ke sini supaya page.tsx tidak perlu tahu daftar lengkap
  // state yang harus direset satu-satu.
  const resetWizard = () => {
    sessionStorage.removeItem(ACTIVE_REPORT_ID_KEY);
    setCurrentStep(0);
    setReportId(null);
    setReportDetails(null);
    setEditedSummary({});
    setAiStatus("pending");
    setProcessingStep("idle");
    setProcessingStartedAt(null);
    setFiles([]);
    setRawFiles([]);
    setPeriodStart("");
    setPeriodEnd("");
    setPeriodAutoDetected(false);
    setTemplateType("");
    setLanguage("English");
    setDynamicSections([]);
    setSectionsLoading(false);
    setHeaderTitle("PT PETROKIMIA GRESIK");
    setHeaderSubtitle(
      "Sistem Otomasi Laporan & Eksekutif Presentasi Berbasis AI",
    );
    setThemeColor("green");
    setStylePreset("auto");
    setDomainType("general");
    setTone("Professional");
    setDefaultLevel("Standard");
    setSections(
      Object.fromEntries(REPORT_SECTIONS.map((s) => [s.key, true])),
    );
    setExportFormats({ pdf: false, pptx: false });
    setBlocks([]);
    setBlocksLoading(true);
    setBlocksError("");
  };

  return {
    tx,
    currentStep,
    setCurrentStep,
    errorMsg,
    reportId,

    files,
    rawFiles,
    handleFileDrop,
    handleFileSelect,
    handleRemoveFile,

    periodStart,
    setPeriodStart,
    periodEnd,
    setPeriodEnd,
    periodAutoDetected,
    setPeriodAutoDetected,
    periodDetecting,

    language,
    setLanguage,
    exportFormats,
    setExportFormats,
    sections,
    setSections,
    dynamicSections,
    setDynamicSections,
    sectionsLoading,
    headerTitle,
    setHeaderTitle,
    headerSubtitle,
    setHeaderSubtitle,
    themeColor,
    setThemeColor,
    stylePreset,
    setStylePreset,
    templateType,
    setTemplateType,
    tone,
    setTone,
    defaultLevel,
    setDefaultLevel,

    aiStatus,
    processingStep,
    processingStartedAt,
    estimatedSeconds,
    tokensGenerated,
    expectedTotalTokens,
    reportDetails,

    title,
    editedSummary,
    pages,
    blocks,
    visualStyle,
    resolvedThemeColor,
    blocksLoading,
    blocksError,
    getPageText,
    getPageTitle,
    handleTextChange,
    handleSaveEdits,
    isSaving,
    saveSuccess,
    activeTab,
    setActiveTab,
    activePage,
    setActivePage,

    handleStartGeneration,
    handleRetryAnalysis,
    handleCancelGeneration,
    handleProceedToEditor,
    handleRenameTitle,
    handleNextStep,
    handleBackStep,
    resetWizard,
  };
}
