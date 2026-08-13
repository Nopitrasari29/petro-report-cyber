import { API_BASE_URL } from "@/utils/api";
import { DEFAULT_VISUAL_STYLE, type ReportBlock, type VisualStyle } from "@/utils/reportTheme";

export interface ReportBlocksResult {
  blocks: ReportBlock[];
  visualStyle: VisualStyle;
  themeColor: string;
}

// Satu-satunya cara frontend mengambil "isi laporan yang akan dirender" — sumbernya SAMA
// (build_report_blocks di backend) dengan yang dipakai export_pdf.py/export_ppt.py, jadi
// tab Preview dijamin menampilkan section & angka yang sama dengan file yang diunduh.
// visualStyle ikut dikembalikan (lihat get_visual_style() di backend) — kombinasi bentuk
// (cover solid/split, chart bar/donut/stacked, dst) yang DIKUNCI sekali sewaktu laporan ini
// dianalisis, supaya ReportBlockRenderer merender bentuk yang PERSIS sama dgn PDF/PPTX yang
// akan diunduh untuk laporan yang sama (lihat pick_visual_style() di report_render_logic.py).
export async function fetchReportBlocks(
  reportId: number | string,
  token: string | null,
): Promise<ReportBlocksResult> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE_URL}/api/v1/history/${reportId}/preview`, {
    headers,
  });
  if (!res.ok) {
    let detail = "Gagal memuat preview laporan.";
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {}
    throw new Error(detail);
  }
  const data = await res.json();
  return {
    blocks: data.blocks || [],
    visualStyle: { ...DEFAULT_VISUAL_STYLE, ...(data.visual_style || {}) },
    themeColor: data.theme_color || "green",
  };
}
