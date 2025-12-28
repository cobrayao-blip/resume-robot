import api from './api';

export interface TenantUser {
  id: number;
  email: string;
  full_name?: string;
  role: 'tenant_admin' | 'hr_user';
  user_type: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserCreate {
  email: string;
  password: string;
  full_name?: string;
  role: 'tenant_admin' | 'hr_user';
}

export interface UserUpdate {
  email?: string;
  full_name?: string;
  role?: 'tenant_admin' | 'hr_user';
  is_active?: boolean;
}

export const userApi = {
  // 获取租户内用户列表
  getUsers: async (params?: {
    page?: number;
    pageSize?: number;
    search?: string;
    role?: string;
  }) => {
    const { page = 1, pageSize = 20, search, role } = params || {};
    const skip = (page - 1) * pageSize;
    const response = await api.get('/tenant-users', {
      params: {
        skip,
        limit: pageSize,
        search,
        role,
      },
    });
    // 后端返回的是列表，需要计算total
    const hasMore = response.data.length === pageSize;
    return {
      items: response.data,
      total: hasMore ? (page * pageSize + 1) : ((page - 1) * pageSize + response.data.length),
      page,
      pageSize,
    };
  },

  // 创建用户
  createUser: async (data: UserCreate) => {
    const response = await api.post('/tenant-users', data);
    return response.data;
  },

  // 更新用户
  updateUser: async (id: number, data: UserUpdate) => {
    const response = await api.put(`/tenant-users/${id}`, data);
    return response.data;
  },

  // 删除用户
  deleteUser: async (id: number) => {
    await api.delete(`/tenant-users/${id}`);
  },

  // 重置用户密码（管理员操作）
  resetUserPassword: async (id: number, newPassword: string) => {
    const response = await api.put(`/tenant-users/${id}`, {
      password: newPassword,
    });
    return response.data;
  },

  // 邀请用户（发送邀请邮件）
  inviteUser: async (email: string, role: 'tenant_admin' | 'hr_user') => {
    const response = await api.post('/tenant-users/invite', {
      email,
      role,
    });
    return response.data;
  },
};

