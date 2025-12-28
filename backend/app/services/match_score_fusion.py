"""
匹配度融合算法服务
支持动态权重调整和多维度融合
"""
import logging
from typing import Dict, Any, Optional, Tuple
from ..models.job import MatchModel, JobPosition

logger = logging.getLogger(__name__)


class MatchScoreFusion:
    """匹配度融合算法"""
    
    def __init__(self, match_model: Optional[MatchModel] = None):
        self.match_model = match_model
        self.default_weights = {
            "vector_weight": 0.3,
            "rule_weight": 0.2,
            "llm_weight": 0.5,
            "org_weight": 0.0  # 组织匹配度权重（新增）
        }
    
    def calculate_final_score(
        self,
        vector_similarity: float,      # 0-1
        rule_match_result: Dict,       # 规则匹配结果
        llm_analysis: Dict,            # LLM分析结果
        org_match_score: float = 0.0,  # 组织匹配度（新增）
        job: Optional[JobPosition] = None  # 岗位对象（用于动态调整权重）
    ) -> Tuple[float, Dict[str, Any]]:
        """
        计算最终匹配分数
        
        Args:
            vector_similarity: 向量相似度（0-1）
            rule_match_result: 规则匹配结果
            llm_analysis: LLM分析结果
            org_match_score: 组织匹配度（0-1，新增）
            job: 岗位对象（用于动态调整权重）
        
        Returns:
            (最终分数, 评分明细)
        """
        try:
            # 1. 获取权重配置
            if self.match_model:
                weights = self.match_model.model_config.copy()
            else:
                weights = self.default_weights.copy()
            
            # 2. 动态调整权重（根据岗位类型）
            if job:
                weights = self._adjust_weights_by_job_type(weights, job)
            
            # 3. 计算各维度分数
            vector_score = vector_similarity * 10  # 转换为0-10分
            
            rule_score = self._calculate_rule_score(rule_match_result) * 10
            
            llm_score = llm_analysis.get("score", 0.0)  # 已经是0-10分
            
            org_score = org_match_score * 10  # 转换为0-10分
            
            # 4. 融合算法（加权平均）
            final_score = (
                weights.get("vector_weight", 0.3) * vector_score +
                weights.get("rule_weight", 0.2) * rule_score +
                weights.get("llm_weight", 0.5) * llm_score +
                weights.get("org_weight", 0.0) * org_score
            )
            
            # 确保分数在0-10范围内
            final_score = max(0.0, min(10.0, final_score))
            
            # 5. 生成匹配标签
            match_label = self._generate_match_label(final_score)
            
            # 6. 生成评分明细
            score_breakdown = {
                "vector_score": round(vector_score, 2),
                "rule_score": round(rule_score, 2),
                "llm_score": round(llm_score, 2),
                "org_score": round(org_score, 2),
                "final_score": round(final_score, 2),
                "weights": weights,
                "calculation": (
                    f"{vector_score:.2f} * {weights.get('vector_weight', 0.3):.2f} + "
                    f"{rule_score:.2f} * {weights.get('rule_weight', 0.2):.2f} + "
                    f"{llm_score:.2f} * {weights.get('llm_weight', 0.5):.2f} + "
                    f"{org_score:.2f} * {weights.get('org_weight', 0.0):.2f} = "
                    f"{final_score:.2f}"
                ),
                "match_label": match_label
            }
            
            return final_score, score_breakdown
            
        except Exception as e:
            logger.error(f"计算最终分数失败: {e}", exc_info=True)
            return 0.0, {}
    
    def _adjust_weights_by_job_type(self, weights: Dict, job: JobPosition) -> Dict:
        """
        根据岗位类型动态调整权重
        
        策略：
        - 技术岗位：更看重技能匹配（向量相似度）
        - 管理岗位：更看重经验匹配（LLM分析）
        - 销售岗位：更看重规则匹配（硬门槛）
        """
        job_title = job.title.lower() if job.title else ""
        
        # 技术岗位：更看重技能匹配（向量相似度）
        if any(keyword in job_title for keyword in ["技术", "研发", "开发", "工程师", "程序员", "架构师", "算法"]):
            weights["vector_weight"] = 0.4
            weights["llm_weight"] = 0.4
            weights["rule_weight"] = 0.2
            weights["org_weight"] = 0.0
        
        # 管理岗位：更看重经验匹配（LLM分析）
        elif any(keyword in job_title for keyword in ["管理", "总监", "经理", "主管", "负责人", "leader"]):
            weights["vector_weight"] = 0.2
            weights["llm_weight"] = 0.6
            weights["rule_weight"] = 0.2
            weights["org_weight"] = 0.0
        
        # 销售岗位：更看重规则匹配（硬门槛）
        elif any(keyword in job_title for keyword in ["销售", "市场", "商务", "bd"]):
            weights["vector_weight"] = 0.2
            weights["llm_weight"] = 0.3
            weights["rule_weight"] = 0.5
            weights["org_weight"] = 0.0
        
        # 其他岗位：使用默认权重
        else:
            pass  # 保持原有权重
        
        return weights
    
    def _calculate_rule_score(self, rule_match_result: Dict) -> float:
        """
        计算规则匹配分数
        
        Args:
            rule_match_result: 规则匹配结果
        
        Returns:
            规则匹配分数（0-1）
        """
        if not rule_match_result:
            return 1.0  # 没有规则，默认通过
        
        if rule_match_result.get("passed"):
            return 1.0  # 全部通过
        
        # 根据通过率计算分数
        total_rules = len(rule_match_result.get("rule_details", []))
        failed_rules = len(rule_match_result.get("failed_rules", []))
        
        if total_rules == 0:
            return 1.0  # 没有规则，默认通过
        
        passed_rules = total_rules - failed_rules
        return passed_rules / total_rules
    
    def _generate_match_label(self, score: float) -> str:
        """
        生成匹配标签
        
        Args:
            score: 最终匹配分数（0-10）
        
        Returns:
            匹配标签
        """
        if score >= 8.5:
            return "强烈推荐"
        elif score >= 7.0:
            return "推荐"
        elif score >= 6.0:
            return "谨慎推荐"
        else:
            return "不推荐"
    
    def extract_org_match_score(self, llm_analysis: Dict) -> float:
        """
        从LLM分析结果中提取组织匹配度
        
        Args:
            llm_analysis: LLM分析结果
        
        Returns:
            组织匹配度（0-1）
        """
        try:
            # 尝试从LLM分析结果中提取组织匹配度
            if "organization_match" in llm_analysis:
                org_match = llm_analysis["organization_match"]
                if isinstance(org_match, dict) and "score" in org_match:
                    # 转换为0-1范围（LLM返回的是0-10）
                    org_score = org_match["score"]
                    if org_score > 10:
                        org_score = 10
                    return org_score / 10.0
            
            # 如果没有组织匹配度，返回0.5（中性）
            return 0.5
            
        except Exception as e:
            logger.warning(f"提取组织匹配度失败: {e}")
            return 0.5

