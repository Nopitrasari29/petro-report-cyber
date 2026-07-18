import Link from "next/link";
import ScrollReveal from "@/components/ScrollReveal";

interface Step0OverviewProps {
  onStart: () => void;
  tx: (key: string, fallback: string) => string;
}

export default function Step0Overview({ onStart, tx }: Step0OverviewProps) {
  return (
    <ScrollReveal animation="fadeInUp" className="space-y-6">
      <div className="text-left">
        <h2 className="text-2xl font-extrabold text-stone-900">{tx("Generate Report", "Generate Report")}</h2>
        <p className="text-sm text-stone-500 font-medium mt-1">
          {tx("Upload your security data and let AI generate comprehensive SOC reports automatically.", "Upload your security data and let AI generate comprehensive SOC reports automatically.")}
        </p>
      </div>

      <div className="bg-white rounded-2xl border border-stone-200/80 p-8 shadow-sm text-left mt-6 premium-card-hover">
        <h3 className="font-extrabold text-stone-900 text-lg mb-6">{tx("How It Works", "How It Works")}</h3>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
          {/* Timeline (left 7 cols) */}
          <div className="lg:col-span-7 flex flex-col">
            {/* Item 1 */}
            <div className="flex items-start gap-4">
              <div className="flex flex-col items-center shrink-0">
                <div className="w-8 h-8 rounded-full bg-petro-green text-white border-2 border-petro-green flex items-center justify-center font-bold text-xs shadow-sm">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                    <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="w-0.5 h-12 bg-petro-green"></div>
              </div>
              <div className="flex-1 flex justify-between items-center py-1 text-left">
                <div>
                  <h4 className="font-bold text-stone-855 text-sm">{tx("Upload your data sources", "Upload your data sources")}</h4>
                  <p className="text-[10px] text-stone-450 mt-1">{tx("Upload your security evidence files. Supported formats: PDF, CSV, XLSX", "Upload your security evidence files. Supported formats: PDF, CSV, XLSX")}</p>
                </div>
                <span className="px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-250 text-emerald-600 font-bold text-[10px] shrink-0">{tx("Complete", "Complete")}</span>
              </div>
            </div>

            {/* Item 2 */}
            <div className="flex items-start gap-4">
              <div className="flex flex-col items-center shrink-0">
                <div className="w-8 h-8 rounded-full bg-petro-green text-white border-2 border-petro-green flex items-center justify-center font-bold text-xs shadow-sm">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                    <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                  </svg>
                </div>
                <div className="w-0.5 h-12 bg-petro-green"></div>
              </div>
              <div className="flex-1 flex justify-between items-center py-1 text-left">
                <div>
                  <h4 className="font-bold text-stone-855 text-sm">{tx("Configure report settings", "Configure report settings")}</h4>
                  <p className="text-[10px] text-stone-450 mt-1">{tx("Set period, template, format, and other preferences for your report", "Set period, template, format, and other preferences for your report")}</p>
                </div>
                <span className="px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-255 text-emerald-600 font-bold text-[10px] shrink-0">{tx("Complete", "Complete")}</span>
              </div>
            </div>

            {/* Item 3 */}
            <div className="flex items-start gap-4">
              <div className="flex flex-col items-center shrink-0">
                <div className="w-8 h-8 rounded-full bg-white text-petro-green border-2 border-petro-green flex items-center justify-center font-bold text-xs shadow-sm">
                  3
                </div>
                <div className="w-0.5 h-12 bg-stone-250"></div>
              </div>
              <div className="flex-1 flex justify-between items-center py-1 text-left">
                <div>
                  <h4 className="font-bold text-stone-855 text-sm">{tx("AI processing", "AI processing")}</h4>
                  <p className="text-[10px] text-stone-450 mt-1">{tx("Our AI will analyze the data and generate insights, charts, and summary", "Our AI will analyze the data and generate insights, charts, and summary")}</p>
                </div>
                <span className="px-2.5 py-1 rounded-full bg-stone-100 border border-stone-200 text-stone-450 font-bold text-[10px] shrink-0">{tx("Pending", "Pending")}</span>
              </div>
            </div>

            {/* Item 4 */}
            <div className="flex items-start gap-4">
              <div className="flex flex-col items-center shrink-0">
                <div className="w-8 h-8 rounded-full bg-white text-stone-400 border border-stone-200 flex items-center justify-center font-bold text-xs shadow-sm">
                  4
                </div>
                <div className="w-0.5 h-12 bg-stone-200"></div>
              </div>
              <div className="flex-1 flex justify-between items-center py-1 text-left">
                <div>
                  <h4 className="font-bold text-stone-855 text-sm">{tx("Preview & edit", "Preview & edit")}</h4>
                  <p className="text-[10px] text-stone-450 mt-1">{tx("Review AI generated content and make any necessary edits", "Review AI generated content and make any necessary edits")}</p>
                </div>
                <span className="px-2.5 py-1 rounded-full bg-stone-100 border border-stone-200 text-stone-450 font-bold text-[10px] shrink-0">{tx("Pending", "Pending")}</span>
              </div>
            </div>

            {/* Item 5 */}
            <div className="flex items-start gap-4">
              <div className="flex flex-col items-center shrink-0">
                <div className="w-8 h-8 rounded-full bg-white text-stone-400 border border-stone-200 flex items-center justify-center font-bold text-xs shadow-sm">
                  5
                </div>
              </div>
              <div className="flex-1 flex justify-between items-center py-1 text-left">
                <div>
                  <h4 className="font-bold text-stone-855 text-sm">{tx("Export report", "Export report")}</h4>
                  <p className="text-[10px] text-stone-450 mt-1">{tx("Export your report to PDF or PowerPoint format", "Export your report to PDF or PowerPoint format")}</p>
                </div>
                <span className="px-2.5 py-1 rounded-full bg-stone-100 border border-stone-200 text-stone-450 font-bold text-[10px] shrink-0">{tx("Pending", "Pending")}</span>
              </div>
            </div>
          </div>

          {/* Right Laptop Illustration */}
          <div className="lg:col-span-5 flex flex-col items-center justify-center pl-0 lg:pl-8 border-t lg:border-t-0 lg:border-l border-stone-150 py-6">
            <img src="/soc-logo.png" alt="SOC Report" className="w-full max-w-[280px] object-contain h-auto" />
            <p className="mt-8 text-xs font-bold text-stone-750 tracking-wide uppercase">{tx("Processing Pipeline", "Processing Pipeline")}</p>
            <p className="text-[10px] text-stone-450 mt-1 leading-snug text-center max-w-[200px] font-semibold">{tx("Fully automated monthly SOC reporting workflow.", "Fully automated monthly SOC reporting workflow.")}</p>
          </div>
        </div>
      </div>

      {/* Start Button */}
      <div className="pt-6 border-t border-stone-200/60 mt-8 flex flex-col items-center gap-4 animate-fadeIn">
        <button
          onClick={onStart}
          className="w-full max-w-xl inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-xl bg-petro-green hover:bg-petro-green-hover text-white font-extrabold text-sm shadow-md transition-all duration-200 cursor-pointer"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
            <path d="M6.3 2.841A1.5 1.5 0 0 0 4 4.11v11.78a1.5 1.5 0 0 0 2.3 1.269l9.324-5.89a1.5 1.5 0 0 0 0-2.538L6.3 2.84Z" />
          </svg>
          {tx("Start Processing", "Start Processing")}
        </button>

        <Link
          href="/"
          className="text-stone-500 hover:text-petro-green font-bold text-xs transition-colors flex items-center gap-1.5"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
          </svg>
          {tx("Back to Home Page", "Back to Home Page")}
        </Link>
      </div>
    </ScrollReveal>
  );
}
