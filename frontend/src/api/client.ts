import axios from "axios";

// 取得環境變數，預設指向 localhost:8000
const baseURL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const apiClient = axios.create({
  baseURL,
  headers: {
    "Content-Type": "application/json",
  },
});

// 全局請求攔截器
apiClient.interceptors.request.use(
  (config) => {
    // 可以在這裡加入 token 或其他自訂 header
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 全局回應攔截器
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // [更新] 全局統一抽取後端錯誤字串，不要只丟 Error instance
    let errorMessage = "網路連線異常或伺服器無回應";
    if (error.response?.data?.detail) {
      errorMessage = error.response.data.detail;
    } else if (error.response?.data?.message) {
      errorMessage = error.response.data.message;
    } else if (error.message) {
      errorMessage = error.message;
    }
    console.error("API 請求錯誤:", errorMessage);
    // 包裝成新的 Error 以防前端其他地方還在用 e.message 拿訊息
    return Promise.reject(new Error(errorMessage));
  }
);
