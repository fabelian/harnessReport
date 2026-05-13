"use client";

import clsx from "clsx";

import type { TokenUsage } from "@/lib/types";

export type CardStatus = "pending" | "running" | "done" | "failed";

interface Props {
  title: string;
  subtitle?: string;
  status: CardStatus;
  tokens?: TokenUsage | null;
  retried?: boolean;
  error?: string | null;
  children?: React.ReactNode;
}

const STATUS_LABEL: Record<CardStatus, string> = {
  pending: "대기",
  running: "진행 중",
  done: "완료",
  failed: "실패",
};

const STATUS_CLASS: Record<CardStatus, string> = {
  pending: "bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400",
  running: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  done: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-300",
  failed: "bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-300",
};

export function AgentCard({
  title,
  subtitle,
  status,
  tokens,
  retried,
  error,
  children,
}: Props) {
  return (
    <div
      className={clsx(
        "rounded-lg border p-4 transition-shadow",
        status === "running"
          ? "border-blue-300 shadow-md dark:border-blue-700"
          : "border-neutral-200 dark:border-neutral-800",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">
            {title}
          </h3>
          {subtitle && (
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              {subtitle}
            </p>
          )}
        </div>
        <span
          className={clsx(
            "rounded-full px-2 py-0.5 text-xs font-medium",
            STATUS_CLASS[status],
          )}
        >
          {STATUS_LABEL[status]}
          {status === "running" && (
            <span className="ml-1 inline-block animate-pulse">·</span>
          )}
        </span>
      </div>

      {status === "running" && (
        <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-800">
          <div className="h-full w-1/3 animate-[progress_1.2s_ease-in-out_infinite] bg-blue-500" />
        </div>
      )}

      {(tokens || retried) && status === "done" && (
        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-neutral-500 dark:text-neutral-400">
          {tokens?.total != null && (
            <span>
              tokens: {tokens.total.toLocaleString()}{" "}
              <span className="text-neutral-400">
                ({tokens.prompt ?? 0} in · {tokens.completion ?? 0} out)
              </span>
            </span>
          )}
          {retried && (
            <span className="text-amber-600 dark:text-amber-400">
              · 1회 재시도
            </span>
          )}
        </div>
      )}

      {error && (
        <p className="mt-3 rounded bg-rose-50 px-3 py-2 text-xs text-rose-800 dark:bg-rose-950/40 dark:text-rose-300">
          {error}
        </p>
      )}

      {children && <div className="mt-3">{children}</div>}
    </div>
  );
}
