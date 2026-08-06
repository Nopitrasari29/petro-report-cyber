"use client";

import { useEffect, useRef, useState } from "react";

interface EditableReportTitleProps {
  title: string;
  onSave: (newTitle: string) => void | Promise<void>;
  className?: string;
  tx: (key: string, fallback: string) => string;
}

// Judul laporan yang bisa diedit langsung di tempat (klik pensil ATAU double-click teks
// judulnya langsung -> jadi input di posisi yang sama, Enter/blur simpan, Escape batal) —
// dipakai di halaman History detail dan Preview & Edit (Generate Step 4) supaya keduanya
// konsisten, tanpa modal/box terpisah.
export default function EditableReportTitle({
  title,
  onSave,
  className = "",
  tx,
}: EditableReportTitleProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(title);
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isEditing) setDraft(title);
  }, [title, isEditing]);

  useEffect(() => {
    if (isEditing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [isEditing]);

  const commit = async () => {
    const trimmed = draft.trim();
    setIsEditing(false);
    if (!trimmed || trimmed === title) {
      setDraft(title);
      return;
    }
    setSaving(true);
    try {
      await onSave(trimmed);
    } finally {
      setSaving(false);
    }
  };

  const cancel = () => {
    setDraft(title);
    setIsEditing(false);
  };

  if (isEditing) {
    return (
      <input
        ref={inputRef}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            commit();
          } else if (e.key === "Escape") {
            e.preventDefault();
            cancel();
          }
        }}
        className={`${className} bg-transparent border-b-2 border-petro-green outline-none w-full max-w-full`}
      />
    );
  }

  return (
    <div className="flex items-center gap-2 min-w-0">
      <span
        className={`${className} truncate cursor-text`}
        onDoubleClick={() => !saving && setIsEditing(true)}
        title={tx("Double-click to rename", "Double-click untuk ubah nama")}
      >
        {title}
      </span>
      <button
        type="button"
        onClick={() => setIsEditing(true)}
        disabled={saving}
        className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-lg text-stone-400 hover:text-petro-green hover:bg-petro-green/10 transition-all cursor-pointer disabled:opacity-50"
        aria-label={tx("Edit Report Title", "Edit Report Title")}
        title={tx("Edit Report Title", "Edit Report Title")}
      >
        {saving ? (
          <div className="w-3 h-3 border-2 border-stone-300 border-t-petro-green rounded-full animate-spin" />
        ) : (
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            className="w-3.5 h-3.5"
          >
            <path d="M12 20h9" />
            <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5Z" />
          </svg>
        )}
      </button>
    </div>
  );
}
