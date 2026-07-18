import React from "react";
import ScrollReveal from "@/components/ScrollReveal";

interface UploadedFile {
  name: string;
  type: string;
  size: string;
  status: "success" | "pending" | "failed";
}

interface Step1UploadProps {
  files: UploadedFile[];
  onFileDrop: (e: React.DragEvent<HTMLDivElement>) => void;
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onNext: () => void;
  onBack: () => void;
  tx: (key: string, fallback: string) => string;
}

export default function Step1Upload({
  files,
  onFileDrop,
  onFileSelect,
  onNext,
  onBack,
  tx,
}: Step1UploadProps) {
  return (
    <ScrollReveal animation="fadeInUp" className="space-y-6">
      <div className="text-left">
        <h2 className="text-2xl font-extrabold text-stone-900">{tx("Upload Data", "Upload Data")}</h2>
        <p className="text-sm text-stone-500 font-medium mt-1">
          {tx("Upload the security evidence files you want to include in this report", "Upload the security evidence files you want to include in this report")}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Drag & Drop Area */}
        <div className="lg:col-span-2 space-y-6">
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={onFileDrop}
            className="h-80 border-2 border-dashed border-stone-200 hover:border-petro-green/60 rounded-2xl bg-white flex flex-col items-center justify-center cursor-pointer transition-all p-6 group premium-card-hover"
          >
            <div className="w-16 h-16 rounded-full bg-petro-green-light flex items-center justify-center text-petro-green group-hover:scale-105 transition-all duration-300">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor" className="w-8 h-8">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 16.5V9.75m0 0 3 3m-3-3-3 3M6.75 19.5h10.5a2.25 2.25 0 0 0 2.25-2.25V6.75A2.25 2.25 0 0 0 17.25 4.5H6.75A2.25 2.25 0 0 0 4.5 6.75v10.5a2.25 2.25 0 0 0 2.25 2.25Z" />
              </svg>
            </div>
            <p className="mt-4 font-bold text-stone-880 text-sm">{tx("Drag & drop your files here", "Drag & drop your files here")}</p>
            <p className="text-xs text-stone-400 mt-1 font-semibold">{tx("or", "or")}</p>

            <label className="mt-3 px-5 py-2.5 rounded-lg bg-petro-green hover:bg-petro-green-hover text-white font-bold text-xs shadow-sm cursor-pointer transition-colors">
              {tx("Choose File", "Choose File")}
              <input type="file" onChange={onFileSelect} className="hidden" />
            </label>

            <p className="text-[10px] text-stone-450 mt-4 font-medium">{tx("Supported format: PDF, CSV, XLSX", "Supported format: PDF, CSV, XLSX")}</p>
            <p className="text-[9px] text-stone-400 font-medium">{tx("Maximum file size: 100 MB per file", "Maximum file size: 100 MB per file")}</p>
          </div>

          {/* Uploaded Files Table */}
          <div className="bg-white rounded-2xl border border-stone-200/80 p-5 shadow-sm premium-card-hover">
            <h3 className="font-bold text-stone-855 text-sm border-b border-stone-100 pb-3">
              {tx("Uploaded Files", "Uploaded Files")} ({files.length})
            </h3>
            <div className="mt-3 divide-y divide-stone-100">
              {files.map((file, idx) => (
                <div key={idx} className="py-3 flex items-center justify-between text-sm">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-lg bg-red-50 flex items-center justify-center text-red-655 font-bold text-xs border border-red-100">
                      {file.type}
                    </div>
                    <div className="flex flex-col text-left">
                      <span className="font-bold text-stone-800 text-xs leading-none">{file.name}</span>
                      <span className="text-[10px] text-stone-450 font-semibold mt-1">{file.type}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-5">
                    <span className="text-xs font-semibold text-stone-550">{file.size}</span>
                    <span className="w-5 h-5 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
                        <path fillRule="evenodd" d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z" clipRule="evenodd" />
                      </svg>
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Summary Column */}
        <div className="space-y-6">
          <div className="bg-white border border-stone-200/80 rounded-2xl p-5 shadow-sm text-left premium-card-hover">
            <h3 className="font-bold text-stone-900 text-sm border-b border-stone-100 pb-3">{tx("Upload Summary", "Upload Summary")}</h3>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-petro-green">{files.length}</span>
              <span className="text-xs font-bold text-stone-500">{tx("Files Uploaded", "Files Uploaded")}</span>
            </div>
            <div className="mt-4 space-y-2">
              {files.map((file, idx) => (
                <div key={idx} className="flex items-center gap-2 text-xs font-semibold text-stone-600">
                  <span className="text-emerald-600">✓</span>
                  <span>{file.name}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-white border border-stone-200/80 rounded-2xl p-5 shadow-sm text-left premium-card-hover">
            <h3 className="font-bold text-stone-900 text-sm border-b border-stone-100 pb-3">{tx("Estimated AI Accuracy", "Estimated AI Accuracy")}</h3>
            <div className="mt-4 flex items-center gap-4">
              {/* Circular Progress Ring */}
              <div className="relative w-12 h-12 shrink-0">
                <svg className="w-full h-full transform -rotate-90" viewBox="0 0 36 36">
                  <path
                    className="text-stone-100"
                    strokeWidth="3.5"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845
                      a 15.9155 15.9155 0 0 1 0 31.831
                      a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                  <path
                    className="text-petro-green"
                    strokeDasharray="94, 100"
                    strokeWidth="3.5"
                    strokeLinecap="round"
                    stroke="currentColor"
                    fill="none"
                    d="M18 2.0845
                      a 15.9155 15.9155 0 0 1 0 31.831
                      a 15.9155 15.9155 0 0 1 0 -31.831"
                  />
                </svg>
              </div>
              <div>
                <div className="text-lg font-black text-stone-850">94%</div>
                <div className="text-[10px] text-stone-450 font-bold mt-0.5">{tx("Based on data quality", "Based on data quality")}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Nav Bar */}
      <div className="flex justify-between pt-5 border-t border-stone-200/60 mt-8">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-white border border-stone-200 hover:bg-stone-50 text-stone-700 font-bold text-sm shadow-sm transition-all duration-200 cursor-pointer"
        >
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18" />
          </svg>
          {tx("Back", "Back")}
        </button>
        <button
          onClick={onNext}
          disabled={files.length === 0}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-petro-green hover:bg-petro-green-hover text-white font-bold text-sm shadow transition-all duration-200 group cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {tx("Next: Settings", "Next: Settings")}
          <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor" className="w-3.5 h-3.5 transition-transform group-hover:translate-x-1">
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3" />
          </svg>
        </button>
      </div>
    </ScrollReveal>
  );
}
