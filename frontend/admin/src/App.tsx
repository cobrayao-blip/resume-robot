import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, App as AntdApp } from 'antd';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from './stores/authStore';
import Layout from './components/common/Layout';
import Login from './components/auth/Login';
import Dashboard from './pages/Dashboard';
import TenantList from './pages/Tenants/TenantList';
import TenantDetail from './pages/Tenants/TenantDetail';
import TenantCreate from './pages/Tenants/TenantCreate';
import PlanList from './pages/Subscriptions/PlanList';
import SubscriptionList from './pages/Subscriptions/SubscriptionList';
import LLMConfig from './pages/System/LLMConfig';
import SystemParams from './pages/System/SystemParams';
import FeatureFlags from './pages/System/FeatureFlags';
import Overview from './pages/Statistics/Overview';
import TenantStats from './pages/Statistics/TenantStats';
import Revenue from './pages/Statistics/Revenue';
import './App.css';

const queryClient = new QueryClient();

function App() {
  const { checkAuth, isAuthenticated, isLoading } = useAuthStore();
  const [authChecked, setAuthChecked] = React.useState(false);

  useEffect(() => {
    const initAuth = async () => {
      try {
        await checkAuth();
      } catch (error) {
        console.error('Auth check failed:', error);
      } finally {
        setAuthChecked(true);
        useAuthStore.setState({ isLoading: false });
      }
    };
    if (!authChecked) {
      initAuth();
    }
  }, []);

  return (
    <QueryClientProvider client={queryClient}>
      <ConfigProvider
        theme={{
          token: {
            colorPrimary: '#722ed1',
            colorSuccess: '#10b981',
            colorWarning: '#f59e0b',
            colorError: '#ef4444',
            colorInfo: '#3b82f6',
            fontFamily: "'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif",
            fontSize: 14,
            borderRadius: 6,
          },
        }}
      >
        <AntdApp>
          <Router
            future={{
              v7_startTransition: true,
              v7_relativeSplatPath: true,
            }}
          >
            <div className="App">
              {!authChecked || isLoading ? (
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'center', 
                  alignItems: 'center', 
                  height: '100vh' 
                }}>
                  加载中...
                </div>
              ) : (
                <Routes>
                  <Route 
                    path="/admin/login" 
                    element={!isAuthenticated ? <Login /> : <Navigate to="/admin/dashboard" />} 
                  />
                  <Route 
                    path="/*" 
                    element={isAuthenticated ? <AuthenticatedApp /> : <Navigate to="/admin/login" />} 
                  />
                </Routes>
              )}
            </div>
          </Router>
        </AntdApp>
      </ConfigProvider>
    </QueryClientProvider>
  );
}

function AuthenticatedApp() {
  return (
    <Layout>
      <Routes>
        <Route path="/admin" element={<Navigate to="/admin/dashboard" replace />} />
        <Route path="/admin/dashboard" element={<Dashboard />} />
        
        {/* 租户管理 */}
        <Route path="/admin/tenants" element={<TenantList />} />
        <Route path="/admin/tenants/create" element={<TenantCreate />} />
        <Route path="/admin/tenants/:id" element={<TenantDetail />} />
        <Route path="/admin/tenants/:id/edit" element={<TenantList />} />
        
        {/* 订阅管理 */}
        <Route path="/admin/subscriptions/plans" element={<PlanList />} />
        <Route path="/admin/subscriptions" element={<SubscriptionList />} />
        
        {/* 系统配置 */}
        <Route path="/admin/system/llm" element={<LLMConfig />} />
        <Route path="/admin/system/params" element={<SystemParams />} />
        <Route path="/admin/system/features" element={<FeatureFlags />} />
        
        {/* 数据统计 */}
        <Route path="/admin/statistics/overview" element={<Overview />} />
        <Route path="/admin/statistics/tenants" element={<TenantStats />} />
        <Route path="/admin/statistics/revenue" element={<Revenue />} />
        
        <Route path="*" element={<Navigate to="/admin/dashboard" replace />} />
      </Routes>
    </Layout>
  );
}

export default App;

