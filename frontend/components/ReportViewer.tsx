"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import type { Discrepancy, TokenUsage } from "@/lib/types";

interface Props {
  asset: string | null;
  asOfDate: string | null;
  report: string;
  discrepancies?: Discrepancy[] | null;
  openQuestions?: string[] | null;
  durationMs?: number | null;
  tokens?: TokenUsage | null;
  jobId?: string | null;
}

function downloadMarkdown(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function ReportViewer({
  asset,
  asOfDate,
  report,
  discrepancies,
  openQuestions,
  durationMs,
  tokens,
  jobId,
}: Props) {
  const filename = `${asset ?? "report"}_${asOfDate ?? "report"}.md`;

  return (
    <section className="mt-8 rounded-lg border border-neutral-200 bg-white p-6 shadow-sm dark:border-neutral-800 dark:bg-neutral-950">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-neutral-200 pb-3 dark:border-neutral-800">
        <div className="flex flex-wrap items-baseline gap-2 text-sm text-neutral-500 dark:text-neutral-400">
          {durationMs != null && <span>소요 {(durationMs / 1000).toFixed(1)}s</span>}
          {tokens?.total != null && (
            <span>· 토큰 {tokens.total.toLocaleString()}</span>
          )}
          {jobId && (
            <span>
              · job{" "}
              <a
                href={`/analyze/${jobId}`}
                className="font-mono text-blue-600 underline hover:text-blue-800"
              >
                {jobId.slice(0, 8)}
              </a>
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={() => downloadMarkdown(filename, report)}
          className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm font-medium text-neutral-700 hover:bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:bg-neutral-800"
        >
          ⬇ 마크다운 다운로드
        </button>
      </header>

      <article className="prose prose-sm max-w-none dark:prose-invert prose-headings:scroll-mt-20 prose-table:text-xs prose-pre:text-xs">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
      </article>

      {(discrepancies?.length ?? 0) > 0 && (
        <details className="mt-6 rounded border border-neutral-200 bg-neutral-50 p-4 dark:border-neutral-800 dark:bg-neutral-900">
          <summary className="cursor-pointer text-sm font-semibold">
            🔍 리뷰어가 식별한 데이터 모순 ({discrepancies!.length})
          </summary>
          <ul className="mt-3 space-y-2 text-xs">
            {discrepancies!.map((d, i) => (
              <li key={i} className="rounded bg-white p-2 dark:bg-neutral-950">
                <p className="font-semibold">{d.metric}</p>
                <p className="text-neutral-500">값: {d.values.join(" / ")}</p>
                {d.resolution && (
                  <p className="text-emerald-700 dark:text-emerald-300">
                    → {d.resolution}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </details>
      )}

      {(openQuestions?.length ?? 0) > 0 && (
        <details className="mt-3 rounded border border-neutral-200 bg-neutral-50 p-4 dark:border-neutral-800 dark:bg-neutral-900">
          <summary className="cursor-pointer text-sm font-semibold">
            ❓ 미해결 이슈 ({openQuestions!.length})
          </summary>
          <ul className="mt-3 list-disc space-y-1 pl-5 text-xs">
            {openQuestions!.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
