"""Kamus dua kolom ID<->EN untuk label DESKRIPTIF GENERIK pada nilai kategori.

ATURAN YANG MENENTUKAN SEGALANYA: penggantian hanya terjadi kalau SELURUH label cocok
persis dengan satu entri (tidak peka huruf besar/kecil). Tidak ada substitusi sebagian
kata, tidak ada pencocokan awalan/akhiran, tidak ada regex di dalam label. "Gudang" jadi
"Warehouse", tapi "Gudang Bahan Baku" TETAP "Gudang Bahan Baku" dan "Gedung Ahmad Dahlan"
tidak tersentuh sama sekali - nama diri milik data, bukan istilah yang boleh diterjemahkan.

Isinya sengaja dibatasi pada istilah yang DESKRIPTIF dan GENERIK: jenis fasilitas, jenis
unit organisasi, status, tingkat keparahan, arah lalu lintas, dan satuan waktu. Semuanya
istilah yang maknanya sama di kedua bahasa dan tidak menunjuk entitas tertentu.
"""

# (Indonesia, English). Satu baris satu pasang - dibaca dua arah.
KAMUS: tuple = (
    # --- jenis fasilitas / lokasi ---
    ("Kantor Pusat", "Head Office"),
    ("Kantor Cabang", "Branch Office"),
    ("Kantor Perwakilan", "Representative Office"),
    ("Gudang", "Warehouse"),
    ("Pabrik", "Plant"),
    ("Laboratorium", "Laboratory"),
    ("Bengkel", "Workshop"),
    ("Pelabuhan", "Port"),
    ("Dermaga", "Jetty"),
    ("Pos Jaga", "Guard Post"),
    ("Ruang Server", "Server Room"),
    ("Pusat Data", "Data Center"),
    # --- unit organisasi ---
    ("Unit Kerja", "Work Unit"),
    ("Departemen", "Department"),
    ("Divisi", "Division"),
    ("Direktorat", "Directorate"),
    ("Produksi", "Production"),
    ("Pemeliharaan", "Maintenance"),
    ("Logistik", "Logistics"),
    ("Pengadaan", "Procurement"),
    ("Keuangan", "Finance"),
    ("Pemasaran", "Marketing"),
    ("Penjualan", "Sales"),
    ("Distribusi", "Distribution"),
    ("Keamanan", "Security"),
    ("Teknologi Informasi", "Information Technology"),
    ("Sumber Daya Manusia", "Human Resources"),
    # --- status ---
    ("Selesai", "Completed"),
    ("Sedang Diproses", "In Progress"),
    ("Tertunda", "Pending"),
    ("Dibatalkan", "Cancelled"),
    ("Ditolak", "Rejected"),
    ("Disetujui", "Approved"),
    ("Terbuka", "Open"),
    ("Ditutup", "Closed"),
    ("Baru", "New"),
    ("Aktif", "Active"),
    ("Tidak Aktif", "Inactive"),
    ("Berhasil", "Success"),
    ("Gagal", "Failed"),
    ("Dalam Peninjauan", "Under Review"),
    # --- tingkat keparahan / prioritas ---
    ("Kritis", "Critical"),
    ("Tinggi", "High"),
    ("Sedang", "Medium"),
    ("Rendah", "Low"),
    ("Informasi", "Informational"),
    ("Darurat", "Emergency"),
    # --- arah & keputusan lalu lintas ---
    ("Masuk", "Inbound"),
    ("Keluar", "Outbound"),
    ("Diizinkan", "Allowed"),
    ("Diblokir", "Blocked"),
    ("Dikarantina", "Quarantined"),
    # --- satuan waktu & pengelompokan umum ---
    ("Harian", "Daily"),
    ("Mingguan", "Weekly"),
    ("Bulanan", "Monthly"),
    ("Tahunan", "Annual"),
    ("Hari Kerja", "Weekday"),
    ("Akhir Pekan", "Weekend"),
    ("Pagi", "Morning"),
    ("Siang", "Afternoon"),
    ("Sore", "Evening"),
    ("Malam", "Night"),
    ("Lainnya", "Others"),
    ("Tidak Diketahui", "Unknown"),
)


