// SSE consumer for POST + Server-Sent Events.
//
// Native `EventSource` is GET-only, so we use `fetch` + a ReadableStream
// parser. Yields one `{ event, data }` per SSE block.

import type { AnalyzeRequest, SSEMessage } from "@/lib/types";

export interface SseError {
  status: number;
  statusText: string;
  body?: string;
}

export async function* streamAnalysis(
  req: AnalyzeRequest,
  signal?: AbortSignal,
): AsyncGenerator<SSEMessage> {
  const resp = await fetch("/api/analyze", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(req),
    signal,
  });

  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    const err: SseError = { status: resp.status, statusText: resp.statusText, body };
    throw err;
  }
  if (!resp.body) {
    throw new Error("response has no body");
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let separator: number;
      while ((separator = buffer.indexOf("\n\n")) >= 0) {
        const block = buffer.slice(0, separator);
        buffer = buffer.slice(separator + 2);

        const parsed = parseSseBlock(block);
        if (parsed) yield parsed;
      }
    }
    // flush remaining
    if (buffer.trim().length > 0) {
      const parsed = parseSseBlock(buffer);
      if (parsed) yield parsed;
    }
  } finally {
    reader.releaseLock();
  }
}

function parseSseBlock(block: string): SSEMessage | null {
  let event = "message";
  const dataLines: string[] = [];

  for (const rawLine of block.split("\n")) {
    const line = rawLine.replace(/\r$/, "");
    if (!line || line.startsWith(":")) continue; // comment / keep-alive
    if (line.startsWith("event:")) {
      event = line.slice("event:".length).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trim());
    }
    // Ignore id:, retry:, etc.
  }

  if (dataLines.length === 0) return null;
  const dataStr = dataLines.join("\n");
  try {
    return { event: event as SSEMessage["event"], data: JSON.parse(dataStr) };
  } catch {
    return { event: event as SSEMessage["event"], data: { raw: dataStr } };
  }
}
