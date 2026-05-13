/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const fromEnv = process.env.NEXT_PUBLIC_BACKEND_URL;
    if (!fromEnv && process.env.NODE_ENV === "production") {
      throw new Error(
        "NEXT_PUBLIC_BACKEND_URL is required in production — set it to the backend service URL (e.g. https://<svc>.up.railway.app or http://<svc>.railway.internal:<port>).",
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
