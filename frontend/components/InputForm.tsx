"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { AnalyzeRequest, ModelChoice, ModelEntry } from "@/lib/types";

interface Props {
  onSubmit: (req: AnalyzeRequest) => void;
  disabled?: boolean;
}

/** Status of the /api/models probe used to drive the warning banner. */
type ApiStatus = "loading" | "ok" | "key_missing" | "unreachable";

/** Used when the backend is unreachable so the form still renders model
 * choices. Kept in sync with backend `ModelChoice` enum. */
const FALLBACK_MODELS: ModelEntry[] = [
  {
    id: "openai/gpt-oss-120b" as ModelChoice,
    label: "GPT-OSS 120B (정밀)",
    default: true,
  },
  {
    id: "google/gemma-3-27b-it" as ModelChoice,
    label: "Gemma 3 27B (저렴·빠름)",
    default: false,
  },
];

function today(): string {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${m}-${day}`;
}

export function InputForm({ onSubmit, disabled }: Props) {
  const [asset, setAsset] = useState("NVDA");
  const [asOfDate, setAsOfDate] = useState(today());
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [model, setModel] = useState<ModelChoice | "">("");
  const [apiStatus, setApiStatus] = useState<ApiStatus>("loading");

  const loadModels = useCallback(async () => {
    setApiStatus("loading");
    try {
      const res = await api.models();
      setModels(res.models);
      const def = res.models.find((m) => m.default) ?? res.models[0];
      if (def) setModel(def.id);
      setApiStatus(res.openrouter_configured ? "ok" : "key_missing");
    } catch {
      setModels(FALLBACK_MODELS);
      const def = FALLBACK_MODELS.find((m) => m.default) ?? FALLBACK_MODELS[0];
      if (def) setModel(def.id);
      setApiStatus("unreachable");
    }
  }, []);

  useEffect(() => {
    void loadModels();
  }, [loadModels]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!model) return;
    onSubmit({ asset: asset.trim(), asOfDate, model });
  }

  const submitBlocked =
    disabled ||
    !model ||
    !asset.trim() ||
    apiStatus === "loading" ||
    apiStatus === "unreachable" ||
    apiStatus === "key_missing";

  return (
    <form
      onSubmit={handleSubmit}
      className="grid gap-4 rounded-lg border border-neutral-200 bg-white p-6 shadow-sm dark:border-neutral-800 dark:bg-neutral-950 md:grid-cols-[1fr_180px_1fr_140px]"
    >
      <label className="text-sm">
        <span className="block font-medium text-neutral-700 dark:text-neutral-300">
          기초자산 (Ticker)
        </span>
        <input
          type="text"
          required
          value={asset}
          onChange={(e) => setAsset(e.target.value.toUpperCase())}
          placeholder="NVDA"
          className="mt-1 w-full rounded-md border border-neutral-300 bg-white px-3 py-2 font-mono text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-neutral-700 dark:bg-neutral-900"
          disabled={disabled}
        />
      </label>

      <label className="text-sm">
        <span className="block font-medium text-neutral-700 dark:text-neutral-300">
          분석 기준일
        </span>
        <input
          type="date"
          required
          value={asOfDate}
          max={today()}
          onChange={(e) => setAsOfDate(e.target.value)}
          className="mt-1 w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-neutral-700 dark:bg-neutral-900"
          disabled={disabled}
        />
      </label>

      <label className="text-sm">
        <span className="block font-medium text-neutral-700 dark:text-neutral-300">
          모델
        </span>
        <select
          required
          value={model}
          onChange={(e) => setModel(e.target.value as ModelChoice)}
          className="mt-1 w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 dark:border-neutral-700 dark:bg-neutral-900"
          disabled={disabled || models.length === 0}
        >
          {models.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>
      </label>

      <button
        type="submit"
        disabled={submitBlocked}
        className="self-end rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {disabled ? "분석 중…" : "분석 시작"}
      </button>

      <StatusBanner status={apiStatus} onRetry={loadModels} />
    </form>
  );
}

function StatusBanner({
  status,
  onRetry,
}: {
  status: ApiStatus;
  onRetry: () => void;
}) {
  if (status === "ok" || status === "loading") return null;

  if (status === "unreachable") {
    return (
      <div className="md:col-span-4 -mt-2 flex flex-wrap items-start justify-between gap-2 rounded-md border border-rose-300 bg-rose-50 px-3 py-2 text-xs text-rose-900 dark:border-rose-700 dark:bg-rose-950/30 dark:text-rose-200">
        <div>
          <p className="font-semibold">백엔드 연결 실패</p>
          <p className="mt-0.5">
            <code>http://localhost:8000</code>에 응답이 없습니다. 별도 터미널에서
            백엔드를 실행하세요:
          </p>
          <pre className="mt-1 overflow-x-auto rounded bg-white/60 px-2 py-1 dark:bg-black/30">
            cd backend; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000
          </pre>
        </div>
        <button
          type="button"
          onClick={onRetry}
          className="rounded border border-rose-400 px-2 py-1 text-xs font-medium hover:bg-rose-100 dark:border-rose-600 dark:hover:bg-rose-900/30"
        >
          ↻ 다시 시도
        </button>
      </div>
    );
  }

  // status === "key_missing"
  return (
    <div className="md:col-span-4 -mt-2 flex flex-wrap items-start justify-between gap-2 rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-700 dark:bg-amber-950/30 dark:text-amber-200">
      <div>
        <p className="font-semibold">OPENROUTER_API_KEY 미설정</p>
        <p className="mt-0.5">
          백엔드는 정상이지만 OpenRouter 키가 비어 있어 실제 분석은 실패합니다.
          <code className="ml-1">backend/.env</code>를 편집하거나 환경변수에{" "}
          <code>OPENROUTER_API_KEY=demo</code>를 설정해 데모 모드로 시도하세요.
        </p>
      </div>
      <button
        type="button"
        onClick={onRetry}
        className="rounded border border-amber-400 px-2 py-1 text-xs font-medium hover:bg-amber-100 dark:border-amber-600 dark:hover:bg-amber-900/30"
      >
        ↻ 다시 확인
      </button>
    </div>
  );
}
