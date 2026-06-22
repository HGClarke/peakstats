export type Units = "metric" | "imperial";

const M_PER_MILE = 1609.344;
const M_PER_FOOT = 0.3048;
const MPH_PER_MS = 2.2369362920544;

interface Measure {
  value: string;
  unit: string;
}

export function fmtDistance(meters: number, units: Units): Measure {
  return units === "imperial"
    ? { value: (meters / M_PER_MILE).toFixed(1), unit: "mi" }
    : { value: (meters / 1000).toFixed(1), unit: "km" };
}

export function fmtElevation(meters: number, units: Units): Measure {
  const v = units === "imperial" ? meters / M_PER_FOOT : meters;
  return {
    value: Math.round(v).toLocaleString("en-US"),
    unit: units === "imperial" ? "ft" : "m",
  };
}

export function fmtSpeed(ms: number, units: Units): Measure {
  return units === "imperial"
    ? { value: (ms * MPH_PER_MS).toFixed(1), unit: "mph" }
    : { value: (ms * 3.6).toFixed(1), unit: "km/h" };
}

function label({ value, unit }: Measure): string {
  return `${value} ${unit}`;
}

export function distanceLabel(meters: number, units: Units): string {
  return label(fmtDistance(meters, units));
}

export function elevationLabel(meters: number, units: Units): string {
  return label(fmtElevation(meters, units));
}

export function speedLabel(ms: number, units: Units): string {
  return label(fmtSpeed(ms, units));
}

export function distanceToMeters(value: number, units: Units): number {
  return units === "imperial" ? value * M_PER_MILE : value * 1000;
}

export function elevationToMeters(value: number, units: Units): number {
  return units === "imperial" ? value * M_PER_FOOT : value;
}
