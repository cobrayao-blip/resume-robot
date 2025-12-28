/**
 * 组织架构管理API
 */
import api from './api';

export interface Department {
  id: number;
  tenant_id?: number;
  name: string;
  code?: string;
  description?: string;
  parent_id?: number;
  level?: number;
  path?: string;
  department_culture?: string;
  work_style?: string;
  team_size?: number;
  key_responsibilities?: string;
  manager_id?: number;
  created_at?: string;
  updated_at?: string;
  parent_name?: string;
  manager_name?: string;
  children_count?: number;
  jobs_count?: number;
  children?: Department[];
}

export interface DepartmentCreate {
  name: string;
  code?: string;
  description?: string;
  parent_id?: number;
  department_culture?: string;
  work_style?: string;
  team_size?: number;
  key_responsibilities?: string;
  manager_id?: number;
}

export interface DepartmentUpdate {
  name?: string;
  code?: string;
  description?: string;
  parent_id?: number;
  department_culture?: string;
  work_style?: string;
  team_size?: number;
  key_responsibilities?: string;
  manager_id?: number;
}

export const organizationApi = {
  /**
   * 获取部门列表（树形结构）
   */
  getDepartments: async (tree: boolean = true): Promise<Department[]> => {
    const response = await api.get('/organization/departments', {
      params: { tree }
    });
    return response.data;
  },

  /**
   * 获取部门详情
   */
  getDepartment: async (id: number): Promise<Department> => {
    const response = await api.get(`/organization/departments/${id}`);
    return response.data;
  },

  /**
   * 创建部门
   */
  createDepartment: async (data: DepartmentCreate): Promise<Department> => {
    const response = await api.post('/organization/departments', data);
    return response.data;
  },

  /**
   * 更新部门
   */
  updateDepartment: async (id: number, data: DepartmentUpdate): Promise<Department> => {
    const response = await api.put(`/organization/departments/${id}`, data);
    return response.data;
  },

  /**
   * 删除部门
   */
  deleteDepartment: async (id: number): Promise<void> => {
    await api.delete(`/organization/departments/${id}`);
  },
};

