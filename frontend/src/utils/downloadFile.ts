// Nama file download dari judul laporan (bukan "soc_report_{id}" generik, dan bisa diganti
// user kapan saja lewat pensil di judul) — dipakai bersama oleh history/page.tsx dan
// history/[id]/page.tsx supaya logikanya tidak terduplikasi di 2 tempat.

export function sanitizeFilename(title: string | undefined | null, fallback: string): string {
  if (!title || !title.trim()) return fallback;
  // Karakter ilegal filesystem DIGANTI spasi (bukan dihapus) supaya kata tidak nyambung,
  // mis. "Q1/2024" -> "Q1_2024" bukan "Q12024".
  let name = title.trim().replace(/[\\/:*?"<>|]/g, " ");
  name = name.replace(/\s+/g, "_").replace(/^[_.]+|[_.]+$/g, "");
  if (name.length > 80) name = name.slice(0, 80).replace(/[_.]+$/g, "");
  return name || fallback;
}

/**
 * Langsung download ke folder Downloads browser (tanpa dialog "Save As" apa pun) memakai
 * nama file yang sudah disiapkan (`suggestedName`, dari judul laporan).
 */
export async function downloadBlobAsFile(
  blob: Blob,
  suggestedName: string,
): Promise<void> {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = suggestedName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
