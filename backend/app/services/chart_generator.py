from typing import Any, Dict, List, Optional
import plotly.express as px
import plotly.utils
import json
import os
import tempfile
import pandas as pd
import concurrent.futures
from app.services.period_detector import find_date_column

# CATATAN PENTING SOAL VERSI KALEIDO (dikonfirmasi lewat debugging langsung, termasuk baca
# chrome_debug.log):
#
# Kaleido 0.2.1 (versi lama) membawa Chromium bawaan sendiri yang di banyak mesin Windows
# gagal start dengan error "Cannot create Pref Service with no user data dir" — dan gagalnya
# BUKAN sekadar butuh --user-data-dir tambahan: sudah dicoba paksa argumen itu ke folder temp
# yang valid & writable, errornya tetap sama persis. Chromium child process-nya crash dalam
# hitungan milidetik, tapi sisi Python kaleido 0.2.1 tetap menunggu tanpa batas waktu (blocking
# readline() di pipe yang tidak akan pernah menerima apa pun lagi) — jadi dari luar kelihatan
# seperti hang. Ini bug arsitektur lama kaleido 0.2.1 di Windows, sudah banyak dilaporkan
# komunitas plotly/kaleido, tidak bisa diperbaiki hanya dari argumen command line.
#
# Solusi yang terbukti berhasil: upgrade ke kaleido>=1.0.0 (rewrite total oleh tim Plotly,
# pakai library `choreographer` untuk mengendalikan Chrome ASLI yang terinstall di sistem,
# bukan Chromium custom bawaan). Kalau Chrome belum terdeteksi, kaleido>=1.0 gagal CEPAT
# (<1 detik) dengan pesan jelas ("Kaleido requires Google Chrome to be installed... jalankan
# `plotly_get_chrome`"), bukan hang tanpa akhir. requirements.txt sudah diupdate ke
# plotly>=6.1.1 + kaleido>=1.0.0 untuk ini.
#
# Kode di bawah tetap mendukung kaleido 0.2.1 sebagai fallback best-effort (kalau environment
# belum ter-upgrade), tapi tidak mengandalkan fix --user-data-dir lagi karena terbukti tidak
# selalu cukup — perbaikan sesungguhnya ada di versi kaleido yang dipakai.
_KALEIDO_USER_DATA_DIR = os.path.join(tempfile.gettempdir(), "petro_soc_kaleido_profile")
_kaleido_configured = False


def _get_kaleido_major_version() -> int:
    try:
        import kaleido
        ver = getattr(kaleido, "__version__", None)
        if ver is None:
            # kaleido>=1.0 tidak selalu punya __version__ di modul utamanya; cek lewat metadata.
            from importlib.metadata import version as _pkg_version
            ver = _pkg_version("kaleido")
        return int(str(ver).split(".")[0])
    except Exception:
        return 0


def _ensure_kaleido_configured() -> None:
    global _kaleido_configured
    if _kaleido_configured:
        return
    if _get_kaleido_major_version() >= 1:
        # kaleido>=1.0 tidak pakai scope.chromium_args (API lama) sama sekali — dia
        # mengurus Chrome & profil sementaranya sendiri lewat choreographer. Tidak ada
        # yang perlu dikonfigurasi manual di sini.
        _kaleido_configured = True
        return
    try:
        os.makedirs(_KALEIDO_USER_DATA_DIR, exist_ok=True)
        import plotly.io as pio
        scope = pio.kaleido.scope
        existing = tuple(a for a in scope.chromium_args if not a.startswith("--user-data-dir"))
        extra = [f"--user-data-dir={_KALEIDO_USER_DATA_DIR}"]
        if "--no-sandbox" not in existing:
            extra.append("--no-sandbox")
        scope.chromium_args = existing + tuple(extra)
    except Exception as cfg_err:
        # Kalau gagal konfigurasi (mis. versi kaleido beda API), jangan hentikan render —
        # biarkan lanjut dengan default bawaan kaleido, cuma catat ke log server.
        print(f"[KALEIDO WARNING] Gagal mengatur user-data-dir kustom: {cfg_err}")
    _kaleido_configured = True


