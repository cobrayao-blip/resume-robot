import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Form, Input, Button, message, Space } from 'antd';
import { jobApi } from '@/services/jobApi';
import { JobPosition } from '@/types/job';

const { TextArea } = Input;

const JobDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [job, setJob] = useState<JobPosition | null>(null);

  useEffect(() => {
    if (id) {
      loadJob();
    }
  }, [id]);

  const loadJob = async () => {
    setLoading(true);
    try {
      const response = await jobApi.getPosition(parseInt(id!));
      if (response.success) {
        setJob(response.data);
        form.setFieldsValue(response.data);
      }
    } catch (error: any) {
      message.error('加载岗位失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (values: any) => {
    if (!id) return;
    setLoading(true);
    try {
      await jobApi.updatePosition(parseInt(id), values);
      message.success('岗位更新成功');
      navigate('/jobs');
    } catch (error: any) {
      message.error('更新失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="编辑岗位" loading={loading}>
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        style={{ maxWidth: 800 }}
      >
        <Form.Item
          name="title"
          label="岗位名称"
          rules={[{ required: true, message: '请输入岗位名称' }]}
        >
          <Input placeholder="例如：高级Python开发工程师" />
        </Form.Item>

        <Form.Item
          name="department"
          label="部门"
        >
          <Input placeholder="例如：技术部" />
        </Form.Item>

        <Form.Item
          name="description"
          label="岗位描述"
        >
          <TextArea
            rows={4}
            placeholder="请输入岗位描述..."
          />
        </Form.Item>

        <Form.Item
          name="requirements"
          label="岗位要求"
        >
          <TextArea
            rows={6}
            placeholder="请输入岗位要求，包括学历、经验、技能等..."
          />
        </Form.Item>

        <Form.Item
          name="status"
          label="状态"
        >
          <Input disabled />
        </Form.Item>

        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={loading}>
              保存
            </Button>
            <Button onClick={() => navigate('/jobs')}>
              取消
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </Card>
  );
};

export default JobDetail;


