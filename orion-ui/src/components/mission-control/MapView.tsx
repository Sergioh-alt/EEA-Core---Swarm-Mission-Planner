"use client";

import { useRef, useEffect, useState, useMemo } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { useDroneStore } from "@/stores/droneStore";
import { useAlertStore } from "@/stores/alertStore";
import { loadMissionGeometry } from "@/lib/missionGeometry";
import { HealthLevel } from "@/contracts/types";
import type { DroneState, MissionGeometry } from "@/contracts/types";
import { Layers, Eye, EyeOff } from "lucide-react";

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN || "";

interface LayerVisibility {
  drones: boolean;
  plannedRoutes: boolean;
  executedRoutes: boolean;
  zones: boolean;
  coverage: boolean;
  alerts: boolean;
  events: boolean;
}

const LAYER_LABELS: Record<keyof LayerVisibility, string> = {
  drones: "Drones",
  plannedRoutes: "Planned routes",
  executedRoutes: "Executed routes",
  zones: "Mission zones",
  coverage: "Coverage",
  alerts: "Alerts",
  events: "Event markers",
};

const DRONE_COLORS: Record<string, string> = {
  [HealthLevel.OK]: "#22c55e",
  [HealthLevel.WARNING]: "#f59e0b",
  [HealthLevel.CRITICAL]: "#ef4444",
};

const ROUTE_COLORS = ["#06b6d4", "#8b5cf6", "#f97316", "#eab308", "#ec4899"];

function buildMarkerHTML(
  droneId: number,
  color: string,
  heading: number,
  isSelected: boolean
): string {
  const size = isSelected ? 40 : 32;
  const ring = isSelected ? `stroke="${color}" stroke-width="2"` : "";
  return `
    <svg width="${size}" height="${size}" viewBox="0 0 40 40" xmlns="http://www.w3.org/2000/svg">
      <circle cx="20" cy="20" r="18" fill="${color}20" ${ring} />
      <g transform="rotate(${heading}, 20, 20)">
        <path d="M20 8 L26 28 L20 24 L14 28 Z" fill="${color}" opacity="0.9"/>
      </g>
      <text x="20" y="36" text-anchor="middle" font-size="8" fill="${color}" font-weight="bold">${droneId}</text>
    </svg>
  `;
}

