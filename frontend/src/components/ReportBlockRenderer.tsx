import { REPORT_COLORS, CATEGORY_COLOR_RAMP, SEVERITY_COLOR, TITLE_FONT, BODY_FONT, type ReportBlock } from "@/utils/reportTheme";

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

function BarChart({
  categories,
  values,
  colors,
}: {
  categories: string[];
  values: number[];
  colors?: string[];
}) {
  const max = Math.max(...values, 1);
  return (
    <div className="space-y-2.5">
      {categories.map((cat, i) => {
        const pct = Math.max((values[i] / max) * 100, 1.5);
        const color = colors ? colors[i] : C.greenMain;
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

function IvoryPanel({
  badge,
  title,
  children,
  footnote,
}: {
  badge: string;
  title: string;
  children: React.ReactNode;
  footnote?: string;
}) {
  return (
    <div
      className="rounded-xl p-4 h-full"
      style={{ background: C.ivory, border: `1px solid ${C.panelBorder}` }}
    >
      <div className="flex items-center gap-2 mb-3">
        <span
          className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-black text-white shrink-0"
          style={{ background: C.goldMain }}
        >
          {badge}
        </span>
        <span className="text-xs font-black uppercase tracking-wide" style={{ color: C.greenMain }}>
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

function Pill({ text }: { text: string }) {
  return (
    <div
      className="inline-block rounded-full px-4 py-1.5 text-xs font-black mr-2 mb-2"
      style={{ border: `1px solid ${C.goldMain}`, color: C.goldMain }}
    >
      {text}
    </div>
  );
}

export default function ReportBlockRenderer({ block }: { block: ReportBlock }) {
  const dark = !!block.dark;
  const wrapStyle: React.CSSProperties = dark
    ? { background: C.greenBg, color: C.white }
    : { background: C.white, color: C.textDark };

  return (
    <div className="rounded-2xl p-6 sm:p-8" style={{ ...wrapStyle, fontFamily: BODY_FONT }}>
      {renderInner(block, dark)}
    </div>
  );
}

function renderInner(block: ReportBlock, dark: boolean) {
  switch (block.kind) {
    case "cover":
      return (
        <div className="py-6">
          <Kicker text="LAPORAN ANALISIS" color={C.goldMain} />
          <div className="text-2xl sm:text-3xl font-bold mb-3" style={{ fontFamily: TITLE_FONT }}>
            {block.title}
          </div>
          <div className="text-sm mb-4">{block.subtitle}</div>
          <div className="text-xs">Periode data. {block.period_text}</div>
          <div className="text-xs mt-1" style={{ color: C.goldLight }}>
            {block.total_records} entri log, {block.category_count} kategori kejadian, {block.critical_count} insiden Critical
          </div>
          <div className="text-[10px] font-bold mt-8">{block.header_title}</div>
        </div>
      );

    case "intro":
      return (
        <>
          <Kicker text="PENDAHULUAN" color={C.greenMain} />
          <BlockTitle>Latar Belakang dan Tujuan Analisis</BlockTitle>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <p className="text-sm mb-4" style={{ color: C.grayText }}>
                {block.purpose_text}
              </p>
              {block.objectives.map((o: any) => (
                <BadgeRow key={o.num} num={o.num} title={o.title} detail={o.detail} color={C.greenMain} />
              ))}
            </div>
            <IvoryPanel badge="i" title="Ruang Lingkup Data" footnote="Sumber. Data yang diunggah pengguna, diproses otomatis oleh sistem.">
              {[
                ["Periode", block.scope.period_text],
                ["Total Event", `${block.scope.total_records} entri log`],
                ["Sumber Berkas", block.scope.input_file_name],
                ["Jenis Data", block.scope.data_type_label],
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
          </div>
        </>
      );

    case "executive_summary":
      return (
        <>
          <Kicker text="RINGKASAN EKSEKUTIF" color={C.goldMain} />
          <BlockTitle color={C.white}>{block.heading}</BlockTitle>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mt-4">
            {block.stat_items.map((s: [string, string], i: number) => (
              <div
                key={i}
                className="rounded-xl p-4 text-center"
                style={{ border: `1px solid ${C.goldMain}66`, background: "#ffffff10" }}
              >
                <div className="text-xl font-black">{s[0]}</div>
                <div className="text-[10px] font-bold mt-1 opacity-80">{s[1]}</div>
              </div>
            ))}
          </div>
          <div className="text-xs italic mt-5" style={{ color: C.goldLight }}>
            {block.caption}
          </div>
        </>
      );

    case "category_distribution":
      return (
        <>
          <Kicker text="TINJAUAN DATA" color={C.greenMain} />
          <BlockTitle>Distribusi Event Berdasarkan {block.label}</BlockTitle>
          <p className="text-xs mb-4" style={{ color: C.grayText }}>
            {block.intro}
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <BarChart categories={block.categories} values={block.values} />
            <IvoryPanel badge="%" title="Proporsi Kategori" footnote={block.footnote}>
              {block.legend.map((l: any, i: number) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ background: CATEGORY_COLOR_RAMP[l.color_index] }}
                  />
                  <span className="flex-1 truncate" style={{ color: C.textDark }}>
                    {l.name}
                  </span>
                  <span className="font-bold" style={{ color: C.greenMain }}>
                    {l.pct}%
                  </span>
                </div>
              ))}
            </IvoryPanel>
          </div>
        </>
      );

    case "severity_distribution":
      return (
        <>
          <Kicker text="TINJAUAN DATA" color={C.greenMain} />
          <BlockTitle>Distribusi Tingkat Keparahan (Severity)</BlockTitle>
          <p className="text-xs mb-4" style={{ color: C.grayText }}>
            {block.intro}
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <BarChart
              categories={block.categories}
              values={block.values}
              colors={block.severity_keys.map((k: string) => SEVERITY_COLOR[k])}
            />
            <div
              className="rounded-xl p-4 h-full flex flex-col justify-center"
              style={{ background: C.greenBg, border: `1px solid ${C.goldMain}66` }}
            >
              <div className="text-3xl font-black text-white">{block.crit_pct}%</div>
              <div className="text-xs mt-1" style={{ color: C.goldLight }}>
                {block.panel_text}
              </div>
              {block.detail_text && (
                <div className="text-xs mt-3 pt-3 border-t border-white/20 text-white/80">
                  {block.detail_text}
                </div>
              )}
            </div>
          </div>
        </>
      );

    case "status_distribution":
      return (
        <>
          <Kicker text="TINJAUAN DATA" color={C.greenMain} />
          <BlockTitle>Status Penanganan Insiden</BlockTitle>
          <p className="text-xs mb-4" style={{ color: C.grayText }}>
            {block.intro}
          </p>
          <BarChart categories={block.categories} values={block.values} />
        </>
      );

    case "critical_table":
      return (
        <>
          <Kicker text="SOROTAN INSIDEN" color={block.kicker_is_critical ? C.redCrit : C.greenMain} />
          <BlockTitle>{block.title}</BlockTitle>
          <div className="overflow-x-auto">
            <table className="w-full text-xs border-collapse">
              <thead>
                <tr style={{ background: C.greenBg }}>
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
          <Kicker text="SOROTAN INSIDEN" color={C.goldMain} />
          <BlockTitle color={C.white}>{block.title}</BlockTitle>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-4">
            {block.items.map((it: any) => (
              <div
                key={it.num}
                className="rounded-xl p-4"
                style={{ border: `1px solid ${C.goldMain}66`, background: "#ffffff0d" }}
              >
                <span
                  className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-black mb-2"
                  style={{ background: C.goldMain, color: C.textDark }}
                >
                  {it.num}
                </span>
                <div className="font-bold text-sm">{it.name}</div>
                <div className="text-xs font-black mt-1" style={{ color: C.goldLight }}>
                  {it.stat}
                </div>
                <div className="text-[11px] mt-2 opacity-80">{it.detail}</div>
              </div>
            ))}
          </div>
        </>
      );

    case "key_findings":
      return (
        <>
          <Kicker text="ANALISIS" color={C.greenMain} />
          <BlockTitle>Temuan Utama</BlockTitle>
          {block.items.map((it: any) => (
            <BadgeRow
              key={it.num}
              num={it.num}
              title={it.title}
              detail={it.detail}
              color={it.is_critical ? C.redCrit : C.greenMain}
            />
          ))}
        </>
      );

    case "recommendations":
      return (
        <>
          <Kicker text="TINDAK LANJUT" color={C.greenMain} />
          <BlockTitle>Rekomendasi Mitigasi</BlockTitle>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 mt-4">
            {block.items.map((it: any) => (
              <div
                key={it.num}
                className="rounded-xl p-4"
                style={{ background: C.ivory, border: `1px solid ${C.panelBorder}` }}
              >
                <span
                  className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-black text-white mb-2"
                  style={{ background: C.goldMain }}
                >
                  {it.num}
                </span>
                <div className="text-sm font-bold" style={{ color: C.textDark }}>
                  {it.title}
                </div>
                {it.detail && (
                  <div className="text-xs mt-1.5" style={{ color: C.grayText }}>
                    {it.detail}
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      );

    case "conclusion":
      return (
        <>
          <Kicker text="PENUTUP" color={C.goldMain} />
          <BlockTitle color={C.white}>Kesimpulan</BlockTitle>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <p className="text-sm mb-4" style={{ color: "#E8ECE6" }}>
                {block.text}
              </p>
              <div>
                {block.pills.map((p: string, i: number) => (
                  <Pill key={i} text={p} />
                ))}
              </div>
            </div>
            {block.priority_items.length > 0 && (
              <IvoryPanel badge="!" title="Prioritas Berikutnya">
                {block.priority_items.map((p: any) => (
                  <div key={p.letter} className="flex items-start gap-2 text-xs">
                    <span
                      className="w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-black text-white shrink-0"
                      style={{ background: C.goldMain }}
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

    case "closing":
      return (
        <div className="py-6 text-center">
          <div className="text-2xl font-bold mb-3" style={{ fontFamily: TITLE_FONT }}>
            Terima Kasih
          </div>
          <div className="text-sm mb-2">{block.title}</div>
          <div className="text-xs italic" style={{ color: C.goldLight }}>
            Diskusi dan pertanyaan dipersilakan.
          </div>
        </div>
      );

    default:
      return null;
  }
}
