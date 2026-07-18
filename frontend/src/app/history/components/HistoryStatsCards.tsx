import ScrollReveal from "@/components/ScrollReveal";
import { t } from "@/utils/i18n";

interface HistoryStatsCardsProps {
  totalCount: number;
  approvedCount: number;
  inReviewCount: number;
  draftCount: number;
  exportedCount: number;
  approvedPercent: string;
  inReviewPercent: string;
  draftPercent: string;
  exportedPercent: string;
}

export default function HistoryStatsCards({
  totalCount,
  approvedCount,
  inReviewCount,
  draftCount,
  exportedCount,
  approvedPercent,
  inReviewPercent,
  draftPercent,
  exportedPercent,
}: HistoryStatsCardsProps) {
  return (
    <ScrollReveal animation="fadeInUp" delay={100}>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {/* Total Reports */}
        <div className="bg-white border border-stone-200/80 rounded-2xl p-5 shadow-sm text-left flex flex-col justify-between premium-card-hover cursor-pointer">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-stone-50 border border-stone-100 text-stone-500">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
                </svg>
              </span>
              <span className="text-[10px] font-extrabold text-stone-500 uppercase tracking-wider">{t("Total Reports")}</span>
            </div>
            <div className="text-2xl font-black text-stone-850 mt-3">{totalCount}</div>
          </div>
          <div className="text-[10px] text-stone-400 font-bold mt-2">{t("All time")}</div>
        </div>

        {/* Approved */}
        <div className="bg-white border border-stone-200/80 rounded-2xl p-5 shadow-sm text-left flex flex-col justify-between premium-card-hover cursor-pointer">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-emerald-50 border border-emerald-100 text-emerald-655">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                </svg>
              </span>
              <span className="text-[10px] font-extrabold text-stone-500 uppercase tracking-wider">{t("Approved")}</span>
            </div>
            <div className="text-2xl font-black text-stone-850 mt-3">{approvedCount}</div>
          </div>
          <div className="text-[10px] text-emerald-600 font-bold mt-2">{approvedPercent}% {t("of total")}</div>
        </div>

        {/* In Review */}
        <div className="bg-white border border-stone-200/80 rounded-2xl p-5 shadow-sm text-left flex flex-col justify-between premium-card-hover cursor-pointer">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-sky-50 border border-sky-100 text-sky-655">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
                </svg>
              </span>
              <span className="text-[10px] font-extrabold text-stone-500 uppercase tracking-wider">{t("In Review")}</span>
            </div>
            <div className="text-2xl font-black text-stone-850 mt-3">{inReviewCount}</div>
          </div>
          <div className="text-[10px] text-sky-600 font-bold mt-2">{inReviewPercent}% {t("of total")}</div>
        </div>

        {/* Draft */}
        <div className="bg-white border border-stone-200/80 rounded-2xl p-5 shadow-sm text-left flex flex-col justify-between premium-card-hover cursor-pointer">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-amber-50 border border-amber-100 text-amber-600">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125" />
                </svg>
              </span>
              <span className="text-[10px] font-extrabold text-stone-500 uppercase tracking-wider">{t("Draft")}</span>
            </div>
            <div className="text-2xl font-black text-stone-850 mt-3">{draftCount}</div>
          </div>
          <div className="text-[10px] text-amber-600 font-bold mt-2">{draftPercent}% {t("of total")}</div>
        </div>

        {/* Exported */}
        <div className="bg-white border border-stone-200/80 rounded-2xl p-5 shadow-sm text-left flex flex-col justify-between premium-card-hover cursor-pointer">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-purple-50 border border-purple-100 text-purple-600">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 8.25H7.5a2.25 2.25 0 0 0-2.25 2.25v9a2.25 2.25 0 0 0 2.25 2.25h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25H15M9 12l3 3m0 0 3-3m-3 3V2.25" />
                </svg>
              </span>
              <span className="text-[10px] font-extrabold text-stone-500 uppercase tracking-wider">{t("Exported")}</span>
            </div>
            <div className="text-2xl font-black text-stone-850 mt-3">{exportedCount}</div>
          </div>
          <div className="text-[10px] text-purple-600 font-bold mt-2">{exportedPercent}% {t("of total")}</div>
        </div>
      </div>
    </ScrollReveal>
  );
}
