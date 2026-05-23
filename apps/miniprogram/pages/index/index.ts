import type { StockScoreResponse } from "@stock-scorer/api-client";

import type { AppOption } from "../../app";
import { createMiniProgramApiClient, getApiErrorMessage } from "../../utils/api";
import {
  buildRadarFactors,
  getNearestRadarIndex,
  type Point,
  type RadarFactor,
  type Size
} from "./factor-radar";

const app = getApp<AppOption>();

interface RadarFrame {
  size: number;
  offsetX: number;
  offsetY: number;
}

interface CanvasRect extends Size {
  left: number;
  top: number;
}

interface IndexPageData {
  ticker: string;
  loading: boolean;
  error: string;
  score: StockScoreResponse | null;
  radarFactors: RadarFactor[];
  radarCanvasSize: Size | null;
  selectedFactorIndex: number;
  selectedFactor: RadarFactor | null;
}

interface TickerInputEvent {
  detail: {
    value: string;
  };
}

interface DatasetIndexEvent {
  currentTarget: {
    dataset: {
      index?: string | number;
    };
  };
}

interface RadarTapEvent {
  detail?: {
    x?: number;
    y?: number;
  };
  touches?: Array<{
    pageX: number;
    pageY: number;
  }>;
}

interface IndexPageMethods {
  radarCanvasRect?: CanvasRect;
  onTickerInput(event: TickerInputEvent): void;
  setScore(score: StockScoreResponse): void;
  fetchScore(): void;
  updateSelectedFactor(index: string | number | undefined): void;
  selectRadarFactor(event: DatasetIndexEvent): void;
  onRadarTap(event: RadarTapEvent): void;
  getRadarTapPoint(event: RadarTapEvent): Point;
  playSelectionFeedback(): void;
  drawRadarChart(): void;
  paintRadar(ctx: WechatMiniprogram.CanvasContext, rect: Size): void;
  getRadarChartFrame(size: Size): RadarFrame;
  getShortFactorName(name: string): string;
  drawPolygon(ctx: WechatMiniprogram.CanvasContext, points: readonly Point[]): void;
}

