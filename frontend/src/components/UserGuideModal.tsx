"use client";

import React from "react";
import { getLanguage } from "@/utils/i18n";

interface UserGuideModalProps {
  isOpen: boolean;
  onClose: () => void;
  // Dipertahankan supaya pemanggil di Navbar tidak perlu diubah. Teks modal ini
  // sekarang dipilih sendiri lewat getLanguage() (lihat fungsi L di bawah).
  tx?: (key: string, fallback: string) => string;
}

// Versi query string mencegah browser memakai PDF lama dari cache.
// Naikkan angkanya setiap kali public/user-guide.pdf diganti.
const GUIDE_URL = "/user-guide.pdf?v=2";

const guideTopics = [
  {
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        strokeWidth={2}
        stroke="currentColor"
        className="w-4 h-4"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 16.5V9.75m0 0 3 3m-3-3-3 3M6.75 19.5a4.5 4.5 0 0 1-1.41-8.775 5.25 5.25 0 0 1 10.233-2.33 3 3 0 0 1 3.758 3.848A3.752 3.752 0 0 1 18 19.5H6.75Z"
        />
      </svg>
    ),
    title: ["Upload Data", "Unggah Data"],
    desc: [
      "Upload PDF, CSV, or XLSX files (max 100 MB each). Multiple files are merged into one report.",
      "Unggah berkas PDF, CSV, atau XLSX (maksimal 100 MB per berkas). Beberapa berkas digabung jadi satu laporan.",
    ],
    step: "Step 1",
    color: "bg-blue-50 text-blue-600 border-blue-100",
  },
  {
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        strokeWidth={2}
        stroke="currentColor"
        className="w-4 h-4"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.43l-1.003.828c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.43l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 0 1 0-.255c.007-.378-.138-.75-.43-.991l-1.004-.828a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.28Z"
        />
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"
        />
      </svg>
    ),
    title: ["Report Settings", "Pengaturan Laporan"],
    desc: [
      "Fill in Cover Title, Download File Name, Kop Title, and Kop Subtitle. Then set the period, language, sections, style preset, theme color, and export format.",
      "Isi Cover Title, Download File Name, Kop Title, dan Kop Subtitle. Lalu atur periode, bahasa, section, preset gaya, warna tema, dan format ekspor.",
    ],
    step: "Step 2",
    color: "bg-amber-50 text-amber-600 border-amber-100",
  },
  {
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        strokeWidth={2}
        stroke="currentColor"
        className="w-4 h-4"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M9.75 3.104v5.714a2.25 2.25 0 0 1-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 0 1 4.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0 1 12 15a9.065 9.065 0 0 1-6.23-.693L5 14.5m14.8.8 1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0 1 12 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5"
        />
      </svg>
    ),
    title: ["AI Processing", "Proses AI"],
    desc: [
      "The local AI (qwen3:8b) reads the data and drafts the report. Do not close or refresh the page while it runs.",
      "AI lokal (qwen3:8b) membaca data dan menyusun laporan. Jangan tutup atau refresh halaman selama proses berjalan.",
    ],
    step: "Step 3",
    color: "bg-purple-50 text-purple-600 border-purple-100",
  },
  {
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        strokeWidth={2}
        stroke="currentColor"
        className="w-4 h-4"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z"
        />
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"
        />
      </svg>
    ),
    title: ["Preview & Edit", "Pratinjau & Edit"],
    desc: [
      "Review the result and edit the text in the built-in editor or Fullscreen Studio. Charts are generated automatically and cannot be edited.",
      "Periksa hasil laporan dan edit teks lewat editor bawaan atau Fullscreen Studio. Grafik dibuat otomatis dan tidak bisa diedit.",
    ],
    step: "Step 4",
    color: "bg-emerald-50 text-emerald-600 border-emerald-100",
  },
  {
    icon: (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
        strokeWidth={2}
        stroke="currentColor"
        className="w-4 h-4"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"
        />
      </svg>
    ),
    title: ["Export & Download", "Ekspor & Unduh"],
    desc: [
      "Download the report as PDF or PPTX. It is saved to Report History automatically.",
      "Unduh laporan sebagai PDF atau PPTX. Laporan otomatis tersimpan di Report History.",
    ],
    step: "Step 5",
    color: "bg-rose-50 text-rose-600 border-rose-100",
  },
];

