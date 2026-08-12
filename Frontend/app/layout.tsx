import type { Metadata } from "next";
import { Fraunces, Sora } from "next/font/google";
import "./globals.css";

const sora = Sora({
  subsets: ["latin"],
  variable: "--font-sora",
  display: "swap",
});

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
});

export const metadata: Metadata = {
  title: "MandiSync | Crop Arbitrage Dashboard",
  description:
    "Indian mandi arbitrage routes with live Agmarknet prices where available, transit economics, and honest arrival guidance.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${sora.variable} ${fraunces.variable}`}>
      <head>
        {/* Leaflet CSS via CDN — required for tile grids, controls, and marker chrome. */}
        <link
          rel="stylesheet"
          href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
          integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
          crossOrigin=""
        />
      </head>
      <body className="min-h-screen font-sans antialiased bg-slate-900 text-slate-100">
        {children}
      </body>
    </html>
  );
}
