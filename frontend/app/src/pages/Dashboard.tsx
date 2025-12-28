import React from 'react';
import { Card, Row, Col, Statistic } from 'antd';
import { FileTextOutlined, FolderOutlined, UsergroupAddOutlined, FileSearchOutlined } from '@ant-design/icons';

const Dashboard: React.FC = () => {
  return (
    <div>
      <h1 style={{ marginBottom: 24 }}>控制台</h1>
      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <Statistic
              title="简历总数"
              value={0}
              prefix={<FileTextOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="岗位数量"
              value={0}
              prefix={<FolderOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="匹配记录"
              value={0}
              prefix={<UsergroupAddOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="推荐报告"
              value={0}
              prefix={<FileSearchOutlined />}
            />
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;

