"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import * as THREE from "three";
import { getKGGraph, getKGEntityNeighbors } from "@/lib/api";
import { KGNode } from "@/lib/types";

const ForceGraph3D = dynamic(() => import("react-force-graph-3d"), { ssr: false });

// ── Types ──────────────────────────────────────────────────────────────────────
type GraphMode = "full" | "egocentric";

interface GNode extends KGNode {
  x?: number; y?: number; z?: number;
}

interface GLink {
  source: string | GNode;
  target: string | GNode;
  weight: number;
  edge_type: string;
}

// ── Visual constants ───────────────────────────────────────────────────────────
const TYPE_COLOR: Record<string, string> = {
  document:      "#c8a84b",
  location:      "#b89a60",
  person:        "#6aaa8a",
  organization:  "#9a8aba",
  heritage_type: "#e07050",
  domain:        "#50b0a0",
  time_period:   "#b08060",
  region:        "#70aa80",
};

const CLUSTER_COLOR: Record<number, string> = {
  0: "#e8c86b", 1: "#6aaa8a", 2: "#b89a60",
  3: "#9a8aba", 4: "#e07050", 5: "#50b0a0",
  6: "#b08060", 7: "#70aa80", 8: "#9a8b7a", 9: "#7a8b9a",
};

const EDGE_TYPE_COLOR: Record<string, string> = {
  co_occurrence:          "rgba(255,215,0,0.90)",
  mentions_location:      "rgba(255,223,50,0.90)",
  mentions_person:        "rgba(255,210,30,0.90)",
  mentions_org:           "rgba(255,30,30,0.95)",
  similar_to:             "rgba(255,235,80,0.95)",
  semantically_related:   "rgba(255,228,50,0.95)",
  same_cluster:           "rgba(255,200,20,0.75)",
  shares_keywords:        "rgba(255,218,40,0.90)",
  temporally_related:     "rgba(255,200,30,0.90)",
  geographically_related: "rgba(255,225,60,0.90)",
  has_type:               "rgba(255,210,40,0.85)",
  belongs_to_domain:      "rgba(255,215,50,0.85)",
  from_period:            "rgba(255,205,35,0.85)",
  located_in_region:      "rgba(255,220,55,0.85)",
  related:                "rgba(255,215,45,0.85)",
};

const EDGE_GROUPS: Record<string, string[]> = {
  "Entity Links": ["co_occurrence", "mentions_location", "mentions_person", "mentions_org"],
  "Semantic":     ["similar_to", "semantically_related", "shares_keywords"],
  "Structural":   ["has_type", "belongs_to_domain", "from_period", "located_in_region", "from_source", "same_cluster"],
  "Geo/Time":     ["temporally_related", "geographically_related"],
};

function nodeColor(n: GNode): string {
  if (n.type === "document" && n.cluster_id != null)
    return CLUSTER_COLOR[n.cluster_id % 10] ?? TYPE_COLOR.document;
  return TYPE_COLOR[n.type] ?? "#aaa";
}

function nodeRadius(n: GNode): number {
  if (n.horn_weight > 0) return 4 + n.horn_weight * 10;
  return 4 + Math.sqrt(n.count) * 0.9;
}

