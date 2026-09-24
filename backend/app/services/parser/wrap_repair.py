"""Menyambung kembali teks yang terpenggal oleh WRAP SEL TABEL di PDF sumber.

Masalahnya: kalau sebuah sel tabel lebih sempit daripada teks di dalamnya, PDF menggambar
teks itu di beberapa baris, dan pdfplumber mengekstraknya apa adanya dengan "\\n" di tengah.
Penanganan lama meratakan semua whitespace jadi satu spasi (`re.sub(r"\\s+", " ")`), sehingga
kata yang terpenggal di tengah justru dipisah permanen:

    "Ticke\\nt ID"      -> "Ticke t ID"           (seharusnya "Ticket ID")
    "Hardwar\\ne"       -> "Hardwar e"            (seharusnya "Hardware")
    "Duras\\ni (men\\nit)" -> "Duras i (men it)"  (seharusnya "Durasi (menit)")

Nama kolom itu terbawa ke SELURUH sistem - label chart, kartu KPI, judul, dan kalimat
narasi - jadi perbaikannya harus di hulu, bukan ditambal di tiap penampil.

KENAPA KONSERVATIF. Tidak semua "\\n" di dalam sel adalah kata terpenggal: sel yang berisi
kalimat juga di-wrap, dan di situ pemenggalannya jatuh di SPASI, sehingga spasinya memang
harus dipertahankan. Dua bentuk itu tidak bisa dibedakan dengan pasti dari teksnya saja -
lebar sel dalam piksel tidak ikut tersimpan. Versi pertama aturan ini memakai tebakan "satu
kata yang mengisi penuh lebar sel", dan terbukti MERUSAK 9 nilai nyata di laporan 195:

    'CPU/RAM/storage\\nreview'        -> 'CPU/RAM/storagereview'
    'User meminta perubahan\\nhak akses' -> 'User meminta perubahanhak akses'
    'Suspicious\\nexecutable'        -> 'Suspiciousexecutable'

Karena itu yang dirapatkan HANYA dua pola yang bisa dipertanggungjawabkan; selain itu
spasinya dipertahankan. Merapatkan yang salah merusak makna, sedangkan membiarkan yang
salah cuma menyisakan nama yang kurang rapi - jadi kalau ragu, JANGAN dirapatkan.
"""
from __future__ import annotations

from typing import Any, Iterable

# Tanda yang boleh menyambung deret angka/identitas ("INC-2" + "6070", "01/07" + "/2026").
_LANJUT = "/-.,:"

# Panjang maksimum penggalan kanan yang masih dianggap EKOR KATA, bukan kata berdiri sendiri.
# Dibedakan: kalau baris kanan berisi lebih dari satu kata, wrap-nya jatuh di spasi, jadi
# ambangnya diperketat - itulah yang menahan 'perubahan' + 'hak akses' tetap berspasi,
# sementara 'Resol' + 'ved' tetap dirapatkan.
_EKOR_SENDIRI = 3
_EKOR_BERSAMA = 2


def _rapatkan(kiri: str, kanan: str) -> bool:
    """Apakah batas antara dua baris sel ini pemenggalan di TENGAH KATA?"""
    if not kiri or not kanan:
        return False
    k, c = kiri[-1], kanan[0]
    # Deret angka/identitas yang terpenggal: "INC-2|6070", "01/07|/2026", "CR-26|0701".
    if (k.isdigit() or k in _LANJUT) and (c.isdigit() or c in _LANJUT):
        return True
    tok = kanan.split(" ", 1)[0] if " " in kanan else kanan
    tok = tok.rstrip(")].,;:")          # "it)" -> "it", supaya "(men|it)" ikut tersambung
    # Huruf besar = kata baru ("Kantor|Pusat"), bukan lanjutan kata yang terpotong.
    if not (k.islower() and tok.isalpha() and tok.islower()):
        return False
    return len(tok) <= (_EKOR_BERSAMA if " " in kanan else _EKOR_SENDIRI)


def sambung_penggalan(baris: Iterable[str]) -> str:
    """Gabung baris-baris satu sel tabel jadi satu teks utuh."""
    utuh = [b for b in (str(x).strip() for x in baris) if b]
    if len(utuh) <= 1:
        return utuh[0] if utuh else ""
    hasil = utuh[0]
    for i, b in enumerate(utuh[1:], 1):
        hasil = hasil + ("" if _rapatkan(utuh[i - 1], b) else " ") + b
    return hasil


def perbaiki_sel(nilai: Any) -> str:
    """Bersihkan satu sel tabel: sambung penggalan wrap, ratakan sisa whitespace."""
    if nilai is None:
        return ""
    teks = str(nilai)
    if not teks.strip():
        return ""
    # Tiap baris diratakan dulu (spasi ganda/tab di DALAM satu baris tidak bermakna),
    # baru batas antar barisnya diputuskan.
    baris = [" ".join(b.split()) for b in teks.splitlines()]
    return sambung_penggalan(baris)


