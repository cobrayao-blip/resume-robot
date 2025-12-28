import api from './api';

export interface Tenant {
  id: number;
  name: string;
  domain?: string;
  contact_email?: string;
  contact_phone?: string;
  subscription_plan: string;
  subscription_start?: string;
  subscription_end?: string;
  status: 'active' | 'suspended' | 'expired';
  max_users: number;
  max_jobs: number;
  max_resumes_per_month: number;
  current_month_resume_count: number;
  created_at: string;
  updated_at: string;
}

export interface TenantCreate {
  name: string;
  domain?: string;
  contact_email?: string;
  contact_phone?: string;
  subscription_plan?: string;
  subscription_start?: string;
  subscription_end?: string;
  status?: string;
  max_users?: number;
  max_jobs?: number;
  max_resumes_per_month?: number;
  admin_email?: string;
  admin_password?: string;
  admin_name?: string;
}

export interface TenantUpdate {
  name?: string;
  domain?: string;
  contact_email?: string;
  contact_phone?: string;
  subscription_plan?: string;
  subscription_start?: string;
  subscription_end?: string;
  status?: string;
  max_users?: number;
  max_jobs?: number;
  max_resumes_per_month?: number;
}

export const tenantApi = {
  // 获取租户列表
  getTenants: async (params?: {
    page?: number;
    pageSize?: number;
    search?: string;
    status?: string;
    subscription_plan?: string;
  }) => {
    const { page = 1, pageSize = 20, search, status, subscription_plan } = params || {};
    const skip = (page - 1) * pageSize;
    const response = await api.get('/admin/tenants', {
      params: {
        skip,
        limit: pageSize,
        search,
        status,
        subscription_plan,
      },
    });
    return {
      items: response.data,
      total: response.data.length, // 后端暂时不返回total，使用数组长度
      page,
      pageSize,
    };
  },

  // 获取租户详情
  getTenant: async (id: number) => {
    const response = await api.get(`/admin/tenants/${id}`);
    return response.data;
  },

  // 创建租户
  createTenant: async (data: TenantCreate) => {
    const response = await api.post('/admin/tenants', data);
    return response.data;
  },

  // 更新租户
  updateTenant: async (id: number, data: TenantUpdate) => {
    const response = await api.put(`/admin/tenants/${id}`, data);
    return response.data;
  },

  // 删除租户
  deleteTenant: async (id: number) => {
    await api.delete(`/admin/tenants/${id}`);
  },
};

