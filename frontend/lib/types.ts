// Mirror of backend Pydantic schemas. Keep this file in sync with
// backend/app/schemas/{inputs,outputs,events,data}.py.

// --- Requests ---------------------------------------------------------------

export type ModelChoice =
  | "google/gemma-3-27b-it"
  | "openai/gpt-oss-120b"
  | "deepseek/deepseek-v4-pro";

export interface AnalyzeRequest {
  asset: string;
  asOfDate: string; // YYYY-MM-DD
  model: ModelChoice;
}

export interface ModelEntry {
  id: ModelChoice;
  label: string;
  default: boolean;
}

export interface ModelsResponse {
  models: ModelEntry[];
  default: string;
  openrouter_configured: boolean;
}

// --- Outputs ---------------------------------------------------------------

export type Label = "fact" | "estimate" | "opinion";
export type ScenarioName = "bullish" | "base" | "bearish";

export interface Citation {
  source: string;
  url?: string | null;
  date_ref?: string | null;
}

export interface Claim {
  text: string;
  label: Label;
  citations: Citation[];
}

export interface Scenario {
  name: ScenarioName;
  triggers: string[];
  assumptions: string[];
  target_range_low?: number | null;
  target_range_high?: number | null;
  probability_qualitative?: "low" | "medium" | "high" | null;
  rationale?: string | null;
}

export interface FinancialTrendRow {
  period: string;
  revenue?: number | null;
  operating_income?: number | null;
  net_income?: number | null;
  eps?: number | null;
  op_margin?: number | null;
}

export interface ValuationMetric {
  metric: string;
  value?: number | null;
  peer_median?: number | null;
  note?: string | null;
}

export interface FundamentalOutput {
  summary: string;
  financial_trend: FinancialTrendRow[];
  valuation_metrics: ValuationMetric[];
  key_drivers: Claim[];
  risks: Claim[];
  scenarios: Scenario[];
  data_caveats: string[];
}

export interface Level {
  kind: "support" | "resistance";
  price: number;
  rationale?: string | null;
}

export interface TechnicalOutput {
  summary: string;
  trend: string;
  moving_averages: Record<string, number | null>;
  momentum: string;
  levels: Level[];
  scenarios: Scenario[];
  data_caveats: string[];
}

export interface CompetitorRow {
  name: string;
  position?: string | null;
  strength?: string | null;
  weakness?: string | null;
}

export interface IndustryOutput {
  summary: string;
  cycle_phase: string;
  demand_drivers: Claim[];
  supply_constraints: Claim[];
  competitors: CompetitorRow[];
  market_share_note?: string | null;
  risks: Claim[];
  data_caveats: string[];
}

export interface MacroFactor {
  label: string;
  value?: string | null;
  trend?: string | null;
  impact_on_asset?: string | null;
}

export interface MacroOutput {
  summary: string;
  factors: MacroFactor[];
  fx_view?: string | null;
  capex_cycle?: string | null;
  correlation_notes: string[];
  scenario_bias?: string | null;
  data_caveats: string[];
}

export interface SentimentSignal {
  name: string;
  direction: "bullish" | "neutral" | "bearish";
  strength?: "weak" | "moderate" | "strong" | null;
  evidence?: string | null;
}

export interface SentimentOutput {
  summary: string;
  overall_tone: "bullish" | "neutral" | "bearish";
  consensus_note?: string | null;
  news_signals: SentimentSignal[];
  flow_signals: SentimentSignal[];
  risks: Claim[];
  data_caveats: string[];
}

export interface Discrepancy {
  metric: string;
  values: string[];
  resolution?: string | null;
}

export interface ReviewerOutput {
  final_report_markdown: string;
  discrepancies: Discrepancy[];
  open_questions: string[];
  used_model?: string | null;
}

// --- SSE events ------------------------------------------------------------

export type EventType =
  | "job_start"
  | "data_fetch_start"
  | "data_fetch_progress"
  | "data_fetch_done"
  | "agent_start"
  | "agent_step"
  | "agent_done"
  | "reviewer_start"
  | "reviewer_step"
  | "reviewer_done"
  | "error"
  | "done";

export interface SSEMessage<TData = any> {
  event: EventType;
  data: TData;
}

