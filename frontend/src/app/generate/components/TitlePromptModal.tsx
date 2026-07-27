"use client";

import { useState, useEffect } from "react";

interface TitlePromptModalProps {
  isOpen: boolean;
  initialTitle: string;
  onConfirm: (title: string) => void;
  onClose: () => void;
  tx: (key: string, fallback: string) => string;
}

// Ditampilkan saat klik "Next Export" di Step 4 — sebelumnya field Report Title tidak pernah
// tersambung ke UI apa pun, jadi setiap laporan diam-diam terkirim dengan judul default yang
// sama. Popup ini pas dimunculkan di sini (bukan di awal upload) karena user baru bisa menilai
// judul yang cocok setelah melihat isi laporan yang sudah dianalisis AI.
export default function TitlePromptModal({
  isOpen,
  initialTitle,
  onConfirm,
  onClose,
  tx,
}: TitlePromptModalProps) {
  const [titleInput, setTitleInput] = useState(initialTitle);

  useEffect(() => {
    if (isOpen) setTitleInput(initialTitle);
  }, [isOpen, initialTitle]);

  if (!isOpen) return null;

  const handleConfirm = () => {
    const trimmed = titleInput.trim();
    onConfirm(trimmed || initialTitle);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-stone-900/60 backdrop-blur-xs animate-fadeIn">
      <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-stone-200 space-y-4 text-left animate-scaleIn">
        <div>
          <h3 className="font-extrabold text-stone-900 text-base">
            {tx("Judul Laporan", "Report Title")}
          </h3>
          <p className="text-xs text-stone-500 font-semibold mt-0.5">
            {tx(
              "Beri nama laporan ini sebelum lanjut ke tahap unduh.",
              "Name this report before proceeding to the download step.",
            )}
          </p>
        </div>

        <input
          type="text"
          value={titleInput}
          onChange={(e) => setTitleInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleConfirm();
          }}
          autoFocus
          className="w-full px-3.5 py-2.5 rounded-xl border border-stone-250 focus:border-petro-green focus:ring-2 focus:ring-petro-green/20 text-sm font-semibold text-stone-800 outline-none transition-all"
          placeholder={tx("Judul laporan...", "Report title...")}
        />

        <div className="flex justify-end gap-2.5 pt-2 border-t border-stone-100">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl border border-stone-200 bg-white hover:bg-stone-50 text-stone-700 text-xs font-bold transition-all cursor-pointer"
          >
            {tx("Batal", "Cancel")}
          </button>
          <button
            onClick={handleConfirm}
            disabled={!titleInput.trim()}
            className="px-4 py-2 rounded-xl text-white text-xs font-extrabold shadow-sm transition-all cursor-pointer bg-petro-green hover:bg-petro-green-hover disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {tx("Lanjutkan", "Continue")}
          </button>
        </div>
      </div>
    </div>
  );
}