_MIN_KOSAKATA = 5


def _didukung_kosakata(kiri: str, kanan: str, kosakata: set) -> bool:
    """Apakah ada kata dikenal yang MELINTASI batas sambungan kiri|kanan?

    Bukti hanya bisa muncul kalau penggabungannya benar: sebuah kata yang melintasi batas
    berarti potongan kiri & kanan sama-sama bagian dari kata itu.
    """
    if not kosakata:
        return False
    gabung = (kiri + kanan).lower()
    batas = len(kiri)
    for kata in kosakata:
        i = gabung.find(kata)
        while i != -1:
            if i < batas < i + len(kata):
                return True
            i = gabung.find(kata, i + 1)
    return False


def perbaiki_nama_kolom(nama: Any, kosakata: set | None = None) -> str:
    """Sambung nama kolom yang penggalannya SUDAH terlanjur jadi spasi.

    Dipakai untuk data yang dulu diurai penanganan lama, yang menimpa "\\n" dengan spasi
    sehingga posisi pemenggalannya hilang. Di sini setiap spasi jadi calon batas, jadi
    aturannya lebih mudah salah daripada versi ber-"\\n" - pemanggilnya WAJIB memastikan
    dulu bahwa berkasnya memang korban wrap (lihat perbaiki_parsed_data).
    """
    teks = " ".join(str(nama or "").split())
    if " " not in teks:
        return teks
    bagian = teks.split(" ")
    hasil = bagian[0]
    for i, b in enumerate(bagian[1:], 1):
        rapat = _rapatkan(bagian[i - 1], b)
        if not rapat and kosakata and b[:1].islower():
            rapat = _didukung_kosakata(hasil, b, kosakata)
        hasil = hasil + ("" if rapat else " ") + b
    return hasil


def _ada_jejak_wrap(rows: list) -> bool:
    """Apakah data ini benar-benar korban wrap sel tabel?

    Buktinya diambil dari NILAI, bukan nama kolom: "\\n" di tengah sel tabel tidak punya
    makna lain selain artefak wrap. Gerbang ini yang membuat berkas normal (CSV/Excel, atau
    PDF yang selnya cukup lebar) tidak pernah disentuh perbaikan nama kolom - di sana spasi
    pada nama kolom hampir selalu memang spasi, dan merapatkannya justru merusak.
    """
    for row in rows[:200]:
        if not isinstance(row, dict):
            continue
        for v in row.values():
            if isinstance(v, str) and "\n" in v:
                return True
    return False


def perbaiki_parsed_data(rows: Any) -> Any:
    """Perbaiki penggalan wrap pada data yang SUDAH tersimpan (nama kolom + isi sel).

    Dipakai di titik muat terpusat supaya nama kolom yang benar mengalir ke semua pemakai
    sekaligus - label chart, kartu, judul, dan narasi - bukan ditambal satu per satu.
    Berkas sumbernya sendiri tidak ditulis ulang; perbaikan ini hanya di memori.
    """
    if not isinstance(rows, list) or not rows:
        return rows
    if not _ada_jejak_wrap(rows):
        return rows

    # Kosakata dikumpulkan dari nama kolom yang sudah rapi + isi sel, dipakai sbg bukti
    # pendukung untuk ekor panjang yang ditolak aturan konservatif (lihat _didukung_kosakata).
    kosakata: set = set()
    for row in rows[:200]:
        if not isinstance(row, dict):
            continue
        for k, v in row.items():
            for teks in (k, v if isinstance(v, str) else ""):
                for t in str(teks).replace("/", " ").split():
                    t = t.strip("()[],.;:").lower()
                    if len(t) >= _MIN_KOSAKATA and t.isalpha():
                        kosakata.add(t)

    peta: dict = {}
    for row in rows:
        if isinstance(row, dict):
            for k in row:
                if k not in peta:
                    peta[k] = perbaiki_nama_kolom(k, kosakata)
    # Kalau dua kolom berbeda jadi bernama sama sesudah dirapatkan, nama aslinya
    # dipertahankan untuk keduanya - kehilangan kolom jauh lebih buruk drpd nama kurang rapi.
    dipakai: dict = {}
    for asli, baru in peta.items():
        dipakai.setdefault(baru, []).append(asli)
    for baru, asal in dipakai.items():
        if len(asal) > 1:
            for a in asal:
                peta[a] = a

    hasil = []
    for row in rows:
        if not isinstance(row, dict):
            hasil.append(row)
            continue
        hasil.append({
            peta.get(k, k): (perbaiki_sel(v) if isinstance(v, str) and "\n" in v else v)
            for k, v in row.items()
        })
    return hasil
