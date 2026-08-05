"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import ScrollReveal from "@/components/ScrollReveal";
import { API_BASE_URL } from "@/utils/api";
import { sanitizeFilename, downloadBlobAsFile } from "@/utils/downloadFile";

interface Step5ExportProps {
  reportId: number | null;
  reportTitle?: string;
  exportFormats: Record<string, boolean>;
  onReset: () => void;
  tx: (key: string, fallback: string) => string;
}

async function downloadAuthorizedFile(
  reportId: number | null,
  reportTitle: string | undefined,
  format: "pdf" | "pptx",
) {
  if (!reportId) return;
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;
  if (!token) {
    throw new Error("Token tidak ditemukan. Silakan login ulang.");
  }

  const url = `${API_BASE_URL}/api/v1/history/${reportId}/${format}`;
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
  };

  const res = await fetch(url, { headers });
  if (!res.ok) {
    let detail = `Gagal mengunduh ${format.toUpperCase()}.`;
    if (res.status === 401) {
      detail =
        "Token akses tidak valid atau telah kedaluwarsa. Silakan login ulang.";
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
  tx,
}: Step5ExportProps) {
  const [downloadingFormat, setDownloadingFormat] = useState<"pdf" | "pptx" | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const handleDownload = async (format: "pdf" | "pptx") => {
    setDownloadingFormat(format);
    setErrorMsg("");
    try {
      await downloadAuthorizedFile(reportId, reportTitle, format);
    } catch (err: any) {
      setErrorMsg(err.message || "Gagal mengunduh file.");
    } finally {
      setDownloadingFormat(null);
    }
  };

  const showPdf = exportFormats?.pdf || !exportFormats?.pptx;
  const showPptx = exportFormats?.pptx || !exportFormats?.pdf;
  return (
    <ScrollReveal animation="scaleIn" className="space-y-6 max-w-xl mx-auto">
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
        <h2 className="text-xl font-extrabold text-stone-900">
          {tx(
            "Report Generated Successfully!",
            "Report Generated Successfully!",
          )}
        </h2>
        <p className="text-xs text-stone-500 font-semibold">
          {tx(
            "Your SOC Security report is now ready for download.",
            "Your SOC Security report is now ready for download.",
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
            className="flex flex-col items-center justify-center p-5 bg-white border border-stone-200 rounded-2xl premium-card-hover group text-center space-y-3 w-full cursor-pointer transition-colors disabled:opacity-50"
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
            className="flex flex-col items-center justify-center p-5 bg-white border border-stone-200 rounded-2xl premium-card-hover group text-center space-y-3 w-full cursor-pointer transition-colors disabled:opacity-50"
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

      {/* Reset button to start over */}
      <div className="pt-6 border-t border-stone-100 flex justify-center">
        <button
          onClick={onReset}
          className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl border border-stone-200 hover:bg-stone-50 text-stone-700 font-bold text-xs shadow-sm transition-all cursor-pointer"
        >
          {tx("Generate Another Report", "Generate Another Report")}
        </button>
      </div>
    </ScrollReveal>
  );
}
