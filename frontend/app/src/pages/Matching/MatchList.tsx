/**
 * 简历匹配页面 - 匹配列表
 */
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Table,
  Button,
  Card,
  Space,
  Select,
  Tag,
  message,
  Drawer,
  Descriptions,
  Tabs,
  Progress,
} from 'antd';
import {
  EyeOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { jobApi } from '@/services/jobApi';
import { ResumeJobMatch, JobPosition } from '@/types/job';
import type { ColumnsType } from 'antd/es/table';

const { Option } = Select;

const MatchList: React.FC = () => {
  const navigate = useNavigate();
  const [matches, setMatches] = useState<ResumeJobMatch[]>([]);
  const [jobs, setJobs] = useState<JobPosition[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  
  const [jobFilter, setJobFilter] = useState<number | undefined>();
  const [labelFilter, setLabelFilter] = useState<string | undefined>();
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [selectedMatch, setSelectedMatch] = useState<ResumeJobMatch | null>(null);

  // 加载岗位列表
  const loadJobs = async () => {
    try {
      const response = await jobApi.getPositions({ status: 'published' });
      if (response.success) {
        setJobs(response.data.items || []);
      }
    } catch (error: any) {
      console.error('加载岗位列表失败:', error);
    }
  };

  // 加载匹配结果
  const loadMatches = async () => {
    setLoading(true);
    try {
      const response = await jobApi.getMatchResults({
        skip: (page - 1) * pageSize,
        limit: pageSize,
        job_id: jobFilter,
        match_label: labelFilter,
        status: statusFilter,
      });
      if (response.success) {
        setMatches(response.data.items || []);
        setTotal(response.data.total || 0);
      }
    } catch (error: any) {
      message.error('加载匹配结果失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadJobs();
  }, []);

  useEffect(() => {
    loadMatches();
  }, [page, pageSize, jobFilter, labelFilter, statusFilter]);

  // 查看详情
  const handleView = async (match: ResumeJobMatch) => {
    navigate(`/matching/${match.id}`);
  };

  // 更新状态
  const handleUpdateStatus = async (match: ResumeJobMatch, status: string) => {
    try {
      await jobApi.updateMatchStatus(match.id, status);
      message.success('状态更新成功');
      loadMatches();
    } catch (error: any) {
      message.error('更新失败: ' + (error.response?.data?.detail || error.message));
    }
  };

  const getLabelColor = (label: string) => {
    const colorMap: Record<string, string> = {
      '强烈推荐': 'success',
      '推荐': 'processing',
      '谨慎推荐': 'warning',
      '不推荐': 'error',
    };
    return colorMap[label] || 'default';
  };

  const getStatusIcon = (status: string) => {
    const iconMap: Record<string, any> = {
      pending: <ClockCircleOutlined style={{ color: '#1890ff' }} />,
      reviewed: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
      rejected: <CloseCircleOutlined style={{ color: '#ff4d4f' }} />,
      accepted: <CheckCircleOutlined style={{ color: '#52c41a' }} />,
    };
    return iconMap[status] || null;
  };

  const columns: ColumnsType<ResumeJobMatch> = [
    {
      title: '简历ID',
      dataIndex: 'resume_id',
      key: 'resume_id',
      width: 100,
    },
    {
      title: '岗位ID',
      dataIndex: 'job_id',
      key: 'job_id',
      width: 100,
    },
    {
      title: '匹配度',
      dataIndex: 'match_score',
      key: 'match_score',
      width: 150,
      render: (score: number) => (
        <div>
          <Progress
            percent={score * 10}
            format={(percent) => `${score.toFixed(1)}分`}
            strokeColor={
              score >= 8 ? '#52c41a' :
              score >= 6 ? '#1890ff' :
              score >= 4 ? '#faad14' : '#ff4d4f'
            }
          />
        </div>
      ),
      sorter: (a, b) => a.match_score - b.match_score,
    },
    {
      title: '匹配标签',
      dataIndex: 'match_label',
      key: 'match_label',
      width: 120,
      render: (label: string) => (
        <Tag color={getLabelColor(label)}>{label}</Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 120,
      render: (status: string) => {
        const statusMap: Record<string, { text: string; color: string }> = {
          pending: { text: '待审核', color: 'default' },
          reviewed: { text: '已审核', color: 'processing' },
          rejected: { text: '已拒绝', color: 'error' },
          accepted: { text: '已接受', color: 'success' },
        };
        const config = statusMap[status] || { text: status, color: 'default' };
        return (
          <Space>
            {getStatusIcon(status)}
            <Tag color={config.color}>{config.text}</Tag>
          </Space>
        );
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (text: string) => new Date(text).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleView(record)}
          >
            查看详情
          </Button>
          {record.status === 'pending' && (
            <Space size="small">
              <Button
                type="link"
                size="small"
                onClick={() => handleUpdateStatus(record, 'reviewed')}
              >
                审核
              </Button>
              <Button
                type="link"
                size="small"
                danger
                onClick={() => handleUpdateStatus(record, 'rejected')}
              >
                拒绝
              </Button>
            </Space>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card title="简历匹配结果">
        <Space style={{ marginBottom: 16 }}>
          <Select
            style={{ width: 200 }}
            placeholder="筛选岗位"
            allowClear
            value={jobFilter}
            onChange={(value) => {
              setJobFilter(value);
              setPage(1);
            }}
          >
            {jobs.map(job => (
              <Option key={job.id} value={job.id}>{job.title}</Option>
            ))}
          </Select>
          <Select
            style={{ width: 150 }}
            placeholder="筛选标签"
            allowClear
            value={labelFilter}
            onChange={(value) => {
              setLabelFilter(value);
              setPage(1);
            }}
          >
            <Option value="强烈推荐">强烈推荐</Option>
            <Option value="推荐">推荐</Option>
            <Option value="谨慎推荐">谨慎推荐</Option>
            <Option value="不推荐">不推荐</Option>
          </Select>
          <Select
            style={{ width: 150 }}
            placeholder="筛选状态"
            allowClear
            value={statusFilter}
            onChange={(value) => {
              setStatusFilter(value);
              setPage(1);
            }}
          >
            <Option value="pending">待审核</Option>
            <Option value="reviewed">已审核</Option>
            <Option value="rejected">已拒绝</Option>
            <Option value="accepted">已接受</Option>
          </Select>
        </Space>

        <Table
          columns={columns}
          dataSource={matches}
          loading={loading}
          rowKey="id"
          pagination={{
            current: page,
            pageSize: pageSize,
            total: total,
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
    </div>
  );
};

export default MatchList;


