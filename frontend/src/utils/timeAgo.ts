// Format tanggal ISO jadi teks relatif singkat ("2m ago", "3h ago", dst) — dipakai untuk
// menampilkan waktu notifikasi asli (dari created_at laporan sungguhan), bukan angka karangan.
export function formatTimeAgo(dateString: string): string {
  const then = new Date(dateString).getTime();
  if (Number.isNaN(then)) return "";

  const diffSeconds = Math.max(0, Math.floor((Date.now() - then) / 1000));

  if (diffSeconds < 60) return "just now";

  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) return `${diffMinutes}m ago`;

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 30) return `${diffDays}d ago`;

  const diffMonths = Math.floor(diffDays / 30);
  return `${diffMonths}mo ago`;
}
