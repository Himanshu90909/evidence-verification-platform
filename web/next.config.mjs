/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // API routes run on the Vercel Node.js runtime (not edge) so the Prisma
  // client and bcrypt are available.
  experimental: {},
};

export default nextConfig;
