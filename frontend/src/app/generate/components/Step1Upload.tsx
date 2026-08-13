import React, { useEffect, useState } from "react";
import ScrollReveal from "@/components/ScrollReveal";
import { renderPdfThumbnail } from "@/utils/pdfThumbnail";

interface UploadedFile {
  name: string;
  type: string;
  size: string;
  status: "success" | "pending" | "failed";
}

interface Step1UploadProps {
  files: UploadedFile[];
  rawFiles: File[];
  onFileDrop: (e: React.DragEvent<HTMLDivElement>) => void;
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onFileRemove: (index: number) => void;
  onNext: () => void;
  onBack: () => void;
  tx: (key: string, fallback: string) => string;
}

function fileKey(file: File): string {
  return `${file.name}__${file.size}__${file.lastModified}`;
}

// Ikon per tipe file buat kartu yang bukan PDF (CSV/XLSX tidak punya "halaman" untuk
// di-render sebagai gambar seperti PDF).
function FileTypeIcon({ type }: { type: string }) {
  const color =
    type === "CSV"
      ? "bg-emerald-50 text-emerald-600 border-emerald-100"
      : type === "XLSX" || type === "XLS"
        ? "bg-green-50 text-green-700 border-green-100"
        : "bg-red-50 text-red-655 border-red-100";
  return (
    <div
      className={`w-full h-full flex items-center justify-center font-black text-sm border rounded-xl ${color}`}
    >
      {type}
    </div>
  );
}

