"use client";

import { useEffect, useRef, useState } from "react";

import type { LogEntry } from "@/lib/types";

interface Props {
  logs: LogEntry[];
}

const LEVEL_COLORS: Record<LogEntry["level"], string> = {
  info: "text-neutral-700 dark:text-neutral-300",
  warn: "text-amber-700 dark:text-amber-300",
  error: "text-rose-700 dark:text-rose-300",
};

const STAGE_BADGE: Record<LogEntry["level"], string> = {
  info: "bg-neutral-200 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300",
  warn: "bg-amber-200/70 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200",
  error: "bg-rose-200/70 text-rose-900 dark:bg-rose-900/40 dark:text-rose-200",
};

function fmtClock(ts: number): string {
  const d = new Date(ts);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

function fmtElapsed(ms?: number): string {
  if (ms === undefined || ms === null) return "      ";
  if (ms < 1000) return `+${String(ms).padStart(3, " ")}ms`;
  return `+${(ms / 1000).toFixed(1).padStart(4, " ")}s`;
}

export function LogPanel({ logs }: Props) {
  const [openDetails, setOpenDetails] = useState<Record<number, boolean>>({});
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const userScrolledRef = useRef(false);

  // Auto-scroll to newest unless user has scrolled up.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    if (!userScrolledRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [logs.length]);

  const onScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 30;
    userScrolledRef.current = !atBottom;
  };

  if (logs.length === 0) return null;

  return (
    <section className="mt-6 rounded-lg border border-neutral-200 bg-neutral-50 dark:border-neutral-800 dark:bg-neutral-950/50">
      <header className="flex items-center justify-between border-b border-neutral-200 px-4 py-2 dark:border-neutral-800">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-600 dark:text-neutral-400">
          작업 로그 ({logs.length})
        </h3>
        <button
          type="button"
          onClick={() => {
            const text = logs
              .map(
                (l) =>
                  `${fmtClock(l.ts)} ${fmtElapsed(l.elapsedMs)} [${l.stage}] ${l.message}${l.detail ? `\n  ${l.detail.replace(/\n/g, "\n  ")}` : ""}`,
              )
              .join("\n");
            void navigator.clipboard?.writeText(text);
          }}
          className="text-xs text-blue-600 hover:underline"
        >
          전체 복사
        </button>
      </header>
      <div
        ref={scrollRef}
        onScroll={onScroll}
        className="max-h-80 overflow-y-auto px-3 py-2 font-mono text-xs leading-relaxed"
      >
        {logs.map((entry, i) => {
          const isOpen = openDetails[i] ?? false;
          return (
            <div key={i} className={LEVEL_COLORS[entry.level]}>
              <div className="flex items-start gap-2">
                <span className="shrink-0 text-neutral-400">{fmtClock(entry.ts)}</span>
                <span className="shrink-0 text-neutral-400">
                  {fmtElapsed(entry.elapsedMs)}
                </span>
                <span
                  className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold ${STAGE_BADGE[entry.level]}`}
                >
                  {entry.stage}
                </span>
                <span className="break-all">{entry.message}</span>
                {entry.detail && (
                  <button
                    type="button"
                    onClick={() =>
                      setOpenDetails((s) => ({ ...s, [i]: !isOpen }))
                    }
                    className="ml-1 shrink-0 text-[10px] text-blue-600 hover:underline"
                  >
                    {isOpen ? "닫기" : "상세"}
                  </button>
                )}
              </div>
              {isOpen && entry.detail && (
                <pre className="mt-1 ml-16 whitespace-pre-wrap rounded bg-neutral-100 p-2 text-[11px] text-neutral-800 dark:bg-neutral-900 dark:text-neutral-300">
                  {entry.detail}
                </pre>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
