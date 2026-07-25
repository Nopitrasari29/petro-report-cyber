import React, { useEffect, useState } from "react";
import ScrollReveal from "@/components/ScrollReveal";

type ProcessingStep = "idle" | "uploading" | "analyzing" | "fetching" | "done";

interface Step3AIProcessingProps {
  aiStatus: "pending" | "processing" | "completed";
  processingStep: ProcessingStep;
  processingStartedAt: number | null;
  estimatedSeconds: number | null;
  tokensGenerated: number | null;
  expectedTotalTokens: number | null;
  reportDetails: any;
  errorMsg: string;
  onBack: () => void;
  onProceed: () => void;
  tx: (key: string, fallback: string) => string;
}

// Urutan tahap ASYNC NYATA yang bisa diamati dari frontend (masing-masing 1 network request
// terpisah) — dulu ada 6 item checklist dan progress bar "68%" yang statis, gak berhubungan
// sama sekali dengan proses yang sebenarnya berjalan. 3 tahap ini yang benar-benar bisa
// dibedakan; upload.py sendiri melakukan baca-file + parsing + hitung ancaman dalam SATU
// panggilan sinkron, jadi tidak bisa dipecah lebih detail lagi dari sisi frontend.
const STEP_ORDER: ProcessingStep[] = ["uploading", "analyzing", "fetching", "done"];

function stepIndex(step: ProcessingStep): number {
  return STEP_ORDER.indexOf(step);
}

// Bobot persentase disengaja tidak rata — tahap "analyzing" (Ollama menghasilkan narasi AI)
// biasanya paling lama, jadi diberi rentang persentase paling lebar supaya progress bar
// tidak "macet" kelamaan di satu angka.
const STEP_PROGRESS: Record<ProcessingStep, number> = {
  idle: 0,
  uploading: 10,
  analyzing: 35,
  fetching: 90,
  done: 100,
};

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  if (m === 0) return `${s}s`;
  return `${m}m ${s}s`;
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

// Sisa waktu dihitung dari KECEPATAN GENERATE TOKEN ASLI (tokens_generated / elapsedSeconds),
// persis seperti ETA download dihitung dari bytes/detik yang benar-benar terukur — bukan
// animasi. expectedTotalTokens (rata-rata riwayat laporan user) berperan sebagai "ukuran file"-
// nya; begitu model ternyata lebih cepat/lambat dari biasanya, angka ini otomatis naik/turun
// sendiri di setiap tick karena elapsedSeconds & tokensGenerated terus berubah.
function computeLiveRemainingSeconds(
  tokensGenerated: number | null,
  expectedTotalTokens: number | null,
  elapsedSeconds: number,
): number | null {
  if (!tokensGenerated || tokensGenerated <= 0 || elapsedSeconds <= 0) return null;
  if (!expectedTotalTokens || expectedTotalTokens <= 0) return null;
  const tokensPerSecond = tokensGenerated / elapsedSeconds;
  if (tokensPerSecond <= 0) return null;
  const remainingTokens = expectedTotalTokens - tokensGenerated;
  if (remainingTokens <= 0) return 0;
  return remainingTokens / tokensPerSecond;
}

