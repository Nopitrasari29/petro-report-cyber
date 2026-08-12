// Mekanisme sederhana untuk "menahan" navigasi ke halaman lain (lewat Sidebar/Navbar) selama
// ada proses penting yang sedang berjalan (saat ini: analisis AI di Step 3 wizard Generate).
// SENGAJA bukan React Context — Sidebar/Navbar butuh membaca status ini SEKALI, sinkron, tepat
// saat pengguna mengklik link (di dalam onClick handler), bukan re-render tiap kali status
// berubah — variabel modul biasa lebih pas & lebih sederhana daripada Context utk kebutuhan ini.
let guardMessage: string | null = null;

export function setNavGuardMessage(message: string | null) {
  guardMessage = message;
}

export function getNavGuardMessage(): string | null {
  return guardMessage;
}

// Dipanggil dari onClick link navigasi (Sidebar, dropdown menu Navbar, dst). Mengembalikan
// `true` kalau navigasi BOLEH lanjut (tidak ada guard aktif, atau pengguna mengonfirmasi tetap
// mau keluar), `false` kalau harus dibatalkan (pengguna klik "Cancel" di dialog konfirmasi).
export function confirmNavAway(): boolean {
  if (!guardMessage) return true;
  return window.confirm(guardMessage);
}
