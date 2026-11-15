import type { NextConfig } from "next";

// The browser only talks to this app. /api/* is forwarded to the FastAPI backend,
// so auth cookies are first-party wherever the two are hosted.
const apiUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8400";

const nextConfig: NextConfig = {
  // Self-contained server in .next/standalone, used by the Docker image.
  output: "standalone",
  cacheComponents: true,
  partialPrefetching: true,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
