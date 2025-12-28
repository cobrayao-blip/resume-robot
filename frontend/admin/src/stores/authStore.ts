import { create } from 'zustand';
import { PlatformAdmin, LoginRequest, AuthResponse } from '@/types/user';
import api from '@/services/api';

interface AuthState {
  user: PlatformAdmin | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  
  login: (credentials: LoginRequest) => Promise<void>;
  logout: () => void;
  checkAuth: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,

  login: async (credentials: LoginRequest) => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.post<AuthResponse>('/auth/login', credentials);
      const { access_token, user } = response.data;
      
      // 检查用户是否有平台管理员权限
      if (user.role !== 'platform_admin' && user.user_type !== 'super_admin') {
        throw new Error('该账号不是平台管理员，无法登录管理后台');
      }
      
      localStorage.setItem('admin_access_token', access_token);
      localStorage.setItem('admin_user', JSON.stringify(user));
      
      set({ 
        user, 
        isAuthenticated: true, 
        isLoading: false,
        error: null
      });
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.response?.data?.message || error.message || '登录失败';
      set({ 
        error: errorMessage, 
        isLoading: false,
        isAuthenticated: false
      });
      throw error;
    }
  },

  logout: () => {
    localStorage.removeItem('admin_access_token');
    localStorage.removeItem('admin_user');
    set({ user: null, isAuthenticated: false });
  },

  checkAuth: async () => {
    const token = localStorage.getItem('admin_access_token');
    const userStr = localStorage.getItem('admin_user');
    
    if (token && userStr) {
      try {
        const response = await api.get<PlatformAdmin>('/users/me');
        const user = response.data;
        // 再次检查用户权限
        if (user.role !== 'platform_admin' && user.user_type !== 'super_admin') {
          localStorage.removeItem('admin_access_token');
          localStorage.removeItem('admin_user');
          set({ user: null, isAuthenticated: false, isLoading: false });
          return;
        }
        localStorage.setItem('admin_user', JSON.stringify(user));
        set({ user, isAuthenticated: true, isLoading: false });
      } catch (error: any) {
        localStorage.removeItem('admin_access_token');
        localStorage.removeItem('admin_user');
        set({ user: null, isAuthenticated: false, isLoading: false });
      }
    } else {
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },

  clearError: () => set({ error: null }),
}));

