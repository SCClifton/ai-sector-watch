import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import "./globals.css";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { Analytics } from "@/components/Analytics";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "AI Sector Watch",
    template: "%s | AI Sector Watch",
  },
  description:
    "A live ecosystem map of the Australian and New Zealand AI startup landscape, updated weekly.",
  metadataBase: new URL("https://aimap.cliftonfamily.co"),
  openGraph: {
    type: "website",
    siteName: "AI Sector Watch",
    title: "AI Sector Watch",
    description:
      "A live ecosystem map of the Australian and New Zealand AI startup landscape, updated weekly.",
  },
  twitter: {
    card: "summary_large_image",
    title: "AI Sector Watch",
    description:
      "A live ecosystem map of the Australian and New Zealand AI startup landscape, updated weekly.",
  },
};

export const viewport: Viewport = {
  themeColor: "#0B0F14",
  colorScheme: "dark",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-bg text-text">
        <a href="#main-content" className="aisw-skip-link">
          Skip to main content
        </a>
        <Header />
        <main id="main-content" className="flex-1 flex flex-col">
          {children}
        </main>
        <Footer />
        <Analytics />
      </body>
    </html>
  );
}
