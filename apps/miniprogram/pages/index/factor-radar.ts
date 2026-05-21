import type { FactorScore } from "@stock-scorer/api-client";

const DEFAULT_CENTER = 50;
const DEFAULT_RADIUS = 34;
const DEFAULT_LABEL_RADIUS = 42;

export interface RadarOptions {
  center?: number;
  radius?: number;
  labelRadius?: number;
}

export interface Point {
  x: number;
  y: number;
}

export interface Size {
  width: number;
  height: number;
}

export interface RadarFactor extends FactorScore {
  index: number;
  percent: number;
  angleDeg: number;
  axisX: number;
  axisY: number;
  pointX: number;
  pointY: number;
  labelX: number;
  labelY: number;
  labelStyle: string;
}

function clampScore(score: number): number {
  const numericScore = Number(score);
  if (Number.isNaN(numericScore)) {
    return 0;
  }
  return Math.min(100, Math.max(0, numericScore));
}

function round(value: number): number {
  return Math.round(value * 10) / 10;
}

export function buildRadarFactors(factors: readonly FactorScore[] = [], options: RadarOptions = {}): RadarFactor[] {
  const center = options.center ?? DEFAULT_CENTER;
  const radius = options.radius ?? DEFAULT_RADIUS;
  const labelRadius = options.labelRadius ?? DEFAULT_LABEL_RADIUS;
  const count = factors.length || 1;

  return factors.map((factor, index) => {
    const angleDeg = -90 + (360 / count) * index;
    const angleRad = (angleDeg * Math.PI) / 180;
    const percent = clampScore(factor.score);
    const axisX = center + Math.cos(angleRad) * radius;
    const axisY = center + Math.sin(angleRad) * radius;
    const pointX = center + Math.cos(angleRad) * radius * (percent / 100);
    const pointY = center + Math.sin(angleRad) * radius * (percent / 100);
    const labelX = center + Math.cos(angleRad) * labelRadius;
    const labelY = center + Math.sin(angleRad) * labelRadius;

    return {
      ...factor,
      index,
      percent,
      angleDeg: round(angleDeg),
      axisX: round(axisX),
      axisY: round(axisY),
      pointX: round(pointX),
      pointY: round(pointY),
      labelX: round(labelX),
      labelY: round(labelY),
      labelStyle: `left: ${round(labelX)}%; top: ${round(labelY)}%;`
    };
  });
}

export function getNearestRadarIndex(point: Point | null | undefined, size: Size | null | undefined, factors: readonly RadarFactor[] = []): number {
  if (!point || !size || !size.width || !size.height || !factors.length) {
    return -1;
  }

  const pointX = (point.x / size.width) * 100;
  const pointY = (point.y / size.height) * 100;

  return factors.reduce(
    (nearest, factor, index) => {
      const targetX = Number.isFinite(factor.labelX) ? factor.labelX : factor.axisX;
      const targetY = Number.isFinite(factor.labelY) ? factor.labelY : factor.axisY;
      const distance = (pointX - targetX) ** 2 + (pointY - targetY) ** 2;

      if (distance < nearest.distance) {
        return { index, distance };
      }
      return nearest;
    },
    { index: -1, distance: Number.POSITIVE_INFINITY }
  ).index;
}
