"use client";

/**
 * Client-only Leaflet map for MandiSync route visualization.
 * Loaded via next/dynamic with ssr:false from the dashboard page.
 */

import { useEffect, useMemo } from "react";
import {
  MapContainer,
  Marker,
  Polyline,
  TileLayer,
  Tooltip,
  useMap,
} from "react-leaflet";
import L, { type LatLngExpression } from "leaflet";

import type { ArbitrageRoute } from "@/lib/types";
import { INDIA_CENTER } from "@/lib/types";

interface ArbitrageMapProps {
  selectedRoute: ArbitrageRoute | null;
}

function createPinIcon(color: string, label: string) {
  return L.divIcon({
    className: "",
    iconSize: [28, 28],
    iconAnchor: [14, 28],
    html: `
      <div style="
        width:28px;height:28px;border-radius:9999px;
        background:${color};border:2px solid #e2e8f0;
        box-shadow:0 8px 18px rgba(0,0,0,.45);
        display:flex;align-items:center;justify-content:center;
        color:#0f172a;font:700 11px/1 Sora,sans-serif;
      ">${label}</div>
    `,
  });
}

/** Smoothly frames the selected buy→sell corridor on the map. */
function FlyToSelectedRoute({ route }: { route: ArbitrageRoute }) {
  const map = useMap();

  useEffect(() => {
    const bounds = L.latLngBounds([
      route.source_coordinates,
      route.destination_coordinates,
    ]);
    map.flyToBounds(bounds, {
      padding: [56, 56],
      maxZoom: 8,
      duration: 1.15,
    });
  }, [map, route]);

  return null;
}

export default function ArbitrageMap({ selectedRoute }: ArbitrageMapProps) {
  const sourceIcon = useMemo(() => createPinIcon("#22c55e", "S"), []);
  const destinationIcon = useMemo(() => createPinIcon("#ef4444", "D"), []);

  const polylinePositions: LatLngExpression[] | null = selectedRoute
    ? [selectedRoute.source_coordinates, selectedRoute.destination_coordinates]
    : null;

  return (
    <MapContainer
      center={INDIA_CENTER}
      zoom={5}
      scrollWheelZoom
      className="h-full w-full rounded-none"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {selectedRoute && (
        <>
          <FlyToSelectedRoute route={selectedRoute} />

          {/* Green = buy / source mandi */}
          <Marker
            position={selectedRoute.source_coordinates}
            icon={sourceIcon}
          >
            <Tooltip direction="top" offset={[0, -18]} opacity={0.95}>
              Source: {selectedRoute.source_mandi}
            </Tooltip>
          </Marker>

          {/* Red = sell / destination mandi */}
          <Marker
            position={selectedRoute.destination_coordinates}
            icon={destinationIcon}
          >
            <Tooltip direction="top" offset={[0, -18]} opacity={0.95}>
              Destination: {selectedRoute.destination_mandi}
            </Tooltip>
          </Marker>

          {/* Blue haul corridor between markets */}
          {polylinePositions && (
            <Polyline
              positions={polylinePositions}
              pathOptions={{
                color: "#38bdf8",
                weight: 4,
                opacity: 0.9,
              }}
            />
          )}
        </>
      )}
    </MapContainer>
  );
}
