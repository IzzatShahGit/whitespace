"use client";

import { geoEqualEarth, geoPath } from "d3-geo";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { feature } from "topojson-client";
import type { GeometryCollection, Topology } from "topojson-specification";

import { ISO_NUMERIC } from "@/lib/iso-numeric";

export type MapValue = {
  code: string; // ISO3
  name: string;
  level: 1 | 2 | 3 | 4 | 5; // shade, 5 = strongest
  detail: string; // tooltip line, e.g. "#1 · Go for it · $164M"
  href?: string;
};

type Country = Feature<Geometry, { name: string }> & { id?: string };

const WIDTH = 960;
const HEIGHT = 470;
const ANTARCTICA = "010";

/** Loaded on first use, then shared: the outline file is ~100 KB. */
let shapes: Promise<Country[]> | null = null;
function loadShapes(): Promise<Country[]> {
  shapes ??= import("world-atlas/countries-110m.json").then((mod) => {
    const topo = (mod.default ?? mod) as unknown as Topology<{
      countries: GeometryCollection<{ name: string }>;
    }>;
    const fc = feature(topo, topo.objects.countries) as FeatureCollection<
      Geometry,
      { name: string }
    >;
    return (fc.features as Country[]).filter((f) => f.id !== ANTARCTICA);
  });
  return shapes;
}

/**
 * A choropleth: each market shaded by how strong the opportunity is, the user's own
 * country outlined. Hover (or focus) for details; click to open the market.
 * The ranked list beside it carries the same data, so the map is never the only way in.
 */
export function WorldMap({
  values,
  home,
  label,
}: {
  values: MapValue[];
  home?: string; // ISO3 of the user's country
  label: string;
}) {
  const router = useRouter();
  const [countries, setCountries] = useState<Country[] | null>(null);
  const [hover, setHover] = useState<{ value: MapValue; x: number; y: number } | null>(null);

  useEffect(() => {
    let live = true;
    void loadShapes().then((c) => live && setCountries(c));
    return () => {
      live = false;
    };
  }, []);

  const byNumeric = useMemo(() => {
    const out = new Map<string, MapValue>();
    for (const v of values) {
      const id = ISO_NUMERIC[v.code];
      if (id) out.set(id, v);
    }
    return out;
  }, [values]);
  const homeId = home ? ISO_NUMERIC[home] : undefined;

  const path = useMemo(() => {
    if (!countries) return null;
    const projection = geoEqualEarth().fitSize([WIDTH, HEIGHT], {
      type: "FeatureCollection",
      features: countries,
    });
    return geoPath(projection);
  }, [countries]);

  if (!countries || !path) return <div aria-hidden className="skeleton aspect-[96/47] w-full" />;

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={label}
        className="h-auto w-full"
        onMouseLeave={() => setHover(null)}
      >
        {countries.map((c) => {
          const value = c.id ? byNumeric.get(c.id) : undefined;
          const isHome = c.id === homeId;
          return (
            <path
              key={c.id ?? c.properties.name}
              d={path(c) ?? undefined}
              fill={value ? `var(--map-${value.level})` : "var(--map-empty)"}
              stroke={isHome ? "var(--accent)" : "var(--surface)"}
              strokeWidth={isHome ? 1.6 : 0.5}
              className={value ? "cursor-pointer transition-opacity hover:opacity-80" : undefined}
              onMouseMove={(e) => {
                if (!value) return setHover(null);
                const box = e.currentTarget.ownerSVGElement!.getBoundingClientRect();
                setHover({ value, x: e.clientX - box.left, y: e.clientY - box.top });
              }}
              onClick={() => value?.href && router.push(value.href)}
            />
          );
        })}
      </svg>
      {hover && (
        <div
          role="tooltip"
          className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-[calc(100%+12px)] rounded-xl border border-line bg-surface px-3 py-2 text-xs shadow-pop"
          style={{ left: hover.x, top: hover.y }}
        >
          <p className="font-medium text-fg">{hover.value.name}</p>
          <p className="text-muted">{hover.value.detail}</p>
        </div>
      )}
      <div className="mt-3 flex items-center gap-2 text-xs text-subtle">
        <span>Weaker</span>
        {[1, 2, 3, 4, 5].map((level) => (
          <span
            key={level}
            className="h-2 w-6 rounded-full"
            style={{ background: `var(--map-${level})` }}
          />
        ))}
        <span>Stronger opportunity</span>
        {home && (
          <span className="ml-auto flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm border-2 border-accent" /> You
          </span>
        )}
      </div>
    </div>
  );
}
