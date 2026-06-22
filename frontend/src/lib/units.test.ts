import { describe, expect, it } from "vitest";
import {
  distanceLabel, distanceToMeters, elevationLabel, elevationToMeters,
  fmtDistance, fmtElevation, fmtSpeed, speedLabel,
} from "./units";

describe("units — metric", () => {
  it("distance in km", () => expect(fmtDistance(38700, "metric")).toEqual({ value: "38.7", unit: "km" }));
  it("elevation in m", () => expect(fmtElevation(1240, "metric")).toEqual({ value: "1,240", unit: "m" }));
  it("speed in km/h", () => expect(fmtSpeed(6.889, "metric")).toEqual({ value: "24.8", unit: "km/h" }));
  it("labels", () => {
    expect(distanceLabel(38700, "metric")).toBe("38.7 km");
    expect(elevationLabel(1240, "metric")).toBe("1,240 m");
    expect(speedLabel(6.889, "metric")).toBe("24.8 km/h");
  });
});

describe("units — imperial", () => {
  it("distance in mi", () => expect(fmtDistance(1609.344, "imperial")).toEqual({ value: "1.0", unit: "mi" }));
  it("elevation in ft", () => expect(fmtElevation(1000, "imperial")).toEqual({ value: "3,281", unit: "ft" }));
  it("speed in mph", () => expect(fmtSpeed(10, "imperial")).toEqual({ value: "22.4", unit: "mph" }));
});

describe("units — input → meters", () => {
  it("metric distance km→m", () => expect(distanceToMeters(5, "metric")).toBe(5000));
  it("imperial distance mi→m", () => expect(distanceToMeters(1, "imperial")).toBeCloseTo(1609.344, 3));
  it("metric elevation m→m", () => expect(elevationToMeters(100, "metric")).toBe(100));
  it("imperial elevation ft→m", () => expect(elevationToMeters(100, "imperial")).toBeCloseTo(30.48, 2));
});
