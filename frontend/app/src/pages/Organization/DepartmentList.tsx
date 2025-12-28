/**
 * 组织架构管理页面 - 部门列表
 */
import React, { useState, useEffect } from 'react';
import {
  Table,
  Button,
  Card,
  Space,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  Tree,
  message,
  Popconfirm,
  Drawer,
  Descriptions,
  Tag,
} from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  EyeOutlined,
  ApartmentOutlined,
} from '@ant-design/icons';
import { organizationApi, Department, DepartmentCreate, DepartmentUpdate } from '@/services/organizationApi';
import { useAuthStore } from '@/stores/authStore';

const { TextArea } = Input;
const { Option } = Select;

const DepartmentList: React.FC = () => {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [editingDepartment, setEditingDepartment] = useState<Department | null>(null);
  const [form] = Form.useForm();
  const { user } = useAuthStore();

  // 获取部门列表
  const fetchDepartments = async () => {
    setLoading(true);
    try {
      const data = await organizationApi.getDepartments(true);
      setDepartments(data);
    } catch (error: any) {
      message.error('获取部门列表失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDepartments();
  }, []);

  // 创建部门
  const handleCreate = () => {
    setEditingDepartment(null);
    form.resetFields();
    setModalVisible(true);
  };

  // 编辑部门
  const handleEdit = (department: Department) => {
    setEditingDepartment(department);
    form.setFieldsValue({
      name: department.name,
      code: department.code,
      description: department.description,
      parent_id: department.parent_id,
      department_culture: department.department_culture,
      work_style: department.work_style,
      team_size: department.team_size,
      key_responsibilities: department.key_responsibilities,
      manager_id: department.manager_id,
    });
    setModalVisible(true);
  };

  // 查看部门详情
  const handleView = (department: Department) => {
    setEditingDepartment(department);
    setDrawerVisible(true);
  };

  // 删除部门
  const handleDelete = async (id: number) => {
    try {
      await organizationApi.deleteDepartment(id);
      message.success('删除成功');
      fetchDepartments();
    } catch (error: any) {
      message.error('删除失败: ' + (error.response?.data?.detail || error.message));
    }
  };

  // 提交表单
  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      
      if (editingDepartment) {
        // 更新
        await organizationApi.updateDepartment(editingDepartment.id, values);
        message.success('更新成功');
      } else {
        // 创建
        await organizationApi.createDepartment(values);
        message.success('创建成功');
      }
      
      setModalVisible(false);
      form.resetFields();
      fetchDepartments();
    } catch (error: any) {
      if (error.errorFields) {
        // 表单验证错误
        return;
      }
      message.error((editingDepartment ? '更新' : '创建') + '失败: ' + (error.response?.data?.detail || error.message));
    }
  };

  // 构建树形数据
  const buildTreeData = (departments: Department[]): any[] => {
    return departments.map(dept => ({
      title: (
        <Space>
          <span>{dept.name}</span>
          {dept.code && <Tag color="blue">{dept.code}</Tag>}
          {dept.level && <Tag color="green">L{dept.level}</Tag>}
          {dept.jobs_count !== undefined && dept.jobs_count > 0 && (
            <Tag color="orange">{dept.jobs_count}个岗位</Tag>
          )}
        </Space>
      ),
      key: dept.id,
      value: dept.id,
      children: dept.children ? buildTreeData(dept.children) : [],
    }));
  };

  // 获取所有部门（扁平列表，用于父部门选择）
  const getAllDepartments = (departments: Department[]): Department[] => {
    let result: Department[] = [];
    departments.forEach(dept => {
      result.push(dept);
      if (dept.children) {
        result = result.concat(getAllDepartments(dept.children));
      }
    });
    return result;
  };

  const treeData = buildTreeData(departments);
  const allDepartments = getAllDepartments(departments);

  return (
    <div>
      <Card
        title={
          <Space>
            <ApartmentOutlined />
            <span>组织架构管理</span>
          </Space>
        }
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            创建部门
          </Button>
        }
      >
        <Tree
          showLine
          defaultExpandAll
          treeData={treeData}
          titleRender={(node) => (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
              <span>{node.title}</span>
              <Space>
                <Button
                  type="link"
                  size="small"
                  icon={<EyeOutlined />}
                  onClick={() => {
                    const dept = allDepartments.find(d => d.id === node.key);
                    if (dept) handleView(dept);
                  }}
                >
                  查看
                </Button>
                <Button
                  type="link"
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => {
                    const dept = allDepartments.find(d => d.id === node.key);
                    if (dept) handleEdit(dept);
                  }}
                >
                  编辑
                </Button>
                <Popconfirm
                  title="确定要删除这个部门吗？"
                  description="删除后无法恢复，且该部门下的子部门和岗位需要先处理。"
                  onConfirm={() => handleDelete(node.key as number)}
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
            </div>
          )}
        />
      </Card>

      {/* 创建/编辑模态框 */}
      <Modal
        title={editingDepartment ? '编辑部门' : '创建部门'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => {
          setModalVisible(false);
          form.resetFields();
        }}
        width={600}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="部门名称"
            rules={[{ required: true, message: '请输入部门名称' }]}
          >
            <Input placeholder="请输入部门名称" />
          </Form.Item>

          <Form.Item name="code" label="部门编码">
            <Input placeholder="请输入部门编码（可选）" />
          </Form.Item>

          <Form.Item name="parent_id" label="上级部门">
            <Select
              placeholder="请选择上级部门（可选）"
              allowClear
              showSearch
              filterOption={(input, option) =>
                (option?.children as unknown as string)?.toLowerCase().includes(input.toLowerCase())
              }
            >
              {allDepartments
                .filter(d => !editingDepartment || d.id !== editingDepartment.id)
                .map(dept => (
                  <Option key={dept.id} value={dept.id}>
                    {dept.path || dept.name}
                  </Option>
                ))}
            </Select>
          </Form.Item>

          <Form.Item name="description" label="部门职责描述">
            <TextArea rows={3} placeholder="请输入部门职责描述" />
          </Form.Item>

          <Form.Item name="key_responsibilities" label="核心职责">
            <TextArea rows={2} placeholder="请输入核心职责" />
          </Form.Item>

          <Form.Item name="department_culture" label="部门文化">
            <TextArea rows={2} placeholder="请输入部门文化" />
          </Form.Item>

          <Form.Item name="work_style" label="工作风格">
            <TextArea rows={2} placeholder="请输入工作风格" />
          </Form.Item>

          <Form.Item name="team_size" label="团队规模">
            <InputNumber
              min={0}
              placeholder="请输入团队规模（人数）"
              style={{ width: '100%' }}
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* 查看详情抽屉 */}
      <Drawer
        title="部门详情"
        placement="right"
        width={600}
        open={drawerVisible}
        onClose={() => setDrawerVisible(false)}
      >
        {editingDepartment && (
          <Descriptions column={1} bordered>
            <Descriptions.Item label="部门名称">{editingDepartment.name}</Descriptions.Item>
            {editingDepartment.code && (
              <Descriptions.Item label="部门编码">{editingDepartment.code}</Descriptions.Item>
            )}
            {editingDepartment.path && (
              <Descriptions.Item label="部门路径">{editingDepartment.path}</Descriptions.Item>
            )}
            {editingDepartment.level && (
              <Descriptions.Item label="部门层级">第{editingDepartment.level}级部门</Descriptions.Item>
            )}
            {editingDepartment.parent_name && (
              <Descriptions.Item label="上级部门">{editingDepartment.parent_name}</Descriptions.Item>
            )}
            {editingDepartment.description && (
              <Descriptions.Item label="部门职责描述">{editingDepartment.description}</Descriptions.Item>
            )}
            {editingDepartment.key_responsibilities && (
              <Descriptions.Item label="核心职责">{editingDepartment.key_responsibilities}</Descriptions.Item>
            )}
            {editingDepartment.department_culture && (
              <Descriptions.Item label="部门文化">{editingDepartment.department_culture}</Descriptions.Item>
            )}
            {editingDepartment.work_style && (
              <Descriptions.Item label="工作风格">{editingDepartment.work_style}</Descriptions.Item>
            )}
            {editingDepartment.team_size && (
              <Descriptions.Item label="团队规模">{editingDepartment.team_size}人</Descriptions.Item>
            )}
            {editingDepartment.manager_name && (
              <Descriptions.Item label="部门负责人">{editingDepartment.manager_name}</Descriptions.Item>
            )}
            <Descriptions.Item label="子部门数量">{editingDepartment.children_count || 0}</Descriptions.Item>
            <Descriptions.Item label="关联岗位数量">{editingDepartment.jobs_count || 0}</Descriptions.Item>
            {editingDepartment.created_at && (
              <Descriptions.Item label="创建时间">
                {new Date(editingDepartment.created_at).toLocaleString()}
              </Descriptions.Item>
            )}
            {editingDepartment.updated_at && (
              <Descriptions.Item label="更新时间">
                {new Date(editingDepartment.updated_at).toLocaleString()}
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
};

export default DepartmentList;

