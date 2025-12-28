import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Button,
  Space,
  message,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  Switch,
  Tag,
  Popconfirm,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';
import { jobApi } from '@/services/jobApi';
import { FilterRule } from '@/types/job';

const { Option } = Select;
const { TextArea } = Input;

const FilterRules: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [rules, setRules] = useState<FilterRule[]>([]);
  const [form] = Form.useForm();
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRule, setEditingRule] = useState<FilterRule | null>(null);

  // 加载筛选规则列表
  const loadRules = async () => {
    setLoading(true);
    try {
      const data = await jobApi.getFilterRules({});
      setRules(data || []);
    } catch (error: any) {
      message.error(error.response?.data?.detail || '加载筛选规则失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRules();
  }, []);

  // 创建/更新规则
  const handleSubmit = async (values: any) => {
    try {
      if (editingRule) {
        await jobApi.updateFilterRule(editingRule.id, values);
        message.success('更新成功');
      } else {
        await jobApi.createFilterRule(values);
        message.success('创建成功');
      }
      setModalVisible(false);
      form.resetFields();
      setEditingRule(null);
      loadRules();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '保存失败');
    }
  };

  // 编辑规则
  const handleEdit = (rule: FilterRule) => {
    setEditingRule(rule);
    // 将rule_config转换为JSON字符串以便在TextArea中编辑
    const formValues = {
      ...rule,
      rule_config: typeof rule.rule_config === 'string' 
        ? rule.rule_config 
        : JSON.stringify(rule.rule_config, null, 2),
    };
    form.setFieldsValue(formValues);
    setModalVisible(true);
  };

  // 删除规则
  const handleDelete = async (id: number) => {
    try {
      await jobApi.deleteFilterRule(id);
      message.success('删除成功');
      loadRules();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '删除失败');
    }
  };

  // 启用/禁用规则
  const handleToggleActive = async (rule: FilterRule) => {
    try {
      await jobApi.updateFilterRule(rule.id, { is_active: !rule.is_active });
      message.success(rule.is_active ? '已禁用' : '已启用');
      loadRules();
    } catch (error: any) {
      message.error(error.response?.data?.detail || '操作失败');
    }
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: '规则名称',
      dataIndex: 'name',
      key: 'name',
      width: 150,
    },
    {
      title: '规则类型',
      dataIndex: 'rule_type',
      key: 'rule_type',
      width: 120,
      render: (type: string) => {
        const typeMap: Record<string, { color: string; text: string }> = {
          'education': { color: 'blue', text: '学历要求' },
          'experience': { color: 'green', text: '工作经验' },
          'age': { color: 'orange', text: '年龄限制' },
          'skill': { color: 'purple', text: '技能要求' },
          'custom': { color: 'default', text: '自定义' },
        };
        const typeInfo = typeMap[type] || { color: 'default', text: type };
        return <Tag color={typeInfo.color}>{typeInfo.text}</Tag>;
      },
    },
    {
      title: '规则配置',
      dataIndex: 'rule_config',
      key: 'rule_config',
      ellipsis: true,
      render: (config: any) => {
        if (typeof config === 'string') {
          return config;
        }
        return JSON.stringify(config);
      },
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 100,
      render: (isActive: boolean) => (
        <Tag color={isActive ? 'green' : 'default'}>
          {isActive ? '启用' : '禁用'}
        </Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (time: string) => new Date(time).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      width: 220,
      fixed: 'right' as const,
      render: (_: any, record: FilterRule) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Button
            type="link"
            size="small"
            icon={record.is_active ? <CloseCircleOutlined /> : <CheckCircleOutlined />}
            onClick={() => handleToggleActive(record)}
          >
            {record.is_active ? '禁用' : '启用'}
          </Button>
          <Popconfirm
            title="确定要删除这条规则吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button
              type="link"
              size="small"
              danger
              icon={<DeleteOutlined />}
            >
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card>
        <Space style={{ marginBottom: 16, width: '100%', justifyContent: 'space-between' }}>
          <h2 style={{ margin: 0 }}>筛选规则管理</h2>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => {
              setEditingRule(null);
              form.resetFields();
              setModalVisible(true);
            }}
          >
            创建规则
          </Button>
        </Space>

        <Table
          columns={columns}
          dataSource={rules}
          rowKey="id"
          loading={loading}
          pagination={false}
          scroll={{ x: 1200 }}
        />
      </Card>

      {/* 创建/编辑规则对话框 */}
      <Modal
        title={editingRule ? '编辑筛选规则' : '创建筛选规则'}
        open={modalVisible}
        onOk={() => form.submit()}
        onCancel={() => {
          setModalVisible(false);
          form.resetFields();
          setEditingRule(null);
        }}
        width={600}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
        >
          <Form.Item
            name="name"
            label="规则名称"
            rules={[{ required: true, message: '请输入规则名称' }]}
          >
            <Input placeholder="例如：本科及以上学历" />
          </Form.Item>

          <Form.Item
            name="rule_type"
            label="规则类型"
            rules={[{ required: true, message: '请选择规则类型' }]}
          >
            <Select placeholder="请选择规则类型">
              <Option value="education">学历要求</Option>
              <Option value="experience">工作经验</Option>
              <Option value="age">年龄限制</Option>
              <Option value="skill">技能要求</Option>
              <Option value="custom">自定义</Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="rule_config"
            label="规则配置（JSON格式）"
            rules={[{ required: true, message: '请输入规则配置' }]}
            tooltip='规则配置的JSON格式，例如：{"field": "education.degree", "operator": ">=", "value": "本科"}'
          >
            <TextArea
              rows={4}
              placeholder='例如：{"field": "education.degree", "operator": ">=", "value": "本科"}'
            />
          </Form.Item>

          <Form.Item
            name="logic_operator"
            label="逻辑运算符"
            initialValue="AND"
          >
            <Select>
              <Option value="AND">AND（且）</Option>
              <Option value="OR">OR（或）</Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="priority"
            label="优先级"
            initialValue={0}
          >
            <InputNumber min={0} max={100} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            name="description"
            label="规则描述"
          >
            <TextArea rows={2} placeholder="请输入规则描述" />
          </Form.Item>

          <Form.Item
            name="is_active"
            label="启用状态"
            valuePropName="checked"
            initialValue={true}
          >
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default FilterRules;
