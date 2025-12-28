import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Form, Input, Button, message, Space, Select } from 'antd';
import { jobApi } from '@/services/jobApi';
import { organizationApi } from '@/services/organizationApi';

const { TextArea } = Input;
const { Option } = Select;

interface Department {
  id: number;
  name: string;
  path?: string;
}

const JobCreate: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loadingDepartments, setLoadingDepartments] = useState(false);

  // 获取部门列表
  useEffect(() => {
    const fetchDepartments = async () => {
      setLoadingDepartments(true);
      try {
        const data = await organizationApi.getDepartments(false);
        setDepartments(data);
      } catch (error) {
        console.error('获取部门列表失败:', error);
      } finally {
        setLoadingDepartments(false);
      }
    };
    fetchDepartments();
  }, []);

  const handleSubmit = async (values: any) => {
    setLoading(true);
    try {
      // 准备提交数据
      const submitData: any = {
        title: values.title,
        description: values.description || undefined,
        requirements: values.requirements || undefined,
        status: 'draft',  // 默认状态为草稿
      };
      
      // 如果选择了部门ID，优先使用部门ID
      if (values.department_id) {
        submitData.department_id = values.department_id;
      } else if (values.department) {
        // 如果没有选择部门ID，使用部门名称（兼容字段）
        submitData.department = values.department;
      }
      
      console.log('提交岗位数据:', submitData);
      const response = await jobApi.createPosition(submitData);
      console.log('岗位创建响应:', response);
      message.success('岗位创建成功');
      // 延迟跳转，确保消息显示
      setTimeout(() => {
        navigate('/jobs');
      }, 500);
    } catch (error: any) {
      console.error('创建岗位失败:', error);
      const errorMsg = error.response?.data?.detail || error.message || '创建失败';
      message.error('创建失败: ' + errorMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="创建岗位">
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
          name="department_id"
          label="部门"
          tooltip="选择部门后，岗位将关联到该部门，用于组织架构管理和Prompt增强"
        >
          <Select
            placeholder="请选择部门"
            allowClear
            showSearch
            loading={loadingDepartments}
            filterOption={(input, option) =>
              (option?.children as unknown as string)?.toLowerCase().includes(input.toLowerCase())
            }
          >
            {departments.map(dept => (
              <Option key={dept.id} value={dept.id}>
                {dept.path || dept.name}
              </Option>
            ))}
          </Select>
        </Form.Item>

        <Form.Item
          name="department"
          label="部门名称（兼容字段）"
          tooltip="如果未选择部门，可以手动输入部门名称（建议使用上面的部门选择）"
        >
          <Input placeholder="例如：技术部（可选）" />
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

        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={loading}>
              创建
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

export default JobCreate;

