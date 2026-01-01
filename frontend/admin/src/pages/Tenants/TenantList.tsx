import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  message,
  Modal,
  Form,
  Input,
  Select,
  Tag,
  Popconfirm,
  Descriptions,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
} from '@ant-design/icons';
import { tenantApi, Tenant } from '@/services/tenantApi';

const { Option } = Select;

const TenantList: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [searchText, setSearchText] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [planFilter, setPlanFilter] = useState<string>('');
  const [form] = Form.useForm();
  const [modalVisible, setModalVisible] = useState(false);
  const [detailVisible, setDetailVisible] = useState(false);
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null);
  const [selectedTenant, setSelectedTenant] = useState<Tenant | null>(null);

  // 加载租户列表
  const loadTenants = async () => {
    setLoading(true);
    try {
      const response = await tenantApi.getTenants({
        page,
        pageSize,
        search: searchText || undefined,
        status: statusFilter || undefined,
        subscription_plan: planFilter || undefined,
      });
      setTenants(response.items);
      setTotal(response.total);
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载租户列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTenants();
  }, [page, pageSize, searchText, statusFilter, planFilter]);

  // 创建/更新租户
  const handleSubmit = async (values: any) => {
    try {
      if (editingTenant) {
        // 编辑时不需要管理员信息
        await tenantApi.updateTenant(editingTenant.id, values);
        message.success('更新成功');
      } else {
        // 创建时需要处理管理员信息
        const submitData: any = {
          name: values.name,
          domain: values.domain || undefined,
          contact_email: values.contact_email || undefined,
          contact_phone: values.contact_phone || undefined,
          subscription_plan: values.subscription_plan || 'trial',
          status: values.status || 'active',
          max_users: values.max_users ? parseInt(String(values.max_users)) : 10,
          max_jobs: values.max_jobs ? parseInt(String(values.max_jobs)) : 50,
          max_resumes_per_month: values.max_resumes_per_month ? parseInt(String(values.max_resumes_per_month)) : 500,
        };
        
        // 如果有管理员邮箱，添加管理员信息
        if (values.admin_email) {
          submitData.admin_email = values.admin_email;
          submitData.admin_password = values.admin_password || 'Admin123456'; // 默认密码
          submitData.admin_name = values.admin_name || '租户管理员'; // 默认名称
        }
        
        console.log('提交的租户数据:', JSON.stringify(submitData, null, 2));
        await tenantApi.createTenant(submitData);
        message.success('创建成功');
      }
      setModalVisible(false);
      form.resetFields();
      setEditingTenant(null);
      loadTenants();
    } catch (error: any) {
      console.error('创建/更新租户失败:', error);
      const errorMsg = error.response?.data?.detail || error.message || '保存失败';
      message.error(errorMsg);
    }
  };

  // 编辑租户
  const handleEdit = (tenant: Tenant) => {
    setEditingTenant(tenant);
    form.setFieldsValue({
      name: tenant.name,
      domain: tenant.domain,
      contact_email: tenant.contact_email,
      contact_phone: tenant.contact_phone,
      subscription_plan: tenant.subscription_plan,
      status: tenant.status,
      max_users: tenant.max_users,
      max_jobs: tenant.max_jobs,
      max_resumes_per_month: tenant.max_resumes_per_month,
    });
    setModalVisible(true);
  };

  // 删除租户
  const handleDelete = async (id: number) => {
    try {
      await tenantApi.deleteTenant(id);
      message.success('删除成功');
      loadTenants();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  // 查看详情
  const handleViewDetail = async (id: number) => {
    try {
      const tenant = await tenantApi.getTenant(id);
      setSelectedTenant(tenant);
      setDetailVisible(true);
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载租户详情失败');
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
      title: '租户名称',
      dataIndex: 'name',
      key: 'name',
      width: 150,
    },
    {
      title: '域名',
      dataIndex: 'domain',
      key: 'domain',
      width: 150,
    },
    {
      title: '联系人邮箱',
      dataIndex: 'contact_email',
      key: 'contact_email',
      width: 200,
    },
    {
      title: '订阅套餐',
      dataIndex: 'subscription_plan',
      key: 'subscription_plan',
      width: 120,
      render: (plan: string) => {
        const planMap: Record<string, { color: string; text: string }> = {
          'trial': { color: 'default', text: '试用版' },
          'basic': { color: 'blue', text: '基础版' },
          'professional': { color: 'green', text: '专业版' },
          'enterprise': { color: 'red', text: '企业版' },
        };
        const planInfo = planMap[plan] || { color: 'default', text: plan };
        return <Tag color={planInfo.color}>{planInfo.text}</Tag>;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => {
        const statusMap: Record<string, { color: string; text: string }> = {
          'active': { color: 'green', text: '活跃' },
          'suspended': { color: 'orange', text: '已暂停' },
          'expired': { color: 'red', text: '已过期' },
        };
        const statusInfo = statusMap[status] || { color: 'default', text: status };
        return <Tag color={statusInfo.color}>{statusInfo.text}</Tag>;
      },
    },
    {
      title: '用户数限制',
      dataIndex: 'max_users',
      key: 'max_users',
      width: 100,
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
      width: 250,
      fixed: 'right' as const,
      render: (_: any, record: Tenant) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewDetail(record.id)}
          >
            详情
          </Button>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除这个租户吗？删除后该租户的所有数据将被删除。"
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
          <h2 style={{ margin: 0 }}>租户管理</h2>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditingTenant(null);
              form.resetFields();
              setModalVisible(true);
            }}
          >
            创建租户
          </Button>
        </Space>

        <Space style={{ marginBottom: 16 }}>
          <Input.Search
            placeholder="搜索租户名称"
            allowClear
            style={{ width: 300 }}
            onSearch={(value) => {
              setSearchText(value);
              setPage(1);
            }}
          />
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
            <Option value="active">活跃</Option>
            <Option value="suspended">已暂停</Option>
            <Option value="expired">已过期</Option>
          </Select>
          <Select
            placeholder="筛选套餐"
            allowClear
            style={{ width: 150 }}
            value={planFilter || undefined}
            onChange={(value) => {
              setPlanFilter(value || '');
              setPage(1);
            }}
          >
            <Option value="trial">试用版</Option>
            <Option value="basic">基础版</Option>
            <Option value="professional">专业版</Option>
            <Option value="enterprise">企业版</Option>
          </Select>
        </Space>

        <Table
          columns={columns}
          dataSource={tenants}
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
          scroll={{ x: 1400 }}
        />
      </Card>

      {/* 创建/编辑租户对话框 */}
      <Modal
        title={editingTenant ? '编辑租户' : '创建租户'}
        open={modalVisible}
        onOk={() => form.submit()}
        onCancel={() => {
          setModalVisible(false);
          form.resetFields();
          setEditingTenant(null);
        }}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
        >
          <Form.Item
            name="name"
            label="租户名称"
            rules={[{ required: true, message: '请输入租户名称' }]}
          >
            <Input placeholder="例如：测试公司" />
          </Form.Item>

          <Form.Item
            name="domain"
            label="域名（可选）"
          >
            <Input placeholder="例如：test-company" />
          </Form.Item>

          <Form.Item
            name="contact_email"
            label="联系人邮箱"
            rules={[{ type: 'email', message: '请输入有效的邮箱地址' }]}
          >
            <Input placeholder="contact@example.com" />
          </Form.Item>

          <Form.Item
            name="contact_phone"
            label="联系人电话"
          >
            <Input placeholder="13800138000" />
          </Form.Item>

          <Form.Item
            name="subscription_plan"
            label="订阅套餐"
            rules={[{ required: true, message: '请选择订阅套餐' }]}
            initialValue="trial"
          >
            <Select>
              <Option value="trial">试用版</Option>
              <Option value="basic">基础版</Option>
              <Option value="professional">专业版</Option>
              <Option value="enterprise">企业版</Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="status"
            label="状态"
            rules={[{ required: true, message: '请选择状态' }]}
            initialValue="active"
          >
            <Select>
              <Option value="active">活跃</Option>
              <Option value="suspended">已暂停</Option>
              <Option value="expired">已过期</Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="max_users"
            label="最大用户数"
            rules={[
              { required: true, message: '请输入最大用户数' },
              { type: 'number', min: 1, message: '最大用户数必须大于0' }
            ]}
            initialValue={10}
            getValueFromEvent={(e) => parseInt(e.target.value) || 0}
            normalize={(value) => value ? parseInt(value) : undefined}
          >
            <Input type="number" min={1} />
          </Form.Item>

          <Form.Item
            name="max_jobs"
            label="最大岗位数"
            rules={[
              { required: true, message: '请输入最大岗位数' },
              { type: 'number', min: 1, message: '最大岗位数必须大于0' }
            ]}
            initialValue={50}
            getValueFromEvent={(e) => parseInt(e.target.value) || 0}
            normalize={(value) => value ? parseInt(value) : undefined}
          >
            <Input type="number" min={1} />
          </Form.Item>

          <Form.Item
            name="max_resumes_per_month"
            label="每月最大简历处理数"
            rules={[
              { required: true, message: '请输入每月最大简历处理数' },
              { type: 'number', min: 1, message: '每月最大简历处理数必须大于0' }
            ]}
            initialValue={500}
            getValueFromEvent={(e) => parseInt(e.target.value) || 0}
            normalize={(value) => value ? parseInt(value) : undefined}
          >
            <Input type="number" min={1} />
          </Form.Item>

          {/* 仅在创建时显示管理员信息 */}
          {!editingTenant && (
            <>
              <Form.Item label="租户管理员信息（可选）" style={{ marginTop: 16 }}>
                <div style={{ marginBottom: 16, padding: 12, background: '#f0f0f0', borderRadius: 4 }}>
                  <p style={{ margin: '0 0 8px 0', fontSize: '12px', color: '#666' }}>
                    💡 提示：如果不填写管理员信息，租户创建后需要手动创建管理员账户。
                    如果填写，系统会自动创建管理员账户（默认密码：Admin123456）
                  </p>
                </div>
                <Form.Item
                  name="admin_email"
                  label="管理员邮箱（账户名）"
                  rules={[
                    { type: 'email', message: '请输入有效的邮箱地址' }
                  ]}
                  style={{ marginBottom: 16 }}
                  tooltip="填写后会自动创建该邮箱对应的租户管理员账户，该邮箱即为登录账户名"
                >
                  <Input placeholder="admin@example.com" />
                </Form.Item>

                <Form.Item
                  name="admin_password"
                  label="管理员初始密码"
                  rules={[
                    { min: 6, message: '密码至少6位' }
                  ]}
                  style={{ marginBottom: 16 }}
                  tooltip="留空则使用默认密码：Admin123456（管理员首次登录后应尽快修改）"
                >
                  <Input.Password placeholder="留空则使用默认密码：Admin123456" />
                </Form.Item>

                <Form.Item
                  name="admin_name"
                  label="管理员姓名"
                  tooltip="留空则使用默认名称：租户管理员"
                >
                  <Input placeholder="留空则使用默认名称：租户管理员" />
                </Form.Item>
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>

      {/* 租户详情对话框 */}
      <Modal
        title="租户详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={800}
      >
        {selectedTenant && (
          <Descriptions column={2} bordered>
            <Descriptions.Item label="ID">{selectedTenant.id}</Descriptions.Item>
            <Descriptions.Item label="租户名称">{selectedTenant.name}</Descriptions.Item>
            <Descriptions.Item label="域名">{selectedTenant.domain || 'N/A'}</Descriptions.Item>
            <Descriptions.Item label="联系人邮箱">{selectedTenant.contact_email || 'N/A'}</Descriptions.Item>
            <Descriptions.Item label="联系人电话">{selectedTenant.contact_phone || 'N/A'}</Descriptions.Item>
            <Descriptions.Item label="订阅套餐">
              <Tag>{selectedTenant.subscription_plan}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={
                selectedTenant.status === 'active' ? 'green' :
                selectedTenant.status === 'suspended' ? 'orange' : 'red'
              }>
                {selectedTenant.status === 'active' ? '活跃' :
                 selectedTenant.status === 'suspended' ? '已暂停' : '已过期'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="最大用户数">{selectedTenant.max_users}</Descriptions.Item>
            <Descriptions.Item label="最大岗位数">{selectedTenant.max_jobs}</Descriptions.Item>
            <Descriptions.Item label="每月最大简历处理数">{selectedTenant.max_resumes_per_month}</Descriptions.Item>
            <Descriptions.Item label="当前月已处理简历数">{selectedTenant.current_month_resume_count}</Descriptions.Item>
            <Descriptions.Item label="订阅开始时间">
              {selectedTenant.subscription_start ? new Date(selectedTenant.subscription_start).toLocaleString('zh-CN') : 'N/A'}
            </Descriptions.Item>
            <Descriptions.Item label="订阅结束时间">
              {selectedTenant.subscription_end ? new Date(selectedTenant.subscription_end).toLocaleString('zh-CN') : 'N/A'}
            </Descriptions.Item>
            <Descriptions.Item label="创建时间" span={2}>
              {new Date(selectedTenant.created_at).toLocaleString('zh-CN')}
            </Descriptions.Item>
            <Descriptions.Item label="更新时间" span={2}>
              {new Date(selectedTenant.updated_at).toLocaleString('zh-CN')}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
};

export default TenantList;
