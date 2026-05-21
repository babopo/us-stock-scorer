const DEFAULT_CENTER = 50;
const DEFAULT_RADIUS = 34;
const DEFAULT_LABEL_RADIUS = 42;

function clampScore(score) {
  const numericScore = Number(score);
  if (Number.isNaN(numericScore)) {
    return 0;
  }
  return Math.min(100, Math.max(0, numericScore));
}

function round(value) {
  return Math.round(value * 10) / 10;
}

function buildRadarFactors(factors = [], options = {}) {
  const center = options.center || DEFAULT_CENTER;
  const radius = options.radius || DEFAULT_RADIUS;
  const labelRadius = options.labelRadius || DEFAULT_LABEL_RADIUS;
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

function getNearestRadarIndex(point, size, factors = []) {
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

module.exports = {
  buildRadarFactors,
  getNearestRadarIndex
};
