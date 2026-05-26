import type { Metadata } from "next";
import { Cormorant_Garamond } from "next/font/google";
import "./globals.css";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import { ThemeProvider } from "@/components/providers/ThemeProvider";
import { CommandPalette } from "@/components/ui/CommandPalette";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-cormorant",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Heritage Document Recommender",
  description: "Explore and discover historical heritage documents",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${cormorant.variable} min-h-screen flex flex-col font-sans`}
            style={{ backgroundColor: "var(--bg-base)", color: "var(--text-primary)" }}>
        <ThemeProvider>
          <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:z-50 focus:px-4 focus:py-2 focus:bg-heritage-gold focus:text-heritage-dark focus:font-bold focus:top-2 focus:left-2 focus:rounded">
            Skip to main content
          </a>
          <CommandPalette />
          <Navbar />
          <main id="main-content" className="flex-1">{children}</main>
          <Footer />
        </ThemeProvider>
      </body>
    </html>
  );
}
