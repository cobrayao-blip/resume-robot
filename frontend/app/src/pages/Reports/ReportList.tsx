import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Input,
  Space,
  message,
  Modal,
  Descriptions,
  Tag,
  Popconfirm,
} from 'antd';
import {
  SearchOutlined,
  DeleteOutlined,
  EyeOutlined,
  DownloadOutlined,
} from '@ant-design/icons';
import { reportApi, Report } from '@/services/reportApi';

const { Search } = Input;

const ReportList: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [reports, setReports] = useState<Report[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [searchText, setSearchText] = useState('');
  const [selectedReport, setSelectedReport] = useState<any>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [downloading, setDownloading] = useState<number | null>(null);

  // 加载报告列表
  const loadReports = async () => {
    setLoading(true);
    try {
      const response = await reportApi.getReports({
        page,
        pageSize,
        search: searchText || undefined,
      });
      setReports(response.items);
      setTotal(response.total);
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载报告列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReports();
  }, [page, pageSize, searchText]);

  // 搜索
  const handleSearch = (value: string) => {
    setSearchText(value);
    setPage(1);
  };

  // 查看详情
  const handleViewDetail = async (id: number) => {
    try {
      const detail = await reportApi.getReport(id);
      setSelectedReport(detail);
      setDetailVisible(true);
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载报告详情失败');
    }
  };

  // 下载报告
  const handleDownload = async (id: number) => {
    setDownloading(id);
    try {
      await reportApi.exportReport(id);
      message.success('下载成功');
    } catch (error: any) {
      message.error(error.response?.data?.detail || '下载失败');
    } finally {
      setDownloading(null);
    }
  };

  // 删除报告
  const handleDelete = async (id: number) => {
    try {
      await reportApi.deleteReport(id);
      message.success('删除成功');
      loadReports();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: '候选人姓名',
      dataIndex: 'candidate_name',
      key: 'candidate_name',
      width: 120,
    },
    {
      title: '报告标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
    },
    {
      title: '模板名称',
      dataIndex: 'template_name',
      key: 'template_name',
      width: 150,
      ellipsis: true,
    },
    {
      title: '源文件名',
      dataIndex: 'source_file_name',
      key: 'source_file_name',
      ellipsis: true,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (time: string) => new Date(time).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      width: 220,
      fixed: 'right' as const,
      render: (_: any, record: Report) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetail(record.id)}
          >
            查看
          </Button>
          <Button
            type="link"
            size="small"
            icon={<DownloadOutlined />}
            onClick={() => handleDownload(record.id)}
            loading={downloading === record.id}
          >
            下载
          </Button>
          <Popconfirm
            title="确定要删除这份报告吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card>
        <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
          <Search
            placeholder="搜索候选人姓名、报告标题"
            allowClear
            enterButton={<SearchOutlined />}
            style={{ width: 300 }}
            onSearch={handleSearch}
          />
        </Space>

        <Table
          columns={columns}
          dataSource={reports}
          rowKey="id"
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (page, pageSize) => {
              setPage(page);
              setPageSize(pageSize);
            },
          }}
          scroll={{ x: 1200 }}
        />
      </Card>

      {/* 报告详情对话框 */}
      <Modal
        title="报告详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={[
          <Button key="download" type="primary" icon={<DownloadOutlined />} onClick={() => selectedReport && handleDownload(selectedReport.id)}>
            下载报告
          </Button>,
          <Button key="close" onClick={() => setDetailVisible(false)}>
            关闭
          </Button>,
        ]}
        width={800}
      >
        {selectedReport && (
          <Descriptions column={2} bordered>
            <Descriptions.Item label="ID">{selectedReport.id}</Descriptions.Item>
            <Descriptions.Item label="候选人姓名">
              {selectedReport.candidate_name || '未知'}
            </Descriptions.Item>
            <Descriptions.Item label="报告标题" span={2}>
              {selectedReport.title || '未知'}
            </Descriptions.Item>
            <Descriptions.Item label="模板名称">
              {selectedReport.template_name || '未知'}
            </Descriptions.Item>
            <Descriptions.Item label="源文件名">
              {selectedReport.source_file_name || '未知'}
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">
              {new Date(selectedReport.created_at).toLocaleString('zh-CN')}
            </Descriptions.Item>
            <Descriptions.Item label="更新时间">
              {new Date(selectedReport.updated_at).toLocaleString('zh-CN')}
            </Descriptions.Item>
            <Descriptions.Item label="报告数据" span={2}>
              <pre style={{ maxHeight: 400, overflow: 'auto', background: '#f5f5f5', padding: 12 }}>
                {JSON.stringify(selectedReport.resume_data, null, 2)}
              </pre>
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
};

export default ReportList;
