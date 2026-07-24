"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";

// react-plotly.js di-load hanya di browser (ssr: false)
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface ReportChartPanelProps {
  reportId: number | null | undefined;
  tx: (key: string, fallback: string) => string;
}

/**
 * Menampilkan Dashboard Grafik Visualisasi ASLI dari backend (ChartGenerator + Plotly).
 * Mendukung multiple charts (Severity Breakdown, Time Series Trend, & Top Event Categories).
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

        if (!data || data.error || (!data.data && (!data.charts || data.charts.length === 0))) {
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
      <div className="border border-stone-200 rounded-2xl p-8 bg-stone-50/50 flex flex-col justify-center items-center min-h-[350px] gap-3">
        <div className="w-9 h-9 border-4 border-stone-200 border-t-petro-green rounded-full animate-spin"></div>
        <p className="text-xs text-stone-500 font-semibold">
          {tx(
            "Generating interactive charts from your security logs...",
            "Generating interactive charts from your security logs...",
          )}
        </p>
      </div>
    );
  }

  if (status === "empty") {
    return (
      <div className="border border-stone-200 rounded-2xl p-8 bg-stone-50/50 flex flex-col justify-center items-center min-h-[350px] gap-2 text-center">
        <p className="text-xs font-bold text-stone-600">
          {tx("No chart available yet", "No chart available yet")}
        </p>
        <p className="text-[11px] text-stone-400 font-medium max-w-xs">
          {tx(
            "The charts will appear automatically once the report data has been processed.",
            "The charts will appear automatically once the report data has been processed.",
          )}
        </p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="border border-red-200 rounded-2xl p-8 bg-red-50/50 flex flex-col justify-center items-center min-h-[350px] gap-2 text-center">
        <p className="text-xs font-bold text-red-600">
          {tx("Failed to load chart", "Failed to load chart")}
        </p>
        <p className="text-[11px] text-red-400 font-medium max-w-xs">
          {errorMsg}
        </p>
      </div>
    );
  }

  const chartsList: any[] =
    Array.isArray(chartData?.charts) && chartData.charts.length > 0
      ? chartData.charts
      : chartData?.data
        ? [chartData]
        : [];

  return (
    <div className="space-y-6 w-full animate-fadeIn">
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 w-full">
        {chartsList.map((c: any, idx: number) => (
          <div
            key={idx}
            className="border border-stone-200/80 rounded-2xl p-5 bg-white shadow-sm hover:shadow-md transition-shadow flex flex-col items-center overflow-hidden"
          >
            <Plot
              data={c.data}
              layout={{
                ...c.layout,
                autosize: true,
                margin: { l: 50, r: 30, t: 55, b: 65 },
                font: { family: "Inter, sans-serif", size: 11 },
              }}
              config={{ displayModeBar: false, responsive: true }}
              style={{ width: "100%", height: "360px" }}
              useResizeHandler
            />
          </div>
        ))}
      </div>
    </div>
  );
}
