"use client";

import { AgentCard, type CardStatus } from "@/components/AgentCard";
import type { AnalysisState } from "@/lib/state";
import type { AgentRole } from "@/lib/types";

interface Props {
  state: AnalysisState;
}

function dataFetchStatus(phase: AnalysisState["phase"]): CardStatus {
  if (phase === "idle" || phase === "starting") return "pending";
  if (phase === "fetching") return "running";
  return "done";
}

interface AnalystSpec {
  role: AgentRole;
  title: string;
  subtitle: string;
}

const ANALYSTS: AnalystSpec[] = [
  { role: "fundamental", title: "② 펀더멘털", subtitle: "재무·밸류에이션" },
  { role: "technical", title: "③ 기술적", subtitle: "추세·모멘텀·지지저항" },
  { role: "industry", title: "④ 산업·경쟁", subtitle: "사이클·점유율·경쟁사" },
  { role: "macro", title: "⑤ 거시", subtitle: "금리·환율·CapEx" },
  { role: "sentiment", title: "⑥ 시장 심리", subtitle: "뉴스·수급·컨센서스" },
];

export function ProgressTracker({ state }: Props) {
  if (state.phase === "idle") return null;

  const summary = state.dataFetchSummary;

  return (
    <section className="mt-8 space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <AgentCard
          title="① 데이터 수집"
          subtitle="yfinance · FRED · News"
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

        {ANALYSTS.map((spec) => {
          const agent = state.agents[spec.role];
          return (
            <AgentCard
              key={spec.role}
              title={spec.title}
              subtitle={spec.subtitle}
              status={agent.status}
              tokens={agent.tokens}
              retried={agent.retried}
              error={agent.error}
            />
          );
        })}
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <AgentCard
          title="⑦ 통합·리뷰"
          subtitle="교차 검증 + 마크다운"
          status={state.reviewer.status}
          tokens={state.reviewer.tokens}
          retried={state.reviewer.retried}
          error={state.reviewer.error}
        />
      </div>

      {state.errors.length > 0 && (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-200">
          <p className="font-semibold">경고/오류 로그</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5">
            {state.errors.map((e, i) => (
              <li key={i}>
                <span className="font-mono">
                  [{e.stage}
                  {e.agent ? `:${e.agent}` : ""}]
                </span>{" "}
                {e.message}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
