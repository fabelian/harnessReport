// Reducer driving the live analysis page.
//
// Folds the SSE event stream into a structured state shape that the UI can
// render without inspecting individual events, and also accumulates a
// chronological `logs` array so the frontend can show exactly where the run
// is at — including which external API call (yfinance, FRED, news provider,
// OpenRouter) is currently in flight or where a failure happened.

import type {
  AgentDoneData,
  AgentRole,
  AgentStepData,
  DataFetchDoneData,
  DataFetchProgressData,
  DoneData,
  ErrorData,
  IndustryOutput,
  JobStartData,
  LogEntry,
  MacroOutput,
  ReviewerDoneData,
  ReviewerStepData,
  SentimentOutput,
  SSEMessage,
  FundamentalOutput,
  TechnicalOutput,
  TokenUsage,
} from "@/lib/types";

export type Phase =
  | "idle"
  | "starting"
  | "fetching"
  | "analyzing"
  | "reviewing"
  | "done"
  | "failed";

export type AgentOutput =
  | FundamentalOutput
  | TechnicalOutput
  | IndustryOutput
  | MacroOutput
  | SentimentOutput;

export interface AgentState {
  status: "pending" | "running" | "done" | "failed";
  output: AgentOutput | null;
  tokens: TokenUsage | null;
  retried: boolean;
  error: string | null;
}

export interface ReviewerState {
  status: "pending" | "running" | "done" | "failed";
  report: string | null;
  discrepancies: any[];
  openQuestions: string[];
  tokens: TokenUsage | null;
  retried: boolean;
  error: string | null;
}

export const ANALYST_ROLES = [
  "fundamental",
  "technical",
  "industry",
  "macro",
  "sentiment",
] as const satisfies readonly AgentRole[];

export type AgentsState = Record<AgentRole, AgentState>;

export interface AnalysisState {
  phase: Phase;
  jobId: string | null;
  asset: string | null;
  asOfDate: string | null;
  model: string | null;
  dataFetchSummary: DataFetchDoneData["summary"] | null;
  agents: AgentsState;
  reviewer: ReviewerState;
  errors: ErrorData[];
  logs: LogEntry[];
  durationMs: number | null;
  tokens: TokenUsage | null;
}

function blankAgent(): AgentState {
  return {
    status: "pending",
    output: null,
    tokens: null,
    retried: false,
    error: null,
  };
}

function blankReviewer(): ReviewerState {
  return {
    status: "pending",
    report: null,
    discrepancies: [],
    openQuestions: [],
    tokens: null,
    retried: false,
    error: null,
  };
}

function blankAgents(): AgentsState {
  return ANALYST_ROLES.reduce(
    (acc, role) => {
      acc[role] = blankAgent();
      return acc;
    },
    {} as AgentsState,
  );
}

export const initialState: AnalysisState = {
  phase: "idle",
  jobId: null,
  asset: null,
  asOfDate: null,
  model: null,
  dataFetchSummary: null,
  agents: blankAgents(),
  reviewer: blankReviewer(),
  errors: [],
  logs: [],
  durationMs: null,
  tokens: null,
};

export type Action =
  | { type: "RESET" }
  | { type: "EVENT"; msg: SSEMessage }
  | { type: "STREAM_FAILED"; message: string };

function isAnalystRole(role: string | undefined): role is AgentRole {
  return !!role && (ANALYST_ROLES as readonly string[]).includes(role);
}

