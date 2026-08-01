"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { API_BASE_URL } from "@/utils/api";

// react-plotly.js di-load hanya di browser (ssr: false)
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface ReportChartPanelProps {
  reportId: number | null | undefined;
  chartCaption?: string;
  tx: (key: string, fallback: string) => string;
}

/**
 * Menampilkan Dashboard Grafik Visualisasi ASLI dari backend (ChartGenerator + Plotly).
 * Mendukung multiple charts (Severity Breakdown, Time Series Trend, & Top Event Categories).
 */
export default function ReportChartPanel({
  reportId,
  chartCaption,
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
          `${API_BASE_URL}/api/v1/chart/${reportId}`,
          { headers },
        );
        if (res.ok) {
          const data = await res.json();
          if (!cancelled) {
            if (!data || data.error || (!data.data && (!data.charts || data.charts.length === 0))) {
              setStatus("empty");
            } else {
              setChartData(data);
              setStatus("ready");
            }
          }
        } else {
          if (!cancelled) {
            setStatus("error");
            setErrorMsg("Gagal memuat grafik dari server.");
          }
        }
      } catch (err: any) {
        if (!cancelled) {
          setStatus("error");
          setErrorMsg(err?.message || "Koneksi terputus.");
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
      <div className="border border-stone-200/80 rounded-2xl p-8 bg-stone-50/50 flex flex-col justify-center items-center min-h-[350px] gap-3">
        <div className="w-8 h-8 border-3 border-stone-300 border-t-petro-green rounded-full animate-spin"></div>
        <p className="text-xs font-bold text-stone-600">
          {tx("Loading analytics chart...", "Loading analytics chart...")}
        </p>
      </div>
    );
  }

  if (status === "empty") {
    return (
      <div className="border border-dashed border-stone-250 rounded-2xl p-8 bg-stone-50/30 flex flex-col justify-center items-center min-h-[350px] gap-2 text-center">
        <p className="text-xs font-bold text-stone-500">
          {tx("No chart data available", "No chart data available")}
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
    <div className="space-y-6 w-full animate-fadeIn text-left">
      <div className="grid grid-cols-1 gap-6 w-full">
        {chartsList.map((c: any, idx: number) => {
          const isHorizontalBar = c.data?.[0]?.orientation === "h";
          const leftMargin = c.layout?.margin?.l ?? (isHorizontalBar ? 180 : 55);

          return (
            <div
              key={idx}
              className="border border-stone-200/80 rounded-2xl p-4 bg-white shadow-sm hover:shadow-md transition-shadow flex flex-col items-center overflow-x-auto w-full"
            >
              <Plot
                data={c.data}
                layout={{
                  ...c.layout,
                  autosize: true,
                  margin: c.layout?.margin || { l: leftMargin, r: 30, t: 55, b: 65 },
                  font: { family: "Inter, sans-serif", size: 10 },
                  yaxis: {
                    ...c.layout?.yaxis,
                    automargin: true,
                  },
                }}
                config={{ displayModeBar: false, responsive: true }}
                style={{ width: "100%", height: "340px", minWidth: isHorizontalBar ? "380px" : "auto" }}
                useResizeHandler
              />
            </div>
          );
        })}
      </div>

      {/* Chart Insight Caption Callout (Infographic Narration) */}
      {chartCaption && (
        <div className="p-4 rounded-xl bg-amber-50/80 border-l-4 border-amber-500 text-stone-700 text-xs font-medium leading-relaxed space-y-1 shadow-sm">
          <strong className="text-amber-900 font-bold block flex items-center gap-1.5">
            <span>💡</span> {tx("Infographic Insight", "Keterangan Narasi Infografis & Insight Data")}
          </strong>
          <p className="text-[11px] text-stone-700 font-medium m-0 whitespace-pre-wrap">{chartCaption}</p>
        </div>
      )}
    </div>
  );
}
