import Link from "next/link";
import type { Direction, RoundPage } from "@schema";
import { ConfirmedChip } from "@/components/confirmed-chip";
import { Sparkline } from "@/components/sparkline";
import { Chip, ProvenanceBadge } from "@/components/ui/badge";
import { fmtDateTime, fmtDay } from "@/lib/format";
import { DIRECTION_LABEL } from "@/lib/labels";
import { cn } from "@/lib/utils";

const DIR: Record<string, string> = { up: "↑", down: "↓", same: "＝", unknown: "?" };

/**
 * RoundPage 四段固定（CLAUDE.md §5）。
 * headingLevel=1 時自己是頁面主標（醫師唯讀頁）；嵌進其他頁面時傳 2，四段改用 h3。
 */
export function RoundPageView({
  page,
  showLinks = true,
  headingLevel = 1,
}: {
  page: RoundPage;
  showLinks?: boolean;
  headingLevel?: 1 | 2;
}) {
  const approved = page.status === "approved";
  const Title = headingLevel === 1 ? "h1" : "h2";
  const Section = headingLevel === 1 ? "h2" : "h3";
  return (
    <article className={cn("print-page mx-auto max-w-[190mm] p-6 shadow-[var(--shadow-card)]", approved ? "confirmed" : "ai-draft")}>
      <header className="mb-4 flex flex-wrap items-baseline gap-2 border-b border-line pb-3">
        <Title className="text-xl font-medium">RoundPage · 熟悉頁</Title>
        <span className="text-sm text-ink-2">
          自 {fmtDay(page.since)} 起 · 產生 {fmtDateTime(page.generated_at)}
        </span>
        <span className="ml-auto">
          {approved ? <ConfirmedChip by={page.confirmed_by} at={page.provenance.ts} /> : <Chip tone="primary">AI 草稿，待護理長確認</Chip>}
        </span>
      </header>

      <section className="mb-4">
        <Section className="text-base font-medium">① 這是誰</Section>
        <p className="mt-1">{page.who}</p>
        <ul className="mt-2 grid gap-x-4 gap-y-1 text-sm text-ink-2 sm:grid-cols-2">
          {page.baseline_summary.map((b, i) => (
            <li key={i} className="break-words">{b}</li>
          ))}
        </ul>
      </section>

      <section className="mb-4">
        <Section className="text-base font-medium">② 自上次巡診變了什麼（異常優先）</Section>
        {page.cross_dimension_signal && <p className="mt-1 rounded-[8px] bg-warn-fill px-2 py-1 text-sm text-warn-ink">{page.cross_dimension_signal}</p>}
        <ul className="mt-2 space-y-1 text-sm">
          {page.changes.length === 0 && <li className="text-ink-2">自上次巡診沒有明顯變化。</li>}
          {page.changes.map((c) => (
            <li key={c.dimension} className="flex flex-wrap items-baseline gap-2">
              <span className={c.is_abnormal ? "font-medium text-danger-ink" : "text-ink"}>
                <span aria-hidden="true">{DIR[c.direction]}</span>
                <span className="sr-only">{DIRECTION_LABEL[c.direction as Direction] ?? c.direction}</span> {c.summary}
              </span>
              <span className="text-xs text-ink-2" translate="no">
                {c.evidence_refs.slice(0, 3).map((r) =>
                  showLinks ? (
                    <Link key={r} href={`/record/${page.patient_id}#${r}`} className="mr-1 inline-flex min-h-6 items-center hover:text-primary hover:underline">
                      [{r.slice(0, 19)}]
                    </Link>
                  ) : (
                    <span key={r} className="mr-1 inline-flex min-h-6 items-center">[{r.slice(0, 19)}]</span>
                  ),
                )}
              </span>
            </li>
          ))}
        </ul>
        {page.chart.length > 0 && (
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            {page.chart.map((s) => (
              <Sparkline key={s.dimension} series={s} />
            ))}
          </div>
        )}
      </section>

      <section className="mb-4">
        <Section className="text-base font-medium">③ 上次醫囑做了沒、有效嗎</Section>
        <ul className="mt-1 space-y-1 text-sm">
          {page.order_followup.length === 0 && <li className="text-ink-2">上次沒有醫囑。</li>}
          {page.order_followup.map((o, i) => (
            <li key={i} className="flex flex-wrap gap-2">
              <span>{o.text}</span>
              <Chip tone={o.done == null ? "neutral" : o.done ? "ok" : "warn"}>{o.done == null ? "執行未知" : o.done ? "已執行" : "未執行"}</Chip>
              <Chip tone={o.effective == null ? "neutral" : o.effective ? "ok" : "danger"}>{o.effective == null ? "效果未知" : o.effective ? "有效" : "未改善"}</Chip>
              {o.note && <span className="text-ink-2">{o.note}</span>}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <Section className="text-base font-medium">④ 請醫師確認的事</Section>
        {page.questions.length === 0 ? (
          <p className="mt-1 text-sm text-ink-2">沒有需要醫師確認的事。</p>
        ) : (
          <ol className="mt-1 list-decimal space-y-1 pl-5 text-sm">
            {page.questions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ol>
        )}
      </section>

      <footer className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-2 text-xs text-ink-2">
        <ProvenanceBadge source={page.provenance.source} author={page.provenance.author} />
        <span>generated_from {page.generated_from.length} 筆 timeline</span>
        <span className="ml-auto">AI 只起草，護理長定稿；④ 為提問，非診斷或處置建議。</span>
      </footer>
    </article>
  );
}
