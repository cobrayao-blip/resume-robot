import { create } from 'zustand';
import { User, LoginRequest, AuthResponse } from '@/types/user';
import api from '@/services/api';

interface AuthState {
  user: User | null;
  tenantId: number | null;
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
  tenantId: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,

  login: async (credentials: LoginRequest) => {
    set({ isLoading: true, error: null });
    try {
      const response = await api.post<AuthResponse>('/auth/login', credentials);
      const { access_token, user } = response.data;
      // tenant_id 从 user 对象中获取
      const tenant_id = user.tenant_id || null;
      
      localStorage.setItem('access_token', access_token);
      localStorage.setItem('user', JSON.stringify(user));
      if (tenant_id) {
        localStorage.setItem('tenant_id', String(tenant_id));
      }
      
      set({ 
        user, 
        tenantId: tenant_id,
        isAuthenticated: true, 
        isLoading: false,
        error: null
      });
    } catch (error: any) {
      const errorMessage = error.response?.data?.detail || error.response?.data?.message || '登录失败';
      set({ 
        error: errorMessage, 
        isLoading: false,
        isAuthenticated: false
      });
      throw error;
    }
  },

  logout: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user');
    localStorage.removeItem('tenant_id');
    set({ user: null, tenantId: null, isAuthenticated: false });
  },

  checkAuth: async () => {
    const token = localStorage.getItem('access_token');
    const userStr = localStorage.getItem('user');
    
    if (token && userStr) {
      try {
        const response = await api.get<User>('/users/me');
        const user = response.data;
        const tenantId = user.tenant_id || null;
        localStorage.setItem('user', JSON.stringify(user));
        if (tenantId) {
          localStorage.setItem('tenant_id', String(tenantId));
        }
        set({ 
          user, 
          tenantId: tenantId,
          isAuthenticated: true, 
          isLoading: false 
        });
      } catch (error: any) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        localStorage.removeItem('tenant_id');
        set({ user: null, tenantId: null, isAuthenticated: false, isLoading: false });
      }
    } else {
      set({ user: null, tenantId: null, isAuthenticated: false, isLoading: false });
    }
  },

  clearError: () => set({ error: null }),
}));