// ── Component ──────────────────────────────────────────────────────────────────
export default function GraphViewer() {
  const router  = useRouter();
  const fgRef   = useRef<any>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState<string | null>(null);
  const [mode, setMode]               = useState<GraphMode>("full");
  const [egoCenter, setEgoCenter]     = useState<GNode | null>(null);
  const [showDocs, setShowDocs]       = useState(false);
  const [activeGroups, setActiveGroups] = useState(() => new Set(["Entity Links", "Semantic"]));
  const [search, setSearch]           = useState("");
  const [graphData, setGraphData]     = useState<{ nodes: GNode[]; links: GLink[] }>({ nodes: [], links: [] });
  const [isMounted, setIsMounted]     = useState(false);
  // Hover is managed via ref + direct DOM mutation — never triggers a React re-render
  const hoveredRef  = useRef<GNode | null>(null);
  const tooltipRef  = useRef<HTMLDivElement>(null);
  const modeRef     = useRef<GraphMode>("full");
  const [isFullscreen, setIsFullscreen] = useState(false);
  // canvas dimensions — measured from the wrapper
  const [dims, setDims]               = useState({ w: 700, h: 500 });

  const activeEdgeTypes = new Set<string>(
    Array.from(activeGroups).flatMap((g) => EDGE_GROUPS[g] ?? [])
  );

  // ── Mount + resize ────────────────────────────────────────────────────────
  useEffect(() => {
    setIsMounted(true);

    const measure = () => {
      if (wrapRef.current) {
        setDims({ w: wrapRef.current.clientWidth, h: wrapRef.current.clientHeight });
      }
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (wrapRef.current) ro.observe(wrapRef.current);

    const onFs = () => setIsFullscreen(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", onFs);

    return () => { ro.disconnect(); document.removeEventListener("fullscreenchange", onFs); };
  }, []);

  // Re-measure when fullscreen changes
  useEffect(() => {
    setTimeout(() => {
      if (wrapRef.current)
        setDims({ w: wrapRef.current.clientWidth, h: wrapRef.current.clientHeight });
    }, 120);
  }, [isFullscreen]);

  // ── Data load ────────────────────────────────────────────────────────────
  const loadFull = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getKGGraph(80, showDocs);
      setGraphData({
        nodes: data.nodes as GNode[],
        links: data.edges.map((e) => ({
          source: e.source, target: e.target,
          weight: e.weight, edge_type: e.edge_type,
        })),
      });
    } catch {
      setError("Could not load knowledge graph.");
    } finally {
      setLoading(false);
    }
  }, [showDocs]);

  useEffect(() => { if (mode === "full") loadFull(); }, [loadFull]);

  // Keep modeRef in sync without triggering extra renders
  useEffect(() => { modeRef.current = mode; }, [mode]);

  // ── Camera ────────────────────────────────────────────────────────────────
  const resetCamera = useCallback(() => {
    fgRef.current?.cameraPosition({ x: 0, y: 0, z: 320 }, { x: 0, y: 0, z: 0 }, 900);
  }, []);

  useEffect(() => {
    if (!loading && isMounted) setTimeout(resetCamera, 200);
  }, [loading, isMounted, resetCamera]);

  // ── Fullscreen toggle ─────────────────────────────────────────────────────
  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      wrapRef.current?.requestFullscreen();
    } else {
      document.exitFullscreen();
    }
  }, []);

  // ── Node click ────────────────────────────────────────────────────────────
  const handleNodeClick = useCallback(async (node: object) => {
    const n = node as GNode;
    if (n.type === "document") {
      router.push(`/document/${encodeURIComponent(n.name)}`);
      return;
    }
    if (mode === "full") {
      try {
        const data = await getKGEntityNeighbors(n.id);
        setGraphData({
          nodes: [data.center as GNode, ...data.neighbors as GNode[]],
          links: data.edges.map((e) => ({
            source: e.source, target: e.target,
            weight: e.weight, edge_type: e.edge_type,
          })),
        });
        setMode("egocentric");
        setEgoCenter(n);
        setTimeout(() => fgRef.current?.cameraPosition({ x: 0, y: 0, z: 200 }, { x: 0, y: 0, z: 0 }, 700), 150);
      } catch {
        router.push(`/search?q=${encodeURIComponent(n.name)}`);
      }
    } else {
      router.push(`/search?q=${encodeURIComponent(n.name)}`);
    }
  }, [mode, router]);

  const exitEgo = useCallback(async () => {
    setMode("full");
    setEgoCenter(null);
    await loadFull();
    setTimeout(resetCamera, 400);
  }, [loadFull, resetCamera]);

  // ── Node 3D object — mesh + floating label ────────────────────────────────
  const nodeThreeObject = useCallback((node: object) => {
    const n       = node as GNode;
    const r       = nodeRadius(n);
    const col     = nodeColor(n);
    const isCenter  = mode === "egocentric" && egoCenter?.id === n.id;
    const searchOn  = search.length > 0;
    const matches   = !searchOn || n.name.toLowerCase().includes(search.toLowerCase());

    // Geometry by type
    let geo: THREE.BufferGeometry;
    switch (n.type) {
      case "person":        geo = new THREE.BoxGeometry(r*1.7, r*1.7, r*1.7); break;
      case "organization":  geo = new THREE.OctahedronGeometry(r*1.15); break;
      case "document":      geo = new THREE.DodecahedronGeometry(r*1.05); break;
      case "heritage_type": geo = new THREE.TetrahedronGeometry(r*1.35); break;
      case "domain":        geo = new THREE.IcosahedronGeometry(r); break;
      default:              geo = new THREE.SphereGeometry(r, 18, 14); break;
    }

    const mat = new THREE.MeshPhongMaterial({
      color:            new THREE.Color(col),
      emissive:         new THREE.Color(isCenter ? "#c8a84b" : col),
      emissiveIntensity: isCenter ? 0.7 : (n.is_top_central ? 0.4 : 0.18),
      transparent:      true,
      opacity:          searchOn ? (matches ? 1.0 : 0.07) : 1.0,
      shininess:        110,
      specular:         new THREE.Color("#ffffff"),
    });
    const mesh = new THREE.Mesh(geo, mat);

    // Gold orbit ring on ego center
    if (isCenter) {
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(r * 2.0, r * 0.2, 8, 40),
        new THREE.MeshBasicMaterial({ color: 0xc8a84b, transparent: true, opacity: 0.9 })
      );
      ring.rotation.x = Math.PI / 2;
      mesh.add(ring);
    }

    // Glow sprite on top-central nodes
    if (n.is_top_central || isCenter) {
      const cv = document.createElement("canvas");
      cv.width = cv.height = 80;
      const ctx = cv.getContext("2d")!;
      const g = ctx.createRadialGradient(40, 40, 2, 40, 40, 40);
      g.addColorStop(0,   "rgba(200,168,75,0.9)");
      g.addColorStop(0.5, "rgba(200,168,75,0.25)");
      g.addColorStop(1,   "rgba(200,168,75,0)");
      ctx.fillStyle = g; ctx.fillRect(0, 0, 80, 80);
      const sprite = new THREE.Sprite(
        new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(cv), transparent: true, depthWrite: false })
      );
      sprite.scale.set(r * 6, r * 6, 1);
      mesh.add(sprite);
    }

    // ── Floating text label ──────────────────────────────────────────────
    if (matches || !searchOn) {
      const label = n.name.length > 18 ? n.name.slice(0, 17) + "…" : n.name;

      // Render label into a canvas texture
      const fontSize = isCenter ? 18 : (n.horn_weight > 0.3 ? 14 : 12);
      const padding  = 6;
      const cv2 = document.createElement("canvas");
      const ctx2 = cv2.getContext("2d")!;
      ctx2.font = `${fontSize}px sans-serif`;
      const tw = ctx2.measureText(label).width;
      cv2.width  = tw + padding * 2 + 2;
      cv2.height = fontSize + padding * 2;

      // Pill background
      ctx2.fillStyle = isCenter ? "rgba(30,20,5,0.88)" : "rgba(13,10,5,0.72)";
      ctx2.beginPath();
      const rr = cv2.height / 2;
      ctx2.roundRect(0, 0, cv2.width, cv2.height, rr);
      ctx2.fill();

      // Text
      ctx2.font      = `${fontSize}px sans-serif`;
      ctx2.fillStyle = isCenter ? "#ffd777" : (n.is_top_central ? "#e8c870" : "#d4c090");
      ctx2.textAlign    = "center";
      ctx2.textBaseline = "middle";
      ctx2.fillText(label, cv2.width / 2, cv2.height / 2);

      const sprite2 = new THREE.Sprite(
        new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(cv2), transparent: true, depthWrite: false })
      );
      // Scale: canvas pixel → world unit at roughly 0.35 per px
      const scale = 0.35;
      sprite2.scale.set(cv2.width * scale, cv2.height * scale, 1);
      sprite2.position.set(0, r + cv2.height * scale * 0.6 + 1, 0);
      mesh.add(sprite2);
    }

    return mesh;
  }, [mode, egoCenter, search]);

  const linkColor     = useCallback((l: object) => {
    const link = l as GLink;
    const src = link.source as GNode;
    const tgt = link.target as GNode;
    // Red only when both endpoints are organizations (UNESCO↔ASI etc.)
    if (src?.type === "organization" && tgt?.type === "organization") {
      return "rgba(255,30,30,0.95)";
    }
    return EDGE_TYPE_COLOR[link.edge_type] ?? "rgba(255,215,0,0.90)";
  }, []);
  const linkWidth     = useCallback((l: object) => {
    const link = l as GLink;
    const cap = link.edge_type === "mentions_org" || link.edge_type === "co_occurrence" ? 0.004 : 0.02;
    return Math.max(0.01, link.weight * cap);
  }, []);
  const linkVisibility = useCallback((l: object) => activeEdgeTypes.has((l as GLink).edge_type), [activeEdgeTypes]);

  // Force re-render of node objects on search change
  const [epoch, setEpoch] = useState(0);
  const prevSearch = useRef("");
  useEffect(() => {
    if (search !== prevSearch.current) { prevSearch.current = search; setEpoch((v) => v + 1); }
  }, [search]);

  const visibleLinks = graphData.links.filter((l) => activeEdgeTypes.has(l.edge_type));
  const topNodes = [...graphData.nodes].sort((a, b) => b.horn_weight - a.horn_weight).slice(0, 5);
  const clusterBreakdown = graphData.nodes.reduce<Record<string, number>>((acc, n) => {
    if (n.cluster_label) acc[n.cluster_label] = (acc[n.cluster_label] ?? 0) + 1;
    return acc;
  }, {});

  // ── Render ────────────────────────────────────────────────────────────────
  const containerH = isFullscreen ? "100vh" : "540px";

  return (
    <div className="flex flex-col gap-2">

      {/* ── Controls bar ─────────────────────────────────────────────────── */}
      {!loading && !error && (
        <div className="flex flex-wrap items-center gap-2 px-1 py-1 text-[11px] select-none">
          <label className="flex items-center gap-1 cursor-pointer text-heritage-brown">
            <input type="checkbox" checked={showDocs} onChange={() => setShowDocs((v) => !v)}
              className="accent-amber-600 w-3 h-3" />
            <span>Docs</span>
          </label>

          <span className="text-parchment-300 hidden sm:inline">|</span>

          {Object.keys(EDGE_GROUPS).map((g) => {
            const on = activeGroups.has(g);
            return (
              <button key={g} onClick={() => setActiveGroups((prev) => {
                const next = new Set(prev); on ? next.delete(g) : next.add(g); return next;
              })}
                className={`px-2 py-0.5 rounded-full border transition-colors text-[10px] ${
                  on ? "border-amber-600 bg-amber-50 text-amber-800"
                     : "border-parchment-300 bg-parchment-100 text-parchment-500"}`}>
                {g}
              </button>
            );
          })}

          <div className="flex items-center gap-2 ml-auto">
            <input type="text" value={search} onChange={(e) => setSearch(e.target.value)}
              placeholder="Filter nodes…"
              className="border border-parchment-300 rounded px-2 py-0.5 text-[10px] w-28 bg-parchment-50 text-heritage-brown placeholder-parchment-400 focus:outline-none focus:border-amber-500" />
            <button onClick={resetCamera}
              className="px-2 py-0.5 rounded border border-parchment-300 bg-parchment-100 text-heritage-brown hover:bg-parchment-200 transition-colors text-[10px]">
              Reset
            </button>
            {mode === "egocentric" && (
              <button onClick={exitEgo}
                className="px-2 py-0.5 rounded border border-amber-500 bg-amber-50 text-amber-800 hover:bg-amber-100 transition-colors text-[10px] font-medium">
                ← Full Graph
              </button>
            )}
            {/* Fullscreen button */}
            <button onClick={toggleFullscreen}
              title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
              className="px-2 py-0.5 rounded border border-parchment-300 bg-parchment-100 text-heritage-brown hover:bg-parchment-200 transition-colors text-[11px]">
              {isFullscreen ? "⛶" : "⛶"}
              {isFullscreen ? " Exit" : " Full"}
            </button>
          </div>
        </div>
      )}

      {/* ── Graph wrapper — fullscreen target ────────────────────────────── */}
      <div ref={wrapRef}
        className="relative w-full rounded-xl overflow-hidden border border-parchment-300 bg-[#080808]"
        style={{ height: containerH }}>

        {/* Loading */}
        {loading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-parchment-200">
            <div className="w-8 h-8 border-2 border-amber-400 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm">Loading knowledge graph…</span>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-parchment-300 text-sm">
            <span className="text-4xl opacity-30">🕸️</span>
            <span>{error}</span>
          </div>
        )}

        {/* 3D Graph */}
        {isMounted && !loading && !error && (
          <ForceGraph3D
            key={`${mode}-${epoch}`}
            ref={fgRef}
            width={dims.w}
            height={dims.h}
            graphData={{ nodes: graphData.nodes, links: visibleLinks }}
            backgroundColor="#080808"
            nodeThreeObject={nodeThreeObject}
            nodeThreeObjectExtend={false}
            nodeColor={nodeColor as any}
            nodeVal={(n) => nodeRadius(n as GNode) ** 2}
            nodeLabel={() => ""}
            linkColor={linkColor}
            linkWidth={linkWidth}
            linkVisibility={linkVisibility}
            linkOpacity={0.7}
            linkCurvature={0.12}
            onNodeClick={handleNodeClick}
            onNodeHover={(n) => {
              hoveredRef.current = n as GNode | null;
              const el = tooltipRef.current;
              if (!el) return;
              const node = n as GNode | null;
              if (!node) { el.style.display = "none"; return; }
              const m = modeRef.current;
              const hint =
                node.type === "document" ? "↗ Click to open document" :
                m === "full" ? "⬡ Click to explore neighborhood" :
                "🔍 Click to search";
              el.innerHTML = `
                <div class="font-bold text-amber-300 text-sm">${node.name}</div>
                <div class="text-parchment-300 capitalize mt-0.5">${node.type.replace("_", " ")}</div>
                <div class="text-parchment-400 mt-0.5">
                  ${node.count} connections
                  ${node.horn_weight > 0 ? `<span class="ml-2 text-amber-400">★ ${Math.round(node.horn_weight * 100)}</span>` : ""}
                </div>
                ${node.cluster_label ? `<div class="text-parchment-500 italic text-[10px] mt-1">${node.cluster_label}</div>` : ""}
                <div class="text-amber-400/50 text-[10px] mt-1.5">${hint}</div>
              `;
              el.style.display = "block";
            }}
            d3AlphaDecay={0.04}
            d3VelocityDecay={0.6}
            warmupTicks={120}
            cooldownTicks={0}
            onEngineStop={() => fgRef.current?.pauseAnimation()}
            enableNodeDrag={true}
            onNodeDrag={() => {
              // Keep animation running while dragging
              fgRef.current?.resumeAnimation();
            }}
            onNodeDragEnd={(node) => {
              const n = node as GNode;
              // Fix node in place — fx/fy/fz pins it so force engine won't move it
              (n as any).fx = n.x;
              (n as any).fy = n.y;
              (n as any).fz = n.z;
              // Pause again after a short settle
              setTimeout(() => fgRef.current?.pauseAnimation(), 600);
            }}
            showNavInfo={false}
          />
        )}

        {/* Hover tooltip — top-center, updated via DOM to avoid re-renders */}
        <div
          ref={tooltipRef}
          className="absolute top-4 left-1/2 -translate-x-1/2 pointer-events-none z-20
            px-4 py-2.5 rounded-xl border border-amber-400/50 text-xs leading-relaxed shadow-2xl"
          style={{ display: "none", background: "rgba(8,6,2,0.93)", backdropFilter: "blur(10px)", minWidth: "180px" }}
        />

        {/* Ego mode badge */}
        {mode === "egocentric" && egoCenter && (
          <div className="absolute top-4 left-4 px-3 py-2 rounded-xl border border-amber-500/60 text-xs"
            style={{ background: "rgba(8,6,2,0.88)" }}>
            <div className="text-amber-400 font-semibold text-sm">{egoCenter.name}</div>
            <div className="text-parchment-400 text-[10px] mt-0.5">
              {graphData.nodes.length - 1} neighbors · click any to search
            </div>
          </div>
        )}

        {/* Stats panel — right */}
        {!loading && !error && (
          <div className="absolute top-4 right-4 w-44 rounded-xl border border-white/10 text-[10px] leading-relaxed overflow-hidden"
            style={{ background: "rgba(8,6,2,0.80)", backdropFilter: "blur(8px)" }}>
            <div className="px-3 pt-2.5 pb-2">
              <div className="text-parchment-400 mb-2">
                {graphData.nodes.length} nodes · {visibleLinks.length} edges
              </div>
              {topNodes.length > 0 && (
                <>
                  <div className="text-amber-400 font-semibold mb-1.5 text-[11px]">Top entities</div>
                  {topNodes.map((n) => (
                    <div key={n.id} className="flex items-center gap-1.5 mb-1">
                      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: nodeColor(n) }} />
                      <span className="truncate text-parchment-300">{n.name}</span>
                      <span className="ml-auto text-amber-400/70 flex-shrink-0 font-medium">
                        {Math.round(n.horn_weight * 100)}
                      </span>
                    </div>
                  ))}
                </>
              )}
              {Object.keys(clusterBreakdown).length > 0 && mode === "full" && (
                <>
                  <div className="text-amber-400 font-semibold mt-2 mb-1.5 text-[11px]">Clusters</div>
                  {Object.entries(clusterBreakdown).slice(0, 4).map(([label, count]) => (
                    <div key={label} className="flex justify-between text-parchment-500 gap-1">
                      <span className="truncate">{label}</span>
                      <span className="flex-shrink-0">{count}</span>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>
        )}

        {/* Legend — bottom left */}
        {!loading && !error && (
          <div className="absolute bottom-4 left-4 flex flex-wrap gap-x-3 gap-y-1 text-[9px]"
            style={{ color: "rgba(200,180,140,0.55)" }}>
            {Object.entries(TYPE_COLOR).map(([type, color]) => (
              <span key={type} className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full" style={{ background: color }} />
                {type.replace("_", " ")}
              </span>
            ))}
          </div>
        )}

        {/* Fullscreen hint — bottom right */}
        {!loading && !error && !isFullscreen && (
          <button onClick={toggleFullscreen}
            className="absolute bottom-4 right-4 text-[10px] px-2.5 py-1 rounded-lg border border-white/10 hover:border-amber-400/40 transition-colors"
            style={{ background: "rgba(8,6,2,0.70)", color: "rgba(200,168,75,0.7)", backdropFilter: "blur(4px)" }}>
            ⛶ Fullscreen
          </button>
        )}
      </div>

      {/* Hint */}
      {!loading && !error && (
        <p className="text-[10px] text-center select-none" style={{ color: "rgba(139,94,60,0.45)" }}>
          {mode === "egocentric"
            ? "Click a neighbor to search · ← Full Graph to go back · Drag to rotate · Scroll to zoom"
            : "Drag to rotate · Scroll to zoom · Click any node to explore · Click ◆ doc to open"}
        </p>
      )}
    </div>
  );
}
