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
            # 1. Deteksi Kolom Tanggal/Waktu
            date_col = _find_col(df, ["tanggal", "date", "datetime", "timestamp", "time", "day", "bulan", "month"])
            if date_col and date_col in df.columns:
                date_series = _coerce_datetime_series(df[date_col])
                if date_series is not None:
                    df = df.assign(_chart_date=date_series)
                    df = df.sort_values("_chart_date")
                    date_col = "_chart_date"
                else:
                    date_col = None
            else:
                date_col = None

            # --- GRAFIK 1: Tren Event per Periode (Time Series) ---
            if date_col:
                num_cols = _find_numeric_cols(df, exclude=[date_col])
                if num_cols:
                    main_num = num_cols[0]
                    fig_trend = px.line(
                        df, x=date_col, y=num_cols[:3],
                        title=f"Tren Volume {data_type.replace('_', ' ').title()} per Periode",
                        labels={date_col: "Waktu / Periode"}
                    )
                else:
                    df_trend = df.groupby(date_col).size().reset_index(name="jumlah_event")
                    fig_trend = px.line(
                        df_trend, x=date_col, y="jumlah_event",
                        title=f"Tren Aktivitas Log {data_type.replace('_', ' ').title()} per Periode",
                        labels={date_col: "Waktu / Periode", "jumlah_event": "Jumlah Event"}
                    )
                fig_trend = _build_layout(fig_trend, fig_trend.layout.title.text)
                charts.append(json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig_trend)))

            # --- GRAFIK 2: Distribusi Severity / Level Ancaman ---
            sev_col = _find_col(df, ["severity", "level", "priority", "tingkat", "threat_level", "risk"])
            if sev_col and sev_col in df.columns:
                sev_counts = df[sev_col].value_counts().reset_index()
                sev_counts.columns = [sev_col, "count"]
                fig_sev = px.pie(
                    sev_counts, names=sev_col, values="count", hole=0.4,
                    title="Distribusi Level Severity Ancaman",
                    color_discrete_sequence=["#ef4444", "#f59e0b", "#eab308", "#10b981", "#3b82f6"]
                )
                fig_sev = _build_layout(fig_sev, "Distribusi Level Severity Ancaman")
                charts.append(json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig_sev)))

            # --- GRAFIK 3: Top 10 Kategori / Event Types / Actions / Ports ---
            cat_col = _find_col(df, ["kategori_alert", "kategori", "category", "alert_type", "type", "event_type", "action", "destination_port", "source_ip", "protocol"])
            if cat_col and cat_col in df.columns and cat_col != sev_col:
                top_cats = df[cat_col].value_counts().head(10).reset_index()
                top_cats.columns = [cat_col, "count"]
                fig_cat = px.bar(
                    top_cats, x="count", y=cat_col, orientation="h",
                    title=f"Top 10 Kategori Alert & Aktivitas ({data_type.replace('_', ' ').title()})",
                    labels={cat_col: "Kategori / Event", "count": "Jumlah Incident"}
                )
                fig_cat = _build_layout(fig_cat, fig_cat.layout.title.text)
                charts.append(json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig_cat)))

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
                charts.append(json.loads(plotly.utils.PlotlyJSONEncoder().encode(fig_fb)))

            first_chart = charts[0] if charts else {}
            return {
                "charts": charts,
                "data": first_chart.get("data", []),
                "layout": first_chart.get("layout", {})
            }

        except Exception as e:
            return {"error": f"Gagal membuat visualisasi grafik: {str(e)}"}

    @classmethod
    def render_png(cls, chart_data: Dict[str, Any], width: int, height: int, scale: float = 1.0, timeout_seconds: int = 12) -> bytes:
        import plotly.io as pio
        import plotly.graph_objects as go

        def _do_render():
            # Jika memuat list "charts", gunakan chart pertama untuk ekspor gambar PDF/PPTX
            c_dict = chart_data.get("charts", [chart_data])[0] if isinstance(chart_data.get("charts"), list) and len(chart_data["charts"]) > 0 else chart_data
            fig = go.Figure(c_dict)
            return pio.to_image(fig, format="png", width=width, height=height, scale=scale)

        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(_do_render)
        try:
            return future.result(timeout=timeout_seconds)
        finally:
            executor.shutdown(wait=False)
