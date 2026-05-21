const { appendQuery } = require("../url");

function createWxTransport(wxApi) {
  if (!wxApi || typeof wxApi.request !== "function") {
    throw new TypeError("createWxTransport requires the wx API object");
  }

  return function wxTransport(request) {
    return new Promise((resolve, reject) => {
      wxApi.request({
        url: appendQuery(request.url, request.query),
        method: request.method,
        data: request.body,
        header: request.headers || {},
        timeout: request.timeoutMs,
        success(response) {
          resolve({
            status: response.statusCode,
            headers: response.header || {},
            data: response.data
          });
        },
        fail(error) {
          reject(error);
        }
      });
    });
  };
}

module.exports = {
  createWxTransport
};
