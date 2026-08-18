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

// Dispatcher gaya chart kategori/status — "bar"/"donut"/"stacked" sesuai visual_style laporan
// (lihat category_style/status_style). Severity TIDAK lewat sini (severity tidak punya
// dimensi gaya di backend — selalu bar dgn warna semantik SEVERITY_COLOR yang tetap).
function Chart({
  style,
  categories,
  values,
  colors,
}: {
  style: VisualStyle["category_style"];
  categories: string[];
  values: number[];
  colors?: string[];
}) {
  if (style === "donut") return <DonutChart categories={categories} values={values} colors={colors} />;
  if (style === "stacked") return <StackedBar categories={categories} values={values} colors={colors} />;
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

function AiCaption({ text }: { text?: string }) {
  if (!text) return null;
  return (
    <div className="text-xs italic mt-4" style={{ color: C.grayText }}>
      💡 {text}
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

    case "dynamic_section": {
      const hasAux = !!(block.aux_stat || block.aux_list);
      const textCol = (
        <p className="text-sm" style={{ color: C.grayText }}>
          {block.text}
        </p>
      );
      const auxCol = block.aux_stat ? (
        <div
          className="rounded-xl p-4 h-full flex flex-col justify-center items-center text-center"
          style={{ background: theme.bg, border: `1px solid ${theme.light}66` }}
        >
          <div className="text-3xl font-black" style={{ color: theme.light }}>
            {block.aux_stat[0]}
          </div>
          <div className="text-xs mt-1 text-white">{block.aux_stat[1]}</div>
        </div>
      ) : block.aux_list ? (
        <IvoryPanel badge="i" title="Sorotan Data" theme={theme}>
          {block.aux_list.map((it: any, i: number) => (
            <div key={i} className="flex items-center justify-between text-xs">
              <span className="truncate" style={{ color: C.textDark }}>{it.label}</span>
              <span className="font-bold" style={{ color: theme.main }}>{it.value}</span>
            </div>
          ))}
        </IvoryPanel>
      ) : null;
      return (
        <>
          <Kicker text={block.kicker} color={theme.main} />
          <BlockTitle>{block.title}</BlockTitle>
          {hasAux ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="md:col-span-2">{textCol}</div>
              <div>{auxCol}</div>
            </div>
          ) : (
            textCol
          )}
        </>
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
          <AiCaption text={block.ai_caption} />
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
          <AiCaption text={block.ai_caption} />
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
          />
          <AiCaption text={block.ai_caption} />
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

    case "key_findings":
      return (
        <>
          <Kicker text={block.kicker} color={theme.main} />
          <BlockTitle>{block.title}</BlockTitle>
          {block.items.map((it: any) => (
            <BadgeRow
              key={it.num}
              num={it.num}
              title={it.title}
              detail={it.detail}
              color={it.is_critical ? C.redCrit : theme.main}
            />
          ))}
        </>
      );

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


    // ===== MANAGEMENT REPORT BLOCKS =====

    case "management_kpi_grid": {
      const URGENCY_COLORS: Record<string, string> = {
        blue: "#2563EB",
        red: "#DC2626",
        orange: "#EA580C",
        green: "#16A34A",
        amber: "#D97706",
        gray: "#6B7280",
      };
      return (
        <>
          {block.kicker && <Kicker text={block.kicker} color={theme.main} />}
          <BlockTitle>{block.title}</BlockTitle>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-4">
            {(block.items || []).map((item: any, i: number) => {
              const iconColor = URGENCY_COLORS[item.color] || theme.main;
              return (
                <div
                  key={i}
                  className="rounded-2xl border p-4 flex flex-col gap-1"
                  style={{ borderColor: iconColor + "30", background: iconColor + "08" }}
                >
                  <div className="text-[10px] font-extrabold uppercase tracking-wider" style={{ color: iconColor }}>
                    {item.label}
                  </div>
                  <div className="text-2xl font-black" style={{ color: iconColor }}>
                    {item.value}
                  </div>
                  {item.delta && (
                    <div className="text-[9px] font-semibold" style={{ color: C.grayText }}>
                      {item.delta}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      );
    }

    case "management_risk_heatmap": {
      const SEV_COLORS: Record<string, string> = {
        red: "#DC2626",
        orange: "#EA580C",
        amber: "#D97706",
        blue: "#2563EB",
        gray: "#6B7280",
      };
      return (
        <>
          {block.kicker && <Kicker text={block.kicker} color={theme.main} />}
          <BlockTitle>{block.title}</BlockTitle>
          <div className="mt-4 space-y-2">
            {(block.severity_bars || []).map((bar: any, i: number) => {
              const col = SEV_COLORS[bar.color] || theme.main;
              return (
                <div key={i} className="flex items-center gap-3">
                  <div className="w-20 text-[10px] font-extrabold shrink-0" style={{ color: col }}>
                    {bar.label}
                  </div>
                  <div className="flex-1 h-5 rounded-full bg-stone-100 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${Math.max(bar.pct, 2)}%`, background: col }}
                    />
                  </div>
                  <div className="w-16 text-right text-xs font-bold" style={{ color: col }}>
                    {bar.count} <span className="text-[9px] font-normal text-stone-400">({bar.pct}%)</span>
                  </div>
                </div>
              );
            })}
          </div>
          {block.summary_text && (
            <p className="mt-4 text-xs leading-relaxed" style={{ color: C.grayText }}>
              {block.summary_text}
            </p>
          )}
        </>
      );
    }

    case "management_trend_chart": {
      return (
        <>
          {block.kicker && <Kicker text={block.kicker} color={theme.main} />}
          <BlockTitle>{block.title}</BlockTitle>
          {block.narrative && (
            <p className="text-xs leading-relaxed mt-2 mb-4" style={{ color: C.grayText }}>
              {block.narrative}
            </p>
          )}
          {(block.trend_items || []).length > 0 && (
            <div className="mt-3 space-y-4">
              {block.trend_items.map((ti: any, i: number) => (
                <div key={i}>
                  <div className="text-[10px] font-extrabold uppercase tracking-wider mb-2" style={{ color: theme.main }}>
                    {ti.category}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(ti.top_values || []).map((v: string, j: number) => (
                      <span
                        key={j}
                        className="px-2.5 py-1 rounded-full text-[10px] font-bold"
                        style={{
                          background: theme.soft,
                          color: theme.main,
                          border: `1px solid ${theme.light}40`,
                        }}
                      >
                        {v}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      );
    }

    case "management_action_items": {
      const URGENCY_BG: Record<string, [string, string]> = {
        critical: ["#DC2626", "#FEF2F2"],
        high: ["#EA580C", "#FFF7ED"],
        medium: ["#D97706", "#FFFBEB"],
        low: ["#2563EB", "#EFF6FF"],
      };
      return (
        <>
          {block.kicker && <Kicker text={block.kicker} color={theme.main} />}
          <BlockTitle>{block.title}</BlockTitle>
          <div className="mt-4 space-y-3">
            {(block.items || []).map((item: any, i: number) => {
              const [fg, bg] = URGENCY_BG[item.urgency] || [theme.main, theme.soft];
              return (
                <div key={i} className="rounded-2xl border p-3 flex gap-3" style={{ borderColor: fg + "25", background: bg }}>
                  <div
                    className="w-7 h-7 rounded-xl flex items-center justify-center font-black text-xs text-white shrink-0 mt-0.5"
                    style={{ background: fg }}
                  >
                    {item.number}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-extrabold text-xs mb-0.5" style={{ color: C.textDark }}>
                      {item.title}
                    </div>
                    {item.detail && (
                      <div className="text-[10px] leading-relaxed" style={{ color: C.grayText }}>
                        {item.detail}
                      </div>
                    )}
                    <span
                      className="inline-block mt-1 px-2 py-0.5 rounded-full text-[8px] font-extrabold uppercase tracking-wider"
                      style={{ background: fg, color: "white" }}
                    >
                      {item.urgency}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      );
    }

    default:
      return null;
  }
}
