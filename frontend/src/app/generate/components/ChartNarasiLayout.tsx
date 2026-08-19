"use client";

import ReportBlockRenderer from "@/components/ReportBlockRenderer";
import type { ReportBlock, VisualStyle } from "@/utils/reportTheme";

const CHART_BLOCK_KINDS = [
  "category_distribution",
  "severity_distribution",
  "status_distribution",
  "kpi_radar",
  "time_heatmap",
  "period_compare",
];

interface ChartNarasiLayoutProps {
  blocks: ReportBlock[];
  visualStyle?: VisualStyle;
  themeColor?: string;
  blocksLoading: boolean;
  blocksError: string;
  tx: (key: string, fallback: string) => string;
}

/**
 * Menampilkan chart + narasi AI (ai_caption) untuk tab "Charts" — memakai `blocks` yang SAMA
 * PERSIS dengan tab Preview dan file PDF/PPTX (build_report_blocks di backend), BUKAN sistem
 * Plotly terpisah (/api/v1/chart/{id}) yang sebelumnya dipakai di sini. Sistem lama itu
 * mendeteksi kolom & urutan chart sendiri secara independen, sehingga bisa berbeda dari chart
 * yang benar-benar di-export — akibatnya narasi AI (chart_captions) bisa salah pasang ke chart
 * yang salah. Dengan blocks yang sama, chart & narasinya dijamin identik dengan hasil export.
 */
export default function ChartNarasiLayout({
  blocks,
  visualStyle,
  themeColor,
  blocksLoading,
  blocksError,
  tx,
}: ChartNarasiLayoutProps) {
  if (blocksLoading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[300px] gap-3">
        <div className="w-8 h-8 border-2 border-stone-200 border-t-petro-green rounded-full animate-spin" />
        <p className="text-xs font-bold text-stone-500">
          {tx("Loading charts...", "Memuat grafik...")}
        </p>
      </div>
    );
  }

  if (blocksError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[200px] gap-2 text-center border border-red-200 rounded-2xl p-8 bg-red-50/50">
        <p className="text-xs font-bold text-red-600">{tx("Failed to load charts", "Gagal memuat grafik")}</p>
        <p className="text-[11px] text-red-400">{blocksError}</p>
      </div>
    );
  }

  // Chart (category_distribution/status_distribution/kpi_radar/dst) sekarang bisa ada DI DALAM
  // block "page" (beberapa panel digabung 1 halaman di tab Preview/PDF/PPTX, lihat
  // report_render_logic.py tahap 2) — panel-panelnya sendiri masih berisi data chart UTUH
  // seperti sebelum digabung, cuma field kind-nya bernama "panel_kind" (bukan "kind", supaya
  // tidak bentrok dgn "kind" milik block pembungkusnya) — diratakan (flatten) & dipetakan balik
  // ke "kind" di sini sebelum difilter, supaya ReportBlockRenderer bisa merender tiap panel
  // langsung sebagai kartu terpisah seperti semula.
  const flatBlocks = blocks.flatMap((b) => {
    if (b.kind !== "page" || !Array.isArray(b.panels)) return [b];
    return (b.panels as ReportBlock[]).map((p) => ({ ...p, kind: p.panel_kind }));
  });
  const chartBlocks = flatBlocks.filter((b) => CHART_BLOCK_KINDS.includes(b.kind));

  if (chartBlocks.length === 0) {
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

  return (
    <div className="space-y-6">
      {chartBlocks.map((block, idx) => (
        <div key={idx} className="rounded-2xl border border-stone-200/80 shadow-sm overflow-hidden">
          <ReportBlockRenderer block={block} visualStyle={visualStyle} themeColor={themeColor} />
        </div>
      ))}
    </div>
  );
}
