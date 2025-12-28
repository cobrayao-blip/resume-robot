/**
 * 岗位管理页面 - 岗位列表
 */
import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Table,
  Button,
  Card,
  Space,
  Modal,
  Form,
  Input,
  Select,
  Tag,
  message,
  Popconfirm,
  Drawer,
  Descriptions,
  Tabs,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  RocketOutlined,
  FilterOutlined,
} from '@ant-design/icons';
import { jobApi } from '@/services/jobApi';
import { JobPosition } from '@/types/job';
import type { ColumnsType } from 'antd/es/table';

const { TextArea } = Input;
const { Option } = Select;

const JobList: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [jobs, setJobs] = useState<JobPosition[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();
  const [searchKeyword, setSearchKeyword] = useState<string>('');
  
  const [modalVisible, setModalVisible] = useState(false);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [selectedJob, setSelectedJob] = useState<JobPosition | null>(null);
  const [form] = Form.useForm();

  // 加载岗位列表
  const loadJobs = async () => {
    setLoading(true);
    try {
      const response = await jobApi.getPositions({
        skip: (page - 1) * pageSize,
        limit: pageSize,
        status: statusFilter,
        search: searchKeyword || undefined,
      });
      // 后端返回的是 JobPositionListResponse，直接包含 items 和 total
      if (response && response.items) {
        setJobs(response.items || []);
        setTotal(response.total || 0);
      } else {
        // 兼容旧格式（如果有 success 字段）
        if (response.success && response.data) {
          setJobs(response.data.items || []);
          setTotal(response.data.total || 0);
        } else {
          setJobs([]);
          setTotal(0);
        }
      }
    } catch (error: any) {
      console.error('加载岗位列表失败:', error);
      message.error('加载岗位列表失败: ' + (error.response?.data?.detail || error.message));
      setJobs([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadJobs();
  }, [page, pageSize, statusFilter, searchKeyword]);

  // 监听路由变化，当从创建页面返回时刷新列表
  useEffect(() => {
    if (location.pathname === '/jobs') {
      loadJobs();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  // 创建岗位
  const handleCreate = () => {
    navigate('/jobs/create');
  };

  // 编辑岗位
  const handleEdit = (job: JobPosition) => {
    navigate(`/jobs/${job.id}`);
  };

  // 查看详情
  const handleView = async (job: JobPosition) => {
    try {
      const response = await jobApi.getPosition(job.id, true);
      if (response.success) {
        setSelectedJob(response.data);
        setDrawerVisible(true);
      }
    } catch (error: any) {
      message.error('加载岗位详情失败: ' + (error.response?.data?.detail || error.message));
    }
  };

  // 删除岗位
  const handleDelete = async (id: number) => {
    try {
      await jobApi.deletePosition(id);
      message.success('岗位删除成功');
      loadJobs();
    } catch (error: any) {
      message.error('删除失败: ' + (error.response?.data?.detail || error.message));
    }
  };

  // 发布岗位
  const handlePublish = async (job: JobPosition) => {
    try {
      await jobApi.publishJob(job.id, true, true);
      message.success('岗位发布成功');
      loadJobs();
    } catch (error: any) {
      message.error('发布失败: ' + (error.response?.data?.detail || error.message));
    }
  };

  // 解析岗位画像
  const handleParseProfile = async (job: JobPosition) => {
    try {
      message.loading({ content: '正在解析岗位画像...', key: 'parse' });
      await jobApi.parseJobProfile(job.id);
      message.success({ content: '岗位画像解析成功', key: 'parse' });
      loadJobs();
    } catch (error: any) {
      message.error({ content: '解析失败: ' + (error.response?.data?.detail || error.message), key: 'parse' });
    }
  };

  const columns: ColumnsType<JobPosition> = [
    {
      title: '岗位名称',
      dataIndex: 'title',
      key: 'title',
      width: 200,
    },
    {
      title: '部门',
      key: 'department',
      width: 150,
      render: (_, record) => {
        // 优先显示部门对象信息，否则显示部门名称
        if (record.department_obj) {
          return (
            <span>
              {record.department_obj.path || record.department_obj.name}
            </span>
          );
        }
        return record.department || '-';
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const statusMap: Record<string, { color: string; text: string }> = {
          draft: { color: 'default', text: '草稿' },
          published: { color: 'success', text: '已发布' },
          closed: { color: 'error', text: '已关闭' },
        };
        const config = statusMap[status] || { color: 'default', text: status };
        return <Tag color={config.color}>{config.text}</Tag>;
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
      width: 300,
      fixed: 'right',
      render: (_, record) => (
        <Space size="small">
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleView(record)}
          >
            查看
          </Button>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          {record.status === 'draft' && (
            <>
              <Button
                type="link"
                size="small"
                icon={<FilterOutlined />}
                onClick={() => handleParseProfile(record)}
              >
                解析画像
              </Button>
              <Button
                type="link"
                size="small"
                icon={<RocketOutlined />}
                onClick={() => handlePublish(record)}
              >
                发布
              </Button>
            </>
          )}
          <Popconfirm
            title="确定要删除这个岗位吗？"
            onConfirm={() => handleDelete(record.id)}
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
      <Card
        title="岗位管理"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            新建岗位
          </Button>
        }
      >
        <Space style={{ marginBottom: 16 }}>
          <Input.Search
            placeholder="搜索岗位名称或部门"
            style={{ width: 300 }}
            onSearch={(value) => {
              setSearchKeyword(value);
              setPage(1);
            }}
            allowClear
          />
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
            <Option value="draft">草稿</Option>
            <Option value="published">已发布</Option>
            <Option value="closed">已关闭</Option>
          </Select>
        </Space>

        <Table
          columns={columns}
          dataSource={jobs}
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

      {/* 详情抽屉 */}
      <Drawer
        title="岗位详情"
        placement="right"
        width={600}
        open={drawerVisible}
        onClose={() => setDrawerVisible(false)}
      >
        {selectedJob && (
          <Tabs>
            <Tabs.TabPane tab="基本信息" key="basic">
              <Descriptions column={1} bordered>
                <Descriptions.Item label="岗位名称">{selectedJob.title}</Descriptions.Item>
                <Descriptions.Item label="部门">
                  {selectedJob.department_obj 
                    ? (selectedJob.department_obj.path || selectedJob.department_obj.name)
                    : (selectedJob.department || '-')}
                </Descriptions.Item>
                <Descriptions.Item label="状态">
                  <Tag color={selectedJob.status === 'published' ? 'success' : 'default'}>
                    {selectedJob.status === 'published' ? '已发布' : selectedJob.status === 'draft' ? '草稿' : '已关闭'}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="岗位描述">
                  <div style={{ whiteSpace: 'pre-wrap' }}>{selectedJob.description || '-'}</div>
                </Descriptions.Item>
                <Descriptions.Item label="岗位要求">
                  <div style={{ whiteSpace: 'pre-wrap' }}>{selectedJob.requirements || '-'}</div>
                </Descriptions.Item>
                <Descriptions.Item label="创建时间">
                  {new Date(selectedJob.created_at).toLocaleString('zh-CN')}
                </Descriptions.Item>
              </Descriptions>
            </Tabs.TabPane>
            {selectedJob.profile && (
              <Tabs.TabPane tab="岗位画像" key="profile">
                <pre style={{ background: '#f5f5f5', padding: '16px', borderRadius: '4px', overflow: 'auto' }}>
                  {JSON.stringify(selectedJob.profile, null, 2)}
                </pre>
              </Tabs.TabPane>
            )}
          </Tabs>
        )}
      </Drawer>
    </div>
  );
};

export default JobList;


