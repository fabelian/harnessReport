// Reducer driving the live analysis page.
//
// Folds the SSE event stream into a structured state shape that the UI can
// render without inspecting individual events.

import type {
  AgentDoneData,
  DataFetchDoneData,
  DoneData,
  ErrorData,
  FundamentalOutput,
  JobStartData,
  ReviewerDoneData,
  SSEMessage,
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

export interface AgentState {
  status: "pending" | "running" | "done" | "failed";
  output: FundamentalOutput | TechnicalOutput | null;
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

export interface AnalysisState {
  phase: Phase;
  jobId: string | null;
  asset: string | null;
  asOfDate: string | null;
  model: string | null;
  dataFetchSummary: DataFetchDoneData["summary"] | null;
  agents: {
    fundamental: AgentState;
    technical: AgentState;
  };
  reviewer: ReviewerState;
  errors: ErrorData[];
  durationMs: number | null;
  tokens: TokenUsage | null;
}

export const initialState: AnalysisState = {
  phase: "idle",
  jobId: null,
  asset: null,
  asOfDate: null,
  model: null,
  dataFetchSummary: null,
  agents: {
    fundamental: blankAgent(),
    technical: blankAgent(),
  },
  reviewer: blankReviewer(),
  errors: [],
  durationMs: null,
  tokens: null,
};

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

export type Action =
  | { type: "RESET" }
  | { type: "EVENT"; msg: SSEMessage }
  | { type: "STREAM_FAILED"; message: string };

export function reduce(state: AnalysisState, action: Action): AnalysisState {
  if (action.type === "RESET") return { ...initialState };
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
          ? [...state.errors, ...d.errors.map((m) => ({ stage: "data_fetch", message: m }))]
          : state.errors,
      };
    }
    case "agent_start": {
      const agent = (data as { agent: "fundamental" | "technical" }).agent;
      return {
        ...state,
        agents: {
          ...state.agents,
          [agent]: { ...state.agents[agent], status: "running" },
        },
      };
    }
    case "agent_done": {
      const d = data as AgentDoneData;
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
      return { ...state, phase: "reviewing", reviewer: { ...state.reviewer, status: "running" } };
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
      if (d.stage === "agent" && d.agent && (d.agent === "fundamental" || d.agent === "technical")) {
        next.agents = {
          ...state.agents,
          [d.agent]: { ...state.agents[d.agent], status: "failed", error: d.message },
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
