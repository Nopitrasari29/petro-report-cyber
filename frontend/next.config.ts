// frontend/next.config.ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          {
            key: "Cross-Origin-Opener-Policy",
            value: "same-origin-allow-popups", // Mengizinkan popup Google OAuth berkomunikasi ke Next.js
          },
        ],
      },
    ];
  },
};

export default nextConfig;