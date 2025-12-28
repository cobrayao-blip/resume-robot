import React, { useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ConfigProvider, App as AntdApp } from 'antd';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from './stores/authStore';
import Layout from './components/common/Layout';
import Login from './components/auth/Login';
import Dashboard from './pages/Dashboard';
import TalentPool from './pages/ResumeManagement/TalentPool';
import JobResumePool from './pages/ResumeManagement/JobResumePool';
import FilterBox from './pages/ResumeManagement/FilterBox';
import JobList from './pages/JobManagement/JobList';
import JobDetail from './pages/JobManagement/JobDetail';
import JobCreate from './pages/JobManagement/JobCreate';
import MatchList from './pages/Matching/MatchList';
import MatchDetail from './pages/Matching/MatchDetail';
import ReportList from './pages/Reports/ReportList';
import ReportGenerate from './pages/Reports/ReportGenerate';
import CompanyInfo from './pages/Settings/CompanyInfo';
import FilterRulesSimple from './pages/Settings/FilterRulesSimple';
import UserManagement from './pages/Settings/UserManagement';
import Subscription from './pages/Settings/Subscription';
import ChangePassword from './pages/Settings/ChangePassword';
import DepartmentList from './pages/Organization/DepartmentList';
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
            colorPrimary: '#2563eb',
            colorSuccess: '#10b981',
            colorWarning: '#f59e0b',
            colorError: '#ef4444',
            colorInfo: '#3b82f6',
            fontFamily: "'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif",
            fontSize: 14,
            borderRadius: 6,
            boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
          },
          components: {
            Card: {
              borderRadius: 8,
              boxShadow: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
            },
            Table: {
              headerBg: '#f9fafb',
              headerColor: '#111827',
              borderColor: '#e5e7eb',
            },
            Button: {
              borderRadius: 6,
            },
            Input: {
              borderRadius: 6,
            },
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
                    path="/login" 
                    element={!isAuthenticated ? <Login /> : <Navigate to="/dashboard" replace />} 
                  />
                  <Route 
                    path="/*" 
                    element={isAuthenticated ? <AuthenticatedApp /> : <Navigate to="/login" replace />} 
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
  const { user } = useAuthStore();
  // 检查是否为租户管理员：role 或 user_type 为 tenant_admin
  const isTenantAdmin = user?.role === 'tenant_admin' || user?.user_type === 'tenant_admin';

  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<Dashboard />} />
        
        {/* 简历管理 */}
        <Route path="/resumes/talent-pool" element={<TalentPool />} />
        <Route path="/resumes/job-pool/:jobId" element={<JobResumePool />} />
        <Route path="/resumes/filter-box" element={<FilterBox />} />
        
        {/* 组织架构管理 */}
        {isTenantAdmin && (
          <Route path="/organization/departments" element={<DepartmentList />} />
        )}
        
        {/* 岗位管理 */}
        <Route path="/jobs" element={<JobList />} />
        <Route path="/jobs/create" element={<JobCreate />} />
        <Route path="/jobs/:id" element={<JobDetail />} />
        
        {/* 匹配结果 */}
        <Route path="/matching" element={<MatchList />} />
        <Route path="/matching/:id" element={<MatchDetail />} />
        
        {/* 推荐报告 */}
        <Route path="/reports" element={<ReportList />} />
        <Route path="/reports/generate" element={<ReportGenerate />} />
        
        {/* 系统设置 */}
        <Route path="/settings/filter-rules" element={<FilterRulesSimple />} />
        <Route path="/settings/change-password" element={<ChangePassword />} />
        {isTenantAdmin && (
          <>
            <Route path="/settings/company-info" element={<CompanyInfo />} />
            <Route path="/settings/users" element={<UserManagement />} />
            <Route path="/settings/subscription" element={<Subscription />} />
          </>
        )}
        
        {/* 默认路由 */}
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Layout>
  );
}

export default App;

