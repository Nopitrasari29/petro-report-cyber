// Satu-satunya sumber kebenaran untuk bentuk data laporan yang dikembalikan backend
// (ReportResponse, lihat schemas/report.py) di sisi frontend — SEBELUMNYA didefinisikan ulang
// identik (byte-per-byte, kecuali beberapa field yang diam-diam beda) di 4 file terpisah
// (HistoryTable.tsx, history/page.tsx, CenterPreviewPanel.tsx, history/[id]/page.tsx), risiko
// diam-diam berbeda seiring waktu kalau salah satu diedit tanpa mengedit yang lain.
export interface ReportItem {
  id: number;
  title: string;
  data_type: string;
  status: string;
  input_file_name: string;
  period_start: string;
  period_end: string;
  template_type: string;
  output_format: string;
  language: string;
  ai_confidence: number;
  created_by_name: string;
  file_pdf_path?: string | null;
  file_ppt_path?: string | null;
  threat_count_critical: number;
  threat_count_high: number;
  threat_count_medium: number;
  threat_count_low: number;
  total_records_parsed: number;
  created_at: string;
}

// Halaman detail 1 laporan butuh field tambahan di luar yang tampil di daftar History.
export interface ReportDetails extends ReportItem {
  ai_summary: Record<string, any>;
  total_file_size_bytes?: number | null;
  included_sections?: any;
}
