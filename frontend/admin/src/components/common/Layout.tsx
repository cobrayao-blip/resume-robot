import React from 'react';
import { Layout, Menu, Button, Dropdown, Avatar } from 'antd';
import { 
  DashboardOutlined,
  TeamOutlined,
  CreditCardOutlined,
  SettingOutlined,
  BarChartOutlined,
  UserOutlined,
  LogoutOutlined,
} from '@ant-design/icons';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '@/stores/authStore';

const { Header, Sider, Content } = Layout;

interface AppLayoutProps {
  children: React.ReactNode;
}

const AppLayout: React.FC<AppLayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuthStore();

  const menuItems = [
    {
      key: '/admin/dashboard',
      icon: <DashboardOutlined />,
      label: '仪表盘',
    },
    {
      key: '/admin/tenants',
      icon: <TeamOutlined />,
      label: '租户管理',
    },
    {
      key: '/admin/subscriptions',
      icon: <CreditCardOutlined />,
      label: '订阅管理',
    },
    {
      key: '/admin/system',
      icon: <SettingOutlined />,
      label: '系统配置',
      children: [
        {
          key: '/admin/system/llm',
          label: 'LLM服务配置',
        },
        {
          key: '/admin/system/params',
          label: '系统参数',
        },
        {
          key: '/admin/system/features',
          label: '功能开关',
        },
      ],
    },
    {
      key: '/admin/statistics',
      icon: <BarChartOutlined />,
      label: '数据统计',
      children: [
        {
          key: '/admin/statistics/overview',
          label: '平台概览',
        },
        {
          key: '/admin/statistics/tenants',
          label: '租户统计',
        },
        {
          key: '/admin/statistics/revenue',
          label: '收入统计',
        },
      ],
    },
  ];

  const handleUserMenuClick = ({ key }: { key: string }) => {
    if (key === 'logout') {
      logout();
      navigate('/admin/login');
    }
  };

  const userMenuItems = [
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
    },
  ];

  return (
    <Layout style={{ height: '100vh' }}>
      <Header style={{ 
        background: '#fff', 
        padding: '0 24px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1)',
        borderBottom: '1px solid #e5e7eb'
      }}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          <h1 style={{ 
            margin: 0, 
            color: '#722ed1',
            fontSize: '20px',
            fontWeight: 700,
          }}>
            Resume-Robot 管理后台
          </h1>
        </div>
        
        <Dropdown menu={{ items: userMenuItems, onClick: handleUserMenuClick }} placement="bottomRight">
          <Button type="text" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Avatar size="small" icon={<UserOutlined />} />
            <span>{user?.full_name || user?.email}</span>
          </Button>
        </Dropdown>
      </Header>

      <Layout>
        <Sider 
          width={200} 
          style={{ 
            background: '#fff',
            boxShadow: '1px 0 3px 0 rgba(0, 0, 0, 0.1)',
            borderRight: '1px solid #e5e7eb'
          }}
        >
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            items={menuItems}
            onClick={({ key }) => navigate(key)}
            style={{ 
              height: '100%', 
              borderRight: 0,
              paddingTop: '8px'
            }}
          />
        </Sider>

        <Layout style={{ padding: '24px', background: '#f9fafb' }}>
          <Content style={{
            background: '#fff',
            padding: '24px',
            margin: 0,
            borderRadius: '8px',
            boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1)',
            overflow: 'auto',
            minHeight: 'calc(100vh - 112px)'
          }}>
            {children}
          </Content>
        </Layout>
      </Layout>
    </Layout>
  );
};

export default AppLayout;

