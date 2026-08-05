// Palet & warna — HARUS identik dengan backend (report_render_logic.py / export_pdf.py /
// export_ppt.py) supaya tab Preview benar-benar terlihat sama dengan PDF/PPTX yang diunduh.
export const REPORT_COLORS = {
  greenMain: "#1B5E3C",
  greenBg: "#0E3B26",
  greenChart: "#2F7A52",
  goldMain: "#C9A227",
  goldLight: "#E7C766",
  white: "#FFFFFF",
  ivory: "#F5F7F2",
  textDark: "#16241C",
  grayText: "#5C6B62",
  redCrit: "#B23A2E",
  redCritBg: "#F8E2DE",
  panelBorder: "#E2E5DE",
};

export const CATEGORY_COLOR_RAMP = [
  REPORT_COLORS.greenMain,
  REPORT_COLORS.greenChart,
  REPORT_COLORS.goldMain,
  REPORT_COLORS.goldLight,
  REPORT_COLORS.grayText,
];

export const SEVERITY_COLOR: Record<string, string> = {
  critical: REPORT_COLORS.redCrit,
  high: REPORT_COLORS.goldMain,
  medium: REPORT_COLORS.greenMain,
  low: REPORT_COLORS.greenChart,
  informational: REPORT_COLORS.grayText,
};

export const TITLE_FONT = '"Bookman Old Style", Georgia, serif';
export const BODY_FONT = 'Calibri, "Segoe UI", sans-serif';

export interface ReportBlock {
  kind: string;
  dark?: boolean;
  [key: string]: any;
}

// Judul navigasi singkat per jenis block — dipakai di daftar/anchor Preview.
export function getBlockNavTitle(block: ReportBlock, index: number): string {
  switch (block.kind) {
    case "cover":
      return "Cover";
    case "intro":
      return "Latar Belakang & Tujuan";
    case "executive_summary":
      return "Ringkasan Eksekutif";
    case "category_distribution":
      return `Distribusi ${block.label || "Kategori"}`;
    case "severity_distribution":
      return "Distribusi Severity";
    case "status_distribution":
      return "Status Penanganan";
    case "critical_table":
      return block.title || "Insiden Prioritas Tinggi";
    case "asset_cards":
      return block.title || "Aset Sasaran";
    case "key_findings":
      return "Temuan Utama";
    case "recommendations":
      return "Rekomendasi Mitigasi";
    case "conclusion":
      return "Kesimpulan";
    case "closing":
      return "Penutup";
    default:
      return `Bagian ${index + 1}`;
  }
}
