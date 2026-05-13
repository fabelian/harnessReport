"use client";

import { useEffect, useState } from "react";

import { ReportViewer } from "@/components/ReportViewer";
import { api } from "@/lib/api";
import type { JobRecord } from "@/lib/types";

interface Props {
  params: { jobId: string };
}

export default function JobPage({ params }: Props) {
  const [job, setJob] = useState<JobRecord | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .job(params.jobId)
      .then(setJob)
      .catch((e) => setError(String(e)));
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
