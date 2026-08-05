import { API_BASE_URL } from "@/utils/api";
import type { ReportBlock } from "@/utils/reportTheme";

// Satu-satunya cara frontend mengambil "isi laporan yang akan dirender" — sumbernya SAMA
// (build_report_blocks di backend) dengan yang dipakai export_pdf.py/export_ppt.py, jadi
// tab Preview dijamin menampilkan section & angka yang sama dengan file yang diunduh.
export async function fetchReportBlocks(
  reportId: number | string,
  token: string | null,
): Promise<ReportBlock[]> {
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
  return data.blocks || [];
}
