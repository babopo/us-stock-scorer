export interface AppGlobalData {
  apiBaseUrl: string;
}

export interface AppOption {
  globalData: AppGlobalData;
}

App<AppOption>({
  globalData: {
    apiBaseUrl: "http://127.0.0.1:8000"
  }
});
