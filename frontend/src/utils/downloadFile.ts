// Nama file download dari judul laporan (bukan "soc_report_{id}" generik) + dialog "Save As"
// bawaan OS lewat File System Access API, dipakai bersama oleh history/page.tsx dan
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

interface SaveOptions {
  description: string;
  mimeType: string;
  extension: string;
}

/**
 * Coba dialog "Save As" bawaan OS via File System Access API (Chrome/Edge, secure context) —
 * user bisa ganti nama & folder di situ. Firefox/Safari (tidak dukung API ini) atau error
 * selain user membatalkan -> fallback ke metode <a download> lama. AbortError (user klik
 * Cancel di dialog) -> berhenti diam-diam, TIDAK error, TIDAK memaksa fallback download —
 * kalau user Cancel, mereka memang tidak ingin filenya tersimpan.
 */
export async function downloadBlobAsFile(
  blob: Blob,
  suggestedName: string,
  options: SaveOptions,
): Promise<void> {
  const picker = (window as any).showSaveFilePicker;
  if (typeof picker === "function") {
    try {
      const handle = await picker({
        suggestedName,
        types: [
          {
            description: options.description,
            accept: { [options.mimeType]: [`.${options.extension}`] },
          },
        ],
      });
      const writable = await handle.createWritable();
      await writable.write(blob);
      await writable.close();
      return;
    } catch (err: any) {
      if (err?.name === "AbortError") return;
      // lanjut ke fallback di bawah utk error lain (mis. permission ditolak)
    }
  }

  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = suggestedName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}
