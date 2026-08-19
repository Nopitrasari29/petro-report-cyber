import React, { Fragment } from "react";
import {
  REPORT_COLORS,
  CATEGORY_COLOR_RAMP,
  SEVERITY_COLOR,
  TITLE_FONT,
  BODY_FONT,
  DEFAULT_VISUAL_STYLE,
  THEME_PALETTES,
  resolveThemeColors,
  type ReportBlock,
  type VisualStyle,
  type ThemeColors,
} from "@/utils/reportTheme";

const C = REPORT_COLORS;

// Warna kartu tren berarah panah (dynamic_section "Trend Analysis", lihat block.trend_stat) —
// netral (cuma menunjukkan arah naik/turun/datar, TIDAK menilai baik/buruk secara otomatis).
const DIRECTION_COLOR: Record<string, string> = {
  up: REPORT_COLORS.greenChart,
  down: REPORT_COLORS.redCrit,
  flat: REPORT_COLORS.grayText,
};

function Kicker({ text, color }: { text: string; color: string }) {
  return (
    <div
      className="text-[10px] font-black uppercase tracking-[0.18em] mb-2"
      style={{ color, fontFamily: BODY_FONT }}
    >
      {text}
    </div>
  );
}

function BlockTitle({ children, color = C.textDark }: { children: React.ReactNode; color?: string }) {
  return (
    <div
      className="text-lg sm:text-xl font-bold mb-3"
      style={{ fontFamily: TITLE_FONT, color }}
    >
      {children}
    </div>
  );
}

// Ornamen sudut lengkung (lingkaran konsentris tanpa isi) — mirror `_flourish_html`/
// `add_corner_flourish` di export_pdf.py/export_ppt.py, dipakai cover & penutup. SEBELUMNYA
// preview React sama sekali tidak menampilkan ini (dilaporkan user sbg salah satu perbedaan
// preview vs hasil unduhan) — sekarang direplikasi murni CSS (border lingkaran, tanpa isi).
function Flourish({ corner, theme = THEME_PALETTES.green }: { corner: VisualStyle["flourish_corner"]; theme?: ThemeColors }) {
  const posStyle: React.CSSProperties =
    corner === "top_right"
      ? { top: -70, right: -70 }
      : corner === "bottom_left"
        ? { bottom: -70, left: -70 }
        : { bottom: -70, right: -70 };
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden="true">
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className="absolute rounded-full"
          style={{ ...posStyle, width: 140 + i * 55, height: 140 + i * 55, border: `1px solid ${theme.light}` }}
        />
      ))}
    </div>
  );
}

function BarChart({
  categories,
  values,
  colors,
  theme = THEME_PALETTES.green,
}: {
  categories: string[];
  values: number[];
  colors?: string[];
  theme?: ThemeColors;
}) {
  const max = Math.max(...values, 1);
  return (
    <div className="space-y-2.5">
      {categories.map((cat, i) => {
        const pct = Math.max((values[i] / max) * 100, 1.5);
        const color = colors ? colors[i] : theme.main;
        return (
          <div key={cat} className="flex items-center gap-2 text-xs">
            <div className="w-24 shrink-0 truncate font-semibold" style={{ color: C.textDark }}>
              {cat}
            </div>
            <div className="flex-1 rounded" style={{ background: "#EEEEEE" }}>
              <div
                className="h-4 rounded flex items-center"
                style={{ width: `${pct}%`, background: color }}
              />
            </div>
            <div className="w-8 text-right font-bold" style={{ color: C.textDark }}>
              {values[i]}
            </div>
          </div>
        );
      })}
    </div>
  );
}


// Deret waktu -> batang (nilai per periode) + garis kumulatif (SVG polyline di atas batang) —
// mirror _bar_line_chart_svg/add_bar_line_chart di backend. Dipakai KHUSUS chart.type
// "bar_line" (Analisis Tren dgn data deret waktu asli).
function BarLineChart({
  categories,
  values,
  cumulative,
  theme = THEME_PALETTES.green,
}: {
  categories: string[];
  values: number[];
  cumulative?: number[];
  theme?: ThemeColors;
}) {
  const max = Math.max(...values, 1);
  const maxCum = cumulative && cumulative.length ? Math.max(...cumulative, 1) : 0;
  const n = categories.length || 1;
  return (
    <div className="relative" style={{ height: 110 }}>
      <div className="absolute inset-0 flex items-end gap-1.5">
        {categories.map((cat, i) => (
          <div key={cat} className="flex-1 flex flex-col items-center justify-end h-full min-w-0">
            <div
              className="w-full rounded-t"
              style={{ height: `${Math.max((values[i] / max) * 78, 3)}%`, background: theme.main }}
            />
            <span className="text-[8px] mt-1 truncate w-full text-center" style={{ color: C.grayText }}>
              {cat}
            </span>
          </div>
        ))}
      </div>
      {maxCum > 0 && (
        <svg className="absolute inset-0 pointer-events-none" width="100%" height="100%" viewBox="0 0 100 100" preserveAspectRatio="none">
          <polyline
            fill="none"
            stroke={theme.light}
            strokeWidth={1.6}
            vectorEffect="non-scaling-stroke"
            points={cumulative!.map((v, i) => `${((i + 0.5) / n) * 100},${100 - (v / maxCum) * 84}`).join(" ")}
          />
        </svg>
      )}
    </div>
  );
}

// Skor multi-indikator (radar) — mirror _radar_chart_svg/add_native_radar_chart. Nilai (0-100)
// sudah dinormalisasi di report_render_logic.py, jadi di sini tinggal digambar.
function RadarChart({ axes, values, theme = THEME_PALETTES.green }: { axes: string[]; values: number[]; theme?: ThemeColors }) {
  const n = axes.length;
  if (n < 3) return null;
  const size = 220;
  const cx = size / 2;
  const cy = size / 2;
  const rMax = size / 2 - 46;
  const angle = (i: number) => (-90 + (i * 360) / n) * (Math.PI / 180);
  const point = (i: number, frac: number): [number, number] => [cx + rMax * frac * Math.cos(angle(i)), cy + rMax * frac * Math.sin(angle(i))];
  const ringPts = (frac: number) => axes.map((_a, i) => point(i, frac).join(",")).join(" ");
  const shapePts = values.map((v, i) => point(i, Math.max(0, Math.min(100, v)) / 100).join(",")).join(" ");
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="mx-auto block">
      {[0.25, 0.5, 0.75, 1].map((f) => (
        <polygon key={f} points={ringPts(f)} fill="none" stroke={C.panelBorder} strokeWidth={1} />
      ))}
      {axes.map((_a, i) => {
        const [x, y] = point(i, 1);
        return <line key={i} x1={cx} y1={cy} x2={x} y2={y} stroke={C.panelBorder} strokeWidth={1} />;
      })}
      <polygon points={shapePts} fill={theme.main} fillOpacity={0.25} stroke={theme.main} strokeWidth={2} />
      {values.map((v, i) => {
        const [x, y] = point(i, Math.max(0, Math.min(100, v)) / 100);
        return <circle key={i} cx={x} cy={y} r={3} fill={theme.main} />;
      })}
      {axes.map((ax, i) => {
        const [x, y] = point(i, 1.22);
        const cos = Math.cos(angle(i));
        const anchor = cos > 0.3 ? "start" : cos < -0.3 ? "end" : "middle";
        return (
          <text key={i} x={x} y={y} textAnchor={anchor} fontSize={8.5} fill={C.textDark} style={{ fontFamily: BODY_FONT }}>
            {ax}
          </text>
        );
      })}
    </svg>
  );
}