def _find_col(df: pd.DataFrame, keywords: List[str]) -> Optional[str]:
    cols_lower = {c.lower(): c for c in df.columns}
    for kw in keywords:
        kw_l = kw.lower()
        if kw_l in cols_lower:
            return cols_lower[kw_l]
        for col_l, col in cols_lower.items():
            if kw_l in col_l:
                return col
    return None


def _find_numeric_cols(df: pd.DataFrame, exclude: List[str] = None) -> List[str]:
    exclude = [c.lower() for c in (exclude or [])]
    return [col for col in df.columns if col.lower() not in exclude and pd.api.types.is_numeric_dtype(df[col])]


def _find_categorical_col(df: pd.DataFrame, exclude: List[str] = None) -> Optional[str]:
    exclude = [c.lower() for c in (exclude or [])]
    for col in df.columns:
        if col.lower() in exclude:
            continue
        if pd.api.types.is_string_dtype(df[col]) or pd.api.types.is_object_dtype(df[col]):
            return col
    return None


def _rank_categorical_candidates(
    df: pd.DataFrame, exclude: List[str] = None, max_unique: int = 30, max_unique_ratio: float = 0.7
) -> List[str]:
    """
    Fallback BERBASIS ISI (bukan nama kolom) untuk deteksi kolom kategorikal (severity/status/
    lokasi/apapun) — dipakai kalau nama kolomnya tidak match daftar kata kunci di _find_col.

    Nama kolom di file nyata sangat bervariasi antar sumber data ("Status" vs "Severity" vs
    "Tingkat_Bahaya" vs "Kondisi", dst) — mengandalkan daftar kata kunci yang di-hardcode
    berarti terus main tebak-tebakan tiap ada nama kolom baru. Sebagai gantinya, cari kolom
    TEKS yang nilainya BERULANG di banyak baris (kardinalitas rendah relatif terhadap jumlah
    baris) — itu ciri khas kolom kategorikal apapun namanya, sementara kolom teks bebas
    (deskripsi, nama unik per baris, dst) akan hampir semua nilainya unik sehingga tidak lolos.

    Dikembalikan terurut dari kardinalitas PALING RENDAH (paling "kategorikal") ke paling
    tinggi, supaya pemanggil bisa ambil kandidat berikutnya kalau kandidat pertama sudah
    dipakai kolom lain (mis. severity & top-kategori tidak boleh pakai kolom yang sama).
    """
    exclude_lower = [c.lower() for c in (exclude or []) if c]
    candidates = []
    for col in df.columns:
        if col.lower() in exclude_lower:
            continue
        if not (pd.api.types.is_string_dtype(df[col]) or pd.api.types.is_object_dtype(df[col])):
            continue
        series = df[col].dropna()
        n_total = len(series)
        if n_total == 0:
            continue
        n_unique = series.nunique()
        if n_unique < 2 or n_unique > max_unique:
            continue
        if n_unique / n_total > max_unique_ratio:
            continue
        candidates.append((col, n_unique))

    candidates.sort(key=lambda c: c[1])
    return [c[0] for c in candidates]


def _build_layout(fig: Any, title: str, x_label: str = "", y_label: str = "") -> Any:
    fig.update_layout(
        title={"text": title, "x": 0.02, "xanchor": "left", "font": {"size": 13, "color": "#1e293b"}},
        template="plotly_white",
        autosize=True,
        margin={"l": 50, "r": 30, "t": 50, "b": 60},
        legend={"orientation": "h", "yanchor": "top", "y": -0.18, "xanchor": "center", "x": 0.5},
        font={"family": "Inter, sans-serif", "size": 11},
    )
    if x_label:
        fig.update_xaxes(title_text=x_label)
    if y_label:
        fig.update_yaxes(title_text=y_label)
    return fig