export default function UserGuideModal({
  isOpen,
  onClose,
}: UserGuideModalProps) {
  if (!isOpen) return null;

  // Modal hanya dirender setelah diklik (bukan saat render pertama), jadi aman
  // membaca localStorage langsung. Urutan argumen: (English, Indonesia).
  const isEn = getLanguage() === "English";
  const L = (en: string, id: string) => (isEn ? en : id);

  const handleViewPdf = () => {
    window.open(GUIDE_URL, "_blank");
  };

  const handleDownloadPdf = () => {
    const link = document.createElement("a");
    link.href = GUIDE_URL;
    link.download = "User-Guide-AI-Security-Reports.pdf";
    link.click();
  };

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-stone-900/50 backdrop-blur-sm" />

      {/* Modal */}
      <div className="relative z-10 bg-white rounded-3xl shadow-2xl w-full max-w-lg mx-4 overflow-hidden animate-slideDown">
        {/* Header */}
        <div className="bg-gradient-to-r from-petro-green to-emerald-700 px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/20 rounded-2xl flex items-center justify-center">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.8}
                stroke="currentColor"
                className="w-5 h-5 text-white"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 6.042A8.967 8.967 0 0 0 6 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 0 1 6 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 0 1 6-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0 0 18 18a8.967 8.967 0 0 0-6 2.292m0-14.25v14.25"
                />
              </svg>
            </div>
            <div>
              <h2 className="font-extrabold text-white text-base leading-none">
                {L("User Guide", "Panduan Pengguna")}
              </h2>
              <p className="text-white/70 text-[10px] font-semibold mt-0.5">
                AI Security Reports - PT Petrokimia Gresik
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 bg-white/20 rounded-xl flex items-center justify-center hover:bg-white/30 transition-all cursor-pointer"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2.5}
              stroke="currentColor"
              className="w-4 h-4 text-white"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6 18 18 6M6 6l12 12"
              />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 max-h-[55vh] overflow-y-auto">
          <p className="text-xs text-stone-500 font-semibold mb-4 leading-relaxed">
            {L(
              "Quick guide to generating SOC reports from your data. Open the PDF for the full guide (Indonesian).",
              "Panduan singkat membuat laporan SOC dari data Anda. Buka PDF untuk panduan lengkap.",
            )}
          </p>

          <div className="space-y-2.5">
            {guideTopics.map((topic, i) => (
              <div
                key={i}
                className="flex items-start gap-3 p-3 rounded-2xl border border-stone-100 bg-stone-50/50 hover:bg-stone-50 transition-colors"
              >
                <div
                  className={`w-9 h-9 rounded-xl border flex items-center justify-center shrink-0 ${topic.color}`}
                >
                  {topic.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-[9px] font-extrabold text-stone-400 uppercase tracking-widest">
                      {topic.step}
                    </span>
                    <span className="font-extrabold text-stone-800 text-xs">
                      {topic.title[isEn ? 0 : 1]}
                    </span>
                  </div>
                  <p className="text-[10px] text-stone-500 leading-relaxed">
                    {topic.desc[isEn ? 0 : 1]}
                  </p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-2xl">
            <p className="text-[10px] font-bold text-amber-700 flex items-center gap-1.5">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
                className="w-3.5 h-3.5 shrink-0"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
                />
              </svg>
              {L(
                "Make sure the Ollama server is running before AI processing starts.",
                "Pastikan server Ollama aktif sebelum proses AI dimulai.",
              )}
            </p>
          </div>
        </div>

        {/* Footer - Action Buttons */}
        <div className="px-6 py-4 border-t border-stone-100 flex items-center gap-3 bg-stone-50/50">
          <button
            onClick={handleViewPdf}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-petro-green text-white text-xs font-extrabold rounded-xl hover:bg-petro-green/90 transition-all shadow-sm hover:shadow-md cursor-pointer"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
              className="w-4 h-4"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M2.036 12.322a1.012 1.012 0 0 1 0-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178Z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"
              />
            </svg>
            {L("View PDF", "Lihat PDF")}
          </button>
          <button
            onClick={handleDownloadPdf}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-white border border-stone-200 text-stone-700 text-xs font-extrabold rounded-xl hover:bg-stone-50 hover:border-stone-300 transition-all shadow-sm cursor-pointer"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
              className="w-4 h-4"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"
              />
            </svg>
            {L("Download PDF", "Unduh PDF")}
          </button>
          <button
            onClick={onClose}
            className="px-4 py-2.5 text-stone-400 text-xs font-bold hover:text-stone-600 transition-colors cursor-pointer"
          >
            {L("Close", "Tutup")}
          </button>
        </div>
      </div>
    </div>
  );
}
