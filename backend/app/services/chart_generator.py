from typing import Any, Dict, List, Optional
import plotly.express as px
import plotly.utils
import json
import pandas as pd
import concurrent.futures


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


def _coerce_datetime_series(series: pd.Series) -> Optional[pd.Series]:
    converted = pd.to_datetime(series, errors="coerce", utc=False)
    return converted if converted.notna().any() else None


def _build_layout(fig: Any, title: str, x_label: str = "", y_label: str = "") -> Any:
    fig.update_layout(
        title={"text": title, "x": 0.02, "xanchor": "left"},
        template="plotly_white",
        autosize=True,
        margin={"l": 40, "r": 20, "t": 60, "b": 40},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0.02},
        font={"family": "Inter, sans-serif", "size": 12},
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

        try:
            fig = None
            date_col = _find_col(df, ["tanggal", "date", "datetime", "timestamp", "time", "day", "bulan", "month"])
            date_series = _coerce_datetime_series(df[date_col]) if date_col in df.columns else None
            if date_series is not None:
                df = df.assign(_chart_date=date_series)
                df = df.sort_values("_chart_date")
                date_col = "_chart_date"

            if data_type == "firewall":
                traffic_col = _find_col(df, ["blocked_traffic", "blocked", "traffic", "count", "packets", "jumlah"])
                if date_col and traffic_col:
                    fig = px.bar(df, x=date_col, y=traffic_col,
                                 title="Trafik Firewall yang Diblokir per Periode",
                                 labels={date_col: "Tanggal", traffic_col: "Jumlah Trafik Diblokir"})

            elif data_type == "email_security":
                phishing_col = _find_col(df, ["phishing", "phish"])
                spam_col = _find_col(df, ["spam"])
                y_cols = [c for c in [phishing_col, spam_col] if c]
                if date_col and y_cols:
                    fig = px.line(df, x=date_col, y=y_cols,
                                  title="Deteksi Ancaman Email Security per Periode")
                elif date_col:
                    num_cols = _find_numeric_cols(df, exclude=[date_col])
                    if num_cols:
                        fig = px.line(df, x=date_col, y=num_cols,
                                      title="Ancaman Email per Periode")

            elif data_type == "ids_ips":
                cat_col = _find_col(df, ["kategori_alert", "kategori", "category", "alert_type", "type", "event_type"])
                sev_col = _find_col(df, ["severity", "level", "priority", "tingkat"])
                count_col = _find_col(df, ["jumlah", "count", "total", "hits"])
                if cat_col and count_col:
                    fig = px.bar(df, x=cat_col, y=count_col, color=sev_col if sev_col else None,
                                 title="Alert IDS/IPS per Kategori")
                elif cat_col:
                    num_cols = _find_numeric_cols(df, exclude=[cat_col])
                    if num_cols:
                        fig = px.bar(df, x=cat_col, y=num_cols,
                                     title="Alert IDS/IPS per Kategori")

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
                                 title="Temuan VAPT per Severity")
                elif sev_col:
                    num_cols = _find_numeric_cols(df, exclude=[sev_col])
                    if num_cols:
                        fig = px.bar(df, x=num_cols[0], y=sev_col, orientation="h",
                                     title="Temuan VAPT")

            elif data_type == "network_monitoring":
                uptime_col = _find_col(df, ["uptime_percentage", "uptime", "availability", "persen"])
                if date_col and uptime_col:
                    fig = px.area(df, x=date_col, y=uptime_col,
                                  title="Uptime Jaringan & Ketersediaan")
                elif date_col:
                    num_cols = _find_numeric_cols(df, exclude=[date_col])
                    if num_cols:
                        fig = px.area(df, x=date_col, y=num_cols,
                                      title="Monitoring Jaringan")

            elif data_type == "bandwidth":
                in_col = _find_col(df, ["traffic_in", "inbound", "download", "rx"])
                out_col = _find_col(df, ["traffic_out", "outbound", "upload", "tx"])
                y_cols = [c for c in [in_col, out_col] if c]
                if date_col and y_cols:
                    fig = px.line(df, x=date_col, y=y_cols,
                                  title="Bandwidth In/Out per Periode")
                elif date_col:
                    num_cols = _find_numeric_cols(df, exclude=[date_col])
                    if num_cols:
                        fig = px.line(df, x=date_col, y=num_cols,
                                      title="Monitoring Bandwidth")

            if fig is None:
                num_cols = _find_numeric_cols(df, exclude=[date_col] if date_col else [])
                cat_col = _find_categorical_col(df, exclude=[date_col] if date_col else [])
                if date_col and num_cols:
                    fig = px.line(df, x=date_col, y=num_cols,
                                  title=f'Visualisasi Tren {data_type.replace("_", " ").title()}')
                elif cat_col and num_cols:
                    fig = px.bar(df, x=cat_col, y=num_cols, barmode="group",
                                 title=f'Visualisasi {data_type.replace("_", " ").title()} per {cat_col}')
                elif len(num_cols) == 1:
                    fig = px.bar(df, x=df.index.astype(str), y=num_cols[0],
                                 title=f'Visualisasi {data_type.replace("_", " ").title()}')
                else:
                    fig = px.bar(title="Data terlalu sedikit untuk divisualisasikan")

            default_title = f'Visualisasi {data_type.replace("_", " ").title()}'
            fig = _build_layout(
                fig,
                title=fig.layout.title.text if fig.layout.title.text else default_title,
            )
            chart_json = json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig))
            return chart_json

        except Exception as e:
            return {"error": f"Gagal membuat visualisasi grafik: {str(e)}"}

    @classmethod
    def render_png(cls, chart_data: Dict[str, Any], width: int, height: int, scale: float = 1.0, timeout_seconds: int = 12) -> bytes:
        """
        Render config chart Plotly (dict {"data": ..., "layout": ...}) jadi PNG bytes,
        dipakai saat embed grafik ke PDF/PPTX (bukan tampilan web interaktif, yang render
        di browser via plotly.js dan tidak melewati fungsi ini sama sekali).

        Dibatasi timeout KERAS via thread terpisah. Kaleido memanggil subprocess Chromium
        headless eksternal — kalau subprocess itu gagal start (pernah ditemukan di environment
        Windows tertentu, error "Cannot create Pref Service with no user data dir") dia bisa
        NGE-HANG TANPA PERNAH melempar exception maupun return. try/except biasa di pemanggil
        tidak cukup untuk kasus ini karena tidak ada apapun yang di-raise — request HTTP bisa
        macet tanpa batas waktu. Timeout di sini memastikan pemanggil (export_pdf/export_ppt)
        selalu dapat balasan (baik PNG asli atau TimeoutError) dalam waktu terbatas, supaya
        fallback "Chart tidak dapat dirender" yang sudah ada bisa benar-benar terpakai.
        """
        import plotly.io as pio
        import plotly.graph_objects as go

        def _do_render():
            fig = go.Figure(chart_data)
            return pio.to_image(fig, format="png", width=width, height=height, scale=scale)

        # SENGAJA tidak pakai executor sebagai context manager ("with ... as executor").
        # ThreadPoolExecutor.__exit__ memanggil shutdown(wait=True) yang menunggu thread
        # selesai — kalau thread itu sendiri yang macet (kasus kaleido hang), itu memindahkan
        # hang-nya ke sini alih-alih benar-benar membatasinya. shutdown(wait=False) melepas
        # thread yang macet di background tanpa menahan pemanggil.
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(_do_render)
        try:
            return future.result(timeout=timeout_seconds)
        finally:
            executor.shutdown(wait=False)

