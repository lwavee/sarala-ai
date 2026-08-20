import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["127.0.0.1", "localhost", "127.0.0.1:3000", "localhost:3000", "127.0.0.1:3005", "localhost:3005"],
  turbopack: {
    root: path.resolve(__dirname, ".."),
  },
};

export default nextConfig;
