import axios from 'axios';
import { message } from 'antd';
import { useAuthStore } from '@/stores/authStore';

// 强制使用相对路径，通过 Vite 代理访问后端
// 在开发环境中，Vite 会将 /api 请求代理到 http://backend:8000
// 注意：永远不要使用 Docker 服务名（如 backend:8000）作为 API URL，因为浏览器无法解析

// 直接使用相对路径，不依赖环境变量
const API_BASE_URL = '/api/v1';

console.log('API Base URL 配置:', API_BASE_URL);
console.log('环境变量 VITE_API_BASE:', import.meta.env.VITE_API_BASE);

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 确保全局 axios 默认值不会影响我们的实例
if (axios.defaults.baseURL) {
  console.warn('检测到全局 axios.defaults.baseURL:', axios.defaults.baseURL);
  delete axios.defaults.baseURL;
}

// 锁定 baseURL，防止被修改
try {
  Object.defineProperty(api.defaults, 'baseURL', {
    value: API_BASE_URL,
    writable: false,
    configurable: false,
  });
} catch (e) {
  console.warn('无法锁定 baseURL:', e);
}

// 添加请求拦截器，记录实际请求 URL（用于调试）
// 注意：这个拦截器必须在最前面，确保 baseURL 正确
api.interceptors.request.use(
  (config) => {
    // 强制确保 baseURL 是相对路径（最高优先级）
    config.baseURL = '/api/v1';
    
    // 确保不会使用绝对 URL（包含 http:// 或 https://）
    if (config.url && (config.url.startsWith('http://') || config.url.startsWith('https://'))) {
      console.error('检测到绝对 URL，这会导致错误:', config.url);
      // 移除协议和域名，只保留路径
      try {
        const urlObj = new URL(config.url);
        config.url = urlObj.pathname + urlObj.search;
        console.log('已修复 URL:', config.url);
      } catch (e) {
        console.error('URL 解析失败:', e);
      }
    }
    
    const fullUrl = (config.baseURL || '') + (config.url || '');
    console.log('API 请求:', config.method?.toUpperCase(), fullUrl);
    console.log('baseURL:', config.baseURL);
    console.log('url:', config.url);
    console.log('完整 URL:', fullUrl);
    console.log('config 对象:', JSON.stringify({ baseURL: config.baseURL, url: config.url }));
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  },
  { runWhen: () => true } // 确保在所有情况下都运行
);

// Token工具函数：检查token是否即将过期（剩余时间少于5分钟）
const isTokenExpiringSoon = (token: string): boolean => {
  try {
    // JWT token格式：header.payload.signature
    const payload = JSON.parse(atob(token.split('.')[1]));
    const exp = payload.exp; // 过期时间（Unix时间戳，秒）
    const now = Math.floor(Date.now() / 1000); // 当前时间（Unix时间戳，秒）
    const remainingSeconds = exp - now;
    // 如果剩余时间少于5分钟（300秒），则认为即将过期
    return remainingSeconds < 300;
  } catch (e) {
    console.error('解析token失败:', e);
    return true; // 解析失败，认为即将过期
  }
};

// 刷新token的Promise，防止并发刷新
let refreshTokenPromise: Promise<boolean> | null = null;

// 请求拦截器 - 添加token，并在token即将过期时自动刷新
api.interceptors.request.use(
  async (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      // 检查token是否即将过期
      if (isTokenExpiringSoon(token) && !config.url?.includes('/auth/refresh')) {
        // 如果token即将过期且不是刷新请求，尝试刷新token
        if (!refreshTokenPromise) {
          const { useAuthStore } = await import('@/stores/authStore');
          refreshTokenPromise = useAuthStore.getState().refreshToken();
          refreshTokenPromise.finally(() => {
            refreshTokenPromise = null;
          });
        }
        // 等待token刷新完成
        await refreshTokenPromise;
        // 使用新的token
        const newToken = localStorage.getItem('access_token');
        if (newToken) {
          config.headers.Authorization = `Bearer ${newToken}`;
        }
      } else {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器 - 处理错误，包括token过期自动刷新
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const isLoginRequest = originalRequest?.url?.includes('/auth/login');
    const isRefreshRequest = originalRequest?.url?.includes('/auth/refresh');
    
    // 如果是401错误且不是登录/刷新请求，尝试刷新token
    if (error.response?.status === 401 && !isLoginRequest && !isRefreshRequest) {
      // 如果已经尝试过刷新，则直接跳转登录
      if (originalRequest._retry) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        localStorage.removeItem('tenant_id');
        window.location.href = '/login';
        return Promise.reject(error);
      }
      
      // 标记已尝试刷新，防止无限循环
      originalRequest._retry = true;
      
      try {
        // 尝试刷新token
        const { useAuthStore } = await import('@/stores/authStore');
        const refreshed = await useAuthStore.getState().refreshToken();
        
        if (refreshed) {
          // token刷新成功，使用新token重试原请求
          const newToken = localStorage.getItem('access_token');
          if (newToken) {
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
            return api(originalRequest);
          }
        }
      } catch (refreshError) {
        console.error('刷新token失败:', refreshError);
      }
      
      // 刷新失败，清除token并跳转登录
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      localStorage.removeItem('tenant_id');
      window.location.href = '/login';
    } else if (error.response?.status === 403) {
      message.error('权限不足');
    }
    
    return Promise.reject(error);
  }
);

export default api;

