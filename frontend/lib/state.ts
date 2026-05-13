// Reducer driving the live analysis page.
//
// Folds the SSE event stream into a structured state shape that the UI can
// render without inspecting individual events.

import type {
  AgentDoneData,
  AgentRole,
  DataFetchDoneData,
  DoneData,
  ErrorData,
  IndustryOutput,
  JobStartData,
  MacroOutput,
  ReviewerDoneData,
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

export function reduce(state: AnalysisState, action: Action): AnalysisState {
  if (action.type === "RESET") return { ...initialState, agents: blankAgents() };
  if (action.type === "STREAM_FAILED") {
    return {
      ...state,
      phase: "failed",
      errors: [
        ...state.errors,
        { stage: "stream", message: action.message },
      ],
    };
  }

  const { event, data } = action.msg;
  switch (event) {
    case "job_start": {
      const d = data as JobStartData;
      return {
        ...state,
        phase: "starting",
        jobId: d.jobId,
        asset: d.asset,
        asOfDate: d.asOfDate,
        model: d.model,
      };
    }
    case "data_fetch_start":
      return { ...state, phase: "fetching" };
    case "data_fetch_done": {
      const d = data as DataFetchDoneData;
      return {
        ...state,
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
      if (!isAnalystRole(role)) return state;
      return {
        ...state,
        agents: {
          ...state.agents,
          [role]: { ...state.agents[role], status: "running" },
        },
      };
    }
    case "agent_done": {
      const d = data as AgentDoneData;
      if (!isAnalystRole(d.agent)) return state;
      return {
        ...state,
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
        phase: "reviewing",
        reviewer: { ...state.reviewer, status: "running" },
      };
    case "reviewer_done": {
      const d = data as ReviewerDoneData;
      return {
        ...state,
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
      const next = { ...state, errors: [...state.errors, d] };
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
        phase: d.ok ? "done" : "failed",
        durationMs: d.durationMs,
        tokens: d.tokens ?? state.tokens,
      };
    }
    default:
      return state;
  }
}