// Pola per hari/jam (heatmap grid) — mirror _heatmap_grid_svg/add_heatmap_grid, warna sel
// makin pekat makin sering kejadian di kombinasi hari/jam itu.
function HeatmapGrid({
  dayLabels,
  hourLabels,
  grid,
  theme = THEME_PALETTES.green,
}: {
  dayLabels: string[];
  hourLabels: string[];
  grid: number[][];
  theme?: ThemeColors;
}) {
  const maxVal = Math.max(...grid.flat(), 1);
  return (
    <div className="inline-grid gap-[3px]" style={{ gridTemplateColumns: `40px repeat(${hourLabels.length}, 1fr)` }}>
      <div />
      {hourLabels.map((hl) => (
        <div key={hl} className="text-[7px] text-center" style={{ color: C.grayText }}>
          {hl}
        </div>
      ))}
      {dayLabels.map((day, r) => (
        <React.Fragment key={day}>
          <div className="text-[8px] text-right pr-1 flex items-center justify-end" style={{ color: C.textDark }}>
            {day}
          </div>
          {grid[r].map((val, c) => {
            const frac = 0.12 + 0.8 * (val / maxVal);
            return (
              <div
                key={`${day}-${c}`}
                className="rounded flex items-center justify-center text-[7px] font-bold"
                style={{ background: theme.main, opacity: val ? frac : 0.08, color: frac > 0.5 ? "#fff" : C.textDark, height: 24 }}
              >
                {val || ""}
              </div>
            );
          })}
        </React.Fragment>
      ))}
    </div>
  );
}

// Perbandingan 2 periode/seri per kategori (grouped bar) — mirror _grouped_bar_chart_svg/
// add_grouped_bar_chart, 2 batang berdampingan per kategori (bukan ditumpuk).
function GroupedBarChart({
  categories,
  seriesA,
  seriesB,
  labelA,
  labelB,
  theme = THEME_PALETTES.green,
}: {
  categories: string[];
  seriesA: number[];
  seriesB: number[];
  labelA?: string;
  labelB?: string;
  theme?: ThemeColors;
}) {
  const max = Math.max(...seriesA, ...seriesB, 1);
  return (
    <div>
      <div className="flex items-end gap-3" style={{ height: 110 }}>
        {categories.map((cat, i) => (
          <div key={cat} className="flex-1 flex flex-col items-center justify-end h-full min-w-0">
            <div className="flex items-end gap-1 w-full justify-center h-full">
              <div className="rounded-t" style={{ width: "40%", height: `${Math.max((seriesA[i] / max) * 90, 3)}%`, background: theme.main }} />
              <div className="rounded-t" style={{ width: "40%", height: `${Math.max((seriesB[i] / max) * 90, 3)}%`, background: theme.light }} />
            </div>
            <span className="text-[8px] mt-1 truncate w-full text-center" style={{ color: C.grayText }}>
              {cat}
            </span>
          </div>
        ))}
      </div>
      <div className="flex gap-4 mt-2 text-[10px]" style={{ color: C.grayText }}>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full" style={{ background: theme.main }} />
          {labelA}
        </span>
        <span className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-full" style={{ background: theme.light }} />
          {labelB}
        </span>
      </div>
    </div>
  );
}

// Alur bertingkat (mis. status Open -> Investigating -> Resolved) — mirror _funnel_chart_svg/
// add_funnel_chart, batang melebar/menyempit sesuai proporsi, ditumpuk dari terbesar ke terkecil.
function FunnelChart({ categories, values, color }: { categories: string[]; values: number[]; color: string }) {
  const max = Math.max(...values, 1);
  const n = categories.length || 1;
  return (
    <div className="space-y-1.5">
      {categories.map((cat, i) => {
        const pct = Math.max(22, (values[i] / max) * 100);
        const shade = 0.45 + 0.55 * (1 - i / Math.max(n - 1, 1));
        return (
          <div
            key={cat}
            className="mx-auto rounded-lg flex items-center justify-center text-white text-xs font-bold py-2.5"
            style={{ width: `${pct}%`, background: color, opacity: shade }}
          >
            {cat} · {values[i]}
          </div>
        );
      })}
    </div>
  );
}

