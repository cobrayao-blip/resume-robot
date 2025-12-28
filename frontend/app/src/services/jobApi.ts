/**
 * 岗位管理相关API
 */
import api from './api';
import { JobPosition, FilterRule, CompanyInfo, MatchModel, ResumeJobMatch } from '@/types/job';

// ========== 岗位管理 ==========

export const jobApi = {
  // 岗位管理
  getPositions: async (params?: {
    skip?: number;
    limit?: number;
    status?: string;
    search?: string;
  }) => {
    const response = await api.get('/jobs/positions', { params });
    return response.data;
  },

  getPosition: async (id: number, includeProfile?: boolean) => {
    const response = await api.get(`/jobs/positions/${id}`, {
      params: { include_profile: includeProfile }
    });
    return response.data;
  },

  createPosition: async (data: Partial<JobPosition>) => {
    const response = await api.post('/jobs/positions', data);
    return response.data;
  },

  updatePosition: async (id: number, data: Partial<JobPosition>) => {
    const response = await api.put(`/jobs/positions/${id}`, data);
    return response.data;
  },

  deletePosition: async (id: number) => {
    await api.delete(`/jobs/positions/${id}`);
  },

  parseJobProfile: async (id: number) => {
    const response = await api.post(`/jobs/positions/${id}/parse-profile`);
    return response.data;
  },

  vectorizeJob: async (id: number, embeddingModel?: string) => {
    const response = await api.post(`/jobs/positions/${id}/vectorize`, null, {
      params: { embedding_model: embeddingModel }
    });
    return response.data;
  },

  publishJob: async (id: number, autoParse?: boolean, autoVectorize?: boolean) => {
    const response = await api.post(`/jobs/positions/${id}/publish`, null, {
      params: {
        auto_parse: autoParse,
        auto_vectorize: autoVectorize
      }
    });
    return response.data;
  },

  // 筛选规则管理
  getFilterRules: async (params?: {
    rule_type?: string;
    is_active?: boolean;
  }) => {
    const response = await api.get('/jobs/filter-rules', { params });
    return response.data;
  },

  getFilterRule: async (id: number) => {
    const response = await api.get(`/jobs/filter-rules/${id}`);
    return response.data;
  },

  createFilterRule: async (data: Partial<FilterRule>) => {
    const response = await api.post('/jobs/filter-rules', data);
    return response.data;
  },

  updateFilterRule: async (id: number, data: Partial<FilterRule>) => {
    const response = await api.put(`/jobs/filter-rules/${id}`, data);
    return response.data;
  },

  deleteFilterRule: async (id: number) => {
    await api.delete(`/jobs/filter-rules/${id}`);
  },

  // 公司信息管理
  getCompanyInfo: async () => {
    const response = await api.get('/jobs/company-info');
    return response.data;
  },

  createOrUpdateCompanyInfo: async (data: Partial<CompanyInfo>) => {
    const response = await api.post('/jobs/company-info', data);
    return response.data;
  },

  updateCompanyInfo: async (id: number, data: Partial<CompanyInfo>) => {
    const response = await api.put(`/jobs/company-info/${id}`, data);
    return response.data;
  },

  // 匹配模型管理
  getMatchModels: async (params?: {
    model_type?: string;
    is_active?: boolean;
  }) => {
    const response = await api.get('/jobs/match-models', { params });
    return response.data;
  },

  getMatchModel: async (id: number) => {
    const response = await api.get(`/jobs/match-models/${id}`);
    return response.data;
  },

  createMatchModel: async (data: Partial<MatchModel>) => {
    const response = await api.post('/jobs/match-models', data);
    return response.data;
  },

  updateMatchModel: async (id: number, data: Partial<MatchModel>) => {
    const response = await api.put(`/jobs/match-models/${id}`, data);
    return response.data;
  },

  deleteMatchModel: async (id: number) => {
    await api.delete(`/jobs/match-models/${id}`);
  },

  // 预筛选
  executeFilter: async (params: {
    resume_id: number;
    resume_type?: string;
    rule_ids?: number[];
  }) => {
    const response = await api.post('/jobs/filter/execute', null, { params });
    return response.data;
  },

  batchExecuteFilter: async (params: {
    resume_ids: number[];
    resume_type?: string;
    rule_ids?: number[];
  }) => {
    const response = await api.post('/jobs/filter/batch-execute', null, { params });
    return response.data;
  },

  // 简历匹配
  matchResumeToJob: async (params: {
    resume_id: number;
    job_id: number;
    resume_type?: string;
    match_model_id?: number;
  }) => {
    const response = await api.post('/jobs/match/resume-to-job', null, { params });
    return response.data;
  },

  batchMatch: async (params: {
    resume_ids: number[];
    job_id: number;
    resume_type?: string;
    match_model_id?: number;
  }) => {
    const response = await api.post('/jobs/match/batch-match', null, { params });
    return response.data;
  },

  getMatchResults: async (params?: {
    job_id?: number;
    resume_id?: number;
    match_label?: string;
    status?: string;
    skip?: number;
    limit?: number;
    page?: number;
    pageSize?: number;
  }) => {
    const { page, pageSize, ...restParams } = params || {};
    const skip = page && pageSize ? (page - 1) * pageSize : restParams.skip || 0;
    const limit = pageSize || restParams.limit || 20;
    const response = await api.get('/jobs/match/results', {
      params: {
        ...restParams,
        skip,
        limit,
      },
    });
    return response.data;
  },

  getMatchResultDetail: async (id: number) => {
    const response = await api.get(`/jobs/match/results/${id}`);
    return response.data;
  },

  updateMatchStatus: async (id: number, status: string) => {
    const response = await api.put(`/jobs/match/results/${id}/status`, null, {
      params: { new_status: status }
    });
    return response.data;
  },
};

// ========== 批量操作 ==========

export const batchApi = {
  batchUploadAndParse: async (files: File[], jobId?: number) => {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });
    if (jobId) {
      formData.append('job_id', jobId.toString());
    }
    const response = await api.post('/batch/upload-and-parse', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  batchMatchToJob: async (params: {
    resume_ids: number[];
    job_id: number;
    resume_type?: string;
    match_model_id?: number;
    auto_filter?: boolean;
  }) => {
    const response = await api.post('/batch/match-to-job', null, { params });
    return response.data;
  },

  batchGenerateReports: async (params: {
    match_ids: number[];
  }) => {
    const response = await api.post('/batch/generate-reports', null, { params });
    return response.data;
  },
};


