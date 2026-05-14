"use client";

import { useRouter } from "next/navigation";
import { useCallback, useReducer, useRef, useState } from "react";

import { InputForm } from "@/components/InputForm";
import { LogPanel } from "@/components/LogPanel";
import { ProgressTracker } from "@/components/ProgressTracker";
import { ReportViewer } from "@/components/ReportViewer";
import { ANALYST_ROLES, initialState, reduce } from "@/lib/state";
import { streamAnalysis } from "@/lib/sse";
import type { AnalyzeRequest } from "@/lib/types";

/** True for browsers where a long fetch SSE stream is unreliable.
 * iOS Safari + cellular is the canonical case ("Load failed" on first
 * idle gap). For these we skip SSE entirely and use the start+poll path. */
function streamingUnreliable(): boolean {
  if (typeof navigator === "undefined") return false;
  const ua = navigator.userAgent;
  return (
    /iP(hone|ad|od)/.test(ua) &&
    /Safari/.test(ua) &&
    !/CriOS|FxiOS|EdgiOS/.test(ua)
  );
}

export default function HomePage() {
  const router = useRouter();
  const [state, dispatch] = useReducer(reduce, initialState);
  const [running, setRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const startDetached = useCallback(
    async (req: AnalyzeRequest) => {
      const resp = await fetch("/api/analyze/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      });
      if (!resp.ok) {
        const body = await resp.text().catch(() => "");
        throw new Error(`/api/analyze/start ${resp.status}: ${body || resp.statusText}`);
      }
      const data = (await resp.json()) as { jobId: string };
      router.push(`/analyze/${data.jobId}`);
    },
    [router],
  );

  const handleSubmit = useCallback(
    async (req: AnalyzeRequest) => {
      dispatch({ type: "RESET" });

      if (streamingUnreliable()) {
        // Mobile Safari / cellular path — go straight to background job.
        setRunning(true);
        try {
          await startDetached(req);
        } catch (err) {
          const message =
            err && typeof err === "object" && "message" in err
              ? String((err as { message?: unknown }).message ?? err)
              : String(err);
          dispatch({ type: "STREAM_FAILED", message });
        } finally {
          setRunning(false);
        }
        return;
      }

      setRunning(true);
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        for await (const msg of streamAnalysis(req, controller.signal)) {
          dispatch({ type: "EVENT", msg });
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        const message =
          err && typeof err === "object" && "message" in err
            ? String((err as { message?: unknown }).message ?? err)
            : String(err);
        dispatch({ type: "STREAM_FAILED", message });
      } finally {
        setRunning(false);
        abortRef.current = null;
      }
    },
    [startDetached],
  );

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reviewerReport = state.reviewer.report;

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-neutral-900 dark:text-neutral-100">
          Equity Research
        </h1>
        <p className="mt-1 text-sm text-neutral-500 dark:text-neutral-400">
          멀티 에이전트 주식 분석 — OpenRouter 기반 (Gemma 3 / GPT-OSS)
        </p>
      </header>

      <InputForm onSubmit={handleSubmit} disabled={running} />

      {running && (
        <button
          type="button"
          onClick={handleCancel}
          className="mt-3 text-xs text-neutral-500 underline hover:text-neutral-700"
        >
          진행 중인 요청 취소
        </button>
      )}

      <ProgressTracker state={state} />

      <LogPanel logs={state.logs} />

      {reviewerReport && (
        <ReportViewer
          asset={state.asset}
          asOfDate={state.asOfDate}
          report={reviewerReport}
          discrepancies={state.reviewer.discrepancies}
          openQuestions={state.reviewer.openQuestions}
          durationMs={state.durationMs}
          tokens={state.tokens}
          jobId={state.jobId}
        />
      )}

      {state.phase === "failed" && !reviewerReport && (
        <section className="mt-6 rounded-lg border border-rose-200 bg-rose-50 p-6 text-sm text-rose-900 dark:border-rose-800 dark:bg-rose-950/30 dark:text-rose-200">
          <h2 className="font-semibold">분석 실패</h2>
          {(() => {
            const agentErrors = ANALYST_ROLES.flatMap((role) => {
              const a = state.agents[role];
              return a.status === "failed" && a.error
                ? [{ stage: "agent", agent: role, message: a.error }]
                : [];
            });
            const reviewerError =
              state.reviewer.status === "failed" && state.reviewer.error
                ? [{ stage: "reviewer", message: state.reviewer.error }]
                : [];
            const all = [...state.errors, ...agentErrors, ...reviewerError];
            return (
              <>
                {all.length === 0 ? (
                  <p className="mt-1">
                    스트림이 종료됐지만 오류 이벤트가 도착하지 않았습니다. 위 로그
                    마지막 줄을 확인하세요.
                  </p>
                ) : (
                  <ul className="mt-2 space-y-1.5">
                    {all.map((e, i) => (
                      <li key={i} className="font-mono text-xs">
                        <span className="rounded bg-rose-200/60 px-1.5 py-0.5 text-rose-950 dark:bg-rose-900/40 dark:text-rose-100">
                          {e.stage}
                          {"agent" in e && e.agent ? `:${e.agent}` : ""}
                        </span>{" "}
                        <span className="break-all">{e.message}</span>
                      </li>
                    ))}
                  </ul>
                )}
                {state.jobId && (
                  <p className="mt-3 text-xs">
                    백엔드는 계속 진행 중일 수 있습니다 →{" "}
                    <a
                      href={`/analyze/${state.jobId}`}
                      className="text-blue-700 underline dark:text-blue-400"
                    >
                      작업 페이지에서 결과 확인
                    </a>
                  </p>
                )}
              </>
            );
          })()}
        </section>
      )}
    </main>
  );
}
