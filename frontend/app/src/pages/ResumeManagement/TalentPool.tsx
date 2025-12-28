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
  Upload,
  Popconfirm,
} from 'antd';
import {
  UploadOutlined,
  SearchOutlined,
  DeleteOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import type { UploadFile } from 'antd/es/upload/interface';
import { resumeApi, ParsedResumeListResponse, ParsedResumeDetail } from '@/services/resumeApi';

const { Search } = Input;

const TalentPool: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [resumes, setResumes] = useState<ParsedResumeListResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [searchText, setSearchText] = useState('');
  const [selectedResume, setSelectedResume] = useState<ParsedResumeDetail | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [uploadVisible, setUploadVisible] = useState(false);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [uploading, setUploading] = useState(false);

  // 加载简历列表
  const loadResumes = async () => {
    setLoading(true);
    try {
      const response = await resumeApi.getTalentPool({
        page,
        pageSize,
        search: searchText || undefined,
      });
      setResumes(response.items);
      setTotal(response.total);
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载简历列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadResumes();
  }, [page, pageSize, searchText]);

  // 搜索
  const handleSearch = (value: string) => {
    setSearchText(value);
    setPage(1);
  };

  // 查看详情
  const handleViewDetail = async (id: number) => {
    try {
      const detail = await resumeApi.getResumeDetail(id);
      setSelectedResume(detail);
      setDetailVisible(true);
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载简历详情失败');
    }
  };

  // 删除简历
  const handleDelete = async (id: number) => {
    try {
      await resumeApi.deleteResume(id);
      message.success('删除成功');
      loadResumes();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  // 上传简历
  const handleUpload = async () => {
    if (fileList.length === 0) {
      message.warning('请选择要上传的文件');
      return;
    }

    setUploading(true);
    try {
      const files = fileList.map(file => file.originFileObj!).filter(Boolean);
      await resumeApi.uploadResume(files);
      message.success('上传成功');
      setUploadVisible(false);
      setFileList([]);
      loadResumes();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '上传失败');
    } finally {
      setUploading(false);
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
      title: '文件名',
      dataIndex: 'source_file_name',
      key: 'source_file_name',
      ellipsis: true,
    },
    {
      title: '文件类型',
      dataIndex: 'source_file_type',
      key: 'source_file_type',
      width: 100,
      render: (type: string) => (
        <Tag color={type === 'pdf' ? 'red' : 'blue'}>{type?.toUpperCase() || '未知'}</Tag>
      ),
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
      width: 180,
      fixed: 'right' as const,
      render: (_: any, record: ParsedResumeListResponse) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetail(record.id)}
          >
            查看
          </Button>
          <Popconfirm
            title="确定要删除这份简历吗？"
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
            placeholder="搜索候选人姓名、文件名"
            allowClear
            enterButton={<SearchOutlined />}
            style={{ width: 300 }}
            onSearch={handleSearch}
          />
          <Button
            type="primary"
            icon={<UploadOutlined />}
            onClick={() => setUploadVisible(true)}
          >
            上传简历
          </Button>
        </Space>

        <Table
          columns={columns}
          dataSource={resumes}
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
          scroll={{ x: 1000 }}
        />
      </Card>

      {/* 上传简历对话框 */}
      <Modal
        title="上传简历"
        open={uploadVisible}
        onOk={handleUpload}
        onCancel={() => {
          setUploadVisible(false);
          setFileList([]);
        }}
        confirmLoading={uploading}
        okText="上传"
        cancelText="取消"
      >
        <Upload
          multiple
          fileList={fileList}
          beforeUpload={() => false}
          onChange={({ fileList }) => setFileList(fileList)}
          accept=".pdf,.doc,.docx"
        >
          <Button icon={<UploadOutlined />}>选择文件</Button>
        </Upload>
        <div style={{ marginTop: 16, color: '#999' }}>
          支持格式：PDF、Word（.doc、.docx），可同时上传多个文件
        </div>
      </Modal>

      {/* 简历详情对话框 */}
      <Modal
        title="简历详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={800}
      >
        {selectedResume && (
          <Descriptions column={2} bordered>
            <Descriptions.Item label="ID">{selectedResume.id}</Descriptions.Item>
            <Descriptions.Item label="候选人姓名">
              {selectedResume.candidate_name || '未知'}
            </Descriptions.Item>
            <Descriptions.Item label="文件名" span={2}>
              {selectedResume.source_file_name || '未知'}
            </Descriptions.Item>
            <Descriptions.Item label="文件类型">
              <Tag color={selectedResume.source_file_type === 'pdf' ? 'red' : 'blue'}>
                {selectedResume.source_file_type?.toUpperCase() || '未知'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">
              {new Date(selectedResume.created_at).toLocaleString('zh-CN')}
            </Descriptions.Item>
            <Descriptions.Item label="解析数据" span={2}>
              <pre style={{ maxHeight: 400, overflow: 'auto', background: '#f5f5f5', padding: 12 }}>
                {JSON.stringify(selectedResume.parsed_data, null, 2)}
              </pre>
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
};

export default TalentPool;