export default function Step3AIProcessing({
  aiStatus,
  processingStep,
  processingStartedAt,
  estimatedSeconds,
  tokensGenerated,
  expectedTotalTokens,
  reportDetails,
  errorMsg,
  onBack,
  onProceed,
  tx,
}: Step3AIProcessingProps) {
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  // Elapsed tetap dihitung (dipakai sebagai fallback kalau belum ada riwayat buat estimasi,
  // dan sebagai info kecil di sebelah estimasi) — tapi yang ditonjolkan ke user sekarang
  // ESTIMASI dari riwayat laporan sebelumnya, sesuai yang diminta, bukan cuma "sudah berapa
  // lama jalan".
  useEffect(() => {
    if (!processingStartedAt || aiStatus === "completed") return;
    const interval = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - processingStartedAt) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [processingStartedAt, aiStatus]);

  const progressPct = aiStatus === "completed" ? 100 : STEP_PROGRESS[processingStep];
  const currentIdx = stepIndex(processingStep);

  // Live, self-correcting (bisa naik/turun sendiri kalau kecepatan model berubah) — dipakai
  // sebagai prioritas utama begitu token pertama sudah datang; sebelum itu (atau kalau user
  // belum punya riwayat token sama sekali) fallback ke estimatedSeconds (rata-rata riwayat).
  const liveRemainingSeconds = computeLiveRemainingSeconds(
    tokensGenerated,
    expectedTotalTokens,
    elapsedSeconds,
  );
  const tokensPerSecond =
    tokensGenerated && elapsedSeconds > 0 ? tokensGenerated / elapsedSeconds : null;

  // Deskripsi per-tahap lebih detail — dikonfirmasi lewat pengetesan langsung bahwa tahap
  // analisis AI (Ollama, model qwen3:8b "thinking") genuinely butuh beberapa menit untuk
  // menghasilkan 6 bagian narasi laporan, bukan cuma beberapa detik seperti kesan progress
  // bar lama yang statis "68%".
  const checklistItems: { label: string; detail: string; stepAt: ProcessingStep }[] = [
    {
      label: tx("Uploading & parsing file", "Uploading & parsing file"),
      detail: tx(
        "Membaca isi berkas dan mengekstrak baris data log.",
        "Membaca isi berkas dan mengekstrak baris data log.",
      ),
      stepAt: "uploading",
    },
    {
      label: tx("Running AI analysis (Ollama)", "Running AI analysis (Ollama)"),
      // Begitu token pertama sudah datang dari background job, tampilkan progress ASLI
      // (jumlah token + kecepatan token/detik) — sebelum itu, tampilkan deskripsi umum.
      detail:
        tokensGenerated && tokensGenerated > 0
          ? tx(
              `~${tokensGenerated} token dihasilkan${tokensPerSecond ? ` (~${tokensPerSecond.toFixed(1)} token/detik)` : ""}.`,
              `~${tokensGenerated} tokens generated${tokensPerSecond ? ` (~${tokensPerSecond.toFixed(1)} tokens/sec)` : ""}.`,
            )
          : tx(
              "Model AI lokal (qwen3:8b) menyusun 6 bagian narasi laporan — biasanya beberapa menit tergantung ukuran data.",
              "Model AI lokal (qwen3:8b) menyusun 6 bagian narasi laporan — biasanya beberapa menit tergantung ukuran data.",
            ),
      stepAt: "analyzing",
    },
    {
      label: tx("Fetching final report", "Fetching final report"),
      detail: tx(
        "Mengambil hasil akhir laporan dari server untuk ditampilkan.",
        "Mengambil hasil akhir laporan dari server untuk ditampilkan.",
      ),
      stepAt: "fetching",
    },
  ];

  return (
    <ScrollReveal animation="fadeInUp" className="space-y-6">
      <div className="text-left">
        <h2 className="text-2xl font-extrabold text-stone-900">{tx("AI Processing", "AI Processing")}</h2>
        <p className="text-sm text-stone-500 font-semibold mt-1">
          {tx("Our AI is analyzing your data and generating insights", "Our AI is analyzing your data and generating insights")}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 text-left items-start mt-6">
        {/* Left Column (60% width): Processing Progress */}
        <div className="lg:col-span-7 bg-white rounded-2xl border border-stone-200/80 p-6 shadow-sm space-y-6 premium-card-hover transition-colors">
          <div>
            <div className="flex justify-between items-center mb-2">
              <h3 className="font-extrabold text-stone-855 text-sm">{tx("Processing Progress", "Processing Progress")}</h3>
              <span className="text-xs font-bold text-petro-green">{progressPct}%</span>
            </div>
            {/* Progress Bar */}
            <div className="w-full h-3 bg-stone-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-petro-green transition-all duration-500"
                style={{ width: `${progressPct}%` }}
              ></div>
            </div>
          </div>

          {/* Checklist — 3 tahap nyata, statusnya diturunkan dari processingStep sungguhan */}
          <div className="space-y-4">
            {checklistItems.map((item) => {
              const itemIdx = stepIndex(item.stepAt);
              const isDone = aiStatus === "completed" || currentIdx > itemIdx;
              const isActive = !isDone && currentIdx === itemIdx;

              return (
                <div key={item.stepAt} className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    {isDone ? (
                      <span className="w-5 h-5 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center shrink-0">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-emerald-600">
                          <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                        </svg>
                      </span>
                    ) : isActive ? (
                      <span className="w-5 h-5 rounded-full bg-amber-50 border border-amber-200 flex items-center justify-center shrink-0">
                        <div className="w-2.5 h-2.5 border-2 border-stone-200 border-t-amber-500 rounded-full animate-spin"></div>
                      </span>
                    ) : (
                      <span className="w-5 h-5 rounded-full bg-stone-50 border border-stone-200 flex items-center justify-center shrink-0"></span>
                    )}
                    <div className="flex flex-col">
                      <span className={`text-xs font-bold ${isDone || isActive ? "text-stone-700" : "text-stone-400"}`}>
                        {item.label}
                      </span>
                      {/* Detail cuma ditampilkan buat tahap yang lagi AKTIF — supaya jelas
                          "AI-nya lagi ngapain" tanpa bikin daftar ini penuh teks sekaligus. */}
                      {isActive && (
                        <span className="text-[10px] text-stone-500 font-medium mt-0.5 max-w-xs">
                          {item.detail}
                        </span>
                      )}
                    </div>
                  </div>
                  <span className={`text-[10px] font-bold shrink-0 ${isDone ? "text-emerald-600" : isActive ? "text-amber-600" : "text-stone-400"}`}>
                    {isDone
                      ? tx("Completed", "Completed")
                      : isActive
                        ? tx("In Progress", "In Progress")
                        : tx("Waiting", "Waiting")}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Warning Alert */}
          <div className="bg-emerald-50/50 border border-emerald-100 rounded-xl p-4 flex gap-3 text-left">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5 text-emerald-650 shrink-0 mt-0.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
            <div>
              <p className="text-xs font-bold text-stone-800">{tx("Please don't close or refresh this page", "Please don't close or refresh this page")}</p>
              <p className="text-[10px] text-stone-500 font-semibold mt-0.5">{tx("This process may take a few minutes as our AI analyzes log data.", "This process may take a few minutes as our AI analyzes log data.")}</p>
            </div>
          </div>
        </div>

        {/* Right Column (40% width): AI Insights Preview */}
        <div className="lg:col-span-5 bg-white rounded-2xl border border-stone-200/80 p-6 shadow-sm space-y-4 premium-card-hover transition-colors">
          <h3 className="font-extrabold text-stone-855 text-sm border-b border-stone-100 pb-2">{tx("AI Insights Preview", "AI Insights Preview")}</h3>

          {!reportDetails ? (
            // Belum ada hasil sungguhan — dulu di sini nongol angka karangan (Critical 18,
            // High 56, dst dengan "+12% vs last month" yang juga karangan) SELAMA proses
            // masih berjalan, seolah-olah itu data asli. Sekarang jujur: kosong dulu sampai
            // hasil beneran datang dari backend.
            <div className="flex flex-col items-center justify-center py-10 text-center gap-3">
              <div className="w-8 h-8 border-4 border-stone-100 border-t-petro-green rounded-full animate-spin"></div>
              <p className="text-xs font-bold text-stone-500">
                {tx("Waiting for AI analysis to finish...", "Waiting for AI analysis to finish...")}
              </p>
            </div>
          ) : (
            <>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3.5 bg-red-50/50 border border-red-100 rounded-xl">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-red-600"></span>
                    <span className="text-xs font-bold text-stone-750">Critical</span>
                  </div>
                  <div className="text-sm font-black text-red-600">{reportDetails.threat_count_critical ?? 0}</div>
                </div>

                <div className="flex items-center justify-between p-3.5 bg-amber-50/40 border border-amber-100 rounded-xl">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
                    <span className="text-xs font-bold text-stone-750">High</span>
                  </div>
                  <div className="text-sm font-black text-amber-600">{reportDetails.threat_count_high ?? 0}</div>
                </div>

                <div className="flex items-center justify-between p-3.5 bg-yellow-50/30 border border-yellow-100 rounded-xl">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-yellow-400"></span>
                    <span className="text-xs font-bold text-stone-750">Medium</span>
                  </div>
                  <div className="text-sm font-black text-yellow-600">{reportDetails.threat_count_medium ?? 0}</div>
                </div>
              </div>

              {/* Summary Grid stats */}
              <div className="grid grid-cols-2 gap-4 border-t border-stone-100 pt-4 text-center">
                <div className="p-3 bg-stone-50 border border-stone-150 rounded-xl">
                  <div className="text-[9px] text-stone-400 font-bold uppercase tracking-wider">{tx("Total Records", "Total Records")}</div>
                  <div className="text-base font-black text-stone-800 mt-1">{reportDetails.total_records_parsed ?? 0}</div>
                </div>
                <div className="p-3 bg-stone-50 border border-stone-150 rounded-xl">
                  <div className="text-[9px] text-stone-400 font-bold uppercase tracking-wider">{tx("Total Incidents", "Total Incidents")}</div>
                  <div className="text-base font-black text-stone-800 mt-1">
                    {(reportDetails.threat_count_critical ?? 0) +
                      (reportDetails.threat_count_high ?? 0) +
                      (reportDetails.threat_count_medium ?? 0)}
                  </div>
                </div>
              </div>
            </>
          )}
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
        <p className="text-[10px] text-stone-500 font-bold">
          {aiStatus === "completed" ? (
            `${tx("Completed in", "Completed in")} ${formatElapsed(elapsedSeconds)}`
          ) : liveRemainingSeconds !== null ? (
            // Sisa waktu LIVE dari kecepatan generate token asli — dihitung ulang tiap detik,
            // jadi wajar naik/turun kalau model tiba-tiba lebih lambat/cepat dari rata-rata
            // riwayat. Ini yang bikin dia beda dari "estimatedSeconds" di bawah (angka tetap).
            <>
              {liveRemainingSeconds > 0 ? (
                <>
                  {tx("Estimated remaining", "Estimated remaining")}: ~
                  {formatDuration(liveRemainingSeconds)}
                </>
              ) : (
                tx("Finishing up...", "Finishing up...")
              )}
              <span className="text-stone-400 font-semibold">
                {" "}
                ({tx("elapsed", "elapsed")} {formatElapsed(elapsedSeconds)}
                {tokensPerSecond ? `, ~${tokensPerSecond.toFixed(1)} token/s` : ""})
              </span>
            </>
          ) : estimatedSeconds ? (
            // Belum ada cukup data token live (baru mulai / user belum punya riwayat token) —
            // fallback ke estimasi dari rata-rata processing_time_sec laporan sebelumnya.
            <>
              {tx("Estimated", "Estimated")}: ~{formatDuration(estimatedSeconds)}
              <span className="text-stone-400 font-semibold">
                {" "}
                ({tx("elapsed", "elapsed")} {formatElapsed(elapsedSeconds)})
              </span>
            </>
          ) : (
            <>
              {tx("Elapsed", "Elapsed")}: {formatElapsed(elapsedSeconds)}
              <span className="text-stone-400 font-semibold">
                {" "}
                (
                {tx(
                  "estimate available after your first report",
                  "estimate available after your first report",
                )}
                )
              </span>
            </>
          )}
        </p>

        <div className="flex justify-between items-center w-full">
          <button
            onClick={onBack}
            disabled={aiStatus === "processing"}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white border border-stone-200 hover:bg-stone-50 text-stone-700 font-bold text-sm shadow-sm transition-all duration-200 disabled:opacity-50 cursor-pointer"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
            </svg>
            {tx("Back", "Back")}
          </button>

          {aiStatus === "completed" ? (
            <button
              onClick={onProceed}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-petro-green hover:bg-petro-green-hover text-white font-bold text-sm shadow transition-all duration-200 group cursor-pointer"
            >
              {tx("View Preview & Edit", "View Preview & Edit")}
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
              {tx("Processing......", "Processing......")}
            </button>
          )}
        </div>
      </div>
    </ScrollReveal>
  );
}
