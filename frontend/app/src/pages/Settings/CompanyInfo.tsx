/**
 * 公司信息设置页面
 */
import React, { useState, useEffect } from 'react';
import { Card, Form, Input, Button, message, Space } from 'antd';
import { jobApi } from '@/services/jobApi';
import { CompanyInfo } from '@/types/job';

const { TextArea } = Input;

const CompanyInfoPage: React.FC = () => {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [loadingData, setLoadingData] = useState(false);
  const [companyInfo, setCompanyInfo] = useState<CompanyInfo | null>(null);

  // 加载公司信息
  useEffect(() => {
    const fetchCompanyInfo = async () => {
      setLoadingData(true);
      try {
        const response = await jobApi.getCompanyInfo();
        if (response.success && response.data) {
          setCompanyInfo(response.data);
          form.setFieldsValue({
            name: response.data.name,
            industry: response.data.industry,
            products: response.data.products,
            application_scenarios: response.data.application_scenarios,
            company_culture: response.data.company_culture,
            preferences: response.data.preferences,
            company_size: response.data.company_size,
            development_stage: response.data.development_stage,
            business_model: response.data.business_model,
            core_values: response.data.core_values,
            recruitment_philosophy: response.data.recruitment_philosophy,
          });
        }
      } catch (error: any) {
        console.error('加载公司信息失败:', error);
      } finally {
        setLoadingData(false);
      }
    };
    fetchCompanyInfo();
  }, [form]);

  // 提交表单
  const handleSubmit = async (values: any) => {
    setLoading(true);
    try {
      if (companyInfo) {
        // 更新
        await jobApi.updateCompanyInfo(companyInfo.id, values);
        message.success('更新成功');
      } else {
        // 创建
        await jobApi.createOrUpdateCompanyInfo(values);
        message.success('创建成功');
      }
      // 重新加载数据
      const response = await jobApi.getCompanyInfo();
      if (response.success && response.data) {
        setCompanyInfo(response.data);
      }
    } catch (error: any) {
      message.error('保存失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card
      title="公司信息配置"
      loading={loadingData}
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        style={{ maxWidth: 800 }}
      >
        <Form.Item
          name="name"
          label="公司名称"
          rules={[{ required: true, message: '请输入公司名称' }]}
        >
          <Input placeholder="请输入公司名称" />
        </Form.Item>

        <Form.Item
          name="industry"
          label="所属行业"
        >
          <Input placeholder="例如：互联网、金融、制造业等" />
        </Form.Item>

        <Form.Item
          name="products"
          label="主要产品/服务"
        >
          <TextArea
            rows={3}
            placeholder="请描述公司的主要产品和服务"
          />
        </Form.Item>

        <Form.Item
          name="application_scenarios"
          label="应用场景"
        >
          <TextArea
            rows={3}
            placeholder="请描述产品的应用场景"
          />
        </Form.Item>

        <Form.Item
          name="company_culture"
          label="公司文化"
        >
          <TextArea
            rows={3}
            placeholder="请描述公司文化，用于LLM Prompt增强"
          />
        </Form.Item>

        <Form.Item
          name="preferences"
          label="招聘偏好"
        >
          <TextArea
            rows={2}
            placeholder="例如：注重可靠性、创新性、团队合作等"
          />
        </Form.Item>

        {/* 新增字段 */}
        <Form.Item
          name="company_size"
          label="公司规模"
        >
          <Input placeholder="例如：100-500人、500-1000人等" />
        </Form.Item>

        <Form.Item
          name="development_stage"
          label="发展阶段"
        >
          <Input placeholder="例如：初创期、成长期、成熟期" />
        </Form.Item>

        <Form.Item
          name="business_model"
          label="商业模式"
        >
          <TextArea
            rows={2}
            placeholder="请描述公司的商业模式"
          />
        </Form.Item>

        <Form.Item
          name="core_values"
          label="核心价值观"
        >
          <TextArea
            rows={3}
            placeholder="请描述公司的核心价值观，用于LLM Prompt增强"
          />
        </Form.Item>

        <Form.Item
          name="recruitment_philosophy"
          label="招聘理念"
        >
          <TextArea
            rows={3}
            placeholder="请描述公司的招聘理念，用于LLM Prompt增强"
          />
        </Form.Item>

        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={loading}>
              保存
            </Button>
            <Button onClick={() => form.resetFields()}>
              重置
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </Card>
  );
};

export default CompanyInfoPage;
