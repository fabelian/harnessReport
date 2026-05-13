/** @type {import('next').NextConfig} */

// Build-time / server-start guard. `/api/*` is now proxied by the App Router
// Route Handler at app/api/[...path]/route.ts (which can stream SSE responses
// reliably; the previous rewrites()-based proxy could not). The handler reads
// the same env var at request time, but failing fast here at build / boot
// preserves the original deploy-time signal.
if (!process.env.NEXT_PUBLIC_BACKEND_URL && process.env.NODE_ENV === "production") {
  throw new Error(
    "NEXT_PUBLIC_BACKEND_URL is required in production. Set it to the backend service URL (e.g. https://<svc>.up.railway.app or http://<svc>.railway.internal:<port>).",
  );
}

const nextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
