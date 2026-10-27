import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Imagen de producción mínima: server.js autónomo sin node_modules completos.
  output: "standalone",
  poweredByHeader: false,
  // El indicador de desarrollo de Next tapa la navegación inferior en el celular.
  devIndicators: false,
};

export default nextConfig;
