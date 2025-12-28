import React from 'react';
import { Layout, Menu, Button, Dropdown, Avatar } from 'antd';
import { 
  DashboardOutlined,
  FileTextOutlined,
  FolderOutlined,
  UsergroupAddOutlined,
  UserOutlined,
  LogoutOutlined,
  SettingOutlined,
  FilterOutlined,
  FileSearchOutlined,
  ApartmentOutlined,
  LockOutlined,
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
  // 检查是否为租户管理员：role 或 user_type 为 tenant_admin
  const isTenantAdmin = user?.role === 'tenant_admin' || user?.user_type === 'tenant_admin';

  const menuItems = [
    {
      key: '/dashboard',
      icon: <DashboardOutlined />,
      label: '控制台',
    },
    {
      key: '/resumes',
      icon: <FileTextOutlined />,
      label: '简历管理',
      children: [
        {
          key: '/resumes/talent-pool',
          label: '简历总库',
        },
        {
          key: '/resumes/filter-box',
          label: '过滤箱',
        },
      ],
    },
    ...(isTenantAdmin ? [
      {
        key: '/organization',
        icon: <ApartmentOutlined />,
        label: '组织架构',
        children: [
          {
            key: '/organization/departments',
            label: '部门管理',
          },
        ],
      },
    ] : []),
    {
      key: '/jobs',
      icon: <FolderOutlined />,
      label: '岗位管理',
    },
    {
      key: '/matching',
      icon: <UsergroupAddOutlined />,
      label: '匹配结果',
    },
    {
      key: '/reports',
      icon: <FileSearchOutlined />,
      label: '推荐报告',
    },
    {
      type: 'divider' as const,
    },
    {
      key: '/settings',
      icon: <SettingOutlined />,
      label: '系统设置',
      children: [
        {
          key: '/settings/filter-rules',
          label: '筛选规则',
        },
        ...(isTenantAdmin ? [
          {
            key: '/settings/company-info',
            label: '公司信息',
          },
          {
            key: '/settings/users',
            label: '用户管理',
          },
          {
            key: '/settings/subscription',
            label: '订阅管理',
          },
        ] : []),
      ],
    },
  ];

  const handleUserMenuClick = ({ key }: { key: string }) => {
    if (key === 'profile') {
      // TODO: 跳转到个人资料
    } else if (key === 'change-password') {
      navigate('/settings/change-password');
    } else if (key === 'settings') {
      navigate('/settings/company-info');
    } else if (key === 'logout') {
      logout();
      navigate('/login');
    }
  };

  const userMenuItems = [
    {
      key: 'profile',
      icon: <UserOutlined />,
      label: '个人资料',
    },
    {
      key: 'change-password',
      icon: <LockOutlined />,
      label: '修改密码',
    },
    ...(isTenantAdmin ? [
      {
        key: 'settings',
        icon: <SettingOutlined />,
        label: '系统设置',
      },
    ] : []),
    {
      type: 'divider' as const,
    },
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
            color: '#2563eb',
            fontSize: '20px',
            fontWeight: 700,
          }}>
            Resume-Robot HR工作台
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

