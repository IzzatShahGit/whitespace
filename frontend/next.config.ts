import type { NextConfig } from "next";

// The browser only talks to this app. /api/* is forwarded to the FastAPI backend,
// so auth cookies are first-party wherever the two are hosted.
const apiUrl = process.env.API_INTERNAL_URL ?? "http://localhost:8400";

const nextConfig: NextConfig = {
  // Self-contained server in .next/standalone, used by the Docker image.
  output: "standalone",
  cacheComponents: true,
  partialPrefetching: true,
  poweredByHeader: false,
  async headers() {
    // Baseline hardening on every response. A full script CSP is left out on purpose:
    // Next's inline bootstrapping and Turnstile need nonces to work under one.
    const security = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
      { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
    ];
    if (process.env.NODE_ENV === "production") {
      // Only meaningful over HTTPS; browsers ignore it on plain http://localhost anyway.
      security.push({ key: "Strict-Transport-Security", value: "max-age=31536000" });
    }
    return [{ source: "/:path*", headers: security }];
  },
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
