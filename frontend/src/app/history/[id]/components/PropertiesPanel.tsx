import { useState, useEffect } from "react";
import { t } from "@/utils/i18n";

interface ReportDetails {
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
  ai_summary: Record<string, any>;
}

interface PropertiesPanelProps {
  report: ReportDetails;
}

export default function PropertiesPanel({ report }: PropertiesPanelProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);
  const tx = (key: string, fallback: string) => (mounted ? t(key) : fallback);

  return (
    <div className="lg:col-span-3 bg-white border border-stone-200/85 rounded-2xl p-4 shadow-sm h-[520px]">
      <h3 className="font-extrabold text-stone-900 text-sm border-b border-stone-100 pb-3 flex justify-between items-center cursor-pointer">
        <span>{tx("Properties", "Properties")}</span>
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

      <div className="mt-4 space-y-4 text-left">
        <div className="flex flex-col gap-1.5">
          <label className="text-[10px] font-black text-stone-500 uppercase tracking-wider">
            {tx("Language", "Language")}
          </label>
          <div className="relative">
            <select
              value={report.language || "English"}
              disabled
              className="appearance-none w-full pl-3 pr-8 py-2 border border-stone-200 rounded-xl text-xs font-bold text-stone-700 bg-stone-50 cursor-not-allowed"
            >
              <option>{tx("English", "English")}</option>
              <option>{tx("Indonesian", "Indonesian")}</option>
            </select>
            <span className="absolute inset-y-0 right-0 pr-2.5 flex items-center pointer-events-none text-stone-400">
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
      </div>
    </div>
  );
}
