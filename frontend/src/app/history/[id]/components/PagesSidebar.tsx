import { useState, useEffect } from "react";
import { t } from "@/utils/i18n";
import { REPORT_SECTIONS } from "@/utils/reportSections";

const TOTAL_PAGES = REPORT_SECTIONS.length;
const LAST_PAGE = REPORT_SECTIONS[TOTAL_PAGES - 1].page;

interface PagesSidebarProps {
  activePage: string;
  setActivePage: React.Dispatch<React.SetStateAction<string>>;
  getPageTitle: (page: string) => string;
}

export default function PagesSidebar({
  activePage,
  setActivePage,
  getPageTitle,
}: PagesSidebarProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);
  const tx = (key: string, fallback: string) => (mounted ? t(key) : fallback);

  return (
    <div className="lg:col-span-3 bg-white border border-stone-200/85 rounded-2xl p-4 shadow-sm flex flex-col justify-between h-[520px]">
      <div>
        <h3 className="font-extrabold text-stone-900 text-sm border-b border-stone-100 pb-3 flex justify-between items-center cursor-pointer">
          <span>{tx("Pages", "Pages")}</span>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-4 h-4 text-stone-500"
          >
            <path
              fillRule="evenodd"
              d="M14.77 12.79a.75.75 0 0 1-1.06-.02L10 8.832 6.29 12.77a.75.75 0 1 1-1.08-1.04l4.25-4.5a.75.75 0 0 1 1.08 0l4.25 4.5a.75.75 0 0 1-.02 1.06Z"
              clipRule="evenodd"
            />
          </svg>
        </h3>

        <div className="mt-4 space-y-2">
          {REPORT_SECTIONS.map((sec) => (
            <button
              key={sec.page}
              onClick={() => setActivePage(sec.page)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border transition-all text-left ${
                activePage === sec.page
                  ? "bg-stone-50 border-stone-200 text-stone-900 font-extrabold shadow-sm"
                  : "border-transparent text-stone-500 hover:bg-stone-50/50 hover:text-stone-700 font-bold"
              }`}
            >
              <span className="text-[10px] uppercase font-black text-stone-400">
                {sec.page}
              </span>
              <span className="text-[11px] truncate">
                {tx(getPageTitle(sec.page), getPageTitle(sec.page))}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Sidebar Pagination Footer */}
      <div className="flex justify-between items-center pt-3 border-t border-stone-100">
        <button
          onClick={() =>
            setActivePage((prev) =>
              String(Math.max(Number(prev) - 1, 1)).padStart(2, "0"),
            )
          }
          disabled={activePage === "01"}
          className="p-2 rounded-xl border border-stone-200 hover:bg-stone-50 disabled:opacity-40 transition-colors bg-white shadow-sm"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-3.5 h-3.5 text-stone-600"
          >
            <path
              fillRule="evenodd"
              d="M11.78 5.22a.75.75 0 0 1 0 1.06L8.06 10l3.72 3.72a.75.75 0 1 1-1.06 1.06l-4.25-4.25a.75.75 0 0 1 0-1.06l4.25-4.25a.75.75 0 0 1 1.06 0Z"
              clipRule="evenodd"
            />
          </svg>
        </button>
        <span className="text-[10px] font-black text-stone-500">
          {tx("Page", "Page")} {Number(activePage)} {tx("of", "of")} {TOTAL_PAGES}
        </span>
        <button
          onClick={() =>
            setActivePage((prev) =>
              String(Math.min(Number(prev) + 1, TOTAL_PAGES)).padStart(2, "0"),
            )
          }
          disabled={activePage === LAST_PAGE}
          className="p-2 rounded-xl border border-stone-200 hover:bg-stone-50 disabled:opacity-40 transition-colors bg-white shadow-sm"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-3.5 h-3.5 text-stone-600"
          >
            <path
              fillRule="evenodd"
              d="M8.22 5.22a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06l-4.25 4.25a.75.75 0 0 1-1.06-1.06L11.94 10 8.22 6.28a.75.75 0 0 1 0-1.06Z"
              clipRule="evenodd"
            />
          </svg>
        </button>
      </div>
    </div>
  );
}
