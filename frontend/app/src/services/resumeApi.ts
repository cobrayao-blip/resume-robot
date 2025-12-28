import api from './api';

// ========== 简历总库API ==========

export interface ParsedResume {
  id: number;
  name: string;
  candidate_name?: string;
  source_file_name?: string;
  source_file_type?: string;
  created_at: string;
  updated_at: string;
}

export interface ParsedResumeListResponse {
  id: number;
  name: string;
  candidate_name?: string;
  source_file_name?: string;
  source_file_type?: string;
  created_at: string;
  updated_at: string;
}

export interface ParsedResumeDetail extends ParsedResume {
  parsed_data: any;
  raw_text?: string;
  validation?: any;
  correction?: any;
  quality_analysis?: any;
}

export const resumeApi = {
  // 获取简历总库列表
  getTalentPool: async (params: {
    page?: number;
    pageSize?: number;
    search?: string;
    status?: string;
  }) => {
    const { page = 1, pageSize = 20, search, status } = params;
    const skip = (page - 1) * pageSize;
    const response = await api.get<ParsedResumeListResponse[]>('/parsed-resumes', {
      params: {
        skip,
        limit: pageSize,
        search,
        status,
      },
    });
    // 注意：后端暂时只返回列表，total需要单独查询或通过响应头获取
    // 这里使用列表长度作为临时方案（不准确，但可用）
    // 如果返回的数据量等于pageSize，说明可能还有更多数据
    const hasMore = response.data.length === pageSize;
    return {
      items: response.data,
      total: hasMore ? (page * pageSize + 1) : ((page - 1) * pageSize + response.data.length),
      page,
      pageSize,
    };
  },

  // 获取简历详情
  getResumeDetail: async (id: number) => {
    const response = await api.get<ParsedResumeDetail>(`/parsed-resumes/${id}`);
    return response.data;
  },

  // 删除简历
  deleteResume: async (id: number) => {
    await api.delete(`/parsed-resumes/${id}`);
  },

  // 上传简历（使用批量上传API）
  uploadResume: async (files: File[]) => {
    const formData = new FormData();
    files.forEach(file => {
      formData.append('files', file);
    });
    const response = await api.post('/batch/upload-and-parse', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  // 获取岗位简历库（通过匹配结果查询）
  getJobResumePool: async (jobId: number, params: {
    page?: number;
    pageSize?: number;
    match_label?: string;
    status?: string;
  }) => {
    const { page = 1, pageSize = 20, match_label, status } = params;
    const skip = (page - 1) * pageSize;
    const response = await api.get('/jobs/match/results', {
      params: {
        job_id: jobId,
        skip,
        limit: pageSize,
        match_label,
        status,
      },
    });
    return response.data;
  },

  // 获取过滤箱（被过滤的简历）
  getFilterBox: async (params: {
    page?: number;
    pageSize?: number;
    search?: string;
  }) => {
    const { page = 1, pageSize = 20, search } = params;
    const skip = (page - 1) * pageSize;
    const response = await api.get<ParsedResumeListResponse[]>('/parsed-resumes', {
      params: {
        skip,
        limit: pageSize,
        search,
        status: 'filtered',
      },
    });
    return {
      items: response.data,
      total: response.data.length,
      page,
      pageSize,
    };
  },
};

