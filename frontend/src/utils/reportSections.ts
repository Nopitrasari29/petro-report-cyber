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
