import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  message,
  Select,
  Steps,
  Form,
  Checkbox,
} from 'antd';
import {
  CheckOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import { jobApi } from '@/services/jobApi';
import { reportApi } from '@/services/reportApi';
import api from '@/services/api';
import { ResumeJobMatch } from '@/types/job';

const { Option } = Select;
const { Step } = Steps;

interface Template {
  id: number;
  name: string;
  description?: string;
}

const ReportGenerate: React.FC = () => {
  const [currentStep, setCurrentStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [matches, setMatches] = useState<ResumeJobMatch[]>([]);
  const [selectedMatchIds, setSelectedMatchIds] = useState<number[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | undefined>();
  const [generating, setGenerating] = useState(false);
  const [form] = Form.useForm();

  // 加载匹配结果列表
  const loadMatches = async () => {
    setLoading(true);
    try {
      const response = await jobApi.getMatchResults({
        page: 1,
        pageSize: 100, // 加载更多匹配结果
        match_label: undefined, // 可以筛选匹配标签
        status: undefined,
      });
      setMatches(response.items || []);
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载匹配结果失败');
    } finally {
      setLoading(false);
    }
  };

  // 加载模板列表
  const loadTemplates = async () => {
    try {
      const response = await api.get('/templates');
      setTemplates(response.data || []);
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载模板列表失败');
    }
  };

  useEffect(() => {
    loadMatches();
    loadTemplates();
  }, []);

  // 选择匹配结果
  const handleSelectMatches = (matchIds: number[]) => {
    setSelectedMatchIds(matchIds);
  };

  // 下一步
  const handleNext = () => {
    if (currentStep === 0) {
      if (selectedMatchIds.length === 0) {
        message.warning('请至少选择一个匹配结果');
        return;
      }
      setCurrentStep(1);
    } else if (currentStep === 1) {
      if (!selectedTemplateId) {
        message.warning('请选择一个模板');
        return;
      }
      handleGenerate();
    }
  };

  // 上一步
  const handlePrev = () => {
    setCurrentStep(currentStep - 1);
  };

  // 生成报告
  const handleGenerate = async () => {
    if (!selectedTemplateId) {
      message.warning('请选择一个模板');
      return;
    }

    setGenerating(true);
    try {
      const result = await reportApi.generateReports({
        match_ids: selectedMatchIds,
        template_id: selectedTemplateId,
      });
      message.success(result.message || '报告生成成功');
      setCurrentStep(2);
    } catch (error: any) {
      message.error(error.response?.data?.detail || '生成报告失败');
    } finally {
      setGenerating(false);
    }
  };

  const matchColumns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: '简历ID',
      dataIndex: 'resume_id',
      key: 'resume_id',
      width: 100,
    },
    {
      title: '岗位ID',
      dataIndex: 'job_id',
      key: 'job_id',
      width: 100,
    },
    {
      title: '匹配度',
      dataIndex: 'match_score',
      key: 'match_score',
      width: 120,
      render: (score: number) => (
        <span style={{ fontWeight: 'bold', color: score >= 85 ? 'red' : score >= 70 ? 'orange' : 'blue' }}>
          {score.toFixed(1)}分
        </span>
      ),
    },
    {
      title: '匹配标签',
      dataIndex: 'match_label',
      key: 'match_label',
      width: 120,
      render: (label: string) => {
        const colorMap: Record<string, string> = {
          '强烈推荐': 'red',
          '推荐': 'orange',
          '谨慎推荐': 'blue',
          '不推荐': 'default',
        };
        return <span style={{ color: colorMap[label] || 'default' }}>{label || '未匹配'}</span>;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
    },
  ];

  return (
    <div>
      <Card>
        <Steps current={currentStep} style={{ marginBottom: 32 }}>
          <Step title="选择匹配结果" icon={<FileTextOutlined />} />
          <Step title="选择模板" icon={<FileTextOutlined />} />
          <Step title="完成" icon={<CheckOutlined />} />
        </Steps>

        {currentStep === 0 && (
          <div>
            <div style={{ marginBottom: 16 }}>
              <Button
                type="primary"
                onClick={handleNext}
                disabled={selectedMatchIds.length === 0}
              >
                下一步：选择模板 ({selectedMatchIds.length} 个已选择)
              </Button>
            </div>
            <Table
              columns={matchColumns}
              dataSource={matches}
              rowKey="id"
              loading={loading}
              rowSelection={{
                selectedRowKeys: selectedMatchIds,
                onChange: (selectedRowKeys) => {
                  handleSelectMatches(selectedRowKeys as number[]);
                },
              }}
              pagination={{
                pageSize: 20,
                showSizeChanger: true,
                showTotal: (total) => `共 ${total} 条`,
              }}
            />
          </div>
        )}

        {currentStep === 1 && (
          <div>
            <Form form={form} layout="vertical">
              <Form.Item
                label="选择模板"
                required
                rules={[{ required: true, message: '请选择一个模板' }]}
              >
                <Select
                  placeholder="请选择报告模板"
                  style={{ width: '100%' }}
                  value={selectedTemplateId}
                  onChange={(value) => setSelectedTemplateId(value)}
                >
                  {templates.map((template) => (
                    <Option key={template.id} value={template.id}>
                      {template.name}
                      {template.description && ` - ${template.description}`}
                    </Option>
                  ))}
                </Select>
              </Form.Item>
            </Form>
            <Space style={{ marginTop: 24 }}>
              <Button onClick={handlePrev}>上一步</Button>
              <Button
                type="primary"
                onClick={handleGenerate}
                loading={generating}
                disabled={!selectedTemplateId}
              >
                生成报告
              </Button>
            </Space>
          </div>
        )}

        {currentStep === 2 && (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <CheckOutlined style={{ fontSize: 48, color: '#52c41a', marginBottom: 16 }} />
            <h2>报告生成成功！</h2>
            <p>已为 {selectedMatchIds.length} 个匹配结果生成推荐报告</p>
            <Space style={{ marginTop: 24 }}>
              <Button type="primary" onClick={() => window.location.href = '/reports'}>
                查看报告列表
              </Button>
              <Button onClick={() => {
                setCurrentStep(0);
                setSelectedMatchIds([]);
                setSelectedTemplateId(undefined);
              }}>
                继续生成
              </Button>
            </Space>
          </div>
        )}
      </Card>
    </div>
  );
};

export default ReportGenerate;
