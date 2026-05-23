export interface AppGlobalData {
  apiBaseUrl: string;
  apiReadToken: string;
}

export interface AppOption {
  globalData: AppGlobalData;
}

App<AppOption>({
  globalData: {
    apiBaseUrl: "http://47.90.148.197/",
    apiReadToken: "wxlogin"
  }
});