// Varian donut — dibangun murni CSS conic-gradient (bukan library chart), lingkaran dalam
// solid putih di atasnya menciptakan "lubang" donut. Warna per-kategori pakai CATEGORY_COLOR_RAMP
// (ramp yang sama dipakai legend IvoryPanel) supaya tiap potongan tetap bisa dibedakan.
function DonutChart({ categories, values, colors }: { categories: string[]; values: number[]; colors?: string[] }) {
  const total = values.reduce((a, b) => a + b, 0) || 1;
  let cumulative = 0;
  const stops = categories.map((_cat, i) => {
    const color = colors ? colors[i] : CATEGORY_COLOR_RAMP[i % CATEGORY_COLOR_RAMP.length];
    const start = (cumulative / total) * 360;
    cumulative += values[i];
    const end = (cumulative / total) * 360;
    return `${color} ${start}deg ${end}deg`;
  });
  return (
    <div className="flex items-center gap-5">
      <div className="relative w-28 h-28 sm:w-32 sm:h-32 shrink-0">
        <div className="absolute inset-0 rounded-full" style={{ background: `conic-gradient(${stops.join(", ")})` }} />
        <div className="absolute rounded-full" style={{ inset: "22%", background: C.white }} />
      </div>
      <div className="space-y-1.5 flex-1 min-w-0">
        {categories.map((cat, i) => (
          <div key={cat} className="flex items-center gap-2 text-xs">
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{ background: colors ? colors[i] : CATEGORY_COLOR_RAMP[i % CATEGORY_COLOR_RAMP.length] }}
            />
            <span className="flex-1 truncate font-semibold" style={{ color: C.textDark }}>{cat}</span>
            <span className="font-bold" style={{ color: C.textDark }}>{values[i]}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Gauge/ring persentase — dipakai panel pendukung kecil (dynamic_section/key_findings, lihat
// ReportBlockRenderer di bawah), BUKAN dispatcher `Chart` (yang baca visual_style — bentuk gauge
// sengaja tetap per section, bukan ikut gaya acak laporan). Teknik sama persis dgn DonutChart di
// atas (conic-gradient + lubang putih di tengah), cuma 1 segmen terisi sebesar `value/max`
// (bukan N kategori) + angka besar di tengah, bukan legend di samping.
function GaugeRing({
  value,
  max = 100,
  label,
  color,
  theme = THEME_PALETTES.green,
}: {
  value: number;
  max?: number;
  label?: string;
  color?: string;
  theme?: ThemeColors;
}) {
  const pct = Math.max(0, Math.min(1, max ? value / max : 0));
  const ringColor = color || theme.main;
  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-24 h-24 sm:w-28 sm:h-28 shrink-0">
        <div
          className="absolute inset-0 rounded-full"
          style={{ background: `conic-gradient(${ringColor} ${pct * 360}deg, #EEEEEE 0deg)` }}
        />
        <div
          className="absolute rounded-full flex items-center justify-center"
          style={{ inset: "16%", background: C.white }}
        >
          <span className="text-lg font-black" style={{ color: C.textDark }}>
            {Math.round(value)}%
          </span>
        </div>
      </div>
      {label && (
        <div className="text-xs text-center font-semibold" style={{ color: C.grayText }}>
          {label}
        </div>
      )}
    </div>
  );
}

// Varian stacked — satu bar horizontal terbagi proporsional per kategori + legend di bawahnya.
function StackedBar({ categories, values, colors }: { categories: string[]; values: number[]; colors?: string[] }) {
  const total = values.reduce((a, b) => a + b, 0) || 1;
  return (
    <div>
      <div className="w-full h-8 rounded-lg overflow-hidden flex" style={{ background: "#EEEEEE" }}>
        {categories.map((cat, i) => {
          const pct = (values[i] / total) * 100;
          if (pct <= 0) return null;
          const color = colors ? colors[i] : CATEGORY_COLOR_RAMP[i % CATEGORY_COLOR_RAMP.length];
          return <div key={cat} style={{ width: `${pct}%`, background: color }} title={`${cat}: ${values[i]}`} />;
        })}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-3">
        {categories.map((cat, i) => (
          <div key={cat} className="flex items-center gap-1.5 text-xs">
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{ background: colors ? colors[i] : CATEGORY_COLOR_RAMP[i % CATEGORY_COLOR_RAMP.length] }}
            />
            <span className="font-semibold" style={{ color: C.textDark }}>{cat}</span>
            <span className="font-bold" style={{ color: C.grayText }}>({values[i]})</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// Dispatch bar/donut/stacked/gauge TANPA bungkus kotak — dipakai langsung oleh MiniChartPanel
// (kotak ivory sendirian) DAN InsightDashboard (kartu tile-nya sendiri sudah jadi bungkusnya,
// lihat case "insight_dashboard" di bawah) supaya dispatch-nya tidak diduplikasi 2x. SENGAJA
// panggil BarChart/DonutChart/StackedBar/GaugeRing langsung (bukan dispatcher `Chart` di bawah,
// yang baca visual_style) — bentuk visual di sini tetap per section, lihat report_render_logic.py
// utk alasannya.
function MiniChartContent({ chart, theme = THEME_PALETTES.green }: { chart: any; theme?: ThemeColors }) {
  if (chart.type === "gauge") {
    return (
      <GaugeRing
        value={chart.value}
        max={chart.max}
        label={chart.label}
        color={chart.severity_keys?.[0] ? SEVERITY_COLOR[chart.severity_keys[0]] : undefined}
        theme={theme}
      />
    );
  }
  if (chart.type === "donut") return <DonutChart categories={chart.categories} values={chart.values} />;
  if (chart.type === "stacked") return <StackedBar categories={chart.categories} values={chart.values} />;
  if (chart.type === "bar_line") return <BarLineChart categories={chart.categories} values={chart.values} cumulative={chart.cumulative} theme={theme} />;
  return <BarChart categories={chart.categories} values={chart.values} theme={theme} />;
}

// Panel chart kecil pendukung (block.chart, lihat dynamic_section/key_findings di bawah) —
// dipakai BERSAMA oleh keduanya supaya dispatch bar/donut/stacked/gauge tidak diduplikasi 2x.
function MiniChartPanel({ chart, theme = THEME_PALETTES.green }: { chart: any; theme?: ThemeColors }) {
  return (
    <div
      className="rounded-xl p-3 h-full flex items-center justify-center"
      style={{ background: C.ivory, border: `1px solid ${C.panelBorder}` }}
    >
      <MiniChartContent chart={chart} theme={theme} />
    </div>
  );
}

// Dispatcher gaya chart kategori/status — "bar"/"donut"/"stacked" sesuai visual_style laporan
// (lihat category_style/status_style). Severity TIDAK lewat sini (severity tidak punya
// dimensi gaya di backend — selalu bar dgn warna semantik SEVERITY_COLOR yang tetap).
function Chart({
  style,
  categories,
  values,
  colors,
  color,
}: {
  style: VisualStyle["category_style"] | VisualStyle["status_style"];
  categories: string[];
  values: number[];
  colors?: string[];
  color?: string;
}) {
  if (style === "donut") return <DonutChart categories={categories} values={values} colors={colors} />;
  if (style === "stacked") return <StackedBar categories={categories} values={values} colors={colors} />;
  // "funnel" cuma pernah dikirim sbg vs.status_style (alur bertingkat status penanganan) —
  // status_distribution TIDAK PERNAH pakai ramp per-kategori spt donut/stacked, cuma 1 warna
  // aksen ditingkatkan/direndahkan opacity-nya per baris (lihat FunnelChart).
  if (style === "funnel") return <FunnelChart categories={categories} values={values} color={color || CATEGORY_COLOR_RAMP[0]} />;
  return <BarChart categories={categories} values={values} colors={colors} />;
}

function IvoryPanel({
  badge,
  title,
  children,
  footnote,
  theme = THEME_PALETTES.green,
}: {
  badge: string;
  title: string;
  children: React.ReactNode;
  footnote?: string;
  theme?: ThemeColors;
}) {
  return (
    <div
      className="rounded-xl p-4 h-full"
      style={{ background: C.ivory, border: `1px solid ${C.panelBorder}` }}
    >
      <div className="flex items-center gap-2 mb-3">
        <span
          className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-black text-white shrink-0"
          style={{ background: theme.light }}
        >
          {badge}
        </span>
        <span className="text-xs font-black uppercase tracking-wide" style={{ color: theme.main }}>
          {title}
        </span>
      </div>
      <div className="space-y-2">{children}</div>
      {footnote && (
        <div className="text-[10px] italic mt-3 pt-2 border-t" style={{ color: C.grayText, borderColor: C.panelBorder }}>
          {footnote}
        </div>
      )}
    </div>
  );
}

function BadgeRow({ num, title, detail, color }: { num: string; title: string; detail?: string; color: string }) {
  return (
    <div className="flex items-start gap-3 mb-3">
      <span
        className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-black text-white shrink-0"
        style={{ background: color }}
      >
        {num}
      </span>
      <div>
        <div className="text-sm font-bold" style={{ color: C.textDark }}>
          {title}
        </div>
        {detail && (
          <div className="text-xs mt-0.5" style={{ color: C.grayText }}>
            {detail}
          </div>
        )}
      </div>
    </div>
  );
}

// Pecah teks jadi baris per kalimat — dipakai BulletLines/NoteBox di bawah, regex batas
// kalimat yang sama dgn _shorten_to_caption/_note_box_html backend (bukan .split(". ") polos,
// supaya kalimat yang diakhiri "!"/"?" tetap terpecah benar).
function splitToLines(text?: string): string[] {
  if (!text) return [];
  return text.split(/(?<=[.!?])\s+/).map((s) => s.trim()).filter(Boolean);
}

// Baris bullet polos (titik warna aksen + teks), TANPA bungkus kotak/judul — dipakai NoteBox
// di bawah (mode penuh) DAN tile insight_dashboard (mode ringkas, sudah dibungkus kartu
// bordered sendiri, kotak-dalam-kotak kalau dipakaikan NoteBox utuh lagi di situ).
function BulletLines({ text, theme = THEME_PALETTES.green, sizeClass = "text-[11px]" }: { text?: string; theme?: ThemeColors; sizeClass?: string }) {
  const lines = splitToLines(text);
  if (!lines.length) return null;
  return (
    <ul className="space-y-1">
      {lines.map((line, i) => (
        <li key={i} className={`${sizeClass} leading-snug flex gap-1.5`} style={{ color: C.grayText }}>
          <span className="shrink-0 font-bold" style={{ color: theme.main }}>•</span>
          <span>{line}</span>
        </li>
      ))}
    </ul>
  );
}

// Kotak "Catatan:" (border kiri warna aksen + bullet per kalimat) — GANTI dari AiCaption lama
// (1 baris italic polos) supaya caption AI terasa seperti kotak catatan di laporan referensi,
// BUKAN paragraf mengalir biasa (temuan user: laporan masih terasa "berat kata-kata" meski
// chart-nya sudah ada). Dipakai di semua caption chart (kategori/severity/status) &
// dynamic_section.
function NoteBox({ text, theme = THEME_PALETTES.green, title = "Catatan" }: { text?: string; theme?: ThemeColors; title?: string }) {
  const lines = splitToLines(text);
  if (!lines.length) return null;
  return (
    <div className="rounded-lg p-3 mt-3" style={{ background: C.ivory, borderLeft: `3px solid ${theme.main}` }}>
      <div className="text-[10px] font-black uppercase tracking-wide mb-1.5" style={{ color: theme.main }}>
        {title}:
      </div>
      <BulletLines text={text} theme={theme} />
    </div>
  );
}

function Pill({ text, theme = THEME_PALETTES.green }: { text: string; theme?: ThemeColors }) {
  return (
    <div
      className="inline-block rounded-full px-4 py-1.5 text-xs font-black mr-2 mb-2"
      style={{ border: `1px solid ${theme.light}`, color: theme.light }}
    >
      {text}
    </div>
  );
}

// ---------------------------------------------------------------------------------------
// Cover — "split" (2-kolom emas+hijau, angka hero besar) mirror `_split_cover_td`/
// `add_split_cover_slide`; "solid" (1 warna hijau gelap penuh, tanpa panel hero) mirror
// cabang non-split `_build_cover_slide`. SEBELUMNYA preview SELALU merender "split" apa pun
// visual_style laporannya (dilaporkan user: preview beda dari hasil unduhan kalau backend
// kebetulan pilih "solid") — sekarang dipilih sesuai `vs.cover_style` yang sama persis
// dipakai backend saat laporan ini dianalisis (lihat pick_visual_style()).
// ---------------------------------------------------------------------------------------
function CoverSplit({ block, flourishCorner, theme = THEME_PALETTES.green }: { block: ReportBlock; flourishCorner: VisualStyle["flourish_corner"]; theme?: ThemeColors }) {
  const [heroValue, heroLabel] = block.hero_stat || ["", ""];
  return (
    <div className="overflow-hidden flex flex-col sm:flex-row min-h-full" style={{ fontFamily: BODY_FONT }}>
      <div
        className="sm:w-[37%] p-5 sm:p-6 flex flex-col justify-between gap-4 shrink-0"
        style={{ background: theme.light, color: C.textDark }}
      >
        <div className="text-[10px] font-black uppercase tracking-[0.18em]">
          {block.hero_stat_kicker}
        </div>
        <div>
          <div
            className="text-4xl sm:text-5xl font-bold leading-none"
            style={{ fontFamily: TITLE_FONT, color: theme.bg }}
          >
            {heroValue}
          </div>
          <div className="text-xs sm:text-sm mt-2">{heroLabel}</div>
        </div>
        <div className="text-[9px] sm:text-[10px] font-bold">{block.header_title}</div>
      </div>
      <div className="relative flex-1 p-5 sm:p-8 overflow-hidden" style={{ background: theme.bg, color: C.white }}>
        <Flourish corner={flourishCorner} theme={theme} />
        <div className="relative">
          <Kicker text={block.kicker} color={theme.light} />
          <div className="text-2xl sm:text-3xl font-bold mb-3" style={{ fontFamily: TITLE_FONT }}>
            {block.title}
          </div>
          <div className="text-sm mb-4">{block.subtitle}</div>
          <div className="text-xs">{block.period_label} {block.period_text}</div>
          <div className="text-xs mt-1" style={{ color: theme.soft }}>
            {block.info_line}
          </div>
        </div>
      </div>
    </div>
  );
}

function CoverSolid({ block, flourishCorner, theme = THEME_PALETTES.green }: { block: ReportBlock; flourishCorner: VisualStyle["flourish_corner"]; theme?: ThemeColors }) {
  return (
    <div
      className="relative overflow-hidden min-h-full flex flex-col justify-center p-8 sm:p-12"
      style={{ background: theme.bg, color: C.white, fontFamily: BODY_FONT }}
    >
      <Flourish corner={flourishCorner} theme={theme} />
      <div className="relative">
        <Kicker text={block.kicker} color={theme.light} />
        <div className="text-3xl sm:text-4xl font-bold mb-3" style={{ fontFamily: TITLE_FONT }}>
          {block.title}
        </div>
        <div className="text-sm sm:text-base mb-4">{block.subtitle}</div>
        <div className="text-xs sm:text-sm">{block.period_label} {block.period_text}</div>
        <div className="text-xs sm:text-sm mt-1" style={{ color: theme.soft }}>
          {block.info_line}
        </div>
      </div>
      <div className="absolute left-8 sm:left-12 bottom-6 text-[10px] sm:text-xs font-bold">
        {block.header_title}
      </div>
    </div>
  );
}

function CoverBlock({ block, vs, theme = THEME_PALETTES.green }: { block: ReportBlock; vs: VisualStyle; theme?: ThemeColors }) {
  return vs.cover_style === "solid" ? (
    <CoverSolid block={block} flourishCorner={vs.flourish_corner} theme={theme} />
  ) : (
    <CoverSplit block={block} flourishCorner={vs.flourish_corner} theme={theme} />
  );
}

// ---------------------------------------------------------------------------------------
// Penutup — dipasangkan dgn gaya cover yang sama (bookend), mirror `_split_closing_td`/
// `add_split_closing_slide` vs cabang non-split `_build_closing_slide`.
// ---------------------------------------------------------------------------------------
function ClosingSplit({ block, flourishCorner, theme = THEME_PALETTES.green }: { block: ReportBlock; flourishCorner: VisualStyle["flourish_corner"]; theme?: ThemeColors }) {
  const [heroValue, heroLabel] = block.hero_stat || ["", ""];
  return (
    <div className="overflow-hidden flex flex-col sm:flex-row min-h-full" style={{ fontFamily: BODY_FONT }}>
      <div
        className="sm:w-[37%] p-5 sm:p-6 flex flex-col justify-center shrink-0"
        style={{ background: theme.light, color: C.textDark }}
      >
        <div className="text-4xl sm:text-5xl font-bold leading-none" style={{ fontFamily: TITLE_FONT, color: theme.bg }}>
          {heroValue}
        </div>
        <div className="text-xs sm:text-sm mt-2">{heroLabel}</div>
      </div>
      <div className="relative flex-1 p-5 sm:p-8 flex flex-col justify-center overflow-hidden" style={{ background: theme.bg, color: C.white }}>
        <Flourish corner={flourishCorner} theme={theme} />
        <div className="relative">
          <div className="text-2xl sm:text-3xl font-bold mb-2" style={{ fontFamily: TITLE_FONT }}>
            {block.thank_you}
          </div>
          <div className="text-sm mb-2">{block.title}</div>
          <div className="text-xs italic" style={{ color: theme.soft }}>{block.note}</div>
        </div>
      </div>
    </div>
  );
}

function ClosingSolid({ block, flourishCorner, theme = THEME_PALETTES.green }: { block: ReportBlock; flourishCorner: VisualStyle["flourish_corner"]; theme?: ThemeColors }) {
  return (
    <div
      className="relative overflow-hidden min-h-full flex flex-col items-center justify-center text-center p-8"
      style={{ background: theme.bg, color: C.white, fontFamily: BODY_FONT }}
    >
      <Flourish corner={flourishCorner} theme={theme} />
      <div className="relative">
        <div className="text-2xl sm:text-3xl font-bold mb-3" style={{ fontFamily: TITLE_FONT }}>
          {block.thank_you}
        </div>
        <div className="text-sm mb-2">{block.title}</div>
        <div className="text-xs italic" style={{ color: theme.soft }}>{block.note}</div>
      </div>
    </div>
  );
}

function ClosingBlock({ block, vs, theme = THEME_PALETTES.green }: { block: ReportBlock; vs: VisualStyle; theme?: ThemeColors }) {
  return vs.cover_style === "solid" ? (
    <ClosingSolid block={block} flourishCorner={vs.flourish_corner} theme={theme} />
  ) : (
    <ClosingSplit block={block} flourishCorner={vs.flourish_corner} theme={theme} />
  );
}

// ---------------------------------------------------------------------------------------
// Aset sasaran — "cards" (grid biasa) / "podium" (3 kartu gaya podium, tengah lebih tinggi,
// fallback ke cards kalau bukan persis 3 item) / "bars" (leaderboard batang horizontal).
// ---------------------------------------------------------------------------------------
function AssetCards({ items, theme = THEME_PALETTES.green }: { items: any[]; theme?: ThemeColors }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
      {items.map((it) => (
        <div
          key={it.num}
          className="rounded-xl p-4"
          style={{ border: `1px solid ${theme.light}66`, background: "#ffffff0d" }}
        >
          <span
            className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-black mb-2"
            style={{ background: theme.light, color: C.textDark }}
          >
            {it.num}
          </span>
          <div className="font-bold text-sm">{it.name}</div>
          <div className="text-xs font-black mt-1" style={{ color: theme.soft }}>{it.stat}</div>
          <div className="text-[11px] mt-2 opacity-80">{it.detail}</div>
        </div>
      ))}
    </div>
  );
}

function AssetPodium({ items, theme = THEME_PALETTES.green }: { items: any[]; theme?: ThemeColors }) {
  if (items.length !== 3) return <AssetCards items={items} theme={theme} />;
  const order = [1, 0, 2];
  const heightCls = ["h-32", "h-40", "h-28"];
  return (
    <div className="grid grid-cols-3 gap-3 mt-4 items-end">
      {order.map((itemIdx, pos) => {
        const it = items[itemIdx];
        return (
          <div
            key={it.num}
            className={`rounded-xl p-3 flex flex-col justify-end ${heightCls[pos]}`}
            style={{ border: `1px solid ${theme.light}66`, background: pos === 1 ? "#ffffff1a" : "#ffffff0d" }}
          >
            <span
              className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-black mb-2"
              style={{ background: theme.light, color: C.textDark }}
            >
              {it.num}
            </span>
            <div className="font-bold text-sm truncate">{it.name}</div>
            <div className="text-xs font-black mt-1" style={{ color: theme.soft }}>{it.stat}</div>
          </div>
        );
      })}
    </div>
  );
}

function AssetBars({ items, theme = THEME_PALETTES.green }: { items: any[]; theme?: ThemeColors }) {
  const nums = items.map((it) => parseFloat(String(it.stat).replace(/[^\d.]/g, "")) || 0);
  const max = Math.max(...nums, 1);
  return (
    <div className="space-y-3.5 mt-4">
      {items.map((it, i) => (
        <div key={it.num} className="flex items-center gap-3">
          <span
            className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-black shrink-0"
            style={{ background: theme.light, color: C.textDark }}
          >
            {it.num}
          </span>
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline justify-between text-xs mb-1 gap-2">
              <span className="font-bold truncate">{it.name}</span>
              <span className="font-black shrink-0" style={{ color: theme.soft }}>{it.stat}</span>
            </div>
            <div className="h-2 rounded-full" style={{ background: "#ffffff26" }}>
              <div
                className="h-2 rounded-full"
                style={{ width: `${Math.max((nums[i] / max) * 100, 4)}%`, background: theme.light }}
              />
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function AssetSection({ items, style, theme = THEME_PALETTES.green }: { items: any[]; style: VisualStyle["asset_style"]; theme?: ThemeColors }) {
  if (style === "podium") return <AssetPodium items={items} theme={theme} />;
  if (style === "bars") return <AssetBars items={items} theme={theme} />;
  return <AssetCards items={items} theme={theme} />;
}

// ---------------------------------------------------------------------------------------
// Rekomendasi — "cards" (grid biasa) / "timeline" (garis vertikal tersambung) / "banners"
// (stripe horizontal penuh lebar, ditumpuk).
// ---------------------------------------------------------------------------------------
function RecommendationCards({ items, cols, theme = THEME_PALETTES.green }: { items: any[]; cols: number; theme?: ThemeColors }) {
  return (
    <div
      className="grid grid-cols-1 gap-4 mt-4"
      style={{ gridTemplateColumns: `repeat(${Math.max(1, cols)}, minmax(0, 1fr))` }}
    >
      {items.map((it: any) => (
        <div
          key={it.num}
          className="rounded-xl p-4"
          style={{ background: C.ivory, border: `1px solid ${C.panelBorder}` }}
        >
          <span
            className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-black text-white mb-2"
            style={{ background: theme.light }}
          >
            {it.num}
          </span>
          <div className="text-sm font-bold" style={{ color: C.textDark }}>{it.title}</div>
          {it.detail && (
            <div className="text-xs mt-1.5" style={{ color: C.grayText }}>{it.detail}</div>
          )}
        </div>
      ))}
    </div>
  );
}

function RecommendationTimeline({ items, theme = THEME_PALETTES.green }: { items: any[]; theme?: ThemeColors }) {
  return (
    <div className="mt-4 relative pl-2">
      <div className="absolute left-[15px] top-2 bottom-2 w-px" style={{ background: C.panelBorder }} />
      <div className="space-y-5">
        {items.map((it: any) => (
          <div key={it.num} className="flex gap-4 relative">
            <span
              className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-black text-white shrink-0 relative z-10"
              style={{ background: theme.light }}
            >
              {it.num}
            </span>
            <div className="pt-0.5">
              <div className="text-sm font-bold" style={{ color: C.textDark }}>{it.title}</div>
              {it.detail && (
                <div className="text-xs mt-1" style={{ color: C.grayText }}>{it.detail}</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function RecommendationBanners({ items, theme = THEME_PALETTES.green }: { items: any[]; theme?: ThemeColors }) {
  return (
    <div className="space-y-3 mt-4">
      {items.map((it: any) => (
        <div
          key={it.num}
          className="rounded-xl p-4 flex items-center gap-4"
          style={{ background: C.ivory, border: `1px solid ${C.panelBorder}` }}
        >
          <span
            className="w-9 h-9 rounded-full flex items-center justify-center text-sm font-black text-white shrink-0"
            style={{ background: theme.light }}
          >
            {it.num}
          </span>
          <div className="min-w-0">
            <div className="text-sm font-bold" style={{ color: C.textDark }}>{it.title}</div>
            {it.detail && (
              <div className="text-xs mt-0.5" style={{ color: C.grayText }}>{it.detail}</div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function RecommendationSection({ items, style, cols, theme = THEME_PALETTES.green }: { items: any[]; style: VisualStyle["recommendation_style"]; cols: number; theme?: ThemeColors }) {
  if (style === "timeline") return <RecommendationTimeline items={items} theme={theme} />;
  if (style === "banners") return <RecommendationBanners items={items} theme={theme} />;
  return <RecommendationCards items={items} cols={cols} theme={theme} />;
}

export default function ReportBlockRenderer({
  block,
  visualStyle,
  themeColor,
}: {
  block: ReportBlock;
  visualStyle?: VisualStyle;
  themeColor?: string;
}) {
  const vs = visualStyle || DEFAULT_VISUAL_STYLE;
  const theme = resolveThemeColors(themeColor);

  if (block.kind === "cover") {
    return <CoverBlock block={block} vs={vs} theme={theme} />;
  }
  if (block.kind === "closing") {
    return <ClosingBlock block={block} vs={vs} theme={theme} />;
  }

  const dark = !!block.dark;
  const wrapStyle: React.CSSProperties = dark
    ? { background: theme.bg, color: C.white }
    : { background: C.white, color: C.textDark };

  return (
    <div className="min-h-full p-6 sm:p-8" style={{ ...wrapStyle, fontFamily: BODY_FONT }}>
      {renderInner(block, vs, theme)}
    </div>
  );
}

// Kartu ringkas dipakai BERSAMA oleh panel_kind "insight_tile" (Trend/Severity/Risk bawaan AI)
// DAN "dynamic_section" (section kustom AI) — keduanya bertema "insight" (lihat
// report_render_logic.py) & bisa berbagi 1 halaman berdampingan sampai 4 kartu. TIDAK punya
// kicker/judul sendiri (label kecil di dalam kartu cukup) — judul halaman ditambahkan SEKALI
// di case "page" kalau salah satu panelnya jenis ini.
function InsightTile({ panel, theme = THEME_PALETTES.green }: { panel: any; theme?: ThemeColors }) {
  const label = panel.label || panel.title || "";
  const caption = panel.caption ?? panel.text;
  return (
    <div className="rounded-2xl p-4 flex flex-col" style={{ border: `1px solid ${C.panelBorder}`, background: C.white }}>
      <div className="text-[10px] font-black uppercase tracking-wide mb-3" style={{ color: theme.main }}>
        {label}
      </div>
      <div className="flex-1 flex items-center justify-center py-2">
        {panel.trend_stat ? (
          <div className="text-center">
            <div className="text-2xl font-black" style={{ color: DIRECTION_COLOR[panel.trend_stat.direction] }}>
              {panel.trend_stat.value}
            </div>
            <div className="text-[10px] mt-1" style={{ color: C.grayText }}>{panel.trend_stat.label}</div>
          </div>
        ) : panel.chart ? (
          <MiniChartContent chart={panel.chart} theme={theme} />
        ) : panel.aux_stat ? (
          <div className="text-center">
            <div className="text-2xl font-black" style={{ color: theme.main }}>{panel.aux_stat[0]}</div>
            <div className="text-[10px] mt-1" style={{ color: C.grayText }}>{panel.aux_stat[1]}</div>
          </div>
        ) : panel.aux_list ? (
          <div className="w-full space-y-1">
            {panel.aux_list.map((it: any, i: number) => (
              <div key={i} className="flex items-center justify-between text-[11px]">
                <span className="truncate" style={{ color: C.textDark }}>{it.label}</span>
                <span className="font-bold" style={{ color: theme.main }}>{it.value}</span>
              </div>
            ))}
          </div>
        ) : null}
      </div>
      <div className="mt-2">
        <BulletLines text={caption} theme={theme} sizeClass="text-[10.5px]" />
      </div>
    </div>
  );
}

function renderInner(block: ReportBlock, vs: VisualStyle, theme: ThemeColors): React.ReactNode {
  const accentColor = theme.main;
  // Ramp warna kategori/status DITURUNKAN dari tema — sama seperti export_pdf.py/export_ppt.py.
  // C.grayText tetap warna ke-5 (netral).
  const ramp = [theme.main, theme.chart, theme.light, theme.soft, C.grayText];

  switch (block.kind) {

    case "intro": {
      const textCol = (
        <div>
          <p className="text-sm mb-4" style={{ color: C.grayText }}>
            {block.purpose_text}
          </p>
          {block.objectives.map((o: any) => (
            <BadgeRow key={o.num} num={o.num} title={o.title} detail={o.detail} color={theme.main} />
          ))}
        </div>
      );
      const panelCol = (
        <IvoryPanel badge="i" title={block.scope.panel_title} footnote={block.scope.footnote} theme={theme}>
          {[
            [block.scope.period_label, block.scope.period_text],
            [block.scope.total_event_label, block.scope.total_records_text],
            [block.scope.source_file_label, block.scope.input_file_name],
            [block.scope.data_type_label_label, block.scope.data_type_label],
          ].map(([k, v]) => (
            <div key={k} className="text-xs">
              <div className="font-bold uppercase text-[10px]" style={{ color: C.grayText }}>
                {k}
              </div>
              <div className="font-semibold" style={{ color: C.textDark }}>
                {v}
              </div>
            </div>
          ))}
        </IvoryPanel>
      );
      return (
        <>
          <Kicker text={block.kicker} color={theme.main} />
          <BlockTitle>{block.title}</BlockTitle>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {vs.panel_side === "left" ? (
              <>{panelCol}{textCol}</>
            ) : (
              <>{textCol}{panelCol}</>
            )}
          </div>
        </>
      );
    }

    case "executive_summary":
      return (
        <>
          <Kicker text={block.title || "Executive Summary"} color={theme.light} />
          <BlockTitle color={C.white}>{block.heading}</BlockTitle>
          <div
            className="grid grid-cols-2 gap-3 mt-4"
            style={{ gridTemplateColumns: `repeat(${Math.max(2, vs.stat_cols)}, minmax(0, 1fr))` }}
          >
            {block.stat_items.map((s: [string, string], i: number) => (
              <div
                key={i}
                className="rounded-xl p-4 text-center"
                style={{ border: `1px solid ${theme.light}66`, background: "#ffffff10" }}
              >
                <div className="text-xl font-black">{s[0]}</div>
                <div className="text-[10px] font-bold mt-1 opacity-80">{s[1]}</div>
              </div>
            ))}
          </div>
          <div className="text-xs italic mt-5" style={{ color: theme.soft }}>
            {block.caption}
          </div>
        </>
      );

    // "page" — 1-4 panel (block.panels, lihat report_render_logic.py tahap 2:
    // _group_candidates_into_pages). 1 panel yang BUKAN insight_tile/dynamic_section ->
    // dirender lewat renderInner() yang sama persis (kind diganti panel_kind), kartu/kicker/
    // judulnya sudah "mandiri" (sama seperti versi standalone sebelum refactor ini). Beberapa
    // panel (atau 1 panel insight_tile/dynamic_section, yang TIDAK punya judul sendiri) ->
    // dibungkus kicker+judul halaman bersama, panel-panelnya digambar berdampingan.
    case "page": {
      const panels = (block.panels as ReportBlock[]) || [];
      if (panels.length === 0) return null;
      const isInsight = panels[0].panel_kind === "insight_tile" || panels[0].panel_kind === "dynamic_section";
      if (panels.length === 1 && !isInsight) {
        return renderInner({ ...panels[0], kind: panels[0].panel_kind }, vs, theme);
      }
      if (isInsight) {
        const cols = Math.max(1, Math.min(panels.length, 4));
        return (
          <>
            <Kicker text={block.kicker} color={theme.main} />
            <BlockTitle>{block.title}</BlockTitle>
            <div className="grid grid-cols-1 gap-5" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
              {panels.map((panel, i) => (
                <InsightTile key={i} panel={panel} theme={theme} />
              ))}
            </div>
          </>
        );
      }
      const cols = Math.max(1, Math.min(panels.length, 3));
      return (
        <div className="grid grid-cols-1 gap-x-10 gap-y-8" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}>
          {panels.map((panel, i) => (
            <div key={i}>{renderInner({ ...panel, kind: panel.panel_kind }, vs, theme)}</div>
          ))}
        </div>
      );
    }

    case "category_distribution": {
      const catRampColors = block.legend.map((l: any) => ramp[l.color_index % ramp.length]);
      const chartCol = (
        <Chart
          style={vs.category_style}
          categories={block.categories}
          values={block.values}
          colors={vs.category_style === "bar" ? block.categories.map(() => accentColor) : catRampColors}
        />
      );
      const panelCol = (
        <IvoryPanel badge="%" title={block.legend_panel_title} footnote={block.footnote} theme={theme}>
          {block.legend.map((l: any, i: number) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              <span
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ background: ramp[l.color_index % ramp.length] }}
              />
              <span className="flex-1 truncate" style={{ color: C.textDark }}>
                {l.name}
              </span>
              <span className="font-bold" style={{ color: theme.main }}>
                {l.pct}%
              </span>
            </div>
          ))}
        </IvoryPanel>
      );
      return (
        <>
          <Kicker text={block.kicker} color={theme.main} />
          <BlockTitle>{block.title}</BlockTitle>
          <p className="text-xs mb-4" style={{ color: C.grayText }}>
            {block.intro}
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {vs.panel_side === "left" ? <>{panelCol}{chartCol}</> : <>{chartCol}{panelCol}</>}
          </div>
          <NoteBox text={block.ai_caption} theme={theme} />
        </>
      );
    }

    case "severity_distribution": {
      // Severity TIDAK punya dimensi gaya chart di backend (selalu bar, warna semantik tetap
      // per level) — jadi di sini juga selalu BarChart, cuma posisi panel yang ikut vs.panel_side.
      const chartCol = (
        <BarChart
          categories={block.categories}
          values={block.values}
          colors={block.severity_keys.map((k: string) => SEVERITY_COLOR[k])}
        />
      );
      const panelCol = (
        <div
          className="rounded-xl p-4 h-full flex flex-col justify-center"
          style={{ background: theme.bg, border: `1px solid ${theme.light}66` }}
        >
          <div className="text-3xl font-black text-white">{block.crit_pct}%</div>
          <div className="text-xs mt-1" style={{ color: theme.soft }}>
            {block.panel_text}
          </div>
          {block.detail_text && (
            <div className="text-xs mt-3 pt-3 border-t border-white/20 text-white/80">
              {block.detail_text}
            </div>
          )}
        </div>
      );
      return (
        <>
          <Kicker text={block.kicker} color={theme.main} />
          <BlockTitle>{block.title}</BlockTitle>
          <p className="text-xs mb-4" style={{ color: C.grayText }}>
            {block.intro}
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {vs.panel_side === "left" ? <>{panelCol}{chartCol}</> : <>{chartCol}{panelCol}</>}
          </div>
          <NoteBox text={block.ai_caption} theme={theme} />
        </>
      );
    }

    case "status_distribution":
      return (
        <>
          <Kicker text={block.kicker} color={theme.main} />
          <BlockTitle>{block.title}</BlockTitle>
          <p className="text-xs mb-4" style={{ color: C.grayText }}>
            {block.intro}
          </p>
          <Chart
            style={vs.status_style}
            categories={block.categories}
            values={block.values}
            colors={vs.status_style === "bar" ? block.categories.map(() => accentColor) : block.categories.map((_c: string, i: number) => ramp[i % ramp.length])}
            color={accentColor}
          />
          <NoteBox text={block.ai_caption} theme={theme} />
        </>
      );

    case "kpi_radar":
      return (
        <>
          <Kicker text={block.kicker} color={theme.main} />
          <BlockTitle>{block.title}</BlockTitle>
          <div className="flex justify-center">
            <RadarChart axes={block.axes} values={block.values} theme={theme} />
          </div>
          <NoteBox text={block.intro} theme={theme} />
        </>
      );

    case "time_heatmap":
      return (
        <>
          <Kicker text={block.kicker} color={theme.main} />
          <BlockTitle>{block.title}</BlockTitle>
          <div className="flex justify-center overflow-x-auto">
            <HeatmapGrid dayLabels={block.day_labels} hourLabels={block.hour_labels} grid={block.grid} theme={theme} />
          </div>
          <NoteBox text={block.intro} theme={theme} />
        </>
      );

    case "period_compare":
      return (
        <>
          <Kicker text={block.kicker} color={theme.main} />
          <BlockTitle>{block.title}</BlockTitle>
          <GroupedBarChart
            categories={block.categories}
            seriesA={block.series_a}
            seriesB={block.series_b}
            labelA={block.label_a}
            labelB={block.label_b}
            theme={theme}
          />
          <NoteBox text={block.intro} theme={theme} />
        </>
      );

    case "critical_table":
      return (
        <>
          <Kicker text={block.kicker} color={block.kicker_is_critical ? C.redCrit : theme.main} />
          <BlockTitle>{block.title}</BlockTitle>
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr style={{ background: theme.bg }}>
                  {block.headers.map((h: string) => (
                    <th key={h} className="text-left px-3 py-2 text-white font-bold">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {block.rows.map((row: string[], i: number) => {
                  const highlighted = block.highlight_idx.includes(i);
                  return (
                    <tr
                      key={i}
                      style={{
                        background: highlighted ? C.redCritBg : i % 2 === 0 ? C.ivory : C.white,
                      }}
                    >
                      {row.map((cell, j) => (
                        <td
                          key={j}
                          className="px-3 py-2"
                          style={{
                            color: highlighted && j === row.length - 1 ? C.redCrit : C.textDark,
                            fontWeight: highlighted && j === row.length - 1 ? 700 : 400,
                          }}
                        >
                          {cell}
                        </td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {block.caption && (
            <div className="text-[10px] italic mt-3" style={{ color: C.grayText }}>
              {block.caption}
            </div>
          )}
        </>
      );

    case "asset_cards":
      return (
        <>
          <Kicker text={block.kicker} color={theme.light} />
          <BlockTitle color={C.white}>{block.title}</BlockTitle>
          <AssetSection items={block.items} style={vs.asset_style} theme={theme} />
        </>
      );

    case "key_findings": {
      const findingsCol = (
        <div>
          {block.items.map((it: any) => (
            <BadgeRow
              key={it.num}
              num={it.num}
              title={it.title}
              detail={it.detail}
              color={it.is_critical ? C.redCrit : theme.main}
            />
          ))}
        </div>
      );
      return (
        <>
          <Kicker text={block.kicker} color={theme.main} />
          <BlockTitle>{block.title}</BlockTitle>
          {block.chart ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="md:col-span-2">{findingsCol}</div>
              <div>
                <MiniChartPanel chart={block.chart} theme={theme} />
              </div>
            </div>
          ) : (
            findingsCol
          )}
        </>
      );
    }

    case "recommendations":
      return (
        <>
          <Kicker text={block.kicker} color={theme.main} />
          <BlockTitle>{block.title}</BlockTitle>
          <RecommendationSection items={block.items} style={vs.recommendation_style} cols={vs.card_cols} theme={theme} />
        </>
      );

    case "conclusion":
      return (
        <>
          <Kicker text={block.kicker} color={theme.light} />
          <BlockTitle color={C.white}>{block.title}</BlockTitle>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <p className="text-sm mb-4" style={{ color: "#E8ECE6" }}>
                {block.text}
              </p>
              <div>
                {block.pills.map((p: string, i: number) => (
                  <Pill key={i} text={p} theme={theme} />
                ))}
              </div>
            </div>
            {block.priority_items.length > 0 && (
              <IvoryPanel badge="!" title={block.priority_panel_title} theme={theme}>
                {block.priority_items.map((p: any) => (
                  <div key={p.letter} className="flex items-start gap-2 text-xs">
                    <span
                      className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-black text-white shrink-0"
                      style={{ background: theme.light }}
                    >
                      {p.letter}
                    </span>
                    <span style={{ color: C.textDark }}>{p.text}</span>
                  </div>
                ))}
              </IvoryPanel>
            )}
          </div>
        </>
      );

    default:
      return null;
  }
}
