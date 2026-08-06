// Satu-satunya sumber kebenaran untuk struktur "halaman" laporan (Preview & Edit, History
// Detail, Include Sections). Sebelumnya generate/page.tsx dan history/[id]/page.tsx punya
// masing-masing salinan sendiri yang independen, dan keduanya memetakan 7 "halaman" ke key
// yang TIDAK ADA di ai_summary sungguhan (backend cuma pernah menghasilkan 6 field:
// executive_summary, trend_analysis, severity_analysis, risk_assessment, recommendations,
// conclusion) — jadi 1-2 halaman selalu jatuh ke teks fallback hardcoded yang sama sekali
// tidak berhubungan dengan data laporan yang sesungguhnya.
export interface ReportSection {
  page: string;
  key: string;
  title: string;
}

export const REPORT_SECTIONS: ReportSection[] = [
  { page: "01", key: "executive_summary", title: "Executive Summary" },
  { page: "02", key: "trend_analysis", title: "Trend Analysis" },
  { page: "03", key: "severity_analysis", title: "Severity Analysis" },
  { page: "04", key: "risk_assessment", title: "Risk Assessment" },
  { page: "05", key: "recommendations", title: "Recommendations" },
  { page: "06", key: "conclusion", title: "Conclusion" },
];

export function getSectionTitle(page: string): string {
  return (
    REPORT_SECTIONS.find((s) => s.page === page)?.title ?? "Executive Summary"
  );
}

export function getSectionContentKey(page: string): string {
  return (
    REPORT_SECTIONS.find((s) => s.page === page)?.key ?? "executive_summary"
  );
}

// Daftar halaman LENGKAP untuk tab "Edit Text"/"Pages" — 6 halaman lama di atas DITAMBAH
// section dinamis yang diusulkan AI (ai_summary.sections, muncul kalau user memilihnya di
// Report Settings) dan penjelasan per-chart (ai_summary.chart_captions). Sebelumnya kedua
// jenis konten ini SUDAH dihasilkan AI dan bahkan sudah ditampilkan di tab Charts, tapi tidak
// pernah bisa diedit di sini karena daftar halaman terbatas ke 6 key di atas.
export interface ReportPage {
  page: string;
  key: string;
  title: string;
}

export function buildReportPages(
  aiSummary: Record<string, any> | null | undefined,
): ReportPage[] {
  const pages: ReportPage[] = REPORT_SECTIONS.map((s) => ({ ...s }));
  let n = pages.length;

  const dynamicSections = Array.isArray(aiSummary?.sections)
    ? aiSummary!.sections
    : [];
  dynamicSections.forEach((sec: any, i: number) => {
    n += 1;
    const title =
      sec && typeof sec === "object" && sec.title
        ? String(sec.title)
        : `Analisis Tambahan ${i + 1}`;
    pages.push({ page: String(n).padStart(2, "0"), key: `section:${i}`, title });
  });

  const chartCaptions = Array.isArray(aiSummary?.chart_captions)
    ? aiSummary!.chart_captions
    : [];
  chartCaptions.forEach((_: string, i: number) => {
    n += 1;
    pages.push({
      page: String(n).padStart(2, "0"),
      key: `chart_caption:${i}`,
      title: `Penjelasan Chart ${i + 1}`,
    });
  });

  return pages;
}

export function getPageTitleFromList(pages: ReportPage[], page: string): string {
  return pages.find((p) => p.page === page)?.title ?? "Executive Summary";
}

export function getPageKeyFromList(pages: ReportPage[], page: string): string {
  return pages.find((p) => p.page === page)?.key ?? "executive_summary";
}
