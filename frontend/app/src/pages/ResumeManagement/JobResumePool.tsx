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
  Select,
  Popconfirm,
} from 'antd';
import {
  UploadOutlined,
  SearchOutlined,
  DeleteOutlined,
  EyeOutlined,
  UserAddOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useParams, useNavigate } from 'react-router-dom';
import type { UploadFile } from 'antd/es/upload/interface';
import { resumeApi } from '@/services/resumeApi';
import { jobApi, batchApi } from '@/services/jobApi';
import { ResumeJobMatch, JobPosition } from '@/types/job';

const { Search } = Input;
const { Option } = Select;

const JobResumePool: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [jobInfo, setJobInfo] = useState<JobPosition | null>(null);
  const [resumes, setResumes] = useState<ResumeJobMatch[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [searchText, setSearchText] = useState('');
  const [matchLabelFilter, setMatchLabelFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [selectedMatch, setSelectedMatch] = useState<ResumeJobMatch | null>(null);
  const [detailVisible, setDetailVisible] = useState(false);
  const [uploadVisible, setUploadVisible] = useState(false);
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [matching, setMatching] = useState(false);

  // 加载岗位信息
  const loadJobInfo = async () => {
    if (!jobId) return;
    try {
      const job = await jobApi.getPosition(Number(jobId));
      setJobInfo(job);
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载岗位信息失败');
    }
  };

  // 加载岗位简历列表（通过匹配结果查询）
  const loadJobResumes = async () => {
    if (!jobId) return;
    setLoading(true);
    try {
      const response = await jobApi.getMatchResults({
        job_id: Number(jobId),
        page,
        pageSize,
        match_label: matchLabelFilter || undefined,
        status: statusFilter || undefined,
      });
      setResumes(response.items || []);
      setTotal(response.total || 0);
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载岗位简历列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (jobId) {
      loadJobInfo();
      loadJobResumes();
    }
  }, [jobId, page, pageSize, matchLabelFilter, statusFilter]);

  // 搜索
  const handleSearch = (value: string) => {
    setSearchText(value);
    setPage(1);
    // 注意：当前API不支持通过简历名称搜索，需要后端支持
    loadJobResumes();
  };

  // 查看详情
  const handleViewDetail = async (matchId: number) => {
    try {
      const detail = await jobApi.getMatchResultDetail(matchId);
      setSelectedMatch(detail);
      setDetailVisible(true);
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载匹配详情失败');
    }
  };

  // 上传简历到岗位
  const handleUpload = async () => {
    if (fileList.length === 0) {
      message.warning('请选择要上传的文件');
      return;
    }

    if (!jobId) {
      message.error('岗位ID不存在');
      return;
    }

    setUploading(true);
    try {
      // 使用batchApi上传简历到岗位
      const files = fileList.map(file => file.originFileObj!).filter(Boolean);
      const result = await batchApi.batchUploadAndParse(files, Number(jobId));
      message.success(result.message || '上传成功');
      setUploadVisible(false);
      setFileList([]);
      loadJobResumes();
    } catch (error: any) {
      message.error(error.message || '上传失败');
    } finally {
      setUploading(false);
    }
  };

  // 执行匹配
  const handleMatch = async (resumeId: number) => {
    if (!jobId) return;
    setMatching(true);
    try {
      await jobApi.matchResumeToJob({
        resume_id: resumeId,
        job_id: Number(jobId),
        resume_type: 'parsed', // 使用parsed类型（ParsedResume）
      });
      message.success('匹配成功');
      loadJobResumes();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '匹配失败');
    } finally {
      setMatching(false);
    }
  };

  // 批量匹配
  const handleBatchMatch = async (resumeIds: number[]) => {
    if (!jobId) return;
    setMatching(true);
    try {
      await jobApi.batchMatch({
        resume_ids: resumeIds,
        job_id: Number(jobId),
        resume_type: 'parsed',
      });
      message.success('批量匹配成功');
      loadJobResumes();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '批量匹配失败');
    } finally {
      setMatching(false);
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
      title: '简历ID',
      dataIndex: 'resume_id',
      key: 'resume_id',
      width: 100,
    },
    {
      title: '匹配度',
      dataIndex: 'match_score',
      key: 'match_score',
      width: 120,
      render: (score: number) => (
        <Tag color={
          score >= 85 ? 'red' :
          score >= 70 ? 'orange' :
          score >= 60 ? 'blue' : 'default'
        }>
          {score.toFixed(1)}分
        </Tag>
      ),
      sorter: (a: ResumeJobMatch, b: ResumeJobMatch) => a.match_score - b.match_score,
    },
    {
      title: '匹配标签',
      dataIndex: 'match_label',
      key: 'match_label',
      width: 120,
      render: (label: string) => {
        const colorMap: Record<string, string> = {
          '强烈推荐': 'red',
          '推荐': 'orange',
          '谨慎推荐': 'blue',
          '不推荐': 'default',
        };
        return <Tag color={colorMap[label] || 'default'}>{label || '未匹配'}</Tag>;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const statusMap: Record<string, { color: string; text: string }> = {
          'pending': { color: 'default', text: '待处理' },
          'reviewed': { color: 'blue', text: '已审核' },
          'rejected': { color: 'red', text: '已拒绝' },
          'accepted': { color: 'green', text: '已接受' },
        };
        const statusInfo = statusMap[status] || { color: 'default', text: status };
        return <Tag color={statusInfo.color}>{statusInfo.text}</Tag>;
      },
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
      width: 200,
      fixed: 'right' as const,
      render: (_: any, record: ResumeJobMatch) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetail(record.id)}
          >
            查看
          </Button>
          {!record.match_label && (
            <Button
              type="link"
              size="small"
              icon={<UserAddOutlined />}
              onClick={() => handleMatch(record.resume_id)}
              loading={matching}
            >
              匹配
            </Button>
          )}
          <Button
            type="link"
            size="small"
            onClick={() => navigate(`/matching/${record.id}`)}
          >
            详情
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card>
        <div style={{ marginBottom: 16 }}>
          <Space>
            <Button onClick={() => navigate('/jobs')}>返回岗位列表</Button>
            {jobInfo && (
              <span style={{ fontSize: 16, fontWeight: 'bold' }}>
                岗位：{jobInfo.title}
                {jobInfo.department_obj && ` - ${jobInfo.department_obj.name}`}
              </span>
            )}
          </Space>
        </div>

        <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
          <Space>
            <Search
              placeholder="搜索简历（暂不支持）"
              allowClear
              enterButton={<SearchOutlined />}
              style={{ width: 300 }}
              onSearch={handleSearch}
              disabled
            />
            <Select
              placeholder="筛选匹配标签"
              allowClear
              style={{ width: 150 }}
              value={matchLabelFilter || undefined}
              onChange={(value) => {
                setMatchLabelFilter(value || '');
                setPage(1);
              }}
            >
              <Option value="强烈推荐">强烈推荐</Option>
              <Option value="推荐">推荐</Option>
              <Option value="谨慎推荐">谨慎推荐</Option>
              <Option value="不推荐">不推荐</Option>
            </Select>
            <Select
              placeholder="筛选状态"
              allowClear
              style={{ width: 150 }}
              value={statusFilter || undefined}
              onChange={(value) => {
                setStatusFilter(value || '');
                setPage(1);
              }}
            >
              <Option value="pending">待处理</Option>
              <Option value="reviewed">已审核</Option>
              <Option value="rejected">已拒绝</Option>
              <Option value="accepted">已接受</Option>
            </Select>
          </Space>
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
          scroll={{ x: 1200 }}
        />
      </Card>

      {/* 上传简历对话框 */}
      <Modal
        title="上传简历到岗位"
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
          <br />
          上传的简历将自动解析并关联到当前岗位
        </div>
      </Modal>

      {/* 匹配详情对话框 */}
      <Modal
        title="匹配详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={800}
      >
        {selectedMatch && (
          <Descriptions column={2} bordered>
            <Descriptions.Item label="匹配ID">{selectedMatch.id}</Descriptions.Item>
            <Descriptions.Item label="岗位ID">{selectedMatch.job_id}</Descriptions.Item>
            <Descriptions.Item label="简历ID">{selectedMatch.resume_id}</Descriptions.Item>
            <Descriptions.Item label="匹配度">
              <Tag color={
                selectedMatch.match_score >= 85 ? 'red' :
                selectedMatch.match_score >= 70 ? 'orange' :
                selectedMatch.match_score >= 60 ? 'blue' : 'default'
              }>
                {selectedMatch.match_score.toFixed(1)}分
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="匹配标签">
              <Tag>{selectedMatch.match_label || '未匹配'}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag>{selectedMatch.status || 'pending'}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="创建时间" span={2}>
              {new Date(selectedMatch.created_at).toLocaleString('zh-CN')}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
};

export default JobResumePool;