class ChartGenerator:
    @classmethod
    def generate_chart_config(cls, data_type: str, parsed_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not parsed_data:
            return {}

        df = pd.DataFrame(parsed_data)
        if df.empty:
            return {}

        charts = []
        try:
            # 1. Deteksi Kolom Tanggal/Waktu — pakai find_date_column dari period_detector.py
            # (bukan pencocokan nama kolom sendiri di sini) supaya chart tren dan auto-deteksi
            # periode laporan sama-sama dapat fallback berbasis ISI data yang sama, bukan dua
            # implementasi terpisah dengan kualitas beda (chart sebelumnya cuma cocokkan nama
            # kolom tanpa fallback, jadi gagal total kalau nama kolom tanggalnya tidak lazim).
            detected_date_col, parsed_date_series = find_date_column(parsed_data)
            if detected_date_col and parsed_date_series is not None:
                df = df.assign(_chart_date=parsed_date_series.values)
                df = df.sort_values("_chart_date")
                date_col = "_chart_date"
            else:
                date_col = None

            # --- GRAFIK 1: Tren Event per Periode (Time Series) ---
            if date_col:
                try:
                    daily_dates = pd.to_datetime(df[date_col]).dt.strftime("%Y-%m-%d")
                    df_trend = df.groupby(daily_dates).size().reset_index(name="jumlah_event")
                    df_trend.columns = ["Tanggal", "Jumlah Event"]
                    fig_trend = px.area(
                        df_trend, x="Tanggal", y="Jumlah Event",
                        title=f"Tren Volume Aktivitas Log {data_type.replace('_', ' ').title()} (Jumlah Insiden / Hari)",
                        labels={"Tanggal": "Tanggal", "Jumlah Event": "Jumlah Log / Alert"}
                    )
                except Exception:
                    df_trend = df.groupby(date_col).size().reset_index(name="jumlah_event")
                    fig_trend = px.line(
                        df_trend, x=date_col, y="jumlah_event",
                        title=f"Tren Aktivitas Log {data_type.replace('_', ' ').title()} per Periode",
                        labels={date_col: "Waktu / Periode", "jumlah_event": "Jumlah Event"}
                    )
                fig_trend = _build_layout(fig_trend, fig_trend.layout.title.text)
                cfg = json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig_trend))
                cfg["kind"] = "trend"
                cfg["source_column"] = date_col
                charts.append(cfg)

            # --- GRAFIK 2: Distribusi Severity / Level Ancaman ---
            # Tahap 1: cocokkan nama kolom ke kata kunci umum dulu (cepat & presisi kalau
            # namanya memang lazim seperti "severity"/"status").
            sev_col = _find_col(df, ["severity", "level", "priority", "tingkat", "threat_level", "risk", "status"])
            # Tahap 2: kalau nama kolom sama sekali tidak dikenali, fallback ke deteksi berbasis
            # ISI data (_rank_categorical_candidates) — supaya tetap kedeteksi walau nama kolomnya
            # apapun (mis. "Kondisi", "Tingkat_Bahaya", dst), bukan cuma daftar nama yang di-hardcode
            # yang tidak mungkin mencakup semua variasi penamaan file dari berbagai sumber.
            if not sev_col:
                sev_candidates = _rank_categorical_candidates(df, exclude=[date_col] if date_col else [], max_unique=8)
                if sev_candidates:
                    sev_col = sev_candidates[0]

            if sev_col and sev_col in df.columns:
                sev_counts = df[sev_col].value_counts().reset_index()
                sev_counts.columns = [sev_col, "count"]
                fig_sev = px.pie(
                    sev_counts, names=sev_col, values="count", hole=0.4,
                    title="Distribusi Level Severity Ancaman",
                    color_discrete_sequence=["#ef4444", "#f59e0b", "#eab308", "#10b981", "#3b82f6"]
                )
                fig_sev = _build_layout(fig_sev, "Distribusi Level Severity Ancaman")
                cfg = json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig_sev))
                cfg["kind"] = "severity"
                cfg["source_column"] = sev_col
                charts.append(cfg)

            # --- GRAFIK 3: Top 10 Kategori / Event Types / Actions / Ports / Lokasi ---
            cat_col = _find_col(df, ["kategori_alert", "kategori", "category", "alert_type", "type", "event_type", "action", "destination_port", "source_ip", "protocol", "lokasi", "location"])
            if not cat_col:
                # Kardinalitas maksimum lebih longgar daripada severity (40 vs 8) karena ini
                # chart "top 10" — total kategori boleh banyak, yang ditampilkan cuma teratas.
                exclude_cols = [c for c in [date_col, sev_col] if c]
                cat_candidates = [c for c in _rank_categorical_candidates(df, exclude=exclude_cols, max_unique=40) if c != sev_col]
                if cat_candidates:
                    cat_col = cat_candidates[0]

            if cat_col and cat_col in df.columns and cat_col != sev_col:
                top_cats = df[cat_col].value_counts().head(10).reset_index()
                top_cats.columns = [cat_col, "count"]
                fig_cat = px.bar(
                    top_cats, x="count", y=cat_col, orientation="h",
                    title=f"Top 10 Kategori Alert & Aktivitas ({data_type.replace('_', ' ').title()})",
                    labels={cat_col: "", "count": "Jumlah Incident"}
                )
                fig_cat = _build_layout(fig_cat, fig_cat.layout.title.text)
                fig_cat.update_layout(
                    margin={"l": 180, "r": 30, "t": 50, "b": 50},
                    yaxis={"categoryorder": "total ascending", "title_text": "", "automargin": True}
                )
                cfg = json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig_cat))
                cfg["kind"] = "top_categories"
                cfg["source_column"] = cat_col
                charts.append(cfg)

            # Fallback jika tidak ada chart khusus yang terbentuk
            if not charts:
                num_cols = _find_numeric_cols(df, exclude=[date_col] if date_col else [])
                cat_col = _find_categorical_col(df, exclude=[date_col] if date_col else [])
                if date_col and num_cols:
                    fig_fb = px.line(df, x=date_col, y=num_cols[0], title=f'Visualisasi Tren {data_type.replace("_", " ").title()}')
                elif cat_col and num_cols:
                    fig_fb = px.bar(df, x=cat_col, y=num_cols[0], title=f'Visualisasi {data_type.replace("_", " ").title()} per {cat_col}')
                elif len(num_cols) >= 1:
                    fig_fb = px.bar(df, x=df.index.astype(str), y=num_cols[0], title=f'Visualisasi {data_type.replace("_", " ").title()}')
                else:
                    fig_fb = px.bar(title="Data Log Keamanan")

                fig_fb = _build_layout(fig_fb, f"Visualisasi Data {data_type.replace('_', ' ').title()}")
                cfg = json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig_fb))
                cfg["kind"] = "trend" if date_col else "top_categories"
                charts.append(cfg)

            first_chart = charts[0] if charts else {}
            return {
                "charts": charts,
                "data": first_chart.get("data", []),
                "layout": first_chart.get("layout", {})
            }

        except Exception as e:
            return {"error": f"Gagal membuat visualisasi grafik: {str(e)}"}

    @staticmethod
    def _decode_plotly_array(value):
        """
        PlotlyJSONEncoder kadang mengompres array numerik (dari numpy, mis. hasil
        value_counts()) jadi {"dtype": "i1", "bdata": "<base64>"} demi efisiensi, BUKAN list
        Python polos — decode balik supaya bisa diproses seperti list biasa.
        """
        if isinstance(value, dict) and "bdata" in value and "dtype" in value:
            import base64
            import numpy as np
            raw = base64.b64decode(value["bdata"])
            return np.frombuffer(raw, dtype=value["dtype"]).tolist()
        return value

    @classmethod
    def extract_top_data_points(cls, chart_dict: Dict[str, Any], top_n: int = 3):
        """
        Ambil (label, value) LANGSUNG dari data Plotly chart itu sendiri (trace pertama) —
        tidak perlu tahu "jenis" chart-nya (trend/severity/top kategori dst), otomatis benar
        untuk pie (labels/values) maupun bar/line/area (x/y, deteksi mana yang berisi angka).
        Dipakai buat panel angka kategori & insight otomatis di export PDF/PPTX.

        Return: (top_pairs, total) — top_pairs list [(label, value), ...] terurut turun
        sepanjang top_n, total = jumlah SEMUA titik di trace (dasar persentase yang akurat,
        bukan cuma dari top_n yang ditampilkan).
        """
        try:
            traces = chart_dict.get("data") or []
            if not traces:
                return [], 0
            trace = traces[0]

            if "labels" in trace and "values" in trace:
                labels, values = trace["labels"], trace["values"]
            elif "x" in trace and "y" in trace:
                x, y = trace["x"], trace["y"]

                def _is_numeric_list(vals):
                    return bool(vals) and all(isinstance(v, (int, float)) for v in vals[:5])

                x_dec, y_dec = cls._decode_plotly_array(x), cls._decode_plotly_array(y)
                if _is_numeric_list(x_dec) and not _is_numeric_list(y_dec):
                    values, labels = x_dec, y_dec
                else:
                    labels, values = x_dec, y_dec
            else:
                return [], 0

            values = cls._decode_plotly_array(values)
            labels = cls._decode_plotly_array(labels)
            pairs = [(str(l), v) for l, v in zip(labels, values) if isinstance(v, (int, float))]
            total = sum(v for _, v in pairs)
            pairs.sort(key=lambda p: p[1], reverse=True)
            return pairs[:top_n], total
        except Exception:
            return [], 0

    @classmethod
    def render_png(cls, chart_data: Dict[str, Any], width: int, height: int, scale: float = 1.0, timeout_seconds: int = 45) -> bytes:
        """
        Render config chart Plotly jadi PNG bytes, dipakai saat embed grafik ke PDF/PPTX
        (bukan tampilan web interaktif, yang render di browser via plotly.js dan tidak
        melewati fungsi ini sama sekali).

        Dibatasi timeout KERAS via thread terpisah. Kaleido memanggil Chrome/Chromium
        eksternal — kalau gagal start, ini memastikan pemanggil (export_pdf/export_ppt)
        selalu dapat balasan (baik PNG asli, TimeoutError, atau error lain yang jelas)
        dalam waktu terbatas, bukan macet tanpa batas waktu. 45 detik dipilih karena
        kaleido sendiri punya default internal timeout ~90 detik — 12 detik yang dipakai
        sebelumnya terlalu ketat dan bisa memutus render yang sebenarnya masih jalan normal
        (terutama panggilan pertama di proses backend yang baru start).
        """
        import plotly.io as pio
        import plotly.graph_objects as go

        _ensure_kaleido_configured()

        def _do_render():
            # Jika memuat list "charts", gunakan chart pertama untuk ekspor gambar PDF/PPTX
            c_dict = chart_data.get("charts", [chart_data])[0] if isinstance(chart_data.get("charts"), list) and len(chart_data["charts"]) > 0 else chart_data
            fig = go.Figure(c_dict)
            return pio.to_image(fig, format="png", width=width, height=height, scale=scale)

        # SENGAJA tidak pakai executor sebagai context manager. ThreadPoolExecutor.__exit__
        # memanggil shutdown(wait=True) yang menunggu thread selesai — kalau thread itu
        # sendiri yang macet (kaleido hang), itu memindahkan hang-nya ke sini alih-alih
        # benar-benar membatasinya. shutdown(wait=False) melepas thread yang macet di
        # background tanpa menahan pemanggil.
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(_do_render)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError as timeout_err:
            msg = (
                f"Render chart timeout setelah {timeout_seconds}s — proses Chrome/Kaleido "
                "kemungkinan gagal start di mesin ini (cek log server untuk detail)."
            )
            print(f"[KALEIDO TIMEOUT] {msg}")
            raise TimeoutError(msg) from timeout_err
        except Exception as render_err:
            print(f"[KALEIDO ERROR] Gagal render chart ke PNG: {render_err}")
            raise
        finally:
            executor.shutdown(wait=False)
