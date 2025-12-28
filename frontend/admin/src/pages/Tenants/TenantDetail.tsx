import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Descriptions,
  Button,
  Space,
  message,
  Tag,
  Statistic,
  Row,
  Col,
} from 'antd';
import {
  ArrowLeftOutlined,
  EditOutlined,
} from '@ant-design/icons';
import { tenantApi, Tenant } from '@/services/tenantApi';

const TenantDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [stats, setStats] = useState<any>(null);

  // 加载租户详情
  const loadTenant = async () => {
    if (!id) return;
    setLoading(true);
    try {
      const tenantData = await tenantApi.getTenant(Number(id));
      setTenant(tenantData);
      
      // 加载统计信息
      try {
        const statsResponse = await fetch(`/api/v1/admin/tenants/${id}/stats`, {
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('admin_access_token')}`,
          },
        });
        if (statsResponse.ok) {
          const statsData = await statsResponse.json();
          setStats(statsData);
        }
      } catch (error) {
        console.error('加载统计信息失败:', error);
      }
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载租户详情失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTenant();
  }, [id]);

  if (loading) {
    return <Card>加载中...</Card>;
  }

  if (!tenant) {
    return <Card>租户不存在</Card>;
  }

  return (
    <div>
      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/admin/tenants')}>
            返回列表
          </Button>
          <Button
            type="primary"
            icon={<EditOutlined />}
            onClick={() => navigate(`/admin/tenants/${id}/edit`)}
          >
            编辑
          </Button>
        </Space>

        <Descriptions title="租户基本信息" bordered column={2} style={{ marginBottom: 24 }}>
          <Descriptions.Item label="ID">{tenant.id}</Descriptions.Item>
          <Descriptions.Item label="租户名称">{tenant.name}</Descriptions.Item>
          <Descriptions.Item label="域名">{tenant.domain || 'N/A'}</Descriptions.Item>
          <Descriptions.Item label="联系人邮箱">{tenant.contact_email || 'N/A'}</Descriptions.Item>
          <Descriptions.Item label="联系人电话">{tenant.contact_phone || 'N/A'}</Descriptions.Item>
          <Descriptions.Item label="订阅套餐">
            <Tag color={
              tenant.subscription_plan === 'trial' ? 'default' :
              tenant.subscription_plan === 'basic' ? 'blue' :
              tenant.subscription_plan === 'professional' ? 'green' : 'red'
            }>
              {tenant.subscription_plan === 'trial' ? '试用版' :
               tenant.subscription_plan === 'basic' ? '基础版' :
               tenant.subscription_plan === 'professional' ? '专业版' : '企业版'}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={
              tenant.status === 'active' ? 'green' :
              tenant.status === 'suspended' ? 'orange' : 'red'
            }>
              {tenant.status === 'active' ? '活跃' :
               tenant.status === 'suspended' ? '已暂停' : '已过期'}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="订阅开始时间">
            {tenant.subscription_start ? new Date(tenant.subscription_start).toLocaleString('zh-CN') : 'N/A'}
          </Descriptions.Item>
          <Descriptions.Item label="订阅结束时间">
            {tenant.subscription_end ? new Date(tenant.subscription_end).toLocaleString('zh-CN') : 'N/A'}
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {new Date(tenant.created_at).toLocaleString('zh-CN')}
          </Descriptions.Item>
          <Descriptions.Item label="更新时间">
            {new Date(tenant.updated_at).toLocaleString('zh-CN')}
          </Descriptions.Item>
        </Descriptions>

        <Descriptions title="使用限制" bordered column={2} style={{ marginBottom: 24 }}>
          <Descriptions.Item label="最大用户数">{tenant.max_users}</Descriptions.Item>
          <Descriptions.Item label="最大岗位数">{tenant.max_jobs}</Descriptions.Item>
          <Descriptions.Item label="每月最大简历处理数">{tenant.max_resumes_per_month}</Descriptions.Item>
          <Descriptions.Item label="当前月已处理简历数">{tenant.current_month_resume_count}</Descriptions.Item>
        </Descriptions>

        {stats && (
          <Card title="数据统计" style={{ marginTop: 24 }}>
            <Row gutter={16}>
              <Col span={6}>
                <Statistic title="用户数" value={stats.stats?.users || 0} />
              </Col>
              <Col span={6}>
                <Statistic title="岗位数" value={stats.stats?.jobs || 0} />
              </Col>
              <Col span={6}>
                <Statistic title="简历数" value={stats.stats?.resumes || 0} />
              </Col>
              <Col span={6}>
                <Statistic title="匹配数" value={stats.stats?.matches || 0} />
              </Col>
            </Row>
          </Card>
        )}
      </Card>
    </div>
  );
};

export default TenantDetail;
