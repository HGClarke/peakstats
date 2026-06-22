export type LatLng = [number, number];

/** Decode a Google encoded polyline (precision 5) into [lat, lng] pairs. */
export function decodePolyline(encoded: string): LatLng[] {
  const points: LatLng[] = [];
  let index = 0;
  let lat = 0;
  let lng = 0;
  while (index < encoded.length) {
    let result = 0;
    let shift = 0;
    let byte: number;
    do {
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    lat += result & 1 ? ~(result >> 1) : result >> 1;
    result = 0;
    shift = 0;
    do {
      byte = encoded.charCodeAt(index++) - 63;
      result |= (byte & 0x1f) << shift;
      shift += 5;
    } while (byte >= 0x20);
    lng += result & 1 ? ~(result >> 1) : result >> 1;
    points.push([lat / 1e5, lng / 1e5]);
  }
  return points;
}

export function boundsOf(points: LatLng[]) {
  if (points.length === 0) return null;
  let south = points[0][0];
  let north = points[0][0];
  let west = points[0][1];
  let east = points[0][1];
  for (const [la, ln] of points) {
    south = Math.min(south, la);
    north = Math.max(north, la);
    west = Math.min(west, ln);
    east = Math.max(east, ln);
  }
  return { south, west, north, east };
}