export function MapView() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const markersRef = useRef<Record<number, mapboxgl.Marker>>({});
  const executedRef = useRef<Record<number, [number, number][]>>({});
  const [mapLoaded, setMapLoaded] = useState(false);
  const [geometry, setGeometry] = useState<MissionGeometry | null>(null);
  const [layerVisibility, setLayerVisibility] = useState<LayerVisibility>({
    drones: true,
    plannedRoutes: true,
    executedRoutes: true,
    zones: true,
    coverage: false,
    alerts: true,
    events: false,
  });
  const [showLayerPanel, setShowLayerPanel] = useState(false);

  const drones = useDroneStore((s) => s.drones);
  const selectDrone = useDroneStore((s) => s.selectDrone);
  const selectedDroneId = useDroneStore((s) => s.selectedDroneId);
  const alerts = useAlertStore((s) => s.alerts);

  const activeAlertDroneIds = useMemo(() => {
    const ids = new Set<number>();
    for (const a of alerts) {
      if (!a.active) continue;
      const m = /drone_(\d+)/.exec(a.source);
      if (m) ids.add(Number(m[1]));
    }
    return ids;
  }, [alerts]);

  // Load mission geometry (backend in live mode, mock fallback otherwise).
  useEffect(() => {
    let cancelled = false;
    loadMissionGeometry().then((g) => {
      if (!cancelled) setGeometry(g);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  // Initialize map once.
  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    const center = { lat: 38.7223, lng: -9.1393 };

    if (!MAPBOX_TOKEN) {
      mapboxgl.accessToken = "no-token";
      map.current = new mapboxgl.Map({
        container: mapContainer.current,
        style: {
          version: 8,
          sources: {
            "osm-tiles": {
              type: "raster",
              tiles: [
                "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
                "https://b.tile.openstreetmap.org/{z}/{x}/{y}.png",
              ],
              tileSize: 256,
              attribution: "&copy; OpenStreetMap contributors",
            },
          },
          layers: [
            { id: "background", type: "background", paint: { "background-color": "#0a0a0a" } },
            {
              id: "osm-tiles",
              type: "raster",
              source: "osm-tiles",
              minzoom: 0,
              maxzoom: 19,
              paint: { "raster-opacity": 0.55 },
            },
          ],
        },
        center: [center.lng, center.lat],
        zoom: 15,
      });
    } else {
      map.current = new mapboxgl.Map({
        container: mapContainer.current,
        style: "mapbox://styles/mapbox/dark-v11",
        center: [center.lng, center.lat],
        zoom: 15,
        accessToken: MAPBOX_TOKEN,
      });
    }

    map.current.on("load", () => {
      map.current?.resize();
      setMapLoaded(true);
    });

    const container = mapContainer.current;
    const resizeObserver = new ResizeObserver(() => map.current?.resize());
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
      markersRef.current = {};
      setMapLoaded(false);
    };
  }, []);

  // Add static geometry layers (zone, planned routes, waypoints) once ready.
  useEffect(() => {
    const m = map.current;
    if (!m || !mapLoaded || !geometry) return;

    // Field zone.
    if (!m.getSource("field-zone")) {
      const coords = geometry.field_polygon.map(
        (p) => [p.lng, p.lat] as [number, number]
      );
      if (coords.length) coords.push(coords[0]);
      m.addSource("field-zone", {
        type: "geojson",
        data: {
          type: "Feature",
          properties: {},
          geometry: { type: "Polygon", coordinates: [coords] },
        },
      });
      m.addLayer({
        id: "field-zone-fill",
        type: "fill",
        source: "field-zone",
        paint: { "fill-color": "#3b82f6", "fill-opacity": 0.1 },
      });
      m.addLayer({
        id: "field-zone-outline",
        type: "line",
        source: "field-zone",
        paint: { "line-color": "#3b82f6", "line-width": 2, "line-dasharray": [2, 2] },
      });
    }

    // Planned routes + waypoint (event) markers.
    const waypointFeatures: GeoJSON.Feature[] = [];
    Object.entries(geometry.planned_routes).forEach(([id, route], index) => {
      const sourceId = `planned-${id}`;
      if (!m.getSource(sourceId)) {
        const coords = route.map((p) => [p.lng, p.lat] as [number, number]);
        m.addSource(sourceId, {
          type: "geojson",
          data: {
            type: "Feature",
            properties: {},
            geometry: { type: "LineString", coordinates: coords },
          },
        });
        m.addLayer({
          id: `${sourceId}-line`,
          type: "line",
          source: sourceId,
          paint: {
            "line-color": ROUTE_COLORS[index % ROUTE_COLORS.length],
            "line-width": 1.5,
            "line-opacity": 0.6,
            "line-dasharray": [4, 4],
          },
        });
      }
      route.forEach((p) => {
        waypointFeatures.push({
          type: "Feature",
          properties: {},
          geometry: { type: "Point", coordinates: [p.lng, p.lat] },
        });
      });
    });

    if (!m.getSource("waypoints")) {
      m.addSource("waypoints", {
        type: "geojson",
        data: { type: "FeatureCollection", features: waypointFeatures },
      });
      m.addLayer({
        id: "waypoints-circles",
        type: "circle",
        source: "waypoints",
        layout: { visibility: "none" },
        paint: {
          "circle-radius": 2.5,
          "circle-color": "#94a3b8",
          "circle-opacity": 0.7,
        },
      });
    }
  }, [mapLoaded, geometry]);

  // Executed routes + coverage — accumulate REAL drone positions.
  useEffect(() => {
    const m = map.current;
    if (!m || !mapLoaded) return;

    drones.forEach((drone) => {
      const lng = drone.position.longitude;
      const lat = drone.position.latitude;
      if (lng === 0 && lat === 0) return;
      const path = executedRef.current[drone.drone_id] ?? [];
      const last = path[path.length - 1];
      if (!last || last[0] !== lng || last[1] !== lat) {
        path.push([lng, lat]);
        executedRef.current[drone.drone_id] = path.slice(-500);
      }

      const sourceId = `executed-${drone.drone_id}`;
      const data: GeoJSON.Feature = {
        type: "Feature",
        properties: {},
        geometry: { type: "LineString", coordinates: executedRef.current[drone.drone_id] },
      };
      const existing = m.getSource(sourceId) as mapboxgl.GeoJSONSource | undefined;
      if (existing) {
        existing.setData(data);
      } else {
        m.addSource(sourceId, { type: "geojson", data });
        m.addLayer({
          id: `${sourceId}-line`,
          type: "line",
          source: sourceId,
          layout: { visibility: layerVisibility.executedRoutes ? "visible" : "none" },
          paint: { "line-color": "#22d3ee", "line-width": 2.5, "line-opacity": 0.9 },
        });
        m.addLayer({
          id: `${sourceId}-coverage`,
          type: "line",
          source: sourceId,
          layout: { visibility: layerVisibility.coverage ? "visible" : "none" },
          paint: { "line-color": "#16a34a", "line-width": 18, "line-opacity": 0.12 },
        });
      }
    });
  }, [drones, mapLoaded, layerVisibility.executedRoutes, layerVisibility.coverage]);

  // Drone markers.
  useEffect(() => {
    if (!map.current || !mapLoaded || !layerVisibility.drones) {
      Object.values(markersRef.current).forEach((m) => m.remove());
      markersRef.current = {};
      return;
    }

    const currentIds = new Set(drones.map((d: DroneState) => d.drone_id));
    Object.keys(markersRef.current).forEach((id) => {
      if (!currentIds.has(Number(id))) {
        markersRef.current[Number(id)].remove();
        delete markersRef.current[Number(id)];
      }
    });

    drones.forEach((drone: DroneState) => {
      const hasAlert =
        layerVisibility.alerts && activeAlertDroneIds.has(drone.drone_id);
      const color = hasAlert
        ? "#ef4444"
        : DRONE_COLORS[drone.health] || "#6b7280";
      const isSelected = drone.drone_id === selectedDroneId;
      const lngLat: [number, number] = [
        drone.position.longitude,
        drone.position.latitude,
      ];

      if (markersRef.current[drone.drone_id]) {
        markersRef.current[drone.drone_id].setLngLat(lngLat);
        const el = markersRef.current[drone.drone_id].getElement();
        el.innerHTML = buildMarkerHTML(drone.drone_id, color, drone.heading_deg, isSelected);
      } else {
        const el = document.createElement("div");
        el.innerHTML = buildMarkerHTML(drone.drone_id, color, drone.heading_deg, isSelected);
        el.style.cursor = "pointer";
        el.addEventListener("click", () => selectDrone(drone.drone_id));
        const marker = new mapboxgl.Marker({ element: el })
          .setLngLat(lngLat)
          .addTo(map.current!);
        markersRef.current[drone.drone_id] = marker;
      }
    });
  }, [drones, mapLoaded, layerVisibility.drones, layerVisibility.alerts, selectedDroneId, selectDrone, activeAlertDroneIds]);

  // Layer visibility toggles.
  useEffect(() => {
    const m = map.current;
    if (!m || !mapLoaded) return;
    const setVis = (id: string, on: boolean) => {
      if (m.getLayer(id)) m.setLayoutProperty(id, "visibility", on ? "visible" : "none");
    };
    setVis("field-zone-fill", layerVisibility.zones);
    setVis("field-zone-outline", layerVisibility.zones);
    setVis("waypoints-circles", layerVisibility.events);
    for (const key of Object.keys(executedRef.current)) {
      setVis(`executed-${key}-line`, layerVisibility.executedRoutes);
      setVis(`executed-${key}-coverage`, layerVisibility.coverage);
    }
    if (geometry) {
      for (const id of Object.keys(geometry.planned_routes)) {
        setVis(`planned-${id}-line`, layerVisibility.plannedRoutes);
      }
    }
  }, [layerVisibility, mapLoaded, geometry]);

  // Alert emphasis: markers already recolor; fly to selected drone.
  useEffect(() => {
    if (!map.current || !selectedDroneId) return;
    const drone = drones.find((d: DroneState) => d.drone_id === selectedDroneId);
    if (drone) {
      map.current.flyTo({
        center: [drone.position.longitude, drone.position.latitude],
        zoom: 17,
        duration: 800,
      });
    }
  }, [selectedDroneId, drones]);

  const toggleLayer = (layer: keyof LayerVisibility) => {
    setLayerVisibility((prev) => ({ ...prev, [layer]: !prev[layer] }));
  };

  return (
    <div className="relative w-full h-full min-h-[400px] rounded-lg overflow-hidden border border-neutral-800">
      <div
        ref={mapContainer}
        className="absolute inset-0"
        style={{ position: "absolute", top: 0, right: 0, bottom: 0, left: 0 }}
      />

      <div className="absolute top-3 right-3 z-10">
        <button
          onClick={() => setShowLayerPanel(!showLayerPanel)}
          className="flex items-center gap-1.5 rounded-md bg-neutral-900/90 border border-neutral-700 px-2.5 py-1.5 text-xs text-neutral-300 hover:bg-neutral-800 transition-colors"
        >
          <Layers className="h-3.5 w-3.5" />
          Layers
        </button>

        {showLayerPanel && (
          <div className="mt-1 rounded-md bg-neutral-900/95 border border-neutral-700 p-2 space-y-1 min-w-[160px]">
            {(
              Object.entries(layerVisibility) as [keyof LayerVisibility, boolean][]
            ).map(([key, visible]) => (
              <button
                key={key}
                onClick={() => toggleLayer(key)}
                className="flex items-center gap-2 w-full rounded px-2 py-1 text-xs text-neutral-300 hover:bg-neutral-800 transition-colors"
              >
                {visible ? (
                  <Eye className="h-3 w-3 text-blue-400" />
                ) : (
                  <EyeOff className="h-3 w-3 text-neutral-600" />
                )}
                <span>{LAYER_LABELS[key]}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {!MAPBOX_TOKEN && (
        <div className="absolute bottom-3 left-3 z-10 rounded bg-neutral-900/90 border border-neutral-700 px-2 py-1 text-[10px] text-neutral-500">
          OSM tiles (set NEXT_PUBLIC_MAPBOX_TOKEN for Mapbox Dark)
        </div>
      )}
    </div>
  );
}
