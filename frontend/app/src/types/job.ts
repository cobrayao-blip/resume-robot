/**
 * 岗位管理相关类型定义
 */

export interface JobPosition {
  id: number;
  title: string;
  department?: string;  // 部门名称（兼容字段）
  department_id?: number;  // 部门ID（关联Department表）
  description?: string;
  requirements?: string;
  status: 'draft' | 'published' | 'closed';
  mongodb_id?: string;
  vector_id?: string;
  created_by: number;
  created_at: string;
  updated_at: string;
  profile?: any; // 岗位画像（从MongoDB）
  department_obj?: {  // 部门对象（如果后端返回）
    id: number;
    name: string;
    path?: string;
  };
}

export interface FilterRule {
  id: number;
  name: string;
  description?: string;
  rule_type: string;
  rule_config: Record<string, any>;
  logic_operator: 'AND' | 'OR';
  priority: number;
  is_active: boolean;
  created_by: number;
  created_at: string;
  updated_at: string;
}

export interface CompanyInfo {
  id: number;
  name: string;
  industry?: string;
  products?: string;
  application_scenarios?: string;
  company_culture?: string;
  preferences?: string;
  additional_info?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface MatchModel {
  id: number;
  name: string;
  description?: string;
  model_type: 'vector' | 'llm' | 'hybrid';
  model_config: Record<string, any>;
  is_default: boolean;
  is_active: boolean;
  created_by?: number;
  created_at: string;
  updated_at: string;
}

export interface ResumeJobMatch {
  id: number;
  resume_id: number;
  job_id: number;
  match_score: number;
  match_label: '强烈推荐' | '推荐' | '谨慎推荐' | '不推荐';
  mongodb_detail_id?: string;
  status: 'pending' | 'reviewed' | 'rejected' | 'accepted';
  created_at: string;
  updated_at: string;
  match_detail?: any; // 匹配详情（从MongoDB）
}


