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

      <div className="mt-4 space-y-3.5 text-left overflow-y-auto max-h-[440px] pr-1">
        {/* Report Title */}
        <div className="bg-stone-50/80 p-3 rounded-xl border border-stone-150">
          <span className="text-[10px] font-extrabold text-stone-400 uppercase tracking-wider block">
            {tx("Report Name", "Report Name")}
          </span>
          <span className="text-xs font-black text-stone-850 mt-1 block truncate">
            {report.title}
          </span>
        </div>

        {/* Source File */}
        <div className="bg-stone-50/80 p-3 rounded-xl border border-stone-150">
          <span className="text-[10px] font-extrabold text-stone-400 uppercase tracking-wider block">
            {tx("Input File", "Input File")}
          </span>
          <span className="text-xs font-bold text-stone-700 mt-1 block truncate">
            {report.input_file_name || "firewall_logs.csv"}
          </span>
        </div>

        {/* Created By */}
        <div className="bg-stone-50/80 p-3 rounded-xl border border-stone-150">
          <span className="text-[10px] font-extrabold text-stone-400 uppercase tracking-wider block">
            {tx("Created By", "Created By")}
          </span>
          <span className="text-xs font-bold text-stone-700 mt-1 block">
            {report.created_by_name || tx("Analyst", "Analyst")}
          </span>
        </div>

        {/* Output Formats */}
        <div className="bg-stone-50/80 p-3 rounded-xl border border-stone-150">
          <span className="text-[10px] font-extrabold text-stone-400 uppercase tracking-wider block">
            {tx("Supported Exports", "Supported Exports")}
          </span>
          <div className="flex gap-2 mt-1.5">
            <span className="px-2 py-0.5 bg-red-50 text-red-600 font-extrabold text-[10px] rounded border border-red-150">
              PDF
            </span>
            <span className="px-2 py-0.5 bg-amber-50 text-amber-600 font-extrabold text-[10px] rounded border border-amber-150">
              PPTX
            </span>
          </div>
        </div>

        {/* AI Confidence */}
        <div className="bg-stone-50/80 p-3 rounded-xl border border-stone-150">
          <span className="text-[10px] font-extrabold text-stone-400 uppercase tracking-wider block">
            {tx("AI Confidence Score", "AI Confidence Score")}
          </span>
          <div className="flex items-center gap-2 mt-1">
            <div className="flex-1 h-2 bg-stone-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-petro-green rounded-full"
                style={{ width: `${report.ai_confidence ?? 95}%` }}
              ></div>
            </div>
            <span className="text-xs font-black text-petro-green">
              {report.ai_confidence ?? 95}%
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
