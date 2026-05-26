/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    remotePatterns: [],
  },
  // three.js and react-force-graph-3d use ESM — Next.js needs to transpile them
  transpilePackages: ["three", "react-force-graph-3d", "three-forcegraph", "three-spritetext"],
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
