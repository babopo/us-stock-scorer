const app = getApp();

Page({
  data: {
    ticker: "MSFT",
    loading: false,
    error: "",
    score: null
  },

  onTickerInput(event) {
    this.setData({ ticker: event.detail.value.toUpperCase(), error: "" });
  },

  fetchScore() {
    const ticker = this.data.ticker.trim().toUpperCase();
    if (!ticker) {
      this.setData({ error: "请输入股票代码" });
      return;
    }

    this.setData({ loading: true, error: "" });
    wx.request({
      url: `${app.globalData.apiBaseUrl}/v1/stocks/${ticker}/score`,
      method: "GET",
      success: (response) => {
        if (response.statusCode === 200) {
          this.setData({ score: response.data, error: "" });
          return;
        }
        this.setData({ score: null, error: "没有找到这只股票的数据" });
      },
      fail: () => {
        this.setData({ score: null, error: "无法连接本地后端服务" });
      },
      complete: () => {
        this.setData({ loading: false });
      }
    });
  },

  onLoad() {
    this.fetchScore();
  }
});
