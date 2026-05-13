"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { AnalyzeRequest, ModelChoice, ModelEntry } from "@/lib/types";

interface Props {
  onSubmit: (req: AnalyzeRequest) => void;
  disabled?: boolean;
}

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
  const [openrouterReady, setOpenrouterReady] = useState(true);

  useEffect(() => {
    api
      .models()
      .then((res) => {
        setModels(res.models);
        const def = res.models.find((m) => m.default) ?? res.models[0];
        if (def) setModel(def.id);
        setOpenrouterReady(res.openrouter_configured);
      })
      .catch(() => {
        setOpenrouterReady(false);
      });
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!model) return;
    onSubmit({ asset: asset.trim(), asOfDate, model });
  }

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
        disabled={disabled || !model || !asset.trim()}
        className="self-end rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {disabled ? "분석 중…" : "분석 시작"}
      </button>

      {!openrouterReady && (
        <p className="md:col-span-4 -mt-2 text-xs text-amber-700 dark:text-amber-400">
          ⚠️ 백엔드에 <code>OPENROUTER_API_KEY</code>가 설정되지 않아 실제 분석은
          실패합니다. <code>backend/.env</code>를 확인하세요.
        </p>
      )}
    </form>
  );
}
