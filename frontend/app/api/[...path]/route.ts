// Catch-all reverse proxy for /api/* → backend service.
//
// Replaces the next.config.mjs `rewrites()` proxy. The rewrites path could not
// stream SSE responses for `POST /api/analyze` on Railway: the client received
// 0 bytes for 40s while the backend was emitting events normally when hit
// directly. Implementing the proxy as a Route Handler with explicit
// `duplex: "half"` and a passthrough Response body fixes streaming.

import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

if (!process.env.NEXT_PUBLIC_BACKEND_URL && process.env.NODE_ENV === "production") {
  throw new Error(
    "NEXT_PUBLIC_BACKEND_URL is required in production — set it to the backend service URL.",
  );
}

// Hop-by-hop and host-specific headers that must not be forwarded.
const STRIP_REQUEST_HEADERS = new Set([
  "host",
  "connection",
  "content-length",
  "transfer-encoding",
  "keep-alive",
  "upgrade",
  "proxy-authorization",
  "proxy-connection",
  "te",
  "trailer",
]);

const STRIP_RESPONSE_HEADERS = new Set([
  "connection",
  "transfer-encoding",
  "keep-alive",
  "upgrade",
  "proxy-authorization",
  "proxy-connection",
  "content-encoding",
  "content-length",
  "te",
  "trailer",
]);

async function proxy(
  req: NextRequest,
  ctx: { params: { path: string[] } },
): Promise<Response> {
  const url = new URL(req.url);
  const tail = ctx.params.path.join("/");
  const target = `${BACKEND}/api/${tail}${url.search}`;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!STRIP_REQUEST_HEADERS.has(key.toLowerCase())) headers.set(key, value);
  });

  const init: RequestInit & { duplex?: "half" } = {
    method: req.method,
    headers,
    redirect: "manual",
    signal: req.signal,
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = req.body;
    // Required by undici when streaming a request body in Node 18+ runtimes.
    init.duplex = "half";
  }

  const upstream = await fetch(target, init);

  const respHeaders = new Headers();
  upstream.headers.forEach((value, key) => {
    if (!STRIP_RESPONSE_HEADERS.has(key.toLowerCase())) respHeaders.set(key, value);
  });

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: respHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
export const HEAD = proxy;
