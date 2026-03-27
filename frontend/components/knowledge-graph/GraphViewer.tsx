"use client";

import { useEffect, useRef, useState } from "react";

interface Entity {
  id: string;
  name: string;
  type: string;
  count: number;
}

interface Node extends Entity {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
}

const TYPE_COLORS: Record<string, string> = {
  locations: "#7c6f4a",
  persons: "#5a7a6b",
  organizations: "#6b5a7a",
  dates: "#7a6b5a",
};

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function GraphViewer() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const nodesRef = useRef<Node[]>([]);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const res = await fetch(`${BASE_URL}/kg/entities?limit=30`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const entities: Entity[] = await res.json();
        if (cancelled) return;

        const canvas = canvasRef.current;
        if (!canvas) return;
        const W = canvas.width;
        const H = canvas.height;

        const maxCount = Math.max(...entities.map((e) => e.count), 1);

        nodesRef.current = entities.map((e) => ({
          ...e,
          x: W / 2 + (Math.random() - 0.5) * W * 0.6,
          y: H / 2 + (Math.random() - 0.5) * H * 0.6,
          vx: 0,
          vy: 0,
          r: 8 + (e.count / maxCount) * 22,
        }));

        setLoading(false);
        animate(canvas);
      } catch {
        if (!cancelled) setError("Could not load entities from backend.");
        setLoading(false);
      }
    }

    function animate(canvas: HTMLCanvasElement) {
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const W = canvas.width;
      const H = canvas.height;
      const nodes = nodesRef.current;
      const cx = W / 2;
      const cy = H / 2;

      function tick() {
        // Simple repulsion + center gravity
        for (let i = 0; i < nodes.length; i++) {
          const a = nodes[i];
          // Gravity toward center
          a.vx += (cx - a.x) * 0.002;
          a.vy += (cy - a.y) * 0.002;

          for (let j = i + 1; j < nodes.length; j++) {
            const b = nodes[j];
            const dx = a.x - b.x;
            const dy = a.y - b.y;
            const dist = Math.sqrt(dx * dx + dy * dy) || 1;
            const minDist = a.r + b.r + 12;
            if (dist < minDist) {
              const force = (minDist - dist) / dist * 0.12;
              a.vx += dx * force;
              a.vy += dy * force;
              b.vx -= dx * force;
              b.vy -= dy * force;
            }
          }

          // Damping
          a.vx *= 0.85;
          a.vy *= 0.85;
          a.x = Math.max(a.r, Math.min(W - a.r, a.x + a.vx));
          a.y = Math.max(a.r, Math.min(H - a.r, a.y + a.vy));
        }

        ctx.clearRect(0, 0, W, H);

        // Draw nodes
        for (const node of nodes) {
          const color = TYPE_COLORS[node.type] ?? "#888";
          ctx.beginPath();
          ctx.arc(node.x, node.y, node.r, 0, Math.PI * 2);
          ctx.fillStyle = color + "cc";
          ctx.fill();
          ctx.strokeStyle = color;
          ctx.lineWidth = 1.5;
          ctx.stroke();

          // Label
          ctx.fillStyle = "#fff";
          ctx.font = `${Math.max(9, node.r * 0.55)}px sans-serif`;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          const label = node.name.length > 12 ? node.name.slice(0, 11) + "…" : node.name;
          ctx.fillText(label, node.x, node.y);
        }

        rafRef.current = requestAnimationFrame(tick);
      }

      rafRef.current = requestAnimationFrame(tick);
    }

    load();
    return () => {
      cancelled = true;
      cancelAnimationFrame(rafRef.current);
    };
  }, []);

  return (
    <div className="relative w-full rounded-lg overflow-hidden border border-parchment-300 bg-parchment-100" style={{ height: "288px" }}>
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-heritage-brown">
          Loading graph…
        </div>
      )}
      {error && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-heritage-brown text-sm">
          <span className="text-4xl opacity-30">🕸️</span>
          <span>{error}</span>
        </div>
      )}
      <canvas
        ref={canvasRef}
        width={700}
        height={288}
        className="w-full h-full"
        style={{ display: loading || error ? "none" : "block" }}
      />
      {!loading && !error && (
        <div className="absolute bottom-2 left-3 flex gap-3 text-[10px] text-heritage-brown opacity-70">
          {Object.entries(TYPE_COLORS).map(([type, color]) => (
            <span key={type} className="flex items-center gap-1">
              <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: color }} />
              {type}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
