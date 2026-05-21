function joinUrl(baseUrl, path) {
  const cleanBaseUrl = String(baseUrl || "").replace(/\/+$/, "");
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${cleanBaseUrl}${cleanPath}`;
}

function appendQuery(url, query) {
  const entries = Object.entries(query || {}).filter(([, value]) => value !== undefined && value !== null);
  if (!entries.length) {
    return url;
  }

  const queryString = entries
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join("&");

  return `${url}${url.includes("?") ? "&" : "?"}${queryString}`;
}

module.exports = {
  appendQuery,
  joinUrl
};
