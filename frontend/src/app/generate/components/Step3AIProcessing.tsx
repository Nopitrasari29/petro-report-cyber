import React from "react";
import ScrollReveal from "@/components/ScrollReveal";

interface Step3AIProcessingProps {
  aiStatus: "pending" | "processing" | "completed";
  reportDetails: any;
  errorMsg: string;
  onBack: () => void;
  onProceed: () => void;
  tx: (key: string, fallback: string) => string;
}

export default function Step3AIProcessing({
  aiStatus,
  reportDetails,
  errorMsg,
  onBack,
  onProceed,
  tx,
}: Step3AIProcessingProps) {
  return (
    <ScrollReveal animation="fadeInUp" className="space-y-6">
      <div className="text-left">
        <h2 className="text-2xl font-extrabold text-stone-900">{tx("AI Processing", "AI Processing")}</h2>
        <p className="text-sm text-stone-500 font-semibold mt-1">
          {tx("Our AI is analyzing your data and generating insights", "Our AI is analyzing your data and generating insights")}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 text-left items-start mt-6">
        {/* Left Column (60% width): Processing Progress */}
        <div className="lg:col-span-7 bg-white rounded-2xl border border-stone-200/80 p-6 shadow-sm space-y-6 premium-card-hover transition-colors">
          <div>
            <div className="flex justify-between items-center mb-2">
              <h3 className="font-extrabold text-stone-855 text-sm">{tx("Processing Progress", "Processing Progress")}</h3>
              <span className="text-xs font-bold text-petro-green">
                {aiStatus === "completed" ? "100%" : "68%"}
              </span>
            </div>
            {/* Progress Bar */}
            <div className="w-full h-3 bg-stone-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-petro-green transition-all duration-500"
                style={{ width: aiStatus === "completed" ? "100%" : "68%" }}
              ></div>
            </div>
          </div>

          {/* Checklist */}
          <div className="space-y-4">
            {/* Item 1 */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="w-5 h-5 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-emerald-600">
                    <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                  </svg>
                </span>
                <span className="text-xs font-bold text-stone-700">{tx("Reading uploaded files", "Reading uploaded files")}</span>
              </div>
              <span className="text-[10px] text-emerald-600 font-bold">{tx("Completed", "Completed")}</span>
            </div>

            {/* Item 2 */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="w-5 h-5 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-emerald-600">
                    <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                  </svg>
                </span>
                <span className="text-xs font-bold text-stone-700">{tx("Extracting and structuring data", "Extracting and structuring data")}</span>
              </div>
              <span className="text-[10px] text-emerald-600 font-bold">{tx("Completed", "Completed")}</span>
            </div>

            {/* Item 3 */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <span className="w-5 h-5 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-emerald-600">
                    <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                  </svg>
                </span>
                <span className="text-xs font-bold text-stone-700">{tx("Detecting security threats", "Detecting security threats")}</span>
              </div>
              <span className="text-[10px] text-emerald-600 font-bold">{tx("Completed", "Completed")}</span>
            </div>

            {/* Item 4 */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {aiStatus === "completed" ? (
                  <span className="w-5 h-5 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-emerald-600">
                      <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                    </svg>
                  </span>
                ) : (
                  <span className="w-5 h-5 rounded-full bg-amber-50 border border-amber-200 flex items-center justify-center">
                    <div className="w-2.5 h-2.5 border-2 border-stone-200 border-t-amber-500 rounded-full animate-spin"></div>
                  </span>
                )}
                <span className="text-xs font-bold text-stone-700">{tx("Generating executive summary", "Generating executive summary")}</span>
              </div>
              <span className={`text-[10px] font-bold ${aiStatus === "completed" ? "text-emerald-600" : "text-amber-600"}`}>
                {aiStatus === "completed" ? tx("Completed", "Completed") : tx("In Progress", "In Progress")}
              </span>
            </div>

            {/* Item 5 */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {aiStatus === "completed" ? (
                  <span className="w-5 h-5 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-emerald-600">
                      <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                    </svg>
                  </span>
                ) : (
                  <span className="w-5 h-5 rounded-full bg-stone-50 border border-stone-200 flex items-center justify-center"></span>
                )}
                <span className={`text-xs font-bold ${aiStatus === "completed" ? "text-stone-700" : "text-stone-400"}`}>{tx("Creating charts and visualizations", "Creating charts and visualizations")}</span>
              </div>
              <span className={`text-[10px] font-bold ${aiStatus === "completed" ? "text-emerald-600" : "text-stone-400"}`}>
                {aiStatus === "completed" ? tx("Completed", "Completed") : tx("Waiting", "Waiting")}
              </span>
            </div>

            {/* Item 6 */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {aiStatus === "completed" ? (
                  <span className="w-5 h-5 rounded-full bg-emerald-50 border border-emerald-250 flex items-center justify-center">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5 text-emerald-600">
                      <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                    </svg>
                  </span>
                ) : (
                  <span className="w-5 h-5 rounded-full bg-stone-50 border border-stone-200 flex items-center justify-center"></span>
                )}
                <span className={`text-xs font-bold ${aiStatus === "completed" ? "text-stone-700" : "text-stone-400"}`}>{tx("Preparing report content", "Preparing report content")}</span>
              </div>
              <span className={`text-[10px] font-bold ${aiStatus === "completed" ? "text-emerald-600" : "text-stone-400"}`}>
                {aiStatus === "completed" ? tx("Completed", "Completed") : tx("Waiting", "Waiting")}
              </span>
            </div>
          </div>

          {/* Warning Alert */}
          <div className="bg-emerald-50/50 border border-emerald-100 rounded-xl p-4 flex gap-3 text-left">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-5 h-5 text-emerald-650 shrink-0 mt-0.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
            </svg>
            <div>
              <p className="text-xs font-bold text-stone-800">{tx("Please don't close or refresh this page", "Please don't close or refresh this page")}</p>
              <p className="text-[10px] text-stone-500 font-semibold mt-0.5">{tx("This process may take a few minutes as our AI analyzes log data.", "This process may take a few minutes as our AI analyzes log data.")}</p>
            </div>
          </div>
        </div>

        {/* Right Column (40% width): AI Insights Preview */}
        <div className="lg:col-span-5 bg-white rounded-2xl border border-stone-200/80 p-6 shadow-sm space-y-4 premium-card-hover transition-colors">
          <h3 className="font-extrabold text-stone-855 text-sm border-b border-stone-100 pb-2">{tx("AI Insights Preview", "AI Insights Preview")}</h3>

          <div className="space-y-3">
            {/* Critical */}
            <div className="flex items-center justify-between p-3.5 bg-red-50/50 border border-red-100 rounded-xl">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-red-600 animate-pulse"></span>
                <span className="text-xs font-bold text-stone-750">Critical</span>
              </div>
              <div className="text-right">
                <div className="text-sm font-black text-red-600">{reportDetails?.threat_count_critical ?? 18}</div>
                <div className="text-[9px] text-red-650/80 font-bold mt-0.5">+12% vs last month</div>
              </div>
            </div>

            {/* High */}
            <div className="flex items-center justify-between p-3.5 bg-amber-50/40 border border-amber-100 rounded-xl">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span>
                <span className="text-xs font-bold text-stone-750">High</span>
              </div>
              <div className="text-right">
                <div className="text-sm font-black text-amber-600">{reportDetails?.threat_count_high ?? 56}</div>
                <div className="text-[9px] text-amber-600/80 font-bold mt-0.5">+9% vs last month</div>
              </div>
            </div>

            {/* Medium */}
            <div className="flex items-center justify-between p-3.5 bg-yellow-50/30 border border-yellow-100 rounded-xl">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-yellow-400"></span>
                <span className="text-xs font-bold text-stone-750">Medium</span>
              </div>
              <div className="text-right">
                <div className="text-sm font-black text-yellow-600">{reportDetails?.threat_count_medium ?? 103}</div>
                <div className="text-[9px] text-yellow-650/80 font-bold mt-0.5">+5% vs last month</div>
              </div>
            </div>
          </div>

          {/* Summary Grid stats */}
          <div className="grid grid-cols-2 gap-4 border-t border-stone-100 pt-4 text-center">
            <div className="p-3 bg-stone-50 border border-stone-150 rounded-xl">
              <div className="text-[9px] text-stone-400 font-bold uppercase tracking-wider">{tx("Total Alerts", "Total Alerts")}</div>
              <div className="text-base font-black text-stone-800 mt-1">{reportDetails?.total_records_parsed ?? 177}</div>
            </div>
            <div className="p-3 bg-stone-50 border border-stone-150 rounded-xl">
              <div className="text-[9px] text-stone-400 font-bold uppercase tracking-wider">{tx("Total Incidents", "Total Incidents")}</div>
              <div className="text-base font-black text-stone-800 mt-1">
                {reportDetails
                  ? (reportDetails.threat_count_critical + reportDetails.threat_count_high + reportDetails.threat_count_medium)
                  : 26
                }
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Status information or Error messages */}
      {errorMsg && (
        <div className="bg-red-50 border border-red-200 text-red-750 px-4 py-3 rounded-xl text-xs font-medium text-left">
          <strong>Error:</strong> {errorMsg}
        </div>
      )}

      {/* Bottom Nav Bar */}
      <div className="pt-6 border-t border-stone-200/60 mt-8 flex flex-col items-end gap-2">
        <p className="text-[10px] text-stone-500 font-bold">Estimated time: 2 - 5 minutes</p>

        <div className="flex justify-between items-center w-full">
          <button
            onClick={onBack}
            disabled={aiStatus === "processing"}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white border border-stone-200 hover:bg-stone-50 text-stone-700 font-bold text-sm shadow-sm transition-all duration-200 disabled:opacity-50 cursor-pointer"
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
            </svg>
            {tx("Back", "Back")}
          </button>

          {aiStatus === "completed" ? (
            <button
              onClick={onProceed}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-petro-green hover:bg-petro-green-hover text-white font-bold text-sm shadow transition-all duration-200 group cursor-pointer"
            >
              {tx("View Preview & Edit", "View Preview & Edit")}
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5 transition-transform group-hover:translate-x-1">
                <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
              </svg>
            </button>
          ) : (
            <button
              disabled
              className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-petro-green text-white font-bold text-sm shadow cursor-not-allowed"
            >
              <svg className="animate-spin h-3.5 w-3.5 text-white mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              {tx("Processing......", "Processing......")}
            </button>
          )}
        </div>
      </div>
    </ScrollReveal>
  );
}