Page<IndexPageData, IndexPageMethods>({
  data: {
    ticker: "MSFT",
    loading: false,
    error: "",
    score: null,
    radarFactors: [],
    radarCanvasSize: null,
    selectedFactorIndex: 0,
    selectedFactor: null
  },

  onTickerInput(event) {
    this.setData({ ticker: event.detail.value.toUpperCase(), error: "" });
  },

  setScore(score) {
    const radarFactors = buildRadarFactors(score.factors);
    const selectedFactorIndex = radarFactors.length ? 0 : -1;

    this.setData(
      {
        score,
        radarFactors,
        selectedFactorIndex,
        selectedFactor: radarFactors[selectedFactorIndex] || null,
        error: ""
      },
      () => {
        this.drawRadarChart();
      }
    );
  },

  fetchScore() {
    const ticker = this.data.ticker.trim().toUpperCase();
    if (!ticker) {
      this.setData({ error: "请输入股票代码" });
      return;
    }

    this.setData({ loading: true, error: "" });
    const api = createMiniProgramApiClient(app.globalData.apiBaseUrl, app.globalData.apiReadToken);

    api
      .getStockScore(ticker)
      .then((score) => {
        this.setScore(score);
      })
      .catch((error) => {
        this.setData({
          score: null,
          radarFactors: [],
          selectedFactor: null,
          error: getApiErrorMessage(error)
        });
      })
      .then(() => {
        this.setData({ loading: false });
      });
  },

  updateSelectedFactor(index) {
    const nextIndex = Number(index);
    const selectedFactor = this.data.radarFactors[nextIndex];
    if (!selectedFactor) {
      return;
    }

    const shouldPlayFeedback = nextIndex !== this.data.selectedFactorIndex;
    this.setData(
      {
        selectedFactorIndex: nextIndex,
        selectedFactor
      },
      () => {
        this.drawRadarChart();
        if (shouldPlayFeedback) {
          this.playSelectionFeedback();
        }
      }
    );
  },

  selectRadarFactor(event) {
    this.updateSelectedFactor(event.currentTarget.dataset.index);
  },

  onRadarTap(event) {
    const size = this.data.radarCanvasSize;
    if (!size) {
      return;
    }

    const point = this.getRadarTapPoint(event);
    const frame = this.getRadarChartFrame(size);
    const index = getNearestRadarIndex(
      {
        x: point.x - frame.offsetX,
        y: point.y - frame.offsetY
      },
      {
        width: frame.size,
        height: frame.size
      },
      this.data.radarFactors
    );
    this.updateSelectedFactor(index);
  },

  getRadarTapPoint(event) {
    if (event.detail && typeof event.detail.x === "number" && typeof event.detail.y === "number") {
      return {
        x: event.detail.x,
        y: event.detail.y
      };
    }

    const touch = event.touches && event.touches[0];
    if (touch && this.radarCanvasRect) {
      return {
        x: touch.pageX - this.radarCanvasRect.left,
        y: touch.pageY - this.radarCanvasRect.top
      };
    }

    return { x: 0, y: 0 };
  },

  playSelectionFeedback() {
    if (wx.vibrateShort) {
      wx.vibrateShort({ type: "light", fail: () => {} });
    }
  },

  drawRadarChart() {
    if (!this.data.radarFactors.length) {
      return;
    }

    wx.createSelectorQuery()
      .in(this)
      .select("#factorRadar")
      .boundingClientRect((rect: WechatMiniprogram.BoundingClientRectCallbackResult) => {
        if (!rect || typeof rect.width !== "number" || typeof rect.height !== "number") {
          return;
        }

        this.radarCanvasRect = {
          width: rect.width,
          height: rect.height,
          left: rect.left,
          top: rect.top
        };
        this.setData({
          radarCanvasSize: {
            width: rect.width,
            height: rect.height
          }
        });
        this.paintRadar(wx.createCanvasContext("factorRadar", this), rect);
      })
      .exec();
  },

  paintRadar(ctx, rect) {
    const factors = this.data.radarFactors;
    const selectedIndex = this.data.selectedFactorIndex;
    const width = rect.width;
    const height = rect.height;
    const frame = this.getRadarChartFrame({ width, height });
    const centerX = frame.offsetX + frame.size / 2;
    const centerY = frame.offsetY + frame.size / 2;
    const toPixel = (xPercent: number, yPercent: number): Point => ({
      x: frame.offsetX + (xPercent / 100) * frame.size,
      y: frame.offsetY + (yPercent / 100) * frame.size
    });

    ctx.clearRect(0, 0, width, height);
    ctx.setLineJoin("round");
    ctx.setLineCap("round");

    [0.25, 0.5, 0.75, 1].forEach((level) => {
      const points = factors.map((factor) => {
        const axis = toPixel(factor.axisX, factor.axisY);
        return {
          x: centerX + (axis.x - centerX) * level,
          y: centerY + (axis.y - centerY) * level
        };
      });

      this.drawPolygon(ctx, points);
      ctx.setStrokeStyle(level === 1 ? "rgba(251, 191, 36, 0.52)" : "rgba(148, 163, 184, 0.24)");
      ctx.setLineWidth(level === 1 ? 1.4 : 1);
      ctx.stroke();
    });

    factors.forEach((factor) => {
      const axis = toPixel(factor.axisX, factor.axisY);
      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      ctx.lineTo(axis.x, axis.y);
      ctx.setStrokeStyle("rgba(148, 163, 184, 0.22)");
      ctx.setLineWidth(1);
      ctx.stroke();
    });

    const scorePoints = factors.map((factor) => ({
      ...toPixel(factor.pointX, factor.pointY)
    }));

    this.drawPolygon(ctx, scorePoints);
    ctx.setFillStyle("rgba(245, 158, 11, 0.22)");
    ctx.fill();
    ctx.setStrokeStyle("#f59e0b");
    ctx.setLineWidth(2.4);
    ctx.stroke();

    scorePoints.forEach((point, index) => {
      const isSelected = index === selectedIndex;
      ctx.beginPath();
      ctx.arc(point.x, point.y, isSelected ? 5.5 : 3.5, 0, Math.PI * 2);
      ctx.setFillStyle(isSelected ? "#fbbf24" : "#38bdf8");
      ctx.fill();

      if (isSelected) {
        ctx.beginPath();
        ctx.arc(point.x, point.y, 10, 0, Math.PI * 2);
        ctx.setStrokeStyle("rgba(251, 191, 36, 0.48)");
        ctx.setLineWidth(2);
        ctx.stroke();
      }
    });

    factors.forEach((factor, index) => {
      const label = toPixel(factor.labelX, factor.labelY);
      const isSelected = index === selectedIndex;
      ctx.setTextAlign("center");
      ctx.setTextBaseline("middle");
      ctx.setFontSize(isSelected ? 12 : 11);
      ctx.setFillStyle(isSelected ? "#fbbf24" : "#cbd5e1");
      ctx.fillText(this.getShortFactorName(factor.name), label.x, label.y - 6);
      ctx.setFontSize(10);
      ctx.setFillStyle(isSelected ? "#fde68a" : "#94a3b8");
      ctx.fillText(String(factor.score), label.x, label.y + 9);
    });

    if (this.data.selectedFactor) {
      ctx.beginPath();
      ctx.arc(centerX, centerY, 30, 0, Math.PI * 2);
      ctx.setFillStyle("rgba(2, 6, 23, 0.86)");
      ctx.fill();
      ctx.setStrokeStyle("rgba(56, 189, 248, 0.32)");
      ctx.setLineWidth(1.2);
      ctx.stroke();

      ctx.setTextAlign("center");
      ctx.setTextBaseline("middle");
      ctx.setFillStyle("#fbbf24");
      ctx.setFontSize(22);
      ctx.fillText(String(this.data.selectedFactor.score), centerX, centerY - 6);
      ctx.setFillStyle("#94a3b8");
      ctx.setFontSize(10);
      ctx.fillText("当前维度", centerX, centerY + 17);
    }

    ctx.draw();
  },

  getRadarChartFrame(size) {
    const chartSize = Math.min(size.width, size.height);
    return {
      size: chartSize,
      offsetX: (size.width - chartSize) / 2,
      offsetY: (size.height - chartSize) / 2
    };
  },

  getShortFactorName(name) {
    if (name.indexOf("质量") !== -1) {
      return "质量";
    }
    if (name.indexOf("估值") !== -1) {
      return "估值";
    }
    if (name.indexOf("成长") !== -1) {
      return "成长";
    }
    if (name.indexOf("投资") !== -1 || name.indexOf("稳健") !== -1) {
      return "纪律";
    }
    if (name.indexOf("动量") !== -1 || name.indexOf("风险") !== -1) {
      return "动量";
    }
    return name.slice(0, 4);
  },

  drawPolygon(ctx, points) {
    if (!points.length) {
      return;
    }

    ctx.beginPath();
    points.forEach((point, index) => {
      if (index === 0) {
        ctx.moveTo(point.x, point.y);
        return;
      }
      ctx.lineTo(point.x, point.y);
    });
    ctx.closePath();
  },

  onLoad() {
    this.fetchScore();
  },

  onReady() {
    this.drawRadarChart();
  }
});
