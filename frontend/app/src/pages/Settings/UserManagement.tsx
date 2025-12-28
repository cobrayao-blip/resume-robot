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
  Switch,
  Tag,
  Popconfirm,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  UserAddOutlined,
} from '@ant-design/icons';
import { userApi, TenantUser, UserCreate, UserUpdate } from '@/services/userApi';

const { Option } = Select;

const UserManagement: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [users, setUsers] = useState<TenantUser[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [searchText, setSearchText] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('');
  const [form] = Form.useForm();
  const [modalVisible, setModalVisible] = useState(false);
  const [editingUser, setEditingUser] = useState<TenantUser | null>(null);
  const [inviteVisible, setInviteVisible] = useState(false);
  const [inviteForm] = Form.useForm();

  // 加载用户列表
  const loadUsers = async () => {
    setLoading(true);
    try {
      const response = await userApi.getUsers({
        page,
        pageSize,
        search: searchText || undefined,
        role: roleFilter || undefined,
      });
      setUsers(response.items || []);
      setTotal(response.total || 0);
    } catch (error: any) {
      console.error('加载用户列表失败:', error);
      const errorMsg = error.response?.data?.detail || error.response?.data?.message || error.message || '加载用户列表失败';
      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, [page, pageSize, searchText, roleFilter]);

  // 创建/更新用户
  const handleSubmit = async (values: any) => {
    setLoading(true);
    try {
      if (editingUser) {
        await userApi.updateUser(editingUser.id, values);
        message.success('更新成功');
      } else {
        // 如果没有提供密码，使用默认密码
        const submitData = {
          email: values.email,
          password: values.password || 'User123456',
          full_name: values.full_name || undefined,
          role: values.role || 'hr_user',
        };
        console.log('提交用户数据:', submitData);
        await userApi.createUser(submitData);
        const passwordUsed = values.password || 'User123456';
        message.success(`用户创建成功，初始密码：${passwordUsed}`);
      }
      setModalVisible(false);
      form.resetFields();
      setEditingUser(null);
      loadUsers();
    } catch (error: any) {
      console.error('保存失败:', error);
      const errorMsg = error.response?.data?.detail || error.response?.data?.message || error.message || '保存失败';
      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  // 编辑用户
  const handleEdit = (user: TenantUser) => {
    setEditingUser(user);
    form.setFieldsValue({
      email: user.email,
      full_name: user.full_name,
      role: user.role,
      is_active: user.is_active,
    });
    setModalVisible(true);
  };

  // 删除用户
  const handleDelete = async (id: number) => {
    try {
      await userApi.deleteUser(id);
      message.success('删除成功');
      loadUsers();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  // 邀请用户
  const handleInvite = async (values: any) => {
    try {
      await userApi.inviteUser(values.email, values.role);
      message.success('邀请已发送');
      setInviteVisible(false);
      inviteForm.resetFields();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '邀请失败');
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
      title: '邮箱',
      dataIndex: 'email',
      key: 'email',
      width: 200,
    },
    {
      title: '姓名',
      dataIndex: 'full_name',
      key: 'full_name',
      width: 120,
    },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      width: 120,
      render: (role: string) => {
        const roleMap: Record<string, { color: string; text: string }> = {
          'tenant_admin': { color: 'red', text: '租户管理员' },
          'hr_user': { color: 'blue', text: 'HR用户' },
        };
        const roleInfo = roleMap[role] || { color: 'default', text: role };
        return <Tag color={roleInfo.color}>{roleInfo.text}</Tag>;
      },
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      render: (isActive: boolean) => (
        <Tag color={isActive ? 'green' : 'default'}>
          {isActive ? '启用' : '禁用'}
        </Tag>
      ),
    },
    {
      title: '已验证',
      dataIndex: 'is_verified',
      key: 'is_verified',
      width: 100,
      render: (isVerified: boolean) => (
        <Tag color={isVerified ? 'green' : 'default'}>
          {isVerified ? '是' : '否'}
        </Tag>
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
      width: 220,
      fixed: 'right' as const,
      render: (_: any, record: TenantUser) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定要删除这个用户吗？"
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
          <h2 style={{ margin: 0 }}>用户管理</h2>
          <Space>
            <Button
              icon={<UserAddOutlined />}
              onClick={() => {
                setInviteVisible(true);
                inviteForm.resetFields();
              }}
            >
              邀请用户
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => {
                setEditingUser(null);
                form.resetFields();
                setModalVisible(true);
              }}
            >
              创建用户
            </Button>
          </Space>
        </Space>

        <Space style={{ marginBottom: 16 }}>
          <Input.Search
            placeholder="搜索邮箱、姓名"
            allowClear
            style={{ width: 300 }}
            onSearch={(value) => {
              setSearchText(value);
              setPage(1);
            }}
          />
          <Select
            placeholder="筛选角色"
            allowClear
            style={{ width: 150 }}
            value={roleFilter || undefined}
            onChange={(value) => {
              setRoleFilter(value || '');
              setPage(1);
            }}
          >
            <Option value="tenant_admin">租户管理员</Option>
            <Option value="hr_user">HR用户</Option>
          </Select>
        </Space>

        <Table
          columns={columns}
          dataSource={users}
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

      {/* 创建/编辑用户对话框 */}
      <Modal
        title={editingUser ? '编辑用户' : '创建用户'}
        open={modalVisible}
        onOk={() => form.submit()}
        onCancel={() => {
          setModalVisible(false);
          form.resetFields();
          setEditingUser(null);
        }}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
        >
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input placeholder="user@example.com" disabled={!!editingUser} />
          </Form.Item>

          {!editingUser && (
            <Form.Item
              name="password"
              label="初始密码"
              rules={[
                { min: 6, message: '密码至少6位' },
              ]}
              tooltip="留空则使用默认密码：User123456，用户首次登录后可以修改密码"
            >
              <Input.Password placeholder="留空则使用默认密码：User123456" />
            </Form.Item>
          )}

          <Form.Item
            name="full_name"
            label="姓名"
          >
            <Input placeholder="请输入姓名" />
          </Form.Item>

          <Form.Item
            name="role"
            label="角色"
            rules={[{ required: true, message: '请选择角色' }]}
          >
            <Select placeholder="请选择角色">
              <Option value="hr_user">HR用户</Option>
              <Option value="tenant_admin">租户管理员</Option>
            </Select>
          </Form.Item>

          {editingUser && (
            <>
              <Form.Item
                name="password"
                label="重置密码"
                rules={[
                  { min: 8, message: '密码长度至少8位' },
                  {
                    pattern: /^(?=.*[A-Za-z])(?=.*\d)/,
                    message: '密码必须包含至少一个字母和一个数字',
                  },
                ]}
                tooltip="留空则不修改密码，填写则重置用户密码"
              >
                <Input.Password placeholder="留空则不修改密码" />
              </Form.Item>
              <Form.Item
                name="is_active"
                label="启用状态"
                valuePropName="checked"
              >
                <Switch checkedChildren="启用" unCheckedChildren="禁用" />
              </Form.Item>
            </>
          )}
        </Form>
      </Modal>

      {/* 邀请用户对话框 */}
      <Modal
        title="邀请用户"
        open={inviteVisible}
        onOk={() => inviteForm.submit()}
        onCancel={() => {
          setInviteVisible(false);
          inviteForm.resetFields();
        }}
      >
        <Form
          form={inviteForm}
          layout="vertical"
          onFinish={handleInvite}
        >
          <Form.Item
            name="email"
            label="邮箱"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input placeholder="user@example.com" />
          </Form.Item>

          <Form.Item
            name="role"
            label="角色"
            rules={[{ required: true, message: '请选择角色' }]}
            initialValue="hr_user"
          >
            <Select placeholder="请选择角色">
              <Option value="hr_user">HR用户</Option>
              <Option value="tenant_admin">租户管理员</Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default UserManagement;
