import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, Descriptions, Tabs, Tag, Progress, Button, Space, message } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { jobApi } from '@/services/jobApi';
import { ResumeJobMatch } from '@/types/job';

const MatchDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [match, setMatch] = useState<ResumeJobMatch | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (id) {
      loadMatch();
    }
  }, [id]);

  const loadMatch = async () => {
    setLoading(true);
    try {
      const response = await jobApi.getMatchResultDetail(parseInt(id!));
      if (response.success) {
        setMatch(response.data);
      }
    } catch (error: any) {
      message.error('加载详情失败: ' + (error.response?.data?.detail || error.message));
    } finally {
      setLoading(false);
    }
  };

  const getLabelColor = (label: string) => {
    const colorMap: Record<string, string> = {
      '强烈推荐': 'success',
      '推荐': 'processing',
      '谨慎推荐': 'warning',
      '不推荐': 'error',
    };
    return colorMap[label] || 'default';
  };

  if (!match) {
    return <Card loading={loading}>加载中...</Card>;
  }

  return (
    <Card
      title={
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/matching')}>
            返回
          </Button>
          <span>匹配详情</span>
        </Space>
      }
      loading={loading}
    >
      <Tabs>
        <Tabs.TabPane tab="基本信息" key="basic">
          <Descriptions column={1} bordered>
            <Descriptions.Item label="简历ID">{match.resume_id}</Descriptions.Item>
            <Descriptions.Item label="岗位ID">{match.job_id}</Descriptions.Item>
            <Descriptions.Item label="匹配度">
              <Progress
                percent={match.match_score * 10}
                format={(percent) => `${match.match_score.toFixed(1)}分`}
              />
            </Descriptions.Item>
            <Descriptions.Item label="匹配标签">
              <Tag color={getLabelColor(match.match_label)}>
                {match.match_label}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={match.status === 'pending' ? 'default' : 'success'}>
                {match.status === 'pending' ? '待审核' :
                 match.status === 'reviewed' ? '已审核' :
                 match.status === 'rejected' ? '已拒绝' : '已接受'}
              </Tag>
            </Descriptions.Item>
          </Descriptions>
        </Tabs.TabPane>
        {match.match_detail && (
          <>
            <Tabs.TabPane tab="向量相似度" key="vector">
              <Descriptions column={1} bordered>
                <Descriptions.Item label="相似度分数">
                  {(match.match_detail.vector_similarity * 100).toFixed(2)}%
                </Descriptions.Item>
              </Descriptions>
            </Tabs.TabPane>
            <Tabs.TabPane tab="规则匹配" key="rule">
              <Descriptions column={1} bordered>
                <Descriptions.Item label="是否通过">
                  <Tag color={match.match_detail.rule_match_result?.passed ? 'success' : 'error'}>
                    {match.match_detail.rule_match_result?.passed ? '通过' : '未通过'}
                  </Tag>
                </Descriptions.Item>
                <Descriptions.Item label="失败规则">
                  {match.match_detail.rule_match_result?.failed_rules?.length > 0 ? (
                    <ul>
                      {match.match_detail.rule_match_result.failed_rules.map((rule: any, index: number) => (
                        <li key={index}>{rule.rule_name}: {rule.reason}</li>
                      ))}
                    </ul>
                  ) : '无'}
                </Descriptions.Item>
              </Descriptions>
            </Tabs.TabPane>
            <Tabs.TabPane tab="LLM分析" key="llm">
              {match.match_detail.llm_analysis && (
                <div>
                  <Descriptions column={1} bordered style={{ marginBottom: 16 }}>
                    <Descriptions.Item label="LLM评分">
                      {match.match_detail.llm_analysis.score}分
                    </Descriptions.Item>
                    <Descriptions.Item label="推荐建议">
                      {match.match_detail.llm_analysis.recommendation}
                    </Descriptions.Item>
                  </Descriptions>
                  <Card title="优势" size="small" style={{ marginBottom: 16 }}>
                    <ul>
                      {match.match_detail.llm_analysis.strengths?.map((item: string, index: number) => (
                        <li key={index}>{item}</li>
                      ))}
                    </ul>
                  </Card>
                  <Card title="劣势" size="small" style={{ marginBottom: 16 }}>
                    <ul>
                      {match.match_detail.llm_analysis.weaknesses?.map((item: string, index: number) => (
                        <li key={index}>{item}</li>
                      ))}
                    </ul>
                  </Card>
                  <Card title="风险点" size="small">
                    <ul>
                      {match.match_detail.llm_analysis.risk_points?.map((item: string, index: number) => (
                        <li key={index}>{item}</li>
                      ))}
                    </ul>
                  </Card>
                </div>
              )}
            </Tabs.TabPane>
            <Tabs.TabPane tab="评分明细" key="score">
              {match.match_detail.score_breakdown && (
                <Descriptions column={1} bordered>
                  <Descriptions.Item label="向量分数">
                    {match.match_detail.score_breakdown.vector_score}分
                  </Descriptions.Item>
                  <Descriptions.Item label="规则分数">
                    {match.match_detail.score_breakdown.rule_score}分
                  </Descriptions.Item>
                  <Descriptions.Item label="LLM分数">
                    {match.match_detail.score_breakdown.llm_score}分
                  </Descriptions.Item>
                  <Descriptions.Item label="最终分数">
                    <strong>{match.match_detail.score_breakdown.final_score}分</strong>
                  </Descriptions.Item>
                </Descriptions>
              )}
            </Tabs.TabPane>
          </>
        )}
      </Tabs>
    </Card>
  );
};

export default MatchDetail;


