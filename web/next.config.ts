import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Imagen de producción mínima: server.js autónomo sin node_modules completos.
  output: "standalone",
  poweredByHeader: false,
};

export default nextConfig;
