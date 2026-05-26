"use client";

import { useRef, useEffect } from "react";

export function SpotlightHero({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const spotRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    const spot = spotRef.current;
    if (!el || !spot) return;

    const onMove = (e: MouseEvent) => {
      const rect = el.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      spot.style.background = `radial-gradient(500px circle at ${x}px ${y}px, rgba(200,168,75,0.07) 0%, transparent 70%)`;
    };

    el.addEventListener("mousemove", onMove);
    return () => el.removeEventListener("mousemove", onMove);
  }, []);

  return (
    <div ref={ref} className="relative">
      {/* Cursor spotlight */}
      <div ref={spotRef} className="pointer-events-none absolute inset-0 z-10 transition-all duration-300" />
      {children}
    </div>
  );
}