export default function Step1Upload({
  files,
  rawFiles,
  onFileDrop,
  onFileSelect,
  onFileRemove,
  onNext,
  onBack,
  tx,
}: Step1UploadProps) {
  // Thumbnail PDF di-render sepenuhnya di browser (pdf.js) begitu file ditambahkan — di-cache
  // per file (nama+ukuran+lastModified) supaya tidak render ulang tiap re-render komponen.
  const [thumbnails, setThumbnails] = useState<Record<string, string | null>>(
    {},
  );

  useEffect(() => {
    let cancelled = false;

    rawFiles.forEach((file, idx) => {
      const type = files[idx]?.type;
      if (type !== "PDF") return;
      const key = fileKey(file);
      if (key in thumbnails) return;

      renderPdfThumbnail(file).then((dataUrl) => {
        if (!cancelled) {
          setThumbnails((prev) => ({ ...prev, [key]: dataUrl }));
        }
      });
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rawFiles]);

  return (
    <ScrollReveal animation="fadeInUp" className="space-y-6">
      <div className="text-left -mt-2 mb-3">
        <h2 className="text-2xl font-extrabold text-stone-900">
          {tx("Upload Data", "Upload Data")}
        </h2>
        <p className="text-sm text-stone-500 font-semibold mt-1">
          {tx(
            "Upload the security evidence files you want to include in this report",
            "Upload the security evidence files you want to include in this report",
          )}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Drag & Drop Area — SATU kotak untuk kondisi kosong MAUPUN sudah ada file (sebelumnya
            2 kotak terpisah bertumpuk vertikal: dropzone besar + kartu "Uploaded Files" di
            bawahnya, bikin halaman jadi panjang ke bawah). Kotak ini tetap menerima drag&drop di
            kedua kondisi; begitu sudah ada file, isinya berganti jadi grid thumbnail + 1 kartu
            "+" buat nambah file lagi tanpa perlu drag-drop besar muncul lagi. */}
        <div className="lg:col-span-2 space-y-6">
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={onFileDrop}
            className="border-2 border-dashed border-stone-200 hover:border-petro-green/60 rounded-2xl bg-white transition-all p-6 premium-card-hover"
          >
            {files.length === 0 ? (
              <div className="h-56 flex flex-col items-center justify-center cursor-pointer group">
                <div className="w-16 h-16 rounded-full bg-petro-green-light flex items-center justify-center text-petro-green group-hover:scale-105 transition-all duration-300">
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.8}
                    stroke="currentColor"
                    className="w-8 h-8"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 16.5V9.75m0 0 3 3m-3-3-3 3M6.75 19.5h10.5a2.25 2.25 0 0 0 2.25-2.25V6.75A2.25 2.25 0 0 0 17.25 4.5H6.75A2.25 2.25 0 0 0 4.5 6.75v10.5a2.25 2.25 0 0 0 2.25 2.25Z"
                    />
                  </svg>
                </div>
                <p className="mt-4 font-bold text-stone-880 text-sm">
                  {tx(
                    "Drag & drop your files here",
                    "Drag & drop your files here",
                  )}
                </p>
                <p className="text-xs text-stone-400 mt-1 font-semibold">
                  {tx("or", "or")}
                </p>

                <label className="mt-3 px-5 py-2.5 rounded-lg bg-petro-green hover:bg-petro-green-hover text-white font-bold text-xs shadow-sm cursor-pointer transition-colors">
                  {tx("Choose File", "Choose File")}
                  <input
                    type="file"
                    accept=".pdf,.csv,.xlsx,.xls"
                    multiple
                    onChange={onFileSelect}
                    className="hidden"
                  />
                </label>

                <p className="text-[10px] text-stone-450 mt-4 font-medium">
                  {tx(
                    "Supported format: PDF, CSV, XLSX",
                    "Supported format: PDF, CSV, XLSX",
                  )}
                </p>
                <p className="text-[9px] text-stone-400 font-medium">
                  {tx(
                    "Maximum file size: 100 MB per file — you can add more than one file, they'll be merged into one report",
                    "Maximum file size: 100 MB per file — you can add more than one file, they'll be merged into one report",
                  )}
                </p>
              </div>
            ) : (
              <div>
                <div className="flex items-center justify-between border-b border-stone-100 pb-2 mb-4">
                  <h3 className="font-extrabold text-stone-855 text-sm">
                    {tx("Uploaded Files", "Uploaded Files")} ({files.length})
                  </h3>
                  <span className="text-[9px] text-stone-400 font-semibold">
                    {tx(
                      "PDF, CSV, XLSX · Max 100MB/file",
                      "PDF, CSV, XLSX · Max 100MB/file",
                    )}
                  </span>
                </div>
                {/* Baris scroll horizontal (bukan grid yang wrap ke bawah) — supaya menambah
                    banyak file melebarkan area gulir ke samping, bukan membuat kotak Upload
                    Data ini makin tinggi ke bawah tanpa batas. */}
                <div className="flex gap-4 overflow-x-auto pb-1 -mx-1 px-1">
                  {files.map((file, idx) => {
                    const rawFile = rawFiles[idx];
                    const key = rawFile
                      ? fileKey(rawFile)
                      : `${file.name}-${idx}`;
                    const thumbnail = thumbnails[key];

                    return (
                      <div
                        key={key}
                        className="relative shrink-0 w-40 border border-stone-200 rounded-xl p-2 bg-stone-50 hover:shadow-md transition-shadow group"
                      >
                        <button
                          onClick={() => onFileRemove(idx)}
                          title={tx("Remove file", "Remove file")}
                          className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-white border border-stone-200 shadow-sm flex items-center justify-center text-stone-500 hover:text-red-600 hover:border-red-200 transition-colors z-10 cursor-pointer"
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            viewBox="0 0 20 20"
                            fill="currentColor"
                            className="w-3.5 h-3.5"
                          >
                            <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
                          </svg>
                        </button>

                        <div className="w-full aspect-3/4 rounded-lg overflow-hidden bg-white border border-stone-100 flex items-center justify-center">
                          {file.type === "PDF" ? (
                            thumbnail ? (
                              <img
                                src={thumbnail}
                                alt={file.name}
                                className="w-full h-full object-contain"
                              />
                            ) : (
                              <div className="w-8 h-8 border-2 border-stone-200 border-t-petro-green rounded-full animate-spin"></div>
                            )
                          ) : (
                            <div className="w-16 h-16">
                              <FileTypeIcon type={file.type} />
                            </div>
                          )}
                        </div>

                        <div className="mt-2 px-0.5">
                          <p
                            className="text-[10px] font-bold text-stone-800 truncate"
                            title={file.name}
                          >
                            {file.name}
                          </p>
                          <div className="flex items-center justify-between mt-0.5">
                            <span className="text-[9px] text-stone-400 font-semibold">
                              {file.size}
                            </span>
                            <span className="text-emerald-600">
                              <svg
                                xmlns="http://www.w3.org/2000/svg"
                                viewBox="0 0 20 20"
                                fill="currentColor"
                                className="w-3 h-3"
                              >
                                <path
                                  fillRule="evenodd"
                                  d="M16.704 4.153a.75.75 0 0 1 .143 1.052l-8 10.5a.75.75 0 0 1-1.127.075l-4.5-4.5a.75.75 0 0 1 1.06-1.06l3.894 3.893 7.48-9.817a.75.75 0 0 1 1.05-.143Z"
                                  clipRule="evenodd"
                                />
                              </svg>
                            </span>
                          </div>
                        </div>
                      </div>
                    );
                  })}

                  {/* Kartu "+" — tetap bisa nambah file tanpa dropzone besar muncul lagi */}
                  <label
                    title={tx("Add another file", "Add another file")}
                    className="shrink-0 w-40 aspect-3/4 border-2 border-dashed border-stone-200 hover:border-petro-green/60 rounded-xl flex flex-col items-center justify-center gap-1.5 cursor-pointer text-stone-400 hover:text-petro-green bg-stone-50/50 hover:bg-petro-green-light/40 transition-colors"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      className="w-6 h-6"
                    >
                      <path d="M10.75 4.75a.75.75 0 0 0-1.5 0v4.5h-4.5a.75.75 0 0 0 0 1.5h4.5v4.5a.75.75 0 0 0 1.5 0v-4.5h4.5a.75.75 0 0 0 0-1.5h-4.5v-4.5Z" />
                    </svg>
                    <span className="text-[10px] font-bold">
                      {tx("Add File", "Add File")}
                    </span>
                    <input
                      type="file"
                      accept=".pdf,.csv,.xlsx,.xls"
                      multiple
                      onChange={onFileSelect}
                      className="hidden"
                    />
                  </label>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Summary Column */}
        <div className="space-y-6">
          <div className="bg-white border border-stone-200/80 rounded-2xl p-6 shadow-sm text-left premium-card-hover">
            <h3 className="font-extrabold text-stone-855 text-sm border-b border-stone-100 pb-2">
              {tx("Upload Summary", "Upload Summary")}
            </h3>
            <div className="mt-4 flex items-baseline gap-2">
              <span className="text-3xl font-extrabold text-petro-green">
                {files.length}
              </span>
              <span className="text-xs font-bold text-stone-500">
                {tx("Files Uploaded", "Files Uploaded")}
              </span>
            </div>
            <div className="mt-4 space-y-2">
              {files.map((file, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 text-xs font-semibold text-stone-600"
                >
                  <span className="text-emerald-600">✓</span>
                  <span className="truncate">{file.name}</span>
                </div>
              ))}
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
              d="M10.5 19.5 3 12m0 0 7.5-7.5M3 12h18"
            />
          </svg>
          {tx("Back", "Back")}
        </button>
        <button
          onClick={onNext}
          disabled={files.length === 0}
          className="inline-flex items-center gap-2 px-6 py-3 rounded-lg bg-petro-green hover:bg-petro-green-hover text-white font-bold text-sm shadow transition-all duration-200 group cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {tx("Next: Settings", "Next: Settings")}
          <svg
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2.5}
            stroke="currentColor"
            className="w-3.5 h-3.5 transition-transform group-hover:translate-x-1"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M13.5 4.5 21 12m0 0-7.5 7.5M21 12H3"
            />
          </svg>
        </button>
      </div>
    </ScrollReveal>
  );
}
