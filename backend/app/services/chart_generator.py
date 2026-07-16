from typing import Any, Dict, List, Optional
import plotly.express as px
import plotly.utils
import json
import pandas as pd


def _find_col(df: pd.DataFrame, keywords: List[str]) -> Optional[str]:
    """
    Mencari nama kolom dalam DataFrame secara fuzzy/case-insensitive
    berdasarkan daftar kata kunci. Mengembalikan nama kolom pertama yang cocok.
    """
    cols_lower = {c.lower(): c for c in df.columns}
    for kw in keywords:
        kw_l = kw.lower()
        # exact match
        if kw_l in cols_lower:
            return cols_lower[kw_l]
        # partial match
        for col_l, col in cols_lower.items():
            if kw_l in col_l:
                return col
    return None


def _find_numeric_col(df: pd.DataFrame, exclude: List[str] = None) -> Optional[str]:
    """Mencari kolom numerik pertama yang bukan kolom yang dikecualikan."""
    exclude = [c.lower() for c in (exclude or [])]
    for col in df.columns:
        if col.lower() not in exclude and pd.api.types.is_numeric_dtype(df[col]):
            return col
    return None


class ChartGenerator:
    @classmethod
    def generate_chart_config(cls, data_type: str, parsed_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Menerima data terstruktur hasil parsing log dan tipe laporan keamanan siber,
        lalu menghasilkan konfigurasi grafik Plotly dalam format JSON.
        Menggunakan deteksi kolom fuzzy agar kompatibel dengan berbagai format log nyata.
        """
        if not parsed_data:
            return {}

        df = pd.DataFrame(parsed_data)

        try:
            fig = None

            if data_type == "firewall":
                # Cari kolom tanggal dan kolom traffic/blocked
                date_col = _find_col(df, ["tanggal", "date", "datetime", "timestamp", "time", "day"])
                traffic_col = _find_col(df, ["blocked_traffic", "blocked", "traffic", "count", "packets", "jumlah"])
                if date_col and traffic_col:
                    fig = px.bar(df, x=date_col, y=traffic_col,
                                 title="Trafik Firewall yang Diblokir per Hari",
                                 labels={date_col: "Tanggal", traffic_col: "Jumlah Trafik Diblokir"})

            elif data_type == "email_security":
                date_col = _find_col(df, ["bulan", "month", "date", "tanggal", "time"])
                phishing_col = _find_col(df, ["phishing", "phish"])
                spam_col = _find_col(df, ["spam"])
                y_cols = [c for c in [phishing_col, spam_col] if c]
                if date_col and y_cols:
                    fig = px.line(df, x=date_col, y=y_cols,
                                  title="Deteksi Ancaman Email Security per Bulan")
                elif date_col:
                    num_col = _find_numeric_col(df, exclude=[date_col])
                    if num_col:
                        fig = px.line(df, x=date_col, y=num_col, title="Ancaman Email per Periode")

            elif data_type == "ids_ips":
                cat_col = _find_col(df, ["kategori_alert", "kategori", "category", "alert_type", "type", "event_type"])
                sev_col = _find_col(df, ["severity", "level", "priority", "tingkat"])
                count_col = _find_col(df, ["jumlah", "count", "total", "hits"])
                if cat_col and count_col:
                    color = sev_col if sev_col else None
                    fig = px.bar(df, x=cat_col, y=count_col, color=color,
                                 title="Alert IDS/IPS per Kategori & Severity")
                elif cat_col:
                    num_col = _find_numeric_col(df, exclude=[cat_col])
                    if num_col:
                        fig = px.bar(df, x=cat_col, y=num_col, title="Alert IDS/IPS per Kategori")

            elif data_type == "soc_incident":
                type_col = _find_col(df, ["jenis_insiden", "jenis", "incident_type", "type", "category", "event"])
                count_col = _find_col(df, ["jumlah", "count", "total", "hits"])
                if type_col and count_col:
                    fig = px.pie(df, values=count_col, names=type_col, hole=0.4,
                                 title="Distribusi Jenis Insiden SOC")
                elif type_col:
                    fig = px.pie(df, names=type_col, hole=0.4, title="Distribusi Insiden SOC")

            elif data_type == "vapt":
                sev_col = _find_col(df, ["severity", "level", "tingkat", "priority"])
                finding_col = _find_col(df, ["jumlah_temuan", "temuan", "findings", "count", "total"])
                if sev_col and finding_col:
                    fig = px.bar(df, x=finding_col, y=sev_col, orientation="h",
                                 title="Temuan Vulnerability Assessment (VAPT) per Severity")
                elif sev_col:
                    num_col = _find_numeric_col(df, exclude=[sev_col])
                    if num_col:
                        fig = px.bar(df, x=num_col, y=sev_col, orientation="h", title="Temuan VAPT")

            elif data_type == "network_monitoring":
                date_col = _find_col(df, ["tanggal", "date", "datetime", "time", "timestamp"])
                uptime_col = _find_col(df, ["uptime_percentage", "uptime", "availability", "persen"])
                if date_col and uptime_col:
                    fig = px.area(df, x=date_col, y=uptime_col,
                                  title="Uptime Jaringan & Anomali")
                elif date_col:
                    num_col = _find_numeric_col(df, exclude=[date_col])
                    if num_col:
                        fig = px.area(df, x=date_col, y=num_col, title="Monitoring Jaringan")

            elif data_type == "bandwidth":
                date_col = _find_col(df, ["bulan", "month", "tanggal", "date", "time"])
                in_col = _find_col(df, ["traffic_in", "inbound", "download", "rx"])
                out_col = _find_col(df, ["traffic_out", "outbound", "upload", "tx"])
                y_cols = [c for c in [in_col, out_col] if c]
                if date_col and y_cols:
                    fig = px.line(df, x=date_col, y=y_cols,
                                  title="Monitoring Bandwidth Bulanan (Traffic In/Out)")
                elif date_col:
                    num_col = _find_numeric_col(df, exclude=[date_col])
                    if num_col:
                        fig = px.line(df, x=date_col, y=num_col, title="Monitoring Bandwidth")

            # Fallback universal — gunakan 2 kolom yang paling sesuai
            if fig is None:
                cols = list(df.columns)
                date_col = _find_col(df, ["tanggal", "date", "datetime", "time", "timestamp", "bulan", "month"])
                num_col = _find_numeric_col(df, exclude=[date_col] if date_col else [])

                if date_col and num_col:
                    fig = px.bar(df, x=date_col, y=num_col,
                                 title=f"Visualisasi Data {data_type.upper()}")
                elif len(cols) >= 2:
                    x_col = cols[0]
                    y_col = next((c for c in cols[1:] if pd.api.types.is_numeric_dtype(df[c])), cols[1])
                    fig = px.bar(df, x=x_col, y=y_col,
                                 title=f"Visualisasi Data {data_type.upper()}")
                else:
                    fig = px.bar(title="Data terlalu sedikit untuk divisualisasikan")

            # Konversi ke JSON Plotly
            chart_json = json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig))
            return chart_json

        except Exception as e:
            return {"error": f"Gagal membuat visualisasi grafik: {str(e)}"}

