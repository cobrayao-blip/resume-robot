import axios from 'axios';
import { message } from 'antd';
import { useAuthStore } from '@/stores/authStore';

// 强制使用相对路径，通过 Vite 代理访问后端
// 在开发环境中，Vite 会将 /api 请求代理到 http://backend:8000
// 在生产环境中，应该使用实际的后端 URL
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

// 添加请求拦截器，记录实际请求 URL（用于调试）
api.interceptors.request.use(
  (config) => {
    const fullUrl = (config.baseURL || '') + (config.url || '');
    console.log('API 请求:', config.method?.toUpperCase(), fullUrl);
    console.log('baseURL:', config.baseURL);
    console.log('url:', config.url);
    
    // 确保不会使用绝对 URL（包含 http:// 或 https://）
    if (config.url && (config.url.startsWith('http://') || config.url.startsWith('https://'))) {
      console.error('检测到绝对 URL，这会导致错误:', config.url);
      // 移除协议和域名，只保留路径
      try {
        const urlObj = new URL(config.url);
        config.url = urlObj.pathname + urlObj.search;
      } catch (e) {
        console.error('URL 解析失败:', e);
      }
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// 请求拦截器 - 添加token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('admin_access_token');
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
    // 检查是否是登录请求（包括 /auth/login 和 /admin/auth/login）
    const requestUrl = error.config?.url || '';
    const isLoginRequest = requestUrl.includes('/auth/login') || requestUrl.includes('/admin/auth/login');
    
    console.log('API 错误拦截:', {
      url: requestUrl,
      status: error.response?.status,
      isLoginRequest: isLoginRequest,
    });
    
    if (error.response?.status === 401) {
      // 登录接口的 401 错误不跳转，让登录组件显示错误提示
      if (!isLoginRequest) {
        localStorage.removeItem('admin_access_token');
        localStorage.removeItem('admin_user');
        window.location.href = '/admin/login';
      }
    } else if (error.response?.status === 403) {
      message.error('权限不足');
    }
    return Promise.reject(error);
  }
);

export default api;