def _peta(ke_inggris: bool) -> dict:
    """Peta pencarian berkunci huruf kecil. Entri pertama menang kalau ada tabrakan,
    jadi hasilnya deterministik dan tidak bergantung urutan iterasi dict."""
    peta = {}
    for idn, eng in KAMUS:
        sumber, tujuan = (idn, eng) if ke_inggris else (eng, idn)
        peta.setdefault(sumber.strip().lower(), tujuan)
    return peta


_KE_EN = _peta(True)
_KE_ID = _peta(False)


def terjemahkan_label(nilai, is_en: bool):
    """Terjemahkan SATU label kalau SELURUH isinya cocok persis satu entri kamus.

    Yang tidak cocok dikembalikan apa adanya, termasuk tipenya - pemanggil boleh
    mengoper apa pun tanpa takut nilainya berubah bentuk."""
    if not isinstance(nilai, str):
        return nilai
    kunci = nilai.strip().lower()
    if not kunci:
        return nilai
    return (_KE_EN if is_en else _KE_ID).get(kunci, nilai)


def terjemahkan_label_list(labels, is_en: bool) -> list:
    return [terjemahkan_label(x, is_en) for x in (labels or [])]


def entri_terpakai(nilai_kategori, is_en: bool) -> list:
    """Entri kamus yang BENAR-BENAR cocok dengan nilai kategori di data ini.

    Dipakai untuk memeriksa bahwa kamus memang dibangun dari kolom kategori yang ada di
    data - bukan daftar tebakan yang tidak pernah kena."""
    peta = _KE_EN if is_en else _KE_ID
    kena = []
    for v in (nilai_kategori or []):
        if isinstance(v, str) and v.strip().lower() in peta:
            kena.append((v, peta[v.strip().lower()]))
    return kena


def terjemahkan_parsed_data(rows: list, is_en: bool) -> list:
    """Terjemahkan NILAI kategori di seluruh baris data, sekali, di hulu.

    Dilakukan di hulu (bukan di tiap titik gambar) supaya chart, kartu KPI, tabel, dan
    catatan menyebut kategori yang sama dengan kata yang sama - kalau diterjemahkan di
    sebagian tempat saja, satu kategori akan muncul dengan dua nama di halaman yang sama.

    Yang disentuh hanya sel bertipe string yang SELURUH isinya cocok persis satu entri
    kamus. Angka, tanggal, dan teks bebas tidak tersentuh.

    Penerjemahan sebuah kolom DIBATALKAN seluruhnya kalau ia mengurangi jumlah nilai unik
    kolom itu - artinya dua kategori berbeda akan menyatu (mis. kolom yang memuat "Medium"
    DAN "Sedang" sekaligus). Dua kategori yang menyatu jadi satu batang jauh lebih merusak
    daripada satu kolom yang tidak ikut diterjemahkan."""
    if not rows:
        return rows
    peta = _KE_EN if is_en else _KE_ID
    kolom = []
    for r in rows:
        if isinstance(r, dict):
            for k in r:
                if k not in kolom:
                    kolom.append(k)

    boleh = []
    for k in kolom:
        asli, baru, kena = set(), set(), False
        for r in rows:
            v = r.get(k) if isinstance(r, dict) else None
            if not isinstance(v, str):
                continue
            asli.add(v)
            t = peta.get(v.strip().lower(), v)
            baru.add(t)
            kena = kena or (t != v)
        if kena and len(baru) == len(asli):
            boleh.append(k)
    if not boleh:
        return rows

    hasil = []
    for r in rows:
        if not isinstance(r, dict):
            hasil.append(r)
            continue
        salin = dict(r)
        for k in boleh:
            v = salin.get(k)
            if isinstance(v, str):
                salin[k] = peta.get(v.strip().lower(), v)
        hasil.append(salin)
    return hasil
