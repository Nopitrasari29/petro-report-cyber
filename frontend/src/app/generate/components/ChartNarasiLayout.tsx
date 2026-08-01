"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { API_BASE_URL } from "@/utils/api";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

interface ChartNarasiLayoutProps {
  reportId: number | null | undefined;
  chartCaptions?: string[];
  tx: (key: string, fallback: string) => string;
}

/**
 * Layout 2-kolom per chart:
 *   KIRI  = Visualisasi Grafik (Plotly)
 *   KANAN = Narasi AI yang menjelaskan grafik tersebut (chart_captions dari AI)
 *
 * Setiap chart ditampilkan berdampingan dengan narasi penjelasannya masing-masing.
 */
export default function ChartNarasiLayout({
  reportId,
  chartCaptions = [],
  tx,
}: ChartNarasiLayoutProps) {
  const [chartData, setChartData] = useState<any>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error" | "empty">("loading");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    if (!reportId) {
      setStatus("empty");
      return;
    }
    let cancelled = false;
    const fetchChart = async () => {
      setStatus("loading");
      try {
        const token = localStorage.getItem("token");
        const headers: Record<string, string> = {};
        if (token) headers["Authorization"] = `Bearer ${token}`;
        const res = await fetch(`${API_BASE_URL}/api/v1/chart/${reportId}`, { headers });
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
    return () => { cancelled = true; };
  }, [reportId]);

  // Loading
  if (status === "loading") {
    return (
      <div className="flex flex-col items-center justify-center min-h-[300px] gap-3">
        <div className="w-8 h-8 border-2 border-stone-200 border-t-petro-green rounded-full animate-spin" />
        <p className="text-xs font-bold text-stone-500">
          {tx("Loading charts...", "Memuat grafik...")}
        </p>
      </div>
    );
  }

  if (status === "empty") {
    return (
      <div className="flex flex-col items-center justify-center min-h-[200px] gap-2 text-center border border-dashed border-stone-200 rounded-2xl p-8">
        <p className="text-xs font-bold text-stone-500">
          {tx("No charts available", "Belum ada grafik yang tersedia")}
        </p>
        <p className="text-[11px] text-stone-400">
          {tx("Charts will appear after report is generated.", "Grafik akan muncul setelah laporan selesai diproses.")}
        </p>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="flex flex-col items-center justify-center min-h-[200px] gap-2 text-center border border-red-200 rounded-2xl p-8 bg-red-50/50">
        <p className="text-xs font-bold text-red-600">{tx("Failed to load charts", "Gagal memuat grafik")}</p>
        <p className="text-[11px] text-red-400">{errorMsg}</p>
      </div>
    );
  }

  const chartsList: any[] =
    Array.isArray(chartData?.charts) && chartData.charts.length > 0
      ? chartData.charts
      : chartData?.data
        ? [chartData]
        : [];

  // Fallback captions jika belum ada dari AI
  const defaultCaptions = [
    "Distribusi data berdasarkan kategori utama dalam periode laporan ini.",
    "Tren dan pola data dari waktu ke waktu selama periode yang dianalisis.",
    "Perbandingan antar entitas atau kategori berdasarkan indikator utama.",
    "Analisis frekuensi dan proporsi per kelompok data yang diidentifikasi.",
    "Ringkasan visual temuan utama dari keseluruhan dataset yang diproses.",
  ];

  return (
    <div className="space-y-8">
      {chartsList.map((c: any, idx: number) => {
        const isHorizontalBar = c.data?.[0]?.orientation === "h";
        const leftMargin = c.layout?.margin?.l ?? (isHorizontalBar ? 180 : 55);

        // Ambil narasi: prioritas dari chartCaptions prop (AI-generated), fallback ke default
        const narasi =
          chartCaptions[idx]?.trim() ||
          defaultCaptions[idx % defaultCaptions.length];

        const chartTitle = c.layout?.title?.text || c.layout?.title || `Chart ${idx + 1}`;

        return (
          <div
            key={idx}
            className="grid grid-cols-1 lg:grid-cols-5 gap-4 bg-white border border-stone-200/80 rounded-2xl shadow-sm overflow-hidden hover:shadow-md transition-shadow"
          >
            {/* KIRI: Visualisasi Chart */}
            <div className="lg:col-span-3 p-4 bg-stone-50/50 flex flex-col items-center border-b lg:border-b-0 lg:border-r border-stone-200/60">
              <p className="text-[10px] font-black text-stone-500 uppercase tracking-wider mb-2 self-start">
                {tx("Visualisasi", "Visualisasi")}
              </p>
              <Plot
                data={c.data}
                layout={{
                  ...c.layout,
                  autosize: true,
                  margin: c.layout?.margin || { l: leftMargin, r: 20, t: 45, b: 55 },
                  font: { family: "Inter, sans-serif", size: 9.5 },
                  yaxis: { ...c.layout?.yaxis, automargin: true },
                  paper_bgcolor: "rgba(0,0,0,0)",
                  plot_bgcolor: "rgba(0,0,0,0)",
                }}
                config={{ displayModeBar: false, responsive: true }}
                style={{
                  width: "100%",
                  height: "280px",
                  minWidth: isHorizontalBar ? "320px" : "auto",
                }}
                useResizeHandler
              />
            </div>

            {/* KANAN: Narasi AI */}
            <div className="lg:col-span-2 p-5 flex flex-col justify-start gap-3 text-left">
              <div>
                <span className="inline-flex items-center gap-1 text-[10px] font-black text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2.5 py-0.5 mb-2">
                  💡 {tx("Narasi Insight", "Narasi Insight AI")}
                </span>
                {typeof chartTitle === "string" && chartTitle && (
                  <h5 className="text-xs font-black text-stone-800 leading-tight mb-2">
                    {chartTitle}
                  </h5>
                )}
              </div>

              <p className="text-xs text-stone-600 font-medium leading-relaxed whitespace-pre-wrap">
                {narasi}
              </p>

              {/* Hint edit */}
              <div className="mt-auto pt-3 border-t border-stone-100">
                <p className="text-[9.5px] text-stone-400 font-medium">
                  {tx(
                    "Narasi ini dihasilkan AI berdasarkan data aktual. Dapat diedit di tab Edit Text.",
                    "Narasi ini dihasilkan AI berdasarkan data aktual. Dapat diedit di tab Edit Text.",
                  )}
                </p>
              </div>
            </div>
          </div>
        );
      })}

      {/* Jika tidak ada chart sama sekali */}
      {chartsList.length === 0 && (
        <div className="flex flex-col items-center justify-center min-h-[200px] gap-2 text-center border border-dashed border-stone-200 rounded-2xl p-8">
          <p className="text-xs font-bold text-stone-500">
            {tx("No chart data", "Tidak ada data grafik")}
          </p>
        </div>
      )}
    </div>
  );
}
