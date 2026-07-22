"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";

// react-plotly.js pakai `window` di dalamnya, jadi HARUS di-load cuma di browser
// (ssr: false) — kalau di-render di server bakal error karena `window` belum ada.
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface ReportChartPanelProps {
  reportId: number | null | undefined;
  tx: (key: string, fallback: string) => string;
}

/**
 * Menampilkan grafik ASLI dari backend (ChartGenerator + Plotly), bukan grafik statis/hardcode.
 * Chart yang tampil di sini persis sama dengan yang otomatis ter-embed di PDF/PPTX saat export,
 * karena keduanya sama-sama konsumsi endpoint GET /api/v1/chart/{report_id}.
 */
export default function ReportChartPanel({
  reportId,
  tx,
}: ReportChartPanelProps) {
  const [chartData, setChartData] = useState<any>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error" | "empty">(
    "loading",
  );
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (!reportId) {
      setStatus("empty");
      return;
    }

    let cancelled = false;

    const fetchChart = async () => {
      setStatus("loading");
      setErrorMsg("");
      try {
        const token = localStorage.getItem("token");
        const headers: Record<string, string> = {};
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }

        const res = await fetch(
          `http://localhost:8000/api/v1/chart/${reportId}`,
          { headers },
        );
        const data = await res.json();

        if (cancelled) return;

        if (!res.ok) {
          throw new Error(data.detail || "Gagal memuat grafik.");
        }

        if (!data || data.error || !data.data) {
          setStatus("empty");
          return;
        }

        setChartData(data);
        setStatus("ready");
      } catch (err: any) {
        if (!cancelled) {
          setErrorMsg(err.message || "Terjadi kesalahan saat memuat grafik.");
          setStatus("error");
        }
      }
    };

    fetchChart();
    return () => {
      cancelled = true;
    };
  }, [reportId]);

  if (status === "loading") {
    return (
      <div className="border border-stone-200 rounded-xl p-6 bg-stone-50/50 flex flex-col justify-center items-center min-h-[350px] gap-3">
        <div className="w-8 h-8 border-4 border-stone-200 border-t-petro-green rounded-full animate-spin"></div>
        <p className="text-xs text-stone-500 font-semibold">
          {tx(
            "Loading chart from your data...",
            "Loading chart from your data...",
          )}
        </p>
      </div>
    );
  }

  if (status === "empty") {
    return (
      <div className="border border-stone-200 rounded-xl p-6 bg-stone-50/50 flex flex-col justify-center items-center min-h-[350px] gap-2 text-center">
        <p className="text-xs font-bold text-stone-600">
          {tx("No chart available yet", "No chart available yet")}
        </p>
        <p className="text-[11px] text-stone-400 font-medium max-w-xs">
          {tx(
            "The chart will appear automatically once the report data has been processed.",
            "The chart will appear automatically once the report data has been processed.",
          )}
        </p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="border border-red-200 rounded-xl p-6 bg-red-50/50 flex flex-col justify-center items-center min-h-[350px] gap-2 text-center">
        <p className="text-xs font-bold text-red-600">
          {tx("Failed to load chart", "Failed to load chart")}
        </p>
        <p className="text-[11px] text-red-400 font-medium max-w-xs">
          {errorMsg}
        </p>
      </div>
    );
  }

  return (
    <div className="border border-stone-200 rounded-xl p-4 bg-white flex flex-col items-center min-h-[350px]">
      <Plot
        data={chartData.data}
        layout={{
          ...chartData.layout,
          autosize: true,
          margin: { l: 50, r: 20, t: 50, b: 50 },
          font: { family: "Inter, sans-serif", size: 11 },
        }}
        config={{ displayModeBar: false, responsive: true }}
        style={{ width: "100%", height: "380px" }}
        useResizeHandler
      />
    </div>
  );
}
