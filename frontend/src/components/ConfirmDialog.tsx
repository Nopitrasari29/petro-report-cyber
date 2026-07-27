"use client";

import { useEffect, useState } from "react";
import { t } from "@/utils/i18n";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  cancelLabel,
  danger = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);
  const tx = (key: string, fallback: string) => (mounted ? t(key) : fallback);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCancel();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-100 bg-stone-900/40 flex items-center justify-center p-4 animate-fadeIn"
      onClick={onCancel}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-sm bg-white rounded-2xl shadow-2xl border border-stone-200/80 p-6 text-left"
      >
        <div className="flex items-start gap-3">
          <span
            className={`shrink-0 w-9 h-9 rounded-full flex items-center justify-center ${
              danger
                ? "bg-red-50 text-red-600"
                : "bg-petro-green-light text-petro-green"
            }`}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
              className="w-5 h-5"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
              />
            </svg>
          </span>
          <div className="flex-1">
            <h3 className="font-black text-stone-900 text-sm">{title}</h3>
            <p className="text-xs text-stone-500 font-semibold mt-1.5 leading-relaxed">
              {message}
            </p>
          </div>
        </div>

        <div className="flex justify-end gap-2.5 mt-6">
          <button
            type="button"
            onClick={onCancel}
            className="px-4 py-2 rounded-lg bg-white border border-stone-200 hover:bg-stone-50 text-stone-700 font-bold text-xs shadow-sm transition-colors cursor-pointer"
          >
            {cancelLabel ?? tx("Cancel", "Cancel")}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`px-4 py-2 rounded-lg text-white font-bold text-xs shadow-sm transition-colors cursor-pointer ${
              danger
                ? "bg-red-500 hover:bg-red-600"
                : "bg-petro-green hover:bg-petro-green-hover"
            }`}
          >
            {confirmLabel ?? tx("Confirm", "Confirm")}
          </button>
        </div>
      </div>
    </div>
  );
}
