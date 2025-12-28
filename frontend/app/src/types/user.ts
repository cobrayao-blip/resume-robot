export interface User {
  id: number;
  tenant_id?: number | null; // SaaS多租户（平台管理员为null）
  email: string;
  full_name?: string;
  role?: string; // 角色：platform_admin/tenant_admin/hr_user
  user_type?: string; // 用户类型：super_admin/platform_admin/tenant_admin/hr_user
  is_active: boolean;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
  tenant_id: number; // 返回租户ID
}

