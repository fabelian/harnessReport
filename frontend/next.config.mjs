/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const fromEnv = process.env.NEXT_PUBLIC_BACKEND_URL;
    if (!fromEnv && process.env.NODE_ENV === "production") {
      // rewrites() runs both during `next build` and at server start. The
      // build-time read is what actually bakes the destination into the build,
      // so this var MUST be present in the docker build environment (declare
      // ARG NEXT_PUBLIC_BACKEND_URL in the Dockerfile), not just at runtime.
      throw new Error(
        "NEXT_PUBLIC_BACKEND_URL is required in production. It must be set during `next build` (Docker build arg), not just at runtime — Next.js bakes the rewrite destination into the build. Set it to the backend URL (e.g. https://<svc>.up.railway.app or http://<svc>.railway.internal:<port>).",
      );
    }
    const backend = fromEnv ?? "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backend}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
