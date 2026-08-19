"use client";

/**
 * Client-only Leaflet map for MandiSync route visualization.
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
    iconSize: [26, 26],
    iconAnchor: [13, 26],
    html: `
      <div style="
        width:26px;height:26px;border-radius:2px;
        background:${color};border:1px solid #fff;
        box-shadow:0 1px 4px rgba(12,39,68,.35);
        display:flex;align-items:center;justify-content:center;
        color:#fff;font:700 11px/1 'Noto Sans',sans-serif;
      ">${label}</div>
    `,
  });
}

function FlyToSelectedRoute({ route }: { route: ArbitrageRoute }) {
  const map = useMap();

  useEffect(() => {
    const bounds = L.latLngBounds([
      route.source_coordinates,
      route.destination_coordinates,
    ]);
    const reduceMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    if (reduceMotion) {
      map.fitBounds(bounds, { padding: [48, 48], maxZoom: 8 });
      return;
    }
    map.flyToBounds(bounds, {
      padding: [48, 48],
      maxZoom: 8,
      duration: 0.7,
    });
  }, [map, route]);

  return null;
}

export default function ArbitrageMap({ selectedRoute }: ArbitrageMapProps) {
  const sourceIcon = useMemo(() => createPinIcon("#1b6b3a", "S"), []);
  const destinationIcon = useMemo(() => createPinIcon("#c45c0a", "D"), []);

  const polylinePositions: LatLngExpression[] | null = selectedRoute
    ? [selectedRoute.source_coordinates, selectedRoute.destination_coordinates]
    : null;

  return (
    <MapContainer
      center={INDIA_CENTER}
      zoom={5}
      scrollWheelZoom
      className="h-full w-full"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {selectedRoute && (
        <>
          <FlyToSelectedRoute route={selectedRoute} />
          <Marker
            position={selectedRoute.source_coordinates}
            icon={sourceIcon}
          >
            <Tooltip direction="top" offset={[0, -16]} opacity={1}>
              Source: {selectedRoute.source_mandi}
            </Tooltip>
          </Marker>
          <Marker
            position={selectedRoute.destination_coordinates}
            icon={destinationIcon}
          >
            <Tooltip direction="top" offset={[0, -16]} opacity={1}>
              Destination: {selectedRoute.destination_mandi}
            </Tooltip>
          </Marker>
          {polylinePositions && (
            <Polyline
              positions={polylinePositions}
              pathOptions={{
                color: "#123a63",
                weight: 3,
                opacity: 0.85,
              }}
            />
          )}
        </>
      )}
    </MapContainer>
  );
}
