"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import ScrollReveal from "@/components/ScrollReveal";
import { API_BASE_URL, getToken, authHeaders } from "@/utils/api";
import { sanitizeFilename, downloadBlobAsFile } from "@/utils/downloadFile";

interface Step5ExportProps {
  reportId: number | null;
  reportTitle?: string;
  exportFormats: Record<string, boolean>;
  onReset: () => void;
  onBack: () => void;
  tx: (key: string, fallback: string) => string;
}

async function downloadAuthorizedFile(
  reportId: number | null,
  reportTitle: string | undefined,
  format: "pdf" | "pptx",
  tx: (key: string, fallback: string) => string,
) {
  if (!reportId) return;
  if (!getToken()) {
    throw new Error(
      tx(
        "Token tidak ditemukan. Silakan login ulang.",
        "Token not found. Please log in again.",
      ),
    );
  }

  const url = `${API_BASE_URL}/api/v1/history/${reportId}/${format}`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) {
    let detail = tx(
      "Gagal mengunduh {format}.",
      "Failed to download {format}.",
    ).replace("{format}", format.toUpperCase());
    if (res.status === 401) {
      detail = tx(
        "Token akses tidak valid atau telah kedaluwarsa. Silakan login ulang.",
        "Access token is invalid or has expired. Please log in again.",
      );
    }
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }

  const blob = await res.blob();
  const filenameBase = sanitizeFilename(reportTitle, `soc_report_${reportId}`);
  await downloadBlobAsFile(blob, `${filenameBase}.${format}`);
}

export default function Step5Export({
  reportId,
  reportTitle,
  exportFormats,
  onReset,
  onBack,
  tx,
}: Step5ExportProps) {
  const [downloadingFormat, setDownloadingFormat] = useState<"pdf" | "pptx" | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const handleDownload = async (format: "pdf" | "pptx") => {
    setDownloadingFormat(format);
    setErrorMsg("");
    try {
      await downloadAuthorizedFile(reportId, reportTitle, format, tx);
    } catch (err: any) {
      setErrorMsg(
        err.message || tx("Gagal mengunduh file.", "Failed to download file."),
      );
    } finally {
      setDownloadingFormat(null);
    }
  };

  const showPdf = exportFormats?.pdf || !exportFormats?.pptx;
  const showPptx = exportFormats?.pptx || !exportFormats?.pdf;
  return (
    // Sebelumnya root-nya sendiri dibatasi "max-w-xl mx-auto" — SATU-SATUNYA step yang
    // dibatasi begitu (Step0/1/2/4 semua mengisi penuh "max-w-6xl" dari page.tsx), makanya
    // proporsinya kelihatan kecil/beda sendiri dibanding step lain. Pembatas lebar sekarang
    // cuma di div pembungkus konten sukses di bawah (biar checkmark+kartu tetap ringkas &
    // tidak melebar aneh), bar tombol Back/Generate-Another-Report di paling bawah mengisi
    // lebar penuh & pakai pola bottom-nav-bar yang sama seperti step lain.
    <ScrollReveal animation="scaleIn" className="space-y-6">
    <div className="max-w-xl mx-auto space-y-6">
      {/* Success Checkmark Circle */}
      <div className="w-16 h-16 rounded-full bg-emerald-50 border border-emerald-100 flex items-center justify-center mx-auto">
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 24 24"
          fill="currentColor"
          className="w-8 h-8 text-emerald-600 animate-bounce"
        >
          <path
            fillRule="evenodd"
            d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12Zm13.36-1.814a.75.75 0 1 0-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 0 0-1.06 1.06l2.5 2.5a.75.75 0 0 0 1.14-.059l4.14-5.795Z"
            clipRule="evenodd"
          />
        </svg>
      </div>

      <div className="space-y-2">
        <h2 className="text-2xl font-extrabold text-stone-900">
          {tx(
            "Report Generated Successfully!",
            "Report Generated Successfully!",
          )}
        </h2>
        <p className="text-sm text-stone-500 font-semibold">
          {tx(
            "Your report is now ready for download.",
            "Your report is now ready for download.",
          )}
        </p>
      </div>

      {errorMsg && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-xs p-3 rounded-xl">
          {errorMsg}
        </div>
      )}

      {/* Big Cards for Download — cuma tampil sesuai format yang dicentang di Report Settings */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-4">
        {showPdf && (
          <button
            disabled={downloadingFormat !== null}
            onClick={() => handleDownload("pdf")}
            className="flex flex-col items-center justify-center p-6 bg-white border border-stone-200 rounded-2xl premium-card-hover group text-center space-y-3 w-full cursor-pointer transition-colors disabled:opacity-50"
          >
            {downloadingFormat === "pdf" ? (
              <div className="w-10 h-10 border-3 border-stone-200 border-t-red-600 rounded-full animate-spin"></div>
            ) : (
              <div className="w-10 h-10 rounded-xl bg-red-50 flex items-center justify-center text-red-655 font-black text-xs">
                PDF
              </div>
            )}
            <div className="space-y-1">
              <div className="text-xs font-extrabold text-stone-800">
                {downloadingFormat === "pdf" ? tx("Generating PDF...", "Generating PDF...") : tx("Download PDF", "Download PDF")}
              </div>
              <div className="text-[9px] text-stone-400 font-bold">
                {tx("Standard Document Format", "Standard Document Format")}
              </div>
            </div>
          </button>
        )}

        {showPptx && (
          <button
            disabled={downloadingFormat !== null}
            onClick={() => handleDownload("pptx")}
            className="flex flex-col items-center justify-center p-6 bg-white border border-stone-200 rounded-2xl premium-card-hover group text-center space-y-3 w-full cursor-pointer transition-colors disabled:opacity-50"
          >
            {downloadingFormat === "pptx" ? (
              <div className="w-10 h-10 border-3 border-stone-200 border-t-amber-600 rounded-full animate-spin"></div>
            ) : (
              <div className="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center text-amber-600 font-black text-xs">
                PPTX
              </div>
            )}
            <div className="space-y-1">
              <div className="text-xs font-extrabold text-stone-800">
                {downloadingFormat === "pptx" ? tx("Generating PPTX...", "Generating PPTX...") : tx("Download PPTX", "Download PPTX")}
              </div>
              <div className="text-[9px] text-stone-400 font-bold">
                {tx("Presentation Slide Deck", "Presentation Slide Deck")}
              </div>
            </div>
          </button>
        )}
      </div>
    </div>

      {/* Back ke Step 4 (Preview & Edit) + Reset button to start over — sebelumnya step ini
          SATU-SATUNYA yang tidak punya jalan balik sama sekali (dilaporkan user). Back di sini
          TIDAK membatalkan laporan yang sudah jadi — laporannya tetap ada, cuma kembali melihat
          tab Preview/Edit sebelum export. Bar ini sekarang mengisi lebar penuh & pakai ukuran
          tombol yang sama seperti bottom-nav-bar step lain (Step1/2/4), bukan lagi text-xs
          kecil berdempetan di dalam kolom sempit. */}
      <div className="flex justify-between pt-5 border-t border-stone-200/60 mt-8">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white border border-stone-200 hover:bg-stone-50 text-stone-700 font-bold text-sm shadow-sm transition-all duration-200 cursor-pointer"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
          </svg>
          {tx("Back", "Back")}
        </button>
        <button
          onClick={onReset}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-petro-green hover:bg-petro-green-hover text-white font-bold text-sm shadow transition-all duration-200 cursor-pointer"
        >
          {tx("Generate Another Report", "Generate Another Report")}
        </button>
      </div>
    </ScrollReveal>
  );
}
