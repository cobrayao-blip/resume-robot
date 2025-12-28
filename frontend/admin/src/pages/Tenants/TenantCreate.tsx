import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Form,
  Input,
  Select,
  Button,
  message,
  Space,
} from 'antd';
import {
  ArrowLeftOutlined,
  SaveOutlined,
} from '@ant-design/icons';
import { tenantApi, TenantCreate } from '@/services/tenantApi';

const { Option } = Select;

const TenantCreatePage: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (values: any) => {
    setLoading(true);
    try {
      // 处理数据格式
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
      
      // 如果有管理员信息，添加到提交数据
      if (values.admin_email) {
        submitData.admin_email = values.admin_email;
        submitData.admin_password = values.admin_password || 'Admin123456';
        submitData.admin_name = values.admin_name || '租户管理员';
      }
      
      console.log('提交数据:', submitData);
      await tenantApi.createTenant(submitData);
      message.success('租户创建成功');
      navigate('/admin/tenants');
    } catch (error: any) {
      console.error('创建租户失败:', error);
      const errorMsg = error.response?.data?.detail || error.message || '创建租户失败';
      message.error(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Card>
        <Space style={{ marginBottom: 24 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/admin/tenants')}>
            返回列表
          </Button>
        </Space>

        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          style={{ maxWidth: 600 }}
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
            rules={[
              { pattern: /^[a-z0-9-]+$/, message: '域名只能包含小写字母、数字和连字符' }
            ]}
          >
            <Input placeholder="例如：test-company" />
          </Form.Item>

          <Form.Item
            name="contact_email"
            label="联系人邮箱"
            rules={[
              { type: 'email', message: '请输入有效的邮箱地址' }
            ]}
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
            ]}
            initialValue={500}
            getValueFromEvent={(e) => parseInt(e.target.value) || 0}
            normalize={(value) => value ? parseInt(value) : undefined}
          >
            <Input type="number" min={1} />
          </Form.Item>

          <Form.Item label="租户管理员信息（可选）">
            <div style={{ marginBottom: 16, padding: 12, background: '#f0f0f0', borderRadius: 4 }}>
              <p style={{ margin: '0 0 8px 0', fontSize: '12px', color: '#666' }}>
                💡 提示：如果不填写管理员信息，租户创建后需要手动创建管理员账户。
                如果填写，系统会自动创建管理员账户（默认密码：Admin123456）
              </p>
            </div>
            <Form.Item
              name="admin_email"
              label="管理员邮箱"
              rules={[
                { type: 'email', message: '请输入有效的邮箱地址' }
              ]}
              style={{ marginBottom: 16 }}
              tooltip="填写后会自动创建该邮箱对应的租户管理员账户"
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

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" icon={<SaveOutlined />} loading={loading}>
                创建租户
              </Button>
              <Button onClick={() => navigate('/admin/tenants')}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default TenantCreatePage;
