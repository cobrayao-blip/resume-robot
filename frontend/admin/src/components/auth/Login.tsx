import React from 'react';
import { Form, Input, Button, Card, App } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';
import { LoginRequest } from '@/types/user';

const Login: React.FC = () => {
  const navigate = useNavigate();
  const { login, isLoading } = useAuthStore();
  const { message } = App.useApp();

  const onFinish = async (values: LoginRequest) => {
    console.log('开始登录，邮箱:', values.email);
    try {
      await login(values);
      console.log('登录成功');
      message.success('登录成功！');
      setTimeout(() => {
        navigate('/admin/dashboard', { replace: true });
      }, 100);
    } catch (error: any) {
      // 统一错误提示：用户名和密码错误，请重新输入
      // 显示6秒
      console.log('登录错误:', error);
      console.log('错误响应:', error.response);
      console.log('错误状态码:', error.response?.status);
      console.log('错误详情:', error.response?.data?.detail);
      
      // 确保错误提示显示
      message.error({
        content: '用户名和密码错误，请重新输入',
        duration: 6,
      });
    }
  };

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #722ed1 0%, #eb2f96 100%)',
    }}>
      <Card
        style={{
          width: 400,
          boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <h1 style={{ margin: 0, color: '#722ed1' }}>Resume-Robot</h1>
          <p style={{ color: '#6b7280', marginTop: 8 }}>管理后台登录</p>
        </div>
        <Form
          name="login"
          onFinish={onFinish}
          autoComplete="off"
          size="large"
        >
          <Form.Item
            name="email"
            rules={[
              { required: true, message: '请输入邮箱' },
              { type: 'email', message: '请输入有效的邮箱地址' },
            ]}
          >
            <Input
              prefix={<UserOutlined />}
              placeholder="邮箱"
            />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              prefix={<LockOutlined />}
              placeholder="密码"
            />
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              htmlType="submit"
              loading={isLoading}
              block
            >
              登录
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default Login;

