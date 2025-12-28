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

// 请求拦截器 - 添加token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 响应拦截器 - 处理错误
api.interceptors.response.use(
  (response) => response,
  (error) => {
    // 如果是登录接口的 401 错误，不要跳转，让登录组件处理
    const isLoginRequest = error.config?.url?.includes('/auth/login');
    
    if (error.response?.status === 401) {
      // 登录接口的 401 错误不跳转，让登录组件显示错误提示
      if (!isLoginRequest) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        window.location.href = '/login';
      }
    } else if (error.response?.status === 403) {
      message.error('权限不足');
    }
    return Promise.reject(error);
  }
);

export default api;

