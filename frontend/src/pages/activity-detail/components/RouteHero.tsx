import "leaflet/dist/leaflet.css";
import { useEffect } from "react";
import { CircleMarker, MapContainer, Polyline, TileLayer, useMap } from "react-leaflet";
import { useSettings } from "@/app/providers/settings-context";
import { mapTiles } from "@/lib/map-tiles";
import { boundsOf, decodePolyline, type LatLng } from "@/lib/polyline";
import { metaLabel } from "@/api/activity-detail";
import type { ActivityDetailDTO } from "@/types/activity-detail";

function FitBounds({ points }: { points: LatLng[] }) {
  const map = useMap();
  useEffect(() => {
    const b = boundsOf(points);
    if (b) map.fitBounds([[b.south, b.west], [b.north, b.east]], { padding: [24, 24] });
  }, [map, points]);
  return null;
}

function Caption({ detail }: { detail: ActivityDetailDTO }) {
  return (
    <div className="absolute left-0 right-0 bottom-0 px-[22px] pt-[46px] pb-[18px] z-[500]
                    bg-gradient-to-t from-surface-panel2 via-surface-panel2/80 to-transparent">
      <div className="flex items-center gap-[10px] mb-2">
        <span className="font-mono text-[9.5px] tracking-[0.1em] text-strava bg-strava-soft px-[9px] py-[3px] rounded-md uppercase">
          {detail.type}
        </span>
        <span className="font-mono text-[11px] text-subtle">{metaLabel(detail)}</span>
      </div>
      <div className="font-display font-semibold text-[26px] leading-[1.1] tracking-[-0.01em] text-ink">
        {detail.name}
      </div>
      {detail.location && (
        <div className="text-[13px] text-body mt-1">{detail.location}</div>
      )}
    </div>
  );
}

export default function RouteHero({ detail }: { detail: ActivityDetailDTO }) {
  const { isDark } = useSettings();
  const tiles = isDark ? mapTiles.dark : mapTiles.light;
  const points = detail.summary_polyline ? decodePolyline(detail.summary_polyline) : [];
  const start = points[0];
  const end = points[points.length - 1];

  return (
    <div className="relative bg-surface-panel2 border border-line rounded-[18px] overflow-hidden min-h-[330px]">
      {points.length > 0 && (
        <MapContainer
          className="absolute inset-0 h-full w-full"
          zoomControl={false}
          attributionControl
          dragging={false}
          scrollWheelZoom={false}
          doubleClickZoom={false}
          center={start}
          zoom={12}
        >
          <TileLayer url={tiles.url} attribution={tiles.attribution} />
          <Polyline positions={points} pathOptions={{ color: "#fc4c02", weight: 4 }} />
          {start && <CircleMarker center={start} radius={6}
            pathOptions={{ color: "#fff", weight: 2, fillColor: "#34d399", fillOpacity: 1 }} />}
          {end && <CircleMarker center={end} radius={6}
            pathOptions={{ color: "#fff", weight: 2, fillColor: "#fc4c02", fillOpacity: 1 }} />}
          <FitBounds points={points} />
        </MapContainer>
      )}
      <span className="absolute top-[14px] left-4 z-[500] font-mono text-[10px] tracking-[0.1em] text-white bg-black/70 px-[9px] py-[5px] rounded-md">
        GPS ROUTE
      </span>
      <Caption detail={detail} />
    </div>
  );
}
