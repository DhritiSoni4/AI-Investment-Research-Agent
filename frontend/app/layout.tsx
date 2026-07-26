import type { Metadata } from "next";
import "./globals.css";
import { AppProviders } from "@/components/app-providers";

export const metadata: Metadata = {
  title: "AlphaAgent | Investment Research",
  description: "Autonomous, auditable equity research.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body><AppProviders>{children}</AppProviders></body></html>;
}
