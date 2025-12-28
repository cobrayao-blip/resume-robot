import api from './api';
import { ResumeJobMatch } from '@/types/job';

export interface Report {
  id: number;
  candidate_name?: string;
  title: string;
  template_name?: string;
  source_file_name?: string;
  created_at: string;
  updated_at: string;
}

export interface ReportListResponse {
  items: Report[];
  total: number;
  page: number;
  pageSize: number;
}

export const reportApi = {
  // 获取报告列表（使用CandidateResume API）
  getReports: async (params: {
    page?: number;
    pageSize?: number;
    search?: string;
  }) => {
    const { page = 1, pageSize = 20, search } = params;
    const skip = (page - 1) * pageSize;
    const response = await api.get('/resumes', {
      params: {
        skip,
        limit: pageSize,
        search,
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

  // 获取报告详情
  getReport: async (id: number) => {
    const response = await api.get(`/resumes/${id}`);
    return response.data;
  },

  // 生成报告（批量生成）
  generateReports: async (params: {
    match_ids: number[];
    template_id: number;
  }) => {
    const response = await api.post('/batch/generate-reports', null, {
      params: {
        match_ids: params.match_ids,
        template_id: params.template_id,
      },
    });
    return response.data;
  },

  // 导出报告为Word
  exportReport: async (resumeId: number) => {
    // 先获取报告数据
    const report = await reportApi.getReport(resumeId);
    
    // 构建导出数据
    const exportData = {
      template_sections: report.resume_data?.template_sections || [],
      basic_info: report.resume_data?.basic_info || {},
      work_experiences: report.resume_data?.work_experiences || [],
      education: report.resume_data?.education || [],
      skills: report.resume_data?.skills || {},
      projects: report.resume_data?.projects || [],
    };

    // 调用导出API
    const response = await api.post('/export/export-word', exportData, {
      responseType: 'blob',
    });

    // 创建下载链接
    const blob = new Blob([response.data], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    });
    
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    
    const contentDisposition = response.headers['content-disposition'];
    let filename = `${report.candidate_name || '推荐报告'}_${report.id}.docx`;
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
      if (filenameMatch && filenameMatch[1]) {
        filename = filenameMatch[1];
      }
    }
    
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    
    window.URL.revokeObjectURL(url);
    document.body.removeChild(link);
  },

  // 删除报告
  deleteReport: async (id: number) => {
    await api.delete(`/resumes/${id}`);
  },
};

