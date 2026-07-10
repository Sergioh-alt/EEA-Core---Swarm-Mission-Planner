"use client";

import { useRef, useEffect, useState } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { useDroneStore } from "@/stores/droneStore";
import { getFieldPolygon, getPlannedRoutes, getFieldCenter } from "@/lib/mockDataProvider";
import { HealthLevel } from "@/contracts/types";
import type { DroneState } from "@/contracts/types";
import { Layers, Eye, EyeOff } from "lucide-react";

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN || "";

interface LayerVisibility {
  drones: boolean;
  routes: boolean;
  zones: boolean;
  alerts: boolean;
}

const DRONE_COLORS: Record<string, string> = {
  [HealthLevel.OK]: "#22c55e",
  [HealthLevel.WARNING]: "#f59e0b",
  [HealthLevel.CRITICAL]: "#ef4444",
};

function addFieldZoneToMap(mapInstance: mapboxgl.Map): void {
  const polygon = getFieldPolygon();
  const coords = polygon.map((p) => [p.lng, p.lat] as [number, number]);
  coords.push(coords[0]);

  if (mapInstance.getSource("field-zone")) return;

  mapInstance.addSource("field-zone", {
    type: "geojson",
    data: {
      type: "Feature",
      properties: {},
      geometry: {
        type: "Polygon",
        coordinates: [coords],
      },
    },
  });

  mapInstance.addLayer({
    id: "field-zone-fill",
    type: "fill",
    source: "field-zone",
    paint: {
      "fill-color": "#3b82f6",
      "fill-opacity": 0.1,
    },
  });

  mapInstance.addLayer({
    id: "field-zone-outline",
    type: "line",
    source: "field-zone",
    paint: {
      "line-color": "#3b82f6",
      "line-width": 2,
      "line-dasharray": [2, 2],
    },
  });
}

function addRoutesToMap(mapInstance: mapboxgl.Map): void {
  const routes = getPlannedRoutes();
  const routeColors = ["#06b6d4", "#8b5cf6", "#f97316"];

  Object.entries(routes).forEach(([droneId, route], index) => {
    const sourceId = `route-${droneId}`;
    if (mapInstance.getSource(sourceId)) return;

    const coords = route.map((p) => [p.lng, p.lat] as [number, number]);

    mapInstance.addSource(sourceId, {
      type: "geojson",
      data: {
        type: "Feature",
        properties: {},
        geometry: {
          type: "LineString",
          coordinates: coords,
        },
      },
    });

    mapInstance.addLayer({
      id: `${sourceId}-line`,
      type: "line",
      source: sourceId,
      paint: {
        "line-color": routeColors[index % routeColors.length],
        "line-width": 1.5,
        "line-opacity": 0.6,
        "line-dasharray": [4, 4],
      },
    });
  });
}

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
  const [layerVisibility, setLayerVisibility] = useState<LayerVisibility>({
    drones: true,
    routes: true,
    zones: true,
    alerts: true,
  });
  const [showLayerPanel, setShowLayerPanel] = useState(false);

  const drones = useDroneStore((s) => s.drones);
  const selectDrone = useDroneStore((s) => s.selectDrone);
  const selectedDroneId = useDroneStore((s) => s.selectedDroneId);

  // Initialize map once
  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    const center = getFieldCenter();

    if (!MAPBOX_TOKEN) {
      // mapbox-gl requires a non-empty access token to initialize its
      // session/telemetry manager even when rendering a fully custom
      // (non-mapbox://) style. A placeholder token satisfies that check;
      // no mapbox:// resources are requested in this OSM fallback path.
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
            {
              id: "background",
              type: "background",
              paint: {
                "background-color": "#0a0a0a",
              },
            },
            {
              id: "osm-tiles",
              type: "raster",
              source: "osm-tiles",
              minzoom: 0,
              maxzoom: 19,
              paint: {
                "raster-opacity": 0.55,
              },
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
      if (map.current) {
        addFieldZoneToMap(map.current);
        addRoutesToMap(map.current);
        map.current.resize();
      }
    });

    // Keep map sized to its flex container
    const container = mapContainer.current;
    const resizeObserver = new ResizeObserver(() => {
      map.current?.resize();
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, []);

  // Update drone markers
  useEffect(() => {
    if (!map.current || !layerVisibility.drones) {
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
      const color = DRONE_COLORS[drone.health] || "#6b7280";
      const isSelected = drone.drone_id === selectedDroneId;

      if (markersRef.current[drone.drone_id]) {
        markersRef.current[drone.drone_id].setLngLat([
          drone.position.longitude,
          drone.position.latitude,
        ]);
        const el = markersRef.current[drone.drone_id].getElement();
        el.innerHTML = buildMarkerHTML(drone.drone_id, color, drone.heading_deg, isSelected);
      } else {
        const el = document.createElement("div");
        el.innerHTML = buildMarkerHTML(drone.drone_id, color, drone.heading_deg, isSelected);
        el.style.cursor = "pointer";
        el.addEventListener("click", () => {
          selectDrone(drone.drone_id);
        });

        const marker = new mapboxgl.Marker({ element: el })
          .setLngLat([drone.position.longitude, drone.position.latitude])
          .addTo(map.current!);

        markersRef.current[drone.drone_id] = marker;
      }
    });
  }, [drones, layerVisibility.drones, selectedDroneId, selectDrone]);

  // Toggle zone visibility
  useEffect(() => {
    if (!map.current) return;
    const visibility = layerVisibility.zones ? "visible" : "none";
    if (map.current.getLayer("field-zone-fill")) {
      map.current.setLayoutProperty("field-zone-fill", "visibility", visibility);
    }
    if (map.current.getLayer("field-zone-outline")) {
      map.current.setLayoutProperty("field-zone-outline", "visibility", visibility);
    }
  }, [layerVisibility.zones]);

  // Toggle route visibility
  useEffect(() => {
    if (!map.current) return;
    const visibility = layerVisibility.routes ? "visible" : "none";
    for (let i = 1; i <= 3; i++) {
      const layerId = `route-${i}-line`;
      if (map.current.getLayer(layerId)) {
        map.current.setLayoutProperty(layerId, "visibility", visibility);
      }
    }
  }, [layerVisibility.routes]);

  // Fly to selected drone
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

      {/* Layer toggle panel */}
      <div className="absolute top-3 right-3 z-10">
        <button
          onClick={() => setShowLayerPanel(!showLayerPanel)}
          className="flex items-center gap-1.5 rounded-md bg-neutral-900/90 border border-neutral-700 px-2.5 py-1.5 text-xs text-neutral-300 hover:bg-neutral-800 transition-colors"
        >
          <Layers className="h-3.5 w-3.5" />
          Layers
        </button>

        {showLayerPanel && (
          <div className="mt-1 rounded-md bg-neutral-900/95 border border-neutral-700 p-2 space-y-1 min-w-[140px]">
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
                <span className="capitalize">{key}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Map attribution */}
      {!MAPBOX_TOKEN && (
        <div className="absolute bottom-3 left-3 z-10 rounded bg-neutral-900/90 border border-neutral-700 px-2 py-1 text-[10px] text-neutral-500">
          OSM tiles (set NEXT_PUBLIC_MAPBOX_TOKEN for Mapbox Dark)
        </div>
      )}
    </div>
  );
}
