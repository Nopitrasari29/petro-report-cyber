// frontend/src/app/history/components/HistoryTable.tsx
import Link from "next/link";
import { useState, useEffect } from "react";
import { t } from "@/utils/i18n";

interface ReportItem {
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
  threat_count_critical: number;
  threat_count_high: number;
  threat_count_medium: number;
  threat_count_low: number;
  total_records_parsed: number;
  created_at: string;
}

interface HistoryTableProps {
  loading: boolean;
  filteredReports: ReportItem[];
  currentRows: ReportItem[];
  rowsPerPage: number;
  setRowsPerPage: (val: number) => void;
  currentPage: number;
  setCurrentPage: React.Dispatch<React.SetStateAction<number>>;
  totalPages: number;
  indexOfFirstRow: number;
  indexOfLastRow: number;
  getStatusDetails: (status: string) => { label: string; classes: string };
  formatPeriod: (start: string, end: string) => string;
  getDataTypeLabel: (type: string) => string;
  formatDateString: (date: string) => string;
  handleDownloadPDF: (id: number) => void;
  handleDelete: (id: number) => void;
}

export default function HistoryTable({
  loading,
  filteredReports,
  currentRows,
  rowsPerPage,
  setRowsPerPage,
  currentPage,
  setCurrentPage,
  totalPages,
  indexOfFirstRow,
  indexOfLastRow,
  getStatusDetails,
  formatPeriod,
  getDataTypeLabel,
  formatDateString,
  handleDownloadPDF,
  handleDelete,
}: HistoryTableProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);
  const tx = (key: string, fallback: string) => (mounted ? t(key) : fallback);

  return (
    <>
      {/* Table Area */}
      {loading ? (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-stone-50/70 border-b border-stone-150 text-stone-500 font-extrabold text-[11px] uppercase tracking-wider text-left">
                <th className="py-4 px-6">
                  {tx("Report Name", "Report Name")}
                </th>
                <th className="py-4 px-6">{tx("Period", "Period")}</th>
                <th className="py-4 px-6">
                  {tx("Report Type", "Report Type")}
                </th>
                <th className="py-4 px-6">{tx("Created By", "Created By")}</th>
                <th className="py-4 px-6">{tx("Status", "Status")}</th>
                <th className="py-4 px-6">{tx("Created At", "Created At")}</th>
                <th className="py-4 px-6 text-center">
                  {tx("Action", "Action")}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {Array.from({ length: 6 }).map((_, i) => (
                <tr key={i}>
                  <td className="py-4 px-6">
                    <div className="skeleton h-3.5 w-48 rounded" />
                  </td>
                  <td className="py-4 px-6">
                    <div className="skeleton h-3 w-28 rounded" />
                  </td>
                  <td className="py-4 px-6">
                    <div className="skeleton h-3 w-24 rounded" />
                  </td>
                  <td className="py-4 px-6">
                    <div className="skeleton h-3 w-20 rounded" />
                  </td>
                  <td className="py-4 px-6">
                    <div className="skeleton h-5 w-16 rounded-full" />
                  </td>
                  <td className="py-4 px-6">
                    <div className="skeleton h-3 w-24 rounded" />
                  </td>
                  <td className="py-4 px-6">
                    <div className="flex justify-center gap-2">
                      <div className="skeleton h-6 w-6 rounded-lg" />
                      <div className="skeleton h-6 w-6 rounded-lg" />
                      <div className="skeleton h-6 w-6 rounded-lg" />
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : filteredReports.length === 0 ? (
        <div className="p-20 text-center text-stone-400 font-bold text-sm">
          {tx(
            "No reports found matching filters.",
            "No reports found matching filters.",
          )}
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-stone-50/70 border-b border-stone-150 text-stone-500 font-extrabold text-[11px] uppercase tracking-wider text-left">
                <th className="py-4 px-6">
                  {tx("Report Name", "Report Name")}
                </th>
                <th className="py-4 px-6">{tx("Period", "Period")}</th>
                <th className="py-4 px-6">
                  {tx("Report Type", "Report Type")}
                </th>
                <th className="py-4 px-6">{tx("Created By", "Created By")}</th>
                <th className="py-4 px-6">{tx("Status", "Status")}</th>
                <th className="py-4 px-6">{tx("Created At", "Created At")}</th>
                <th className="py-4 px-6 text-center">
                  {tx("Action", "Action")}
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100 text-stone-700 text-xs font-bold">
              {currentRows.map((item, rowIdx) => {
                const statusDetails = getStatusDetails(item.status);
                return (
                  <tr
                    key={item.id}
                    className="group hover:bg-stone-50/70 transition-all duration-200 animate-fadeInUp"
                    style={{ animationDelay: `${rowIdx * 40}ms` }}
                  >
                    <td className="py-4 px-6 font-black text-stone-855 text-left group-hover:text-petro-green transition-colors duration-200">
                      {item.title}
                    </td>
                    <td className="py-4 px-6 text-left">
                      {formatPeriod(item.period_start, item.period_end)}
                    </td>
                    <td className="py-4 px-6 text-left">
                      {tx(
                        getDataTypeLabel(item.data_type),
                        getDataTypeLabel(item.data_type),
                      )}
                    </td>
                    {/* REVISI: Mengganti nama statis dummy "Rafika" menjadi nama pembuat riil dari DB secara dinamis */}
                    <td className="py-4 px-6 text-left">
                      {item.created_by_name || tx("Analyst", "Analyst")}
                    </td>
                    <td className="py-4 px-6 text-left">
                      <span
                        className={`px-3 py-1 rounded-full font-bold text-[10px] whitespace-nowrap inline-flex items-center gap-1.5 ${statusDetails.classes}`}
                      >
                        {item.status === "draft" ||
                        item.status === "analyzed" ? (
                          <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
                        ) : null}
                        {tx(statusDetails.label, statusDetails.label)}
                      </span>
                    </td>
                    <td className="py-4 px-6 text-left text-stone-450">
                      {formatDateString(item.created_at)}
                    </td>
                    <td className="py-4 px-6 text-center flex items-center justify-center gap-2">
                      {/* View Action */}
                      <Link
                        href={`/history/${item.id}`}
                        className="p-1.5 rounded-lg border border-stone-200 bg-white hover:bg-stone-50 text-stone-600 hover:text-stone-800 transition-colors shadow-sm cursor-pointer"
                        title={tx("View Preview", "View Preview")}
                      >
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          fill="none"
                          viewBox="0 0 24 24"
                          strokeWidth={2.2}
                          stroke="currentColor"
                          className="w-3.5 h-3.5"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.43 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"
                          />
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"
                          />
                        </svg>
                      </Link>

                      {/* Download Action */}
                      <button
                        onClick={() => handleDownloadPDF(item.id)}
                        className="p-1.5 rounded-lg border border-stone-200 bg-white hover:bg-stone-50 text-stone-600 hover:text-stone-800 transition-colors shadow-sm cursor-pointer"
                        title={tx("Download PDF", "Download PDF")}
                      >
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          fill="none"
                          viewBox="0 0 24 24"
                          strokeWidth={2.2}
                          stroke="currentColor"
                          className="w-3.5 h-3.5"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"
                          />
                        </svg>
                      </button>

                      {/* Edit Action */}
                      <Link
                        href={`/history/${item.id}?edit=true`}
                        className="p-1.5 rounded-lg border border-stone-200 bg-white hover:bg-stone-50 text-stone-600 hover:text-stone-800 transition-colors shadow-sm cursor-pointer"
                        title={tx("Edit Report", "Edit Report")}
                      >
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          fill="none"
                          viewBox="0 0 24 24"
                          strokeWidth={2.2}
                          stroke="currentColor"
                          className="w-3.5 h-3.5"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L6.832 19.82a4.5 4.5 0 0 1-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 0 1 1.13-1.897L16.863 4.487Zm0 0L19.5 7.125"
                          />
                        </svg>
                      </Link>

                      {/* Delete Action */}
                      <button
                        onClick={() => handleDelete(item.id)}
                        className="p-1.5 rounded-lg border border-red-100 bg-red-50 hover:bg-red-100 text-red-655 hover:text-red-700 transition-colors shadow-sm cursor-pointer"
                        title={tx("Delete Report", "Delete Report")}
                      >
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          fill="none"
                          viewBox="0 0 24 24"
                          strokeWidth={2.2}
                          stroke="currentColor"
                          className="w-3.5 h-3.5"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            d="m14.74 9-.346 9m-4.788 0L9 9m12 6a2.25 2.25 0 0 1-2.25 2.25h-9a2.25 2.25 0 0 1-2.25-2.25V5.25c0-.54.384-1.006.917-1.096A48.24 48.24 0 0 1 12 3c2.78 0 5.518.232 8.161.68.525.09.917.556.917 1.096V15Z"
                          />
                        </svg>
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination Footer */}
      {!loading && filteredReports.length > 0 && (
        <div className="p-5 border-t border-stone-150 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs font-bold text-stone-500 animate-fadeInUp">
          <span>
            {tx("Showing", "Showing")} {indexOfFirstRow + 1} {tx("to", "to")}{" "}
            {Math.min(indexOfLastRow, filteredReports.length)} {tx("of", "of")}{" "}
            {filteredReports.length} {tx("reports", "reports")}
          </span>

          <div className="flex items-center gap-6">
            {/* Rows per page selector */}
            <div className="flex items-center gap-2">
              <span>{tx("Rows per page", "Rows per page")}</span>
              <div className="relative">
                <select
                  value={rowsPerPage}
                  onChange={(e) => {
                    setRowsPerPage(Number(e.target.value));
                    setCurrentPage(1);
                  }}
                  className="appearance-none pl-3 pr-7 py-1.5 border border-stone-200 rounded-lg text-stone-700 bg-white focus:outline-none focus:border-petro-green cursor-pointer transition-colors"
                >
                  <option value={5}>5</option>
                  <option value={10}>10</option>
                  <option value={20}>20</option>
                  <option value={50}>50</option>
                </select>
                <span className="absolute inset-y-0 right-0 pr-2 flex items-center pointer-events-none text-stone-500">
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

            {/* Page selector buttons */}
            <div className="flex items-center gap-1">
              <button
                onClick={() => setCurrentPage((prev) => Math.max(prev - 1, 1))}
                disabled={currentPage === 1}
                className="w-8 h-8 rounded-lg border border-stone-200 flex items-center justify-center bg-white text-stone-500 hover:bg-stone-50 disabled:opacity-50 transition-colors cursor-pointer"
              >
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
                    d="M15.75 19.5 8.25 12l7.5-7.5"
                  />
                </svg>
              </button>

              {Array.from({ length: totalPages }).map((_, i) => {
                const pageNum = i + 1;
                return (
                  <button
                    key={pageNum}
                    onClick={() => setCurrentPage(pageNum)}
                    className={`w-8 h-8 rounded-lg flex items-center justify-center font-bold transition-all cursor-pointer ${
                      currentPage === pageNum
                        ? "bg-petro-green text-white"
                        : "border border-stone-200 bg-white text-stone-600 hover:bg-stone-50"
                    }`}
                  >
                    {pageNum}
                  </button>
                );
              })}

              <button
                onClick={() =>
                  setCurrentPage((prev) => Math.min(prev + 1, totalPages))
                }
                disabled={currentPage === totalPages}
                className="w-8 h-8 rounded-lg border border-stone-200 flex items-center justify-center bg-white text-stone-500 hover:bg-stone-50 disabled:opacity-50 transition-colors cursor-pointer"
              >
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
                    d="m8.25 4.5 7.5 7.5-7.5 7.5"
                  />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
