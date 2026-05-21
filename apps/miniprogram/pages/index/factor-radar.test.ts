import assert from "node:assert/strict";
import { test } from "node:test";
import type { FactorScore } from "@stock-scorer/api-client";

import {
  buildRadarFactors,
  getNearestRadarIndex
} from "./factor-radar";

const sampleFactors: FactorScore[] = [
  { name: "质量/盈利", score: 90, evidence: ["ROIC 强"] },
  { name: "估值", score: 62, evidence: ["估值偏高"] },
  { name: "成长与预期", score: 84, evidence: ["EPS 稳定"] },
  { name: "投资纪律/财务稳健", score: 86, evidence: ["负债表稳健"] },
  { name: "中期动量与风险", score: 78, evidence: ["相对强势"] }
];

test("buildRadarFactors maps five factors to clockwise pentagon positions", () => {
  const factors = buildRadarFactors(sampleFactors);

  assert.equal(factors.length, 5);
  assert.deepEqual(
    factors.map((factor) => factor.percent),
    [90, 62, 84, 86, 78]
  );
  const firstFactor = factors[0];
  const secondFactor = factors[1];

  assert.ok(firstFactor);
  assert.ok(secondFactor);
  assert.equal(firstFactor.angleDeg, -90);
  assert.equal(secondFactor.angleDeg, -18);
  assert.equal(firstFactor.labelX, 50);
  assert.ok(firstFactor.labelY < 10);
});

test("getNearestRadarIndex selects the closest factor axis from a canvas tap", () => {
  const factors = buildRadarFactors(sampleFactors);
  const size = { width: 200, height: 200 };

  assert.equal(getNearestRadarIndex({ x: 100, y: 8 }, size, factors), 0);
  assert.equal(getNearestRadarIndex({ x: 190, y: 72 }, size, factors), 1);
  assert.equal(getNearestRadarIndex({ x: 20, y: 162 }, size, factors), 3);
});
