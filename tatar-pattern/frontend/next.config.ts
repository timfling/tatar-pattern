import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  devIndicators: false,
  async rewrites() {
    const origin = process.env.API_ORIGIN?.replace(/\/$/, "");
    return origin ? [{ source: "/api/:path*", destination: `${origin}/api/:path*` }] : [];
  },
};
export default nextConfig;
