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

// Kombinasi varian tampilan (bentuk cover, gaya chart, gaya kartu, dst) — DIKIRIM backend
// (lihat GET /history/{id}/blocks & get_visual_style() di report_render_logic.py) SEKALI per
// laporan, bukan ditentukan di sini. ReportBlockRenderer memilih JSX yang sesuai berdasarkan
// nilai-nilai ini, supaya preview web PERSIS meniru bentuk yang akan dipakai file PDF/PPTX
// yang diunduh utk laporan yang sama (lihat pick_visual_style() utk alasan lengkapnya).
export interface VisualStyle {
  cover_style: "solid" | "split";
  category_style: "bar" | "donut" | "stacked";
  status_style: "bar" | "donut" | "stacked";
  asset_style: "cards" | "podium" | "bars";
  recommendation_style: "cards" | "timeline" | "banners";
  panel_side: "left" | "right";
  stat_cols: number;
  card_cols: number;
  accent_bar_color: "green" | "gold";
  flourish_corner: "bottom_right" | "top_right" | "bottom_left";
}

// Dipakai laporan LAMA (dibuat sebelum backend mengirim visual_style, atau saat field-nya
// belum lengkap) — HARUS identik dgn DEFAULT_VISUAL_STYLE di report_render_logic.py (backend).
export const DEFAULT_VISUAL_STYLE: VisualStyle = {
  cover_style: "split",
  category_style: "bar",
  status_style: "bar",
  asset_style: "cards",
  recommendation_style: "cards",
  panel_side: "right",
  stat_cols: 3,
  card_cols: 3,
  accent_bar_color: "green",
  flourish_corner: "bottom_right",
};

// Judul navigasi singkat per jenis block — dipakai di panel "Pages"/Focus Studio (lihat
// buildPagesFromBlocks di reportSections.ts). SEBELUMNYA daftar ini hardcode Bahasa Indonesia
// utk tiap kind, padahal `block.title` yang dikirim backend (build_report_blocks) SUDAH
// mengikuti report.language & domain data (mis. "Distribution & Priority Analysis" utk laporan
// berbahasa Inggris, atau "Analisis Distribusi & Prioritas" utk domain non-keamanan) — dipakai
// langsung di sini supaya judul di panel Pages PERSIS sama dengan judul yang tampil di Preview,
// bukan salinan terpisah yang gampang diam-diam beda. Cuma "cover" & "closing" yang perlu
// label tetap sendiri (BUKAN diturunkan dari block): `block.title` keduanya berisi judul
// LAPORAN (report.title), bukan nama section, jadi tidak cocok dipakai sebagai label navigasi.
// "closing" SENGAJA tidak lagi memakai block.thank_you ("Terima Kasih"/"Thank You") APA
// ADANYA sebagai label navigasi — itu tetap jadi judul besar yang tercetak di halaman penutup
// PDF/PPTX sungguhan (nada penutup yang hangat, dipertahankan), tapi label navigasi di panel
// Pages dibuat netral "Closing"/"Penutup" — BUG YANG DIPERBAIKI (dilaporkan user): dulu
// hardcode "Penutup" SELALU, tidak ikut menyesuaikan walau laporan berbahasa Inggris. Karena
// tidak ada prop bahasa/tx yang dioper sampai ke fungsi ini (dipanggil dari beberapa tempat
// lewat buildPagesFromBlocks), bahasa disimpulkan dari block.thank_you sendiri — field itu
// SUDAH dipilih backend sesuai report.language ("Terima Kasih" vs "Thank You"), jadi cukup
// diandalkan tanpa perlu menambah parameter baru ke rantai pemanggil manapun.
export function getBlockNavTitle(block: ReportBlock, index: number): string {
  switch (block.kind) {
    case "cover":
      return "Cover";
    case "closing": {
      const isEnglish = block.thank_you === "Thank You";
      return isEnglish ? "Closing" : "Penutup";
    }
    default: {
      // block.title praktis SELALU terisi (semua block non-cover/closing di build_report_blocks
      // selalu menyertakannya) — fallback di bawah nyaris tidak pernah tereksekusi, daftar kicker
      // Indonesia yang dikenal cukup sbg heuristik kasar drpd menambah parameter bahasa baru.
      if (block.title) return block.title;
      const KNOWN_ID_KICKERS = new Set([
        "ANALISIS", "ANALISIS DATA", "SOROTAN INSIDEN", "SOROTAN DATA", "TINDAK LANJUT", "PENUTUP",
      ]);
      const isIndonesian = typeof block.kicker === "string" && KNOWN_ID_KICKERS.has(block.kicker);
      return isIndonesian ? `Bagian ${index + 1}` : `Section ${index + 1}`;
    }
  }
}
