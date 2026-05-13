"use client";

import { AgentCard, type CardStatus } from "@/components/AgentCard";
import type { AnalysisState } from "@/lib/state";

interface Props {
  state: AnalysisState;
}

function dataFetchStatus(phase: AnalysisState["phase"]): CardStatus {
  if (phase === "idle" || phase === "starting") return "pending";
  if (phase === "fetching") return "running";
  return "done";
}

export function ProgressTracker({ state }: Props) {
  if (state.phase === "idle") return null;

  const summary = state.dataFetchSummary;

  return (
    <section className="mt-8 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <AgentCard
        title="① 데이터 수집"
        subtitle="yfinance · SEC · FRED · News"
        status={dataFetchStatus(state.phase)}
      >
        {summary && (
          <ul className="mt-1 space-y-0.5 text-xs text-neutral-600 dark:text-neutral-400">
            <li>가격 {summary.price_rows}봉</li>
            <li>분기 {summary.quarters}건</li>
            <li>뉴스 {summary.news_count}건</li>
            <li>거시 {summary.macro_available ? "있음" : "없음"}</li>
          </ul>
        )}
      </AgentCard>

      <AgentCard
        title="② 펀더멘털 분석"
        subtitle="재무·밸류에이션·시나리오"
        status={state.agents.fundamental.status}
        tokens={state.agents.fundamental.tokens}
        retried={state.agents.fundamental.retried}
        error={state.agents.fundamental.error}
      />

      <AgentCard
        title="③ 기술적 분석"
        subtitle="추세·모멘텀·지지저항"
        status={state.agents.technical.status}
        tokens={state.agents.technical.tokens}
        retried={state.agents.technical.retried}
        error={state.agents.technical.error}
      />

      <AgentCard
        title="④ 통합·리뷰"
        subtitle="교차 검증 + 마크다운 보고서"
        status={state.reviewer.status}
        tokens={state.reviewer.tokens}
        retried={state.reviewer.retried}
        error={state.reviewer.error}
      />

      {state.errors.length > 0 && (
        <div className="md:col-span-2 lg:col-span-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-200">
          <p className="font-semibold">경고/오류 로그</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5">
            {state.errors.map((e, i) => (
              <li key={i}>
                <span className="font-mono">[{e.stage}{e.agent ? `:${e.agent}` : ""}]</span>{" "}
                {e.message}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
