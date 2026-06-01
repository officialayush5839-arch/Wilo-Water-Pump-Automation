import type { Metadata } from "next";
import { Cormorant_Garamond, IBM_Plex_Mono, Syne, Sora } from "next/font/google";
import "./globals.css";

const display = Syne({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["400", "500", "600", "700", "800"],
});

const body = Sora({
  subsets: ["latin"],
  variable: "--font-body",
  weight: ["300", "400", "500", "600", "700"],
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500", "600"],
});

const serif = Cormorant_Garamond({
  subsets: ["latin"],
  variable: "--font-serif",
  weight: ["400", "500", "600", "700"],
  style: ["normal", "italic"],
});

export const metadata: Metadata = {
  title: "Wilo Water Pump Automation",
  description:
    "A Next.js website for the Wilo Water Pump Automation codebase: ESP32 sensing, LoRa telemetry, Raspberry Pi control, simulation, and pump logic.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body
        className={`${display.variable} ${body.variable} ${mono.variable} ${serif.variable} font-body`}
      >
        {children}
      </body>
    </html>
  );
}
