"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Sun, Moon, Bookmark, Search, LayoutDashboard, FlaskConical, Landmark, Command } from "lucide-react";

const NAV_LINKS = [
  { href: "/search",     label: "Browse Archives", icon: Search },
  { href: "/dashboard",  label: "Dashboard",       icon: LayoutDashboard },
  { href: "/evaluation", label: "Evaluation",      icon: FlaskConical },
];

export default function Navbar() {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  return (
    <nav
      className="sticky top-0 z-50 border-b border-white/10 backdrop-blur-md"
      style={{ background: "var(--nav-bg)" }}
      aria-label="Main navigation"
    >
      <div className="max-w-6xl mx-auto px-4 flex items-center justify-between" style={{ height: "56px" }}>

        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="w-7 h-7 rounded-lg bg-heritage-gold flex items-center justify-center shadow">
            <Landmark className="w-4 h-4 text-heritage-dark" />
          </div>
          <span className="font-serif font-bold text-base tracking-wide text-white group-hover:text-heritage-gold transition-colors">
            Heritage Recommender
          </span>
        </Link>

        {/* Nav links */}
        <ul className="flex items-center gap-0.5">
          {NAV_LINKS.map((link) => {
            const active = pathname === link.href || pathname.startsWith(link.href + "?");
            const Icon = link.icon;
            return (
              <li key={link.href} className="relative">
                <Link
                  href={link.href}
                  className={`
                    flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-150
                    ${active
                      ? "text-heritage-gold"
                      : "text-parchment-200 hover:text-white hover:bg-white/10"
                    }
                  `}
                >
                  <Icon className="w-3.5 h-3.5 opacity-70" />
                  {link.label}
                </Link>
                {/* Animated active underline */}
                {active && (
                  <span className="absolute bottom-0 left-3 right-3 h-0.5 rounded-full bg-heritage-gold" />
                )}
              </li>
            );
          })}

          <li className="relative">
            <Link
              href="/saved"
              className={`
                flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-150
                ${pathname === "/saved"
                  ? "text-heritage-gold"
                  : "text-parchment-200 hover:text-white hover:bg-white/10"
                }
              `}
            >
              <Bookmark className="w-3.5 h-3.5 opacity-70" />
              Saved
            </Link>
            {pathname === "/saved" && (
              <span className="absolute bottom-0 left-3 right-3 h-0.5 rounded-full bg-heritage-gold" />
            )}
          </li>

          {/* ⌘K shortcut hint */}
          <li className="ml-1">
            <button
              onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }))}
              className="hidden sm:flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-parchment-300 hover:text-white hover:bg-white/10 transition-all"
              aria-label="Open command palette"
            >
              <Command className="w-3.5 h-3.5" />
              <kbd className="text-[10px] font-mono opacity-60">K</kbd>
            </button>
          </li>

          {/* Dark / Light toggle */}
          <li className="ml-1">
            {mounted && (
              <button
                onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-parchment-200 hover:text-heritage-gold hover:bg-white/10 transition-all duration-200"
                aria-label="Toggle dark mode"
              >
                {theme === "dark"
                  ? <Sun className="w-4 h-4" />
                  : <Moon className="w-4 h-4" />
                }
              </button>
            )}
          </li>
        </ul>

      </div>
    </nav>
  );
}
