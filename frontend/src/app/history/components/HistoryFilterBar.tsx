import { useTx } from "@/hooks/useTx";

interface HistoryFilterBarProps {
  searchQuery: string;
  setSearchQuery: (val: string) => void;
  statusFilter: string;
  setStatusFilter: (val: string) => void;
  periodFilter: string;
  setPeriodFilter: (val: string) => void;
  periodOptions: string[];
  sortOrder: string;
  setSortOrder: (val: string) => void;
  setCurrentPage: (page: number) => void;
}

export default function HistoryFilterBar({
  searchQuery,
  setSearchQuery,
  statusFilter,
  setStatusFilter,
  periodFilter,
  setPeriodFilter,
  periodOptions,
  sortOrder,
  setSortOrder,
  setCurrentPage,
}: HistoryFilterBarProps) {
  const { tx } = useTx();

  return (
    <div className="p-4 sm:p-5 border-b border-stone-150 flex flex-col sm:flex-row sm:items-center justify-between gap-3 sm:gap-4">
      <div className="flex flex-wrap items-center gap-2.5 sm:gap-3 flex-1 w-full">
        {/* Search query input */}
        <div className="relative flex-1 min-w-[180px] w-full sm:w-auto">
          <span className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-stone-400">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2.5}
              stroke="currentColor"
              className="w-4 h-4"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.604 10.604Z"
              />
            </svg>
          </span>
          <input
            type="text"
            value={searchQuery || ""}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setCurrentPage(1);
            }}
            placeholder={tx(
              "Search report title, period, keyword....",
              "Search report title, period, keyword...."
            )}
            className="w-full pl-9 pr-4 py-2 border border-stone-200 rounded-xl text-xs font-semibold focus:outline-none focus:border-petro-green text-stone-800 placeholder-stone-400 transition-colors"
          />
        </div>

        {/* Status selector */}
        <div className="relative">
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setCurrentPage(1);
            }}
            className="appearance-none pl-3 pr-8 py-2 border border-stone-200 rounded-xl text-xs font-bold text-stone-700 bg-white focus:outline-none focus:border-petro-green cursor-pointer transition-colors"
          >
            <option value="All Statuses">
              {tx("All Statuses", "All Statuses")}
            </option>
            <option value="Completed">{tx("Completed", "Completed")}</option>
            <option value="Draft">{tx("Draft", "Draft")}</option>
            <option value="In Review">{tx("In Review", "In Review")}</option>
            <option value="Failed">{tx("Failed", "Failed")}</option>
          </select>
          <span className="absolute inset-y-0 right-0 pr-2.5 flex items-center pointer-events-none text-stone-500">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2.5}
              stroke="currentColor"
              className="w-3.5 h-3.5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="m19.5 8.25-7.5 7.5-7.5-7.5"
              />
            </svg>
          </span>
        </div>

        {/* Dynamic Period selector */}
        <div className="relative">
          <select
            value={periodFilter}
            onChange={(e) => {
              setPeriodFilter(e.target.value);
              setCurrentPage(1);
            }}
            className="appearance-none pl-3 pr-8 py-2 border border-stone-200 rounded-xl text-xs font-bold text-stone-700 bg-white focus:outline-none focus:border-petro-green cursor-pointer transition-colors"
          >
            <option value="Select Periods">{tx("Select Periods", "Select Periods")}</option>
            {periodOptions.map((pItem) => (
              <option key={pItem} value={pItem}>
                {pItem}
              </option>
            ))}
          </select>
          <span className="absolute inset-y-0 right-0 pr-2.5 flex items-center pointer-events-none text-stone-500">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2.5}
              stroke="currentColor"
              className="w-3.5 h-3.5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="m19.5 8.25-7.5 7.5-7.5-7.5"
              />
            </svg>
          </span>
        </div>

        {/* Sorting Dropdown (Baru: Pengurutan Laporan) */}
        <div className="relative">
          <select
            value={sortOrder}
            onChange={(e) => {
              setSortOrder(e.target.value);
              setCurrentPage(1);
            }}
            className="appearance-none pl-8 pr-8 py-2 border border-stone-200 rounded-xl text-xs font-bold text-stone-700 bg-white focus:outline-none focus:border-petro-green cursor-pointer transition-colors"
          >
            <option value="newest">{tx("Newest First", "Newest First")}</option>
            <option value="oldest">{tx("Oldest First", "Oldest First")}</option>
            <option value="title_asc">{tx("Title (A - Z)", "Title (A - Z)")}</option>
            <option value="title_desc">{tx("Title (Z - A)", "Title (Z - A)")}</option>
          </select>
          {/* Sorting Icon */}
          <span className="absolute inset-y-0 left-0 pl-2.5 flex items-center pointer-events-none text-stone-400">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-3.5 h-3.5 text-petro-green">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 7.5L7.5 3m0 0L12 7.5M7.5 3v13.5m13.5-3L16.5 21m0 0L12 16.5m4.5 4.5V7.5" />
            </svg>
          </span>
          <span className="absolute inset-y-0 right-0 pr-2.5 flex items-center pointer-events-none text-stone-500">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2.5}
              stroke="currentColor"
              className="w-3.5 h-3.5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="m19.5 8.25-7.5 7.5-7.5-7.5"
              />
            </svg>
          </span>
        </div>
      </div>

      {/* Action buttons on the right - Reset Filters */}
      <button
        onClick={() => {
          setSearchQuery("");
          setStatusFilter("All Statuses");
          setPeriodFilter("Select Periods");
          setSortOrder("newest");
          setCurrentPage(1);
        }}
        className="flex items-center gap-2 px-3 py-2 bg-stone-50 hover:bg-stone-100 border border-stone-200 text-stone-700 font-extrabold text-xs rounded-xl transition-colors shadow-sm cursor-pointer active:scale-95"
        title={tx("Reset Filters", "Reset Filters")}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2.2}
          stroke="currentColor"
          className="w-3.5 h-3.5 text-petro-green"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 3c2.755 0 5.455.232 8.083.678.533.09.917.556.917 1.096v1.044a2.25 2.25 0 0 1-.659 1.591l-5.432 5.432a2.25 2.25 0 0 0-.659 1.591v2.927a2.25 2.25 0 0 1-1.244 2.013L9.75 21v-6.568a2.25 2.25 0 0 0-.659-1.591L3.659 7.409A2.25 2.25 0 0 1 3 5.818V4.774c0-.54.384-1.006.917-1.096A48.32 48.32 0 0 1 12 3Z"
          />
        </svg>
        {tx("Reset Filters", "Reset Filters")}
      </button>
    </div>
  );
}