function fmtElapsed(ms?: number | null): string {
  if (ms === undefined || ms === null) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Build a LogEntry from an SSE message. Returns null if the event is not
 * worth surfacing (extremely unlikely — we log everything for visibility). */
function logFromMessage(msg: SSEMessage): LogEntry | null {
  const ts = Date.now();
  const elapsedMs = (msg.data as { elapsedMs?: number })?.elapsedMs;
  switch (msg.event) {
    case "job_start": {
      const d = msg.data as JobStartData;
      return {
        ts,
        elapsedMs,
        stage: "job",
        level: "info",
        message: `job_start ${d.jobId.slice(0, 8)} | ${d.asset} | ${d.model}`,
      };
    }
    case "data_fetch_start":
      return {
        ts,
        elapsedMs,
        stage: "data_fetch",
        level: "info",
        message: "data_fetch start",
      };
    case "data_fetch_progress": {
      const d = msg.data as DataFetchProgressData;
      const elapsed = fmtElapsed(d.sourceElapsedMs ?? null);
      return {
        ts,
        elapsedMs,
        stage: `data_fetch:${d.source}`,
        level: d.status === "error" ? "error" : "info",
        message:
          d.status === "start"
            ? `${d.source} → start`
            : `${d.source} → ${d.status}${elapsed ? ` (${elapsed})` : ""}`,
      };
    }
    case "data_fetch_done": {
      const d = msg.data as DataFetchDoneData;
      const s = d.summary;
      return {
        ts,
        elapsedMs,
        stage: "data_fetch",
        level: d.errors?.length ? "warn" : "info",
        message: `data_fetch done | price_rows=${s.price_rows} quarters=${s.quarters} news=${s.news_count} macro=${s.macro_available}${d.errors?.length ? ` | errors=${d.errors.length}` : ""}`,
        detail: d.errors?.length ? d.errors.join("\n") : undefined,
      };
    }
    case "agent_start": {
      const role = (msg.data as { agent: string }).agent;
      return {
        ts,
        elapsedMs,
        stage: `agent:${role}`,
        level: "info",
        message: "start",
      };
    }
    case "agent_step": {
      const d = msg.data as AgentStepData;
      const parts: string[] = [d.step];
      if (d.attempt) parts.push(`#${d.attempt}`);
      if (d.elapsedMs !== undefined && d.step.includes("response"))
        parts.push(`${fmtElapsed(d.elapsedMs)}`);
      if (d.totalTokens != null) parts.push(`tokens=${d.totalTokens}`);
      if (d.finishReason) parts.push(`finish=${d.finishReason}`);
      if (d.errorType) parts.push(`${d.errorType}`);
      if (d.message) parts.push(`— ${d.message}`);
      if (d.reason) parts.push(`reason=${d.reason}`);
      const hasErr = d.step === "llm_error" || d.ok === false;
      return {
        ts,
        elapsedMs,
        stage: `agent:${d.agent}`,
        level: hasErr ? "warn" : "info",
        message: parts.join(" "),
      };
    }
    case "agent_done": {
      const d = msg.data as AgentDoneData & { elapsedMs?: number };
      return {
        ts,
        elapsedMs: d.elapsedMs ?? elapsedMs,
        stage: `agent:${d.agent}`,
        level: "info",
        message: `done${d.retried ? " (retried)" : ""} tokens=${d.tokens?.total ?? "?"}`,
      };
    }
    case "reviewer_start":
      return {
        ts,
        elapsedMs,
        stage: "reviewer",
        level: "info",
        message: "start",
      };
    case "reviewer_step": {
      const d = msg.data as ReviewerStepData;
      const parts: string[] = [d.step];
      if (d.attempt) parts.push(`#${d.attempt}`);
      if (d.elapsedMs !== undefined && d.step.includes("response"))
        parts.push(`${fmtElapsed(d.elapsedMs)}`);
      if (d.totalTokens != null) parts.push(`tokens=${d.totalTokens}`);
      if (d.finishReason) parts.push(`finish=${d.finishReason}`);
      if (d.errorType) parts.push(`${d.errorType}`);
      if (d.message) parts.push(`— ${d.message}`);
      if (d.reason) parts.push(`reason=${d.reason}`);
      const hasErr = d.step === "llm_error" || d.ok === false;
      return {
        ts,
        elapsedMs,
        stage: "reviewer",
        level: hasErr ? "warn" : "info",
        message: parts.join(" "),
      };
    }
    case "reviewer_done": {
      const d = msg.data as ReviewerDoneData & { elapsedMs?: number };
      return {
        ts,
        elapsedMs: (d as any).elapsedMs ?? elapsedMs,
        stage: "reviewer",
        level: "info",
        message: `done${d.retried ? " (retried)" : ""} tokens=${d.tokens?.total ?? "?"}`,
      };
    }
    case "error": {
      const d = msg.data as ErrorData;
      const stagePrefix = d.agent ? `${d.stage}:${d.agent}` : d.stage;
      return {
        ts,
        elapsedMs,
        stage: stagePrefix,
        level: "error",
        message: d.message,
        detail: [d.function, d.tracebackTail].filter(Boolean).join("\n\n"),
      };
    }
    case "done": {
      const d = msg.data as DoneData;
      return {
        ts,
        elapsedMs,
        stage: "job",
        level: d.ok ? "info" : "error",
        message: `done ok=${d.ok} duration=${fmtElapsed(d.durationMs)}${d.tokens?.total ? ` tokens=${d.tokens.total}` : ""}`,
      };
    }
    default:
      return null;
  }
}

export function reduce(state: AnalysisState, action: Action): AnalysisState {
  if (action.type === "RESET") return { ...initialState, agents: blankAgents(), logs: [] };
  if (action.type === "STREAM_FAILED") {
    const entry: LogEntry = {
      ts: Date.now(),
      stage: "stream",
      level: "error",
      message: action.message,
    };
    return {
      ...state,
      phase: "failed",
      errors: [...state.errors, { stage: "stream", message: action.message }],
      logs: [...state.logs, entry],
    };
  }

  // Append a log entry for every event.
  const entry = logFromMessage(action.msg);
  const logs = entry ? [...state.logs, entry] : state.logs;

  const { event, data } = action.msg;
  switch (event) {
    case "job_start": {
      const d = data as JobStartData;
      return {
        ...state,
        logs,
        phase: "starting",
        jobId: d.jobId,
        asset: d.asset,
        asOfDate: d.asOfDate,
        model: d.model,
      };
    }
    case "data_fetch_start":
      return { ...state, logs, phase: "fetching" };
    case "data_fetch_progress":
      return { ...state, logs };
    case "data_fetch_done": {
      const d = data as DataFetchDoneData;
      return {
        ...state,
        logs,
        phase: "analyzing",
        dataFetchSummary: d.summary,
        errors: d.errors?.length
          ? [
              ...state.errors,
              ...d.errors.map((m) => ({ stage: "data_fetch", message: m })),
            ]
          : state.errors,
      };
    }
    case "agent_start": {
      const role = (data as { agent: string }).agent;
      if (!isAnalystRole(role)) return { ...state, logs };
      return {
        ...state,
        logs,
        agents: {
          ...state.agents,
          [role]: { ...state.agents[role], status: "running" },
        },
      };
    }
    case "agent_step":
      return { ...state, logs };
    case "agent_done": {
      const d = data as AgentDoneData;
      if (!isAnalystRole(d.agent)) return { ...state, logs };
      return {
        ...state,
        logs,
        agents: {
          ...state.agents,
          [d.agent]: {
            status: "done",
            output: d.output,
            tokens: d.tokens,
            retried: d.retried,
            error: null,
          },
        },
      };
    }
    case "reviewer_start":
      return {
        ...state,
        logs,
        phase: "reviewing",
        reviewer: { ...state.reviewer, status: "running" },
      };
    case "reviewer_step":
      return { ...state, logs };
    case "reviewer_done": {
      const d = data as ReviewerDoneData;
      return {
        ...state,
        logs,
        reviewer: {
          status: "done",
          report: d.report,
          discrepancies: d.discrepancies ?? [],
          openQuestions: d.openQuestions ?? [],
          tokens: d.tokens,
          retried: d.retried,
          error: null,
        },
      };
    }
    case "error": {
      const d = data as ErrorData;
      const next = { ...state, logs, errors: [...state.errors, d] };
      if (d.stage === "agent" && isAnalystRole(d.agent)) {
        next.agents = {
          ...state.agents,
          [d.agent]: {
            ...state.agents[d.agent],
            status: "failed",
            error: d.message,
          },
        };
      } else if (d.stage === "reviewer") {
        next.reviewer = { ...state.reviewer, status: "failed", error: d.message };
      }
      return next;
    }
    case "done": {
      const d = data as DoneData;
      return {
        ...state,
        logs,
        phase: d.ok ? "done" : "failed",
        durationMs: d.durationMs,
        tokens: d.tokens ?? state.tokens,
      };
    }
    default:
      return { ...state, logs };
  }
}
