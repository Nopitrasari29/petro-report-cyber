"use client";

import { useEffect, useState } from "react";
import { useTx } from "@/hooks/useTx";
import { API_BASE_URL, authHeaders } from "@/utils/api";

// Tab "Data Quality" — SEBELUMNYA mesin pengecekannya (log_validator.py) sudah lengkap di
// backend (deteksi duplikat, nilai kosong, outlier, penulisan kategori tidak konsisten, +
// format IP/Port khusus data keamanan) tapi tidak ada satu pun tempat di aplikasi yang
// memanggilnya — fitur ini terpasang tapi genuinely tidak bisa diakses siapa pun. Komponen
// ini yang menyambungkannya ke UI.
interface ValidationIssue {
  issue_type: string;
  description: string;
  affected_records: number;
  severity: "Low" | "Medium" | "High";
  status: string;
}

interface ValidationResult {
  overall_validation_score: number;
  validation_completed: string;
  preview_columns: string[];
  counters: {
    valid_records: number;
    duplicate_records: number;
    missing_values: number;
    invalid_records: number;
    outlier_values: number;
    inconsistent_categories: number;
  };
  validation_breakdown: Record<string, string>;
  validation_issues: ValidationIssue[];
  sample_preview: Record<string, string>[];
}

const SEVERITY_STYLES: Record<string, string> = {
  Low: "bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-300 border-stone-200 dark:border-stone-700",
  Medium: "bg-amber-50 text-amber-700 border-amber-200",
  High: "bg-red-50 text-red-700 border-red-200",
};

export default function DataQualityPanel({ reportId }: { reportId: number }) {
  const { tx } = useTx();
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState("");
  const [result, setResult] = useState<ValidationResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setErrorMsg("");
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/validation/summary/${reportId}`, { headers: authHeaders() });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || "Gagal memuat hasil validasi kualitas data.");
        }
        const data = await res.json();
        if (!cancelled) setResult(data);
      } catch (e: any) {
        if (!cancelled) setErrorMsg(e.message || "Gagal memuat hasil validasi kualitas data.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => {
      cancelled = true;
    };
  }, [reportId]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-3">
        <div className="w-6 h-6 border-2 border-stone-200 dark:border-stone-700 border-t-petro-green rounded-full animate-spin" />
        <span className="text-xs font-bold text-stone-500 dark:text-stone-400">
          {tx("Memvalidasi kualitas data...", "Memvalidasi kualitas data...")}
        </span>
      </div>
    );
  }

  if (errorMsg || !result) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 text-xs font-semibold p-4 rounded-xl">
        {errorMsg || tx("Gagal memuat hasil validasi.", "Gagal memuat hasil validasi.")}
      </div>
    );
  }

  const scoreColor =
    result.overall_validation_score >= 90
      ? "text-emerald-600"
      : result.overall_validation_score >= 75
        ? "text-amber-600"
        : "text-red-600";

  const counterLabels: [keyof ValidationResult["counters"], string, string][] = [
    ["valid_records", "Data Valid", "Valid Records"],
    ["duplicate_records", "Baris Kembar", "Duplicates"],
    ["missing_values", "Nilai Kosong", "Missing Values"],
    ["outlier_values", "Nilai Tidak Wajar", "Outlier Values"],
    ["inconsistent_categories", "Kategori Tak Konsisten", "Inconsistent Categories"],
    ["invalid_records", "Format Tidak Valid", "Invalid Format"],
  ];

  return (
    <div className="space-y-5 text-left">
      {/* Skor keseluruhan */}
      <div className="bg-white dark:bg-stone-900 border border-stone-200/80 dark:border-stone-700/80 rounded-2xl p-6 flex items-center gap-6">
        <div className={`text-4xl font-black ${scoreColor}`}>
          {result.overall_validation_score}
          <span className="text-base font-bold text-stone-400 dark:text-stone-500">/100</span>
        </div>
        <div>
          <h4 className="font-extrabold text-stone-900 dark:text-stone-100 text-sm">
            {tx("Skor Kualitas Data", "Data Quality Score")}
          </h4>
          <p className="text-[11px] text-stone-500 dark:text-stone-400 font-semibold mt-0.5">
            {tx("Divalidasi pada", "Validated on")} {result.validation_completed}
          </p>
        </div>
      </div>

      {/* Counter grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {counterLabels.map(([key, idLabel, enLabel]) => (
          <div
            key={key}
            className="bg-white dark:bg-stone-900 border border-stone-200/80 dark:border-stone-700/80 rounded-xl p-3.5 text-center"
          >
            <div className="text-xl font-black text-stone-900 dark:text-stone-100">
              {result.counters[key]}
            </div>
            <div className="text-[10px] font-bold text-stone-500 dark:text-stone-400 mt-0.5">
              {tx(idLabel, enLabel)}
            </div>
          </div>
        ))}
      </div>

      {/* Daftar isu */}
      <div>
        <h4 className="font-extrabold text-stone-900 dark:text-stone-100 text-xs uppercase tracking-wide mb-2">
          {tx("Temuan", "Findings")}
        </h4>
        <div className="space-y-2">
          {result.validation_issues.map((issue, i) => (
            <div
              key={i}
              className={`border rounded-xl p-3.5 flex items-center justify-between gap-3 ${SEVERITY_STYLES[issue.severity] || SEVERITY_STYLES.Low}`}
            >
              <div>
                <div className="font-bold text-xs">{issue.issue_type}</div>
                <div className="text-[11px] font-semibold opacity-80 mt-0.5">{issue.description}</div>
              </div>
              {issue.affected_records > 0 && (
                <div className="text-[10px] font-black shrink-0 px-2 py-1 rounded-full bg-white/60 dark:bg-black/20">
                  {issue.affected_records} {tx("baris", "rows")}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Sample preview */}
      {result.sample_preview.length > 0 && (
        <div>
          <h4 className="font-extrabold text-stone-900 dark:text-stone-100 text-xs uppercase tracking-wide mb-2">
            {tx("Contoh Data", "Sample Data")}
          </h4>
          <div className="overflow-x-auto border border-stone-200/80 dark:border-stone-700/80 rounded-xl">
            <table className="w-full text-[11px]">
              <thead>
                <tr className="bg-stone-50 dark:bg-stone-800 text-stone-500 dark:text-stone-400 font-bold uppercase">
                  {result.preview_columns.map((col) => (
                    <th key={col} className="px-3 py-2 text-left whitespace-nowrap">
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.sample_preview.map((row, i) => (
                  <tr key={i} className="border-t border-stone-100 dark:border-stone-800">
                    {result.preview_columns.map((col) => (
                      <td key={col} className="px-3 py-2 text-stone-700 dark:text-stone-300 whitespace-nowrap">
                        {row[col] ?? "-"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
