import type { CSSProperties } from "react";

// The Whitespace mark: a 3x3 isometric grid of markets with one gap, and the
// orange tile (the opportunity) hovering over it. Pure SVG, so it is sharp at any size.

const W = 100; // tile width
const H = 58; // tile height (isometric)
const D = 22; // tile thickness
const P = 108; // grid pitch (tile + gap)
const LIFT = 92; // how high the orange tile hovers

const GAP: [number, number] = [2, 0];
const TOPS: Record<string, string> = {
  "0,0": "var(--tile-2)",
  "1,0": "var(--tile-3)",
  "0,1": "var(--tile-3)",
  "1,1": "var(--tile-2)",
  "0,2": "var(--tile-1)",
  "2,1": "var(--tile-1)",
  "1,2": "var(--tile-3)",
  "2,2": "var(--tile-2)",
};

function center(i: number, j: number): [number, number] {
  return [((i - j) * P) / 2, (i + j) * P * 0.29];
}

function pts(points: [number, number][]): string {
  return points.map(([x, y]) => `${x},${y}`).join(" ");
}

function Tile({
  cx,
  cy,
  top,
  left = "var(--tile-side-l)",
  right = "var(--tile-side-r)",
}: {
  cx: number;
  cy: number;
  top: string;
  left?: string;
  right?: string;
}) {
  const n: [number, number] = [cx, cy - H / 2];
  const e: [number, number] = [cx + W / 2, cy];
  const s: [number, number] = [cx, cy + H / 2];
  const w: [number, number] = [cx - W / 2, cy];
  return (
    <>
      <polygon points={pts([w, s, [s[0], s[1] + D], [w[0], w[1] + D]])} fill={left} />
      <polygon points={pts([s, e, [e[0], e[1] + D], [s[0], s[1] + D]])} fill={right} />
      <polygon points={pts([n, e, s, w])} fill={top} />
    </>
  );
}

const delay = (ms: number) => ({ "--delay": `${ms}ms` }) as CSSProperties;

export function IsoGrid({
  animated = false,
  className,
  title = "Whitespace",
}: {
  animated?: boolean;
  className?: string;
  title?: string;
}) {
  // Back-to-front draw order so nearer tiles overlap farther ones.
  const cells: [number, number][] = [];
  for (let sum = 0; sum <= 4; sum++)
    for (let i = 0; i <= 2; i++) {
      const j = sum - i;
      if (j >= 0 && j <= 2) cells.push([i, j]);
    }

  const [gx, gy] = center(...GAP);
  const minX = -P - W / 2 - 8;
  const minY = -H / 2 - LIFT - 8;
  const width = 2 * P + W + 16;
  const height = 4 * P * 0.29 + H + D + LIFT + 16;

  return (
    <svg
      viewBox={`${minX} ${minY} ${width} ${height}`}
      className={className}
      role="img"
      aria-label={title}
    >
      {cells.map(([i, j], k) => {
        const [cx, cy] = center(i, j);
        if (i === GAP[0] && j === GAP[1]) {
          return (
            <polygon
              key="gap"
              className={animated ? "gap-pulse" : undefined}
              points={pts([
                [cx, cy - H / 2 + D * 0.6],
                [cx + W / 2, cy + D * 0.6],
                [cx, cy + H / 2 + D * 0.6],
                [cx - W / 2, cy + D * 0.6],
              ])}
              fill="#2c2a22"
              stroke="var(--accent)"
              strokeWidth={2}
              strokeDasharray="7 5"
              strokeOpacity={0.85}
            >
              {animated && <title>The gap: an open market</title>}
            </polygon>
          );
        }
        return (
          <g key={`${i},${j}`} className={animated ? "tile-in" : undefined} style={delay(k * 90)}>
            <Tile cx={cx} cy={cy} top={TOPS[`${i},${j}`]} />
          </g>
        );
      })}

      <g className={animated ? "tile-in" : undefined} style={delay(cells.length * 90 + 150)}>
        <g className={animated ? "ember-hover" : undefined}>
          <Tile
            cx={gx}
            cy={gy - LIFT}
            top="var(--accent)"
            left="var(--accent-strong)"
            right="var(--accent-side)"
          />
        </g>
      </g>
    </svg>
  );
}
