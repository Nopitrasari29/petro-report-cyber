// Render halaman pertama file PDF jadi gambar data URL (PNG), dijalankan sepenuhnya di
// browser (pdf.js) — tidak ada round-trip ke server dan tidak butuh library native apapun
// di backend (beda dari WeasyPrint/kaleido yang sempat bermasalah karena dependency native
// di Windows). CSV/XLSX tidak punya "halaman" untuk di-render, jadi tidak melalui fungsi ini.
let workerConfigured = false;

async function ensureWorker() {
  if (workerConfigured) return;
  const pdfjsLib = await import("pdfjs-dist");
  pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
    "pdfjs-dist/build/pdf.worker.min.mjs",
    import.meta.url,
  ).toString();
  workerConfigured = true;
}

export async function renderPdfThumbnail(file: File): Promise<string | null> {
  try {
    await ensureWorker();
    const pdfjsLib = await import("pdfjs-dist");

    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    const page = await pdf.getPage(1);
    const viewport = page.getViewport({ scale: 0.6 });

    const canvas = document.createElement("canvas");
    canvas.width = viewport.width;
    canvas.height = viewport.height;

    await page.render({ canvas, viewport }).promise;
    return canvas.toDataURL("image/png");
  } catch (err) {
    // Gagal render bukan error fatal — kartu file tetap tampil pakai ikon fallback biasa.
    console.warn("[PDF THUMBNAIL] Gagal merender preview halaman pertama:", err);
    return null;
  }
}