export interface TokenUsage {
  prompt?: number | null;
  completion?: number | null;
  total?: number | null;
}

export interface JobStartData {
  jobId: string;
  asset: string;
  asOfDate: string;
  model: string;
}

export interface DataFetchDoneData {
  summary: {
    ticker: string;
    as_of_date: string;
    price_rows: number;
    quarters: number;
    news_count: number;
    macro_available: boolean;
    errors: string[];
  };
  errors: string[];
}

export type AgentRole =
  | "fundamental"
  | "technical"
  | "industry"
  | "macro"
  | "sentiment";

export interface AgentDoneData {
  agent: AgentRole;
  output:
    | FundamentalOutput
    | TechnicalOutput
    | IndustryOutput
    | MacroOutput
    | SentimentOutput;
  tokens: TokenUsage;
  model: string;
  retried: boolean;
}

export interface ReviewerDoneData {
  report: string;
  discrepancies: Discrepancy[];
  openQuestions: string[];
  tokens: TokenUsage;
  model: string;
  retried: boolean;
}

export interface DoneData {
  jobId: string;
  durationMs: number;
  ok: boolean;
  tokens?: TokenUsage;
}

export interface ErrorData {
  stage: "data_fetch" | "agent" | "reviewer" | "stream" | string;
  agent?: string;
  message: string;
  function?: string;
  tracebackTail?: string;
  elapsedMs?: number;
  agentElapsedMs?: number;
  reviewerElapsedMs?: number;
}

export interface DataFetchProgressData {
  source: "resolver" | "prices" | "fundamentals" | "news" | "macro" | string;
  status: "start" | "done" | "error";
  sourceElapsedMs?: number | null;
  elapsedMs?: number;
}

export interface AgentStepData {
  agent: AgentRole;
  step:
    | "llm_request"
    | "llm_response"
    | "llm_error"
    | "validate"
    | "retry"
    | string;
  attempt?: number;
  model?: string;
  promptChars?: number;
  systemChars?: number;
  promptTokens?: number | null;
  completionTokens?: number | null;
  totalTokens?: number | null;
  finishReason?: string | null;
  elapsedMs?: number;
  agentElapsedMs?: number | null;
  ok?: boolean;
  errorType?: string;
  message?: string;
  reason?: string;
}

export interface ReviewerStepData {
  step:
    | "llm_request"
    | "llm_response"
    | "llm_error"
    | "validate"
    | "retry"
    | string;
  attempt?: number;
  model?: string;
  promptChars?: number;
  systemChars?: number;
  promptTokens?: number | null;
  completionTokens?: number | null;
  totalTokens?: number | null;
  finishReason?: string | null;
  elapsedMs?: number;
  reviewerElapsedMs?: number;
  ok?: boolean;
  errorType?: string;
  message?: string;
  reason?: string;
}

// --- Frontend-only --------------------------------------------------------

/** Single chronological log entry rendered by LogPanel. */
export interface LogEntry {
  ts: number; // epoch ms (client clock)
  elapsedMs?: number; // server-side elapsed since job_start, when known
  stage: string; // e.g. "job", "data_fetch", "agent:fundamental", "reviewer", "stream"
  message: string;
  level: "info" | "warn" | "error";
  detail?: string; // expandable extra (traceback, etc.)
}

// --- Job record ------------------------------------------------------------

export interface JobRecord {
  id: string;
  asset: string;
  as_of_date: string;
  model: string;
  status: "running" | "completed" | "failed";
  created_at: string;
  completed_at?: string | null;
  duration_ms?: number | null;
  error?: string | null;
  data_summary?: Record<string, unknown> | null;
  fundamental?: FundamentalOutput | null;
  technical?: TechnicalOutput | null;
  industry?: IndustryOutput | null;
  macro?: MacroOutput | null;
  sentiment?: SentimentOutput | null;
  reviewer_report?: string | null;
  discrepancies?: Discrepancy[] | null;
  open_questions?: string[] | null;
  token_usage?: TokenUsage | null;
}

export interface JobsListResponse {
  jobs: Array<{
    id: string;
    asset: string;
    as_of_date: string;
    model: string;
    status: string;
    created_at: string;
    completed_at?: string | null;
    duration_ms?: number | null;
    error?: string | null;
  }>;
  count: number;
}
