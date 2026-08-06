// Jembatan dua-arah antara field array di ai_summary (mis. "recommendations", tersimpan
// sebagai array objek {title, detail}) dan HTML yang dipakai Rich Text Editor (Tiptap) —
// dipakai BERSAMA oleh halaman Generate (Step 4) dan History detail, supaya keduanya
// menyimpan/membaca dengan cara yang SAMA PERSIS, bukan 2 implementasi terpisah yang bisa
// diam-diam beda kalau salah satunya diedit tanpa mengedit yang lain.
//
// "recommendations" adalah SATU-SATUNYA field array di antara 6 key wajib lama yang isinya
// objek (bukan teks polos) — title (kalau ada) ditandai bold di HTML supaya tetap kebaca
// terpisah dari detail saat diedit, dan tetap terpisah lagi saat disimpan balik. Sebelumnya
// objek ini disisipkan mentah ke HTML/di-join seperti teks polos, yang di JavaScript otomatis
// menghasilkan literal "[object Object]" alih-alih tulisan rekomendasi aslinya.
export function arrayItemsToHtml(items: any[]): string {
  if (!items || items.length === 0) return "<ul><li></li></ul>";
  return `<ul>${items
    .map((item) => {
      if (item && typeof item === "object") {
        const itemTitle = item.title ? String(item.title).trim() : "";
        const detail = item.detail ? String(item.detail).trim() : "";
        const titlePart = itemTitle ? `<strong>${itemTitle}</strong> ` : "";
        return `<li>${titlePart}${detail}</li>`;
      }
      return `<li>${item ?? ""}</li>`;
    })
    .join("")}</ul>`;
}

export function htmlToArrayItems(html: string, asObjects: boolean): any[] {
  if (typeof window === "undefined") {
    return asObjects ? [{ title: null, detail: html }] : [html];
  }
  const doc = new DOMParser().parseFromString(html, "text/html");
  let elements: Element[] = Array.from(doc.querySelectorAll("li"));
  if (elements.length === 0) elements = Array.from(doc.querySelectorAll("p"));

  if (!asObjects) {
    if (elements.length > 0) {
      return elements.map((el) => el.innerHTML.trim()).filter(Boolean);
    }
    const text = doc.body.innerHTML.trim();
    return text ? [text] : [];
  }

  return elements
    .map((el) => {
      const strong = el.querySelector("strong, b");
      if (strong) {
        const itemTitle = strong.textContent?.trim() || "";
        const clone = el.cloneNode(true) as HTMLElement;
        clone.querySelector("strong, b")?.remove();
        const detail = clone.textContent?.trim() || "";
        return { title: itemTitle || null, detail };
      }
      return { title: null, detail: el.textContent?.trim() || "" };
    })
    .filter((item) => item.title || item.detail);
}
