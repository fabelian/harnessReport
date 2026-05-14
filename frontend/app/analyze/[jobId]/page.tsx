"use client";

import { useEffect, useState } from "react";

import { ReportViewer } from "@/components/ReportViewer";
import { api } from "@/lib/api";
import type { JobRecord } from "@/lib/types";

interface Props {
  params: { jobId: string };
}

// Polling interval while the job is still running. The backend persists
// jobs so this page is the fallback when SSE drops mid-stream (notably on
// iOS Safari, where fetch streams frequently abort).
const POLL_INTERVAL_MS = 5000;

export default function JobPage({ params }: Props) {
  const [job, setJob] = useState<JobRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const fetchOnce = () => {
      api
        .job(params.jobId)
        .then((j) => {
          if (cancelled) return;
          setJob(j);
          if (j.status === "running") {
            timer = setTimeout(fetchOnce, POLL_INTERVAL_MS);
          }
        })
        .catch((e) => {
          if (cancelled) return;
          setError(String(e));
        });
    };

    fetchOnce();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [params.jobId]);

  if (error) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <a href="/" className="text-sm text-blue-600 underline">
          ← 새 분석
        </a>
        <h1 className="mt-4 text-xl font-semibold">작업을 찾을 수 없습니다</h1>
        <p className="mt-2 text-sm text-rose-700">{error}</p>
      </main>
    );
  }

  if (!job) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-10">
        <p className="text-sm text-neutral-500">로딩 중…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="mb-6 flex items-baseline justify-between">
        <div>
          <a href="/" className="text-xs text-blue-600 underline">
            ← 새 분석
          </a>
          <h1 className="mt-1 text-2xl font-bold tracking-tight">
            {job.asset}{" "}
            <span className="text-base font-normal text-neutral-500">
              ({job.as_of_date})
            </span>
          </h1>
          <p className="text-xs text-neutral-500">
            {job.status} · model {job.model} · created {job.created_at}
          </p>
        </div>
      </header>

      {job.status === "running" && (
        <p className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200">
          분석 진행 중… 5초마다 자동 갱신됩니다. 완료되면 보고서가 표시됩니다.
        </p>
      )}

      {job.status === "failed" && (
        <p className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
          실패: {job.error}
        </p>
      )}

      {job.reviewer_report && (
        <ReportViewer
          asset={job.asset}
          asOfDate={job.as_of_date}
          report={job.reviewer_report}
          discrepancies={job.discrepancies}
          openQuestions={job.open_questions}
          durationMs={job.duration_ms ?? undefined}
          tokens={job.token_usage}
          jobId={job.id}
        />
      )}
    </main>
  );
}
