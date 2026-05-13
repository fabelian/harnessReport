"use client";

import { useCallback, useReducer, useRef, useState } from "react";

import { InputForm } from "@/components/InputForm";
import { ProgressTracker } from "@/components/ProgressTracker";
import { ReportViewer } from "@/components/ReportViewer";
import { initialState, reduce } from "@/lib/state";
import { streamAnalysis } from "@/lib/sse";
import type { AnalyzeRequest } from "@/lib/types";

export default function HomePage() {
  const [state, dispatch] = useReducer(reduce, initialState);
  const [running, setRunning] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const handleSubmit = useCallback(async (req: AnalyzeRequest) => {
    dispatch({ type: "RESET" });
    setRunning(true);
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      for await (const msg of streamAnalysis(req, controller.signal)) {
        dispatch({ type: "EVENT", msg });
      }
    } catch (err) {
      const message =
        err && typeof err === "object" && "message" in err
          ? String((err as { message?: unknown }).message ?? err)
          : String(err);
      dispatch({ type: "STREAM_FAILED", message });
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }, []);

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
        <section className="mt-8 rounded-lg border border-rose-200 bg-rose-50 p-6 text-sm text-rose-900 dark:border-rose-800 dark:bg-rose-950/30 dark:text-rose-200">
          <h2 className="font-semibold">분석 실패</h2>
          <p className="mt-1">
            아래 오류 로그를 확인하세요. 백엔드 OPENROUTER_API_KEY 또는 외부 API
            상태를 점검하세요.
          </p>
        </section>
      )}
    </main>
  );
}
