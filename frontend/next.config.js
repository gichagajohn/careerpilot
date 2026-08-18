/** @type {import('next').NextConfig} */
// The dashboard calls relative /api/... URLs; Next proxies them to the FastAPI
// backend server-side, so the browser never needs to know where the API lives
// (works in the sandbox preview and on your PC alike).
const nextConfig = {
  async rewrites() {
    const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [{ source: "/api/:path*", destination: `${api}/api/:path*` }];
  },
};

module.exports = nextConfig;
