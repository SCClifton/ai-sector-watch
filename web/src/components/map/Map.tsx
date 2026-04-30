"use client";

import { useEffect, useMemo, useRef } from "react";
import maplibregl from "maplibre-gl";
import Supercluster from "supercluster";
import "maplibre-gl/dist/maplibre-gl.css";

import type { Company } from "@/lib/types";
import { primarySectorHex } from "@/lib/taxonomy";
import { isRecentlyFunded, isRecentlyVerified } from "@/lib/freshness";

interface MapProps {
  companies: Company[];
  selectedId: string | null;
  onSelect: (companyId: string | null) => void;
}

const ANZ_BOUNDS: [[number, number], [number, number]] = [
  [110, -47],
  [180, -8],
];

// Free vector tiles, no API key. https://openfreemap.org
const STYLE_URL = "https://tiles.openfreemap.org/styles/positron";

interface PointProps {
  companyId: string;
  name: string;
  hex: string;
  fresh: boolean;
}

type ClusterFeature =
  | Supercluster.PointFeature<PointProps>
  | Supercluster.ClusterFeature<PointProps>;

export function Map({ companies, selectedId, onSelect }: MapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<Record<string, maplibregl.Marker>>({});
  const clusterRef = useRef<Supercluster<PointProps> | null>(null);
  const onSelectRef = useRef(onSelect);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  // Build the supercluster index from the filtered companies.
  const features = useMemo<Supercluster.PointFeature<PointProps>[]>(() => {
    const now = new Date();
    return companies
      .filter((c) => c.lat !== null && c.lon !== null)
      .map((c) => ({
        type: "Feature",
        properties: {
          companyId: c.id,
          name: c.name,
          hex: primarySectorHex(c.sector_tags),
          fresh: isRecentlyVerified(c, now) || isRecentlyFunded(c, now),
        },
        geometry: { type: "Point", coordinates: [c.lon as number, c.lat as number] },
      }));
  }, [companies]);

  // Initialise the map once.
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE_URL,
      bounds: ANZ_BOUNDS,
      fitBoundsOptions: { padding: 40 },
      attributionControl: { compact: true },
      cooperativeGestures: false,
      maxZoom: 14,
      minZoom: 2,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");

    const renderHandler = () => {
      renderMarkers(map, clusterRef.current, markersRef.current, onSelectRef);
    };
    map.on("moveend", renderHandler);
    map.on("zoomend", renderHandler);
    map.on("load", renderHandler);

    mapRef.current = map;

    return () => {
      map.off("moveend", renderHandler);
      map.off("zoomend", renderHandler);
      map.off("load", renderHandler);
      Object.values(markersRef.current).forEach((m) => m.remove());
      markersRef.current = {};
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Rebuild supercluster whenever the filtered features change, then re-render.
  useEffect(() => {
    const cluster = new Supercluster<PointProps>({
      radius: 60,
      maxZoom: 12,
      minPoints: 3,
    });
    cluster.load(features);
    clusterRef.current = cluster;

    if (mapRef.current) {
      renderMarkers(mapRef.current, cluster, markersRef.current, onSelectRef);
    }
  }, [features]);

  // Highlight the selected marker without rebuilding everything.
  useEffect(() => {
    Object.entries(markersRef.current).forEach(([id, marker]) => {
      const el = marker.getElement();
      if (id === selectedId) {
        el.classList.add("aisw-marker--selected");
      } else {
        el.classList.remove("aisw-marker--selected");
      }
    });
  }, [selectedId, features]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />
      <style>{`
        .aisw-marker {
          width: 14px;
          height: 14px;
          border-radius: 999px;
          border: 2px solid #0B0F14;
          box-shadow: 0 0 0 1px rgba(255,255,255,0.2), 0 4px 10px rgba(0,0,0,0.4);
          cursor: pointer;
          transition: transform 120ms ease, box-shadow 120ms ease;
        }
        .aisw-marker--fresh {
          box-shadow: 0 0 0 1px rgba(255,255,255,0.2),
                      0 0 0 4px rgba(61,220,132,0.55),
                      0 4px 10px rgba(0,0,0,0.4);
        }
        .aisw-marker:hover {
          transform: scale(1.35);
          box-shadow: 0 0 0 2px rgba(244,183,64,0.6), 0 6px 14px rgba(0,0,0,0.5);
        }
        .aisw-marker--fresh:hover {
          box-shadow: 0 0 0 2px rgba(244,183,64,0.6),
                      0 0 0 5px rgba(61,220,132,0.5),
                      0 6px 14px rgba(0,0,0,0.5);
        }
        .aisw-marker--selected {
          transform: scale(1.55);
          box-shadow: 0 0 0 3px rgba(244,183,64,0.9), 0 6px 14px rgba(0,0,0,0.55);
        }
        .aisw-cluster {
          display: grid;
          place-items: center;
          border-radius: 999px;
          background: rgba(244, 183, 64, 0.18);
          color: #FFD074;
          font-weight: 600;
          font-size: 12px;
          border: 1.5px solid rgba(244, 183, 64, 0.7);
          backdrop-filter: blur(2px);
          cursor: pointer;
          transition: transform 120ms ease;
        }
        .aisw-cluster:hover {
          transform: scale(1.08);
        }
      `}</style>
    </div>
  );
}

function renderMarkers(
  map: maplibregl.Map,
  cluster: Supercluster<PointProps> | null,
  markers: Record<string, maplibregl.Marker>,
  onSelectRef: { current: (id: string | null) => void },
) {
  if (!cluster) return;

  const bounds = map.getBounds();
  const bbox: [number, number, number, number] = [
    bounds.getWest(),
    bounds.getSouth(),
    bounds.getEast(),
    bounds.getNorth(),
  ];
  const zoom = Math.round(map.getZoom());
  const items = cluster.getClusters(bbox, zoom) as ClusterFeature[];
  const seen = new Set<string>();

  for (const feature of items) {
    const [lng, lat] = feature.geometry.coordinates;
    const isCluster = "cluster" in feature.properties && feature.properties.cluster;
    const key = isCluster
      ? `cluster-${feature.id}`
      : `point-${feature.properties.companyId}`;

    seen.add(key);

    let marker = markers[key];
    if (!marker) {
      const el = buildMarkerEl(feature, () => {
        if (isCluster) {
          const expansionZoom = Math.min(
            cluster.getClusterExpansionZoom(feature.id as number),
            14,
          );
          map.flyTo({ center: [lng, lat], zoom: expansionZoom, duration: 500 });
        } else {
          onSelectRef.current(feature.properties.companyId);
        }
      });
      marker = new maplibregl.Marker({ element: el, anchor: "center" })
        .setLngLat([lng, lat])
        .addTo(map);
      markers[key] = marker;
    } else {
      marker.setLngLat([lng, lat]);
    }
  }

  for (const key of Object.keys(markers)) {
    if (!seen.has(key)) {
      markers[key].remove();
      delete markers[key];
    }
  }
}

function buildMarkerEl(feature: ClusterFeature, onClick: () => void): HTMLElement {
  const el = document.createElement("button");
  el.type = "button";
  el.addEventListener("click", (e) => {
    e.stopPropagation();
    onClick();
  });

  const isCluster = "cluster" in feature.properties && feature.properties.cluster;
  if (isCluster) {
    const count = (feature.properties as Supercluster.ClusterProperties).point_count;
    const size = count < 10 ? 30 : count < 50 ? 38 : count < 200 ? 46 : 54;
    el.className = "aisw-cluster";
    el.style.width = `${size}px`;
    el.style.height = `${size}px`;
    el.textContent = String(count);
    el.setAttribute("aria-label", `Cluster of ${count} companies. Click to zoom in.`);
  } else {
    const props = feature.properties as PointProps;
    el.className = props.fresh ? "aisw-marker aisw-marker--fresh" : "aisw-marker";
    el.style.background = props.hex;
    el.setAttribute("aria-label", `${props.name}. Click for details.`);
    el.title = props.name;
  }
  return el;
}
