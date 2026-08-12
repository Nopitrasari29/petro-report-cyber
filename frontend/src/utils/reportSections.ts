import { getBlockNavTitle, type ReportBlock } from "@/utils/reportTheme";

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

// Dipakai HANYA sebagai daftar preset checkbox di Report Settings ("Include Sections") —
// TIDAK LAGI dipakai untuk panel "Pages" (lihat buildPagesFromBlocks di bawah), yang
// sekarang mengikuti struktur laporan ASLI (build_report_blocks di backend), bukan daftar
// 6 field ai_summary yang terpisah dari apa yang benar-benar dirender di Preview/PDF/PPTX.
export const REPORT_SECTIONS: ReportSection[] = [
  { page: "01", key: "executive_summary", title: "Executive Summary" },
  { page: "02", key: "trend_analysis", title: "Trend Analysis" },
  { page: "03", key: "severity_analysis", title: "Severity Analysis" },
  { page: "04", key: "risk_assessment", title: "Risk Assessment" },
  { page: "05", key: "recommendations", title: "Recommendations" },
  { page: "06", key: "conclusion", title: "Conclusion" },
];

// Satu halaman di panel "Pages"/Focus Studio — SEKARANG 1:1 dengan block asli laporan
// (build_report_blocks di backend), urutan & judulnya PERSIS sama dengan yang tampil di tab
// Preview & file PDF/PPTX yang diunduh (termasuk Cover, chart, tabel, dst — bukan lagi cuma
// 6 field teks AI). `key` cuma terisi utk halaman yang MEMANG punya teks bebas yang bisa
// diedit AI (ai_summary) — null utk halaman yang isinya dihitung dari data (Cover, chart,
// tabel, kartu aset, dst), supaya tab "Edit Text" tidak berpura-pura ada teks yang bisa
// diedit padahal tidak ada.
export interface ReportPage {
  page: string;
  key: string | null;
  title: string;
  editable: boolean;
}

// key ai_summary yang 1:1 sesuai kind block-nya — TIDAK termasuk "dynamic_section" (bisa jadi
// trend_analysis/severity_analysis/risk_assessment/section AI tambahan, lihat antrean di bawah).
const DIRECT_EDITABLE_KEY_BY_KIND: Record<string, string> = {
  executive_summary: "executive_summary",
  recommendations: "recommendations",
  conclusion: "conclusion",
};

function isSectionIncluded(key: string, includedSections: unknown): boolean {
  if (includedSections && typeof includedSections === "object" && !Array.isArray(includedSections)) {
    return (includedSections as Record<string, boolean>)[key] !== false;
  }
  if (Array.isArray(includedSections)) {
    const match = includedSections.find(
      (sec) => sec && typeof sec === "object" && (sec.key === key || sec.id === key),
    );
    return match ? match.enabled !== false : true;
  }
  return true;
}

// Bangun daftar "Pages" dari block ASLI yang sudah dirender backend (build_report_blocks) —
// BUKAN lagi dari 6 field ai_summary yang terpisah. Block berkind "dynamic_section" dipakai
// BERULANG utk trend_analysis/severity_analysis/risk_assessment MAUPUN section tambahan usulan
// AI (ai_summary.sections[1:]) — satu-satunya cara membedakan block ke-N mana yang mewakili key
// ai_summary yang mana adalah lewat URUTAN kemunculannya, karena backend (report_render_logic.py
// build_report_blocks) SELALU append dalam urutan tetap: trend -> severity -> risk -> section AI
// tambahan (masing-masing cuma muncul kalau is_included() true DAN field ai_summary-nya terisi,
// persis kondisi yang dicek ulang di sini lewat isSectionIncluded/aiSummary).
export function buildPagesFromBlocks(
  blocks: ReportBlock[],
  aiSummary: Record<string, any> | null | undefined,
  includedSections: unknown,
): ReportPage[] {
  const dynamicKeyQueue: string[] = [];
  if (isSectionIncluded("trend_analysis", includedSections) && aiSummary?.trend_analysis) {
    dynamicKeyQueue.push("trend_analysis");
  }
  if (isSectionIncluded("severity_analysis", includedSections) && aiSummary?.severity_analysis) {
    dynamicKeyQueue.push("severity_analysis");
  }
  if (isSectionIncluded("risk_assessment", includedSections) && aiSummary?.risk_assessment) {
    dynamicKeyQueue.push("risk_assessment");
  }
  const extraSections = Array.isArray(aiSummary?.sections) ? aiSummary!.sections.slice(1) : [];
  extraSections.forEach((_: any, i: number) => dynamicKeyQueue.push(`section:${i + 1}`));

  let dynamicQueueIdx = 0;

  return blocks.map((block, i) => {
    let key: string | null = null;

    if (block.kind === "dynamic_section") {
      key = dynamicKeyQueue[dynamicQueueIdx] ?? null;
      dynamicQueueIdx += 1;
    } else if (DIRECT_EDITABLE_KEY_BY_KIND[block.kind]) {
      key = DIRECT_EDITABLE_KEY_BY_KIND[block.kind];
    }

    return {
      page: String(i + 1).padStart(2, "0"),
      key,
      title: getBlockNavTitle(block, i),
      editable: key !== null,
    };
  });
}

export function getPageByNumber(pages: ReportPage[], page: string): ReportPage | undefined {
  return pages.find((p) => p.page === page);
}
