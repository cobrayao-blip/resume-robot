import api from './api';

export interface ExportResponse {
  success: boolean;
  filename: string;
  file_size: number;
  download_url?: string;
}

export interface ReportData {
  match_id: number;
  resume_id: number;
  job_id: number;
  candidate_name?: string;
  match_score: number;
  match_label: string;
  match_detail?: any;
}

export class ExportService {
  /**
   * 导出推荐报告为Word文档
   */
  static async exportReportToWord(reportData: ReportData): Promise<void> {
    try {
      const response = await api.post('/export/report-word', reportData, {
        responseType: 'blob',
      });

      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      });
      
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      
      const contentDisposition = response.headers['content-disposition'];
      let filename = 'report.docx';
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
      
    } catch (error: any) {
      throw new Error(`导出失败: ${error.response?.data?.detail || error.message}`);
    }
  }

  /**
   * 批量导出推荐报告
   */
  static async batchExportReports(reports: ReportData[]): Promise<void> {
    for (const report of reports) {
      await this.exportReportToWord(report);
    }
  }
}


