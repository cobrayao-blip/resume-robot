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
  Select,
  Switch,
  Popconfirm,
  Tag,
  InputNumber,
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

const FilterRulesSimple: React.FC = () => {
  const [form] = Form.useForm();
  const [rules, setRules] = useState<FilterRule[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRule, setEditingRule] = useState<FilterRule | null>(null);
  const [ruleType, setRuleType] = useState<string>('education');

  useEffect(() => {
    loadRules();
  }, []);

  const loadRules = async () => {
    setLoading(true);
    try {
      const data = await jobApi.getFilterRules();
      setRules(data);
    } catch (error: any) {
      message.error(error.message || '加载筛选规则失败');
    } finally {
      setLoading(false);
    }
  };

  // 根据规则类型构建rule_config
  const buildRuleConfig = (values: any, ruleType: string): Record<string, any> => {
    switch (ruleType) {
      case 'education':
        return {
          degree: values.degree,
          operator: values.operator || '>=',
        };
      case 'experience':
        return {
          years: values.years || 0,
          operator: values.operator || '>=',
        };
      case 'age':
        return {
          min_age: values.min_age,
          max_age: values.max_age,
        };
      case 'skill':
        return {
          skills: Array.isArray(values.skills) ? values.skills : (values.skills ? values.skills.split(',').map((s: string) => s.trim()) : []),
          match_type: values.match_type || 'any',
        };
      default:
        return {};
    }
  };

  const handleSubmit = async (values: any) => {
    setLoading(true);
    try {
      const ruleConfig = buildRuleConfig(values, ruleType);
      const payload = {
        ...values,
        rule_type: ruleType,
        rule_config: ruleConfig,
      };

      if (editingRule) {
        await jobApi.updateFilterRule(editingRule.id, payload);
        message.success('筛选规则更新成功');
      } else {
        await jobApi.createFilterRule(payload);
        message.success('筛选规则创建成功');
      }
      setModalVisible(false);
      form.resetFields();
      setEditingRule(null);
      setRuleType('education');
      loadRules();
    } catch (error: any) {
      message.error(error.message || '操作失败');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (rule: FilterRule) => {
    setEditingRule(rule);
    setRuleType(rule.rule_type);
    
    // 根据规则类型解析rule_config
    const config = rule.rule_config || {};
    const formValues: any = {
      name: rule.name,
      description: rule.description,
      rule_type: rule.rule_type,
      logic_operator: rule.logic_operator,
      priority: rule.priority,
      is_active: rule.is_active,
    };

    // 根据规则类型填充表单值
    if (rule.rule_type === 'education') {
      formValues.degree = config.degree;
      formValues.operator = config.operator || '>=';
    } else if (rule.rule_type === 'experience') {
      formValues.years = config.years;
      formValues.operator = config.operator || '>=';
    } else if (rule.rule_type === 'age') {
      formValues.min_age = config.min_age;
      formValues.max_age = config.max_age;
    } else if (rule.rule_type === 'skill') {
      formValues.skills = Array.isArray(config.skills) ? config.skills.join(', ') : '';
      formValues.match_type = config.match_type || 'any';
    }

    form.setFieldsValue(formValues);
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    setLoading(true);
    try {
      await jobApi.deleteFilterRule(id);
      message.success('筛选规则删除成功');
      loadRules();
    } catch (error: any) {
      message.error(error.message || '删除失败');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleActive = async (rule: FilterRule) => {
    setLoading(true);
    try {
      await jobApi.updateFilterRule(rule.id, { is_active: !rule.is_active });
      message.success(`规则已${rule.is_active ? '禁用' : '启用'}`);
      loadRules();
    } catch (error: any) {
      message.error(error.message || '操作失败');
    } finally {
      setLoading(false);
    }
  };

  // 渲染规则配置表单（根据规则类型）
  const renderRuleConfigForm = () => {
    switch (ruleType) {
      case 'education':
        return (
          <>
            <Form.Item
              name="degree"
              label="学历要求"
              rules={[{ required: true, message: '请选择学历要求' }]}
            >
              <Select placeholder="选择学历">
                <Option value="博士">博士</Option>
                <Option value="硕士">硕士</Option>
                <Option value="本科">本科</Option>
                <Option value="专科">专科</Option>
                <Option value="高中">高中</Option>
              </Select>
            </Form.Item>
            <Form.Item
              name="operator"
              label="比较方式"
              initialValue=">="
            >
              <Select>
                <Option value=">=">大于等于（≥）</Option>
                <Option value="==">等于（=）</Option>
                <Option value="<=">小于等于（≤）</Option>
              </Select>
            </Form.Item>
          </>
        );
      case 'experience':
        return (
          <>
            <Form.Item
              name="years"
              label="工作经验（年）"
              rules={[{ required: true, message: '请输入工作经验年限' }]}
            >
              <InputNumber min={0} max={50} style={{ width: '100%' }} placeholder="例如：3" />
            </Form.Item>
            <Form.Item
              name="operator"
              label="比较方式"
              initialValue=">="
            >
              <Select>
                <Option value=">=">大于等于（≥）</Option>
                <Option value="==">等于（=）</Option>
                <Option value="<=">小于等于（≤）</Option>
              </Select>
            </Form.Item>
          </>
        );
      case 'age':
        return (
          <>
            <Form.Item
              name="min_age"
              label="最小年龄"
              rules={[{ required: true, message: '请输入最小年龄' }]}
            >
              <InputNumber min={18} max={100} style={{ width: '100%' }} placeholder="例如：25" />
            </Form.Item>
            <Form.Item
              name="max_age"
              label="最大年龄"
              rules={[{ required: true, message: '请输入最大年龄' }]}
            >
              <InputNumber min={18} max={100} style={{ width: '100%' }} placeholder="例如：45" />
            </Form.Item>
          </>
        );
      case 'skill':
        return (
          <>
            <Form.Item
              name="skills"
              label="技能要求（用逗号分隔）"
              rules={[{ required: true, message: '请输入技能要求' }]}
              tooltip="例如：Python, Java, React"
            >
              <TextArea rows={3} placeholder="例如：Python, Java, React" />
            </Form.Item>
            <Form.Item
              name="match_type"
              label="匹配方式"
              initialValue="any"
            >
              <Select>
                <Option value="any">任意一个技能即可</Option>
                <Option value="all">必须包含所有技能</Option>
              </Select>
            </Form.Item>
          </>
        );
      default:
        return null;
    }
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: '规则名称',
      dataIndex: 'name',
      key: 'name',
      width: 180,
    },
    {
      title: '规则类型',
      dataIndex: 'rule_type',
      key: 'rule_type',
      width: 120,
      render: (type: string) => {
        const typeMap: { [key: string]: string } = {
          education: '学历要求',
          experience: '工作经验',
          age: '年龄限制',
          skill: '技能要求',
          custom: '自定义',
        };
        return <Tag color="blue">{typeMap[type] || type}</Tag>;
      },
    },
    {
      title: '规则内容',
      dataIndex: 'rule_config',
      key: 'rule_content',
      render: (config: Record<string, any>, record: FilterRule) => {
        if (record.rule_type === 'education') {
          return `${config.operator || '>='} ${config.degree || 'N/A'}`;
        } else if (record.rule_type === 'experience') {
          return `${config.operator || '>='} ${config.years || 0}年`;
        } else if (record.rule_type === 'age') {
          return `${config.min_age || 'N/A'} - ${config.max_age || 'N/A'}岁`;
        } else if (record.rule_type === 'skill') {
          const skills = Array.isArray(config.skills) ? config.skills : [];
          return skills.length > 0 ? skills.join(', ') : 'N/A';
        }
        return JSON.stringify(config);
      },
    },
    {
      title: '优先级',
      dataIndex: 'priority',
      key: 'priority',
      width: 80,
      sorter: (a: FilterRule, b: FilterRule) => a.priority - b.priority,
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
              setRuleType('education');
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
          setRuleType('education');
        }}
        width={600}
        confirmLoading={loading}
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
            <Select 
              placeholder="请选择规则类型"
              onChange={(value) => {
                setRuleType(value);
                form.setFieldsValue({ rule_config: {} });
              }}
            >
              <Option value="education">学历要求</Option>
              <Option value="experience">工作经验</Option>
              <Option value="age">年龄限制</Option>
              <Option value="skill">技能要求</Option>
            </Select>
          </Form.Item>

          {renderRuleConfigForm()}

          <Form.Item
            name="logic_operator"
            label="逻辑运算符"
            initialValue="AND"
            tooltip="与其他规则的关系：AND表示必须同时满足，OR表示满足任意一个即可"
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
            rules={[{ required: true, message: '请输入优先级' }]}
            tooltip="数字越大优先级越高，优先级高的规则会先执行"
          >
            <InputNumber min={0} max={100} style={{ width: '100%' }} />
          </Form.Item>

          <Form.Item
            name="is_active"
            label="是否启用"
            valuePropName="checked"
            initialValue={true}
          >
            <Switch />
          </Form.Item>

          <Form.Item name="description" label="描述">
            <TextArea rows={2} placeholder="规则的详细描述" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default FilterRulesSimple;

