export interface PlatformAdmin {
  id: number;
  email: string;
  full_name?: string;
  is_active: boolean;
  role?: string;
  user_type?: string;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: PlatformAdmin;
}

