"""
预筛选规则引擎服务
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from ..models.job import FilterRule
from ..models.resume import ParsedResume, CandidateResume
from ..core.mongodb_service import mongodb_service

logger = logging.getLogger(__name__)


class FilterService:
    """预筛选规则引擎服务"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
    
    def execute_filter_rules(
        self,
        resume_data: Dict[str, Any],
        rule_ids: Optional[List[int]] = None,
        all_rules: bool = True
    ) -> Dict[str, Any]:
        """
        执行筛选规则
        
        Args:
            resume_data: 简历数据（从MongoDB或PostgreSQL获取）
            rule_ids: 要执行的规则ID列表（如果为None且all_rules=True，则执行所有活跃规则）
            all_rules: 是否执行所有活跃规则
        
        Returns:
            筛选结果
            {
                "passed": bool,  # 是否通过筛选
                "failed_rules": List[Dict],  # 未通过的规则
                "rule_details": List[Dict],  # 所有规则的执行详情
                "summary": str  # 筛选摘要
            }
        """
        try:
            # 获取要执行的规则
            if rule_ids:
                rules = self.db.query(FilterRule).filter(
                    FilterRule.id.in_(rule_ids),
                    FilterRule.is_active == True
                ).order_by(FilterRule.priority.desc()).all()
            elif all_rules:
                rules = self.db.query(FilterRule).filter(
                    FilterRule.is_active == True
                ).order_by(FilterRule.priority.desc()).all()
            else:
                rules = []
            
            if not rules:
                return {
                    "passed": True,
                    "failed_rules": [],
                    "rule_details": [],
                    "summary": "没有配置筛选规则，默认通过"
                }
            
            # 执行每个规则
            rule_details = []
            failed_rules = []
            logic_operator = "AND"  # 默认AND逻辑
            
            for rule in rules:
                result = self._execute_single_rule(rule, resume_data)
                rule_details.append(result)
                
                if not result["passed"]:
                    failed_rules.append({
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "rule_type": rule.rule_type,
                        "reason": result["reason"]
                    })
                    # 如果逻辑运算符是AND且有一个规则失败，可以提前返回
                    if rule.logic_operator == "AND":
                        logic_operator = "AND"
            
            # 根据逻辑运算符判断最终结果
            passed = len(failed_rules) == 0 if logic_operator == "AND" else len(failed_rules) < len(rules)
            
            # 生成摘要
            summary = self._generate_summary(passed, failed_rules, len(rules))
            
            return {
                "passed": passed,
                "failed_rules": failed_rules,
                "rule_details": rule_details,
                "summary": summary
            }
            
        except Exception as e:
            logger.error(f"执行筛选规则失败: {e}", exc_info=True)
            raise
    
    def _execute_single_rule(self, rule: FilterRule, resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行单个规则
        
        Args:
            rule: 筛选规则
            resume_data: 简历数据
        
        Returns:
            规则执行结果
            {
                "rule_id": int,
                "rule_name": str,
                "passed": bool,
                "reason": str,
                "matched_value": Any,
                "expected_value": Any
            }
        """
        try:
            rule_config = rule.rule_config
            rule_type = rule.rule_type
            
            # 根据规则类型执行不同的匹配逻辑
            if rule_type == "education":
                return self._check_education(rule_config, resume_data)
            elif rule_type == "experience":
                return self._check_experience(rule_config, resume_data)
            elif rule_type == "skill":
                return self._check_skill(rule_config, resume_data)
            elif rule_type == "age":
                return self._check_age(rule_config, resume_data)
            elif rule_type == "location":
                return self._check_location(rule_config, resume_data)
            elif rule_type == "custom":
                return self._check_custom(rule_config, resume_data)
            else:
                return {
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "passed": False,
                    "reason": f"未知的规则类型: {rule_type}",
                    "matched_value": None,
                    "expected_value": None
                }
                
        except Exception as e:
            logger.error(f"执行规则失败: rule_id={rule.id}, error={e}", exc_info=True)
            return {
                "rule_id": rule.id,
                "rule_name": rule.name,
                "passed": False,
                "reason": f"规则执行异常: {str(e)}",
                "matched_value": None,
                "expected_value": None
            }
    
    def _check_education(self, rule_config: Dict[str, Any], resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """检查学历要求"""
        try:
            # 获取简历中的学历信息
            education_list = resume_data.get("education", [])
            if not education_list:
                return {
                    "passed": False,
                    "reason": "简历中无学历信息",
                    "matched_value": None,
                    "expected_value": rule_config.get("degree")
                }
            
            # 获取最高学历
            highest_degree = self._get_highest_degree(education_list)
            
            # 获取规则要求
            required_degree = rule_config.get("degree")
            operator = rule_config.get("operator", ">=")
            
            if not required_degree:
                return {
                    "passed": True,
                    "reason": "规则未设置学历要求",
                    "matched_value": highest_degree,
                    "expected_value": required_degree
                }
            
            # 学历等级映射
            degree_levels = {
                "博士": 5,
                "硕士": 4,
                "本科": 3,
                "专科": 2,
                "高中": 1,
                "初中": 0
            }
            
            candidate_level = degree_levels.get(highest_degree, 0)
            required_level = degree_levels.get(required_degree, 0)
            
            # 执行比较
            passed = self._compare_values(candidate_level, required_level, operator)
            
            return {
                "passed": passed,
                "reason": f"候选人学历: {highest_degree} ({candidate_level}), 要求: {required_degree} ({required_level}), 操作符: {operator}",
                "matched_value": highest_degree,
                "expected_value": required_degree
            }
            
        except Exception as e:
            logger.error(f"检查学历要求失败: {e}", exc_info=True)
            return {
                "passed": False,
                "reason": f"检查学历要求异常: {str(e)}",
                "matched_value": None,
                "expected_value": rule_config.get("degree")
            }
    
    def _check_experience(self, rule_config: Dict[str, Any], resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """检查工作经验要求"""
        try:
            # 获取简历中的工作经历
            work_experiences = resume_data.get("work_experiences", [])
            
            # 计算总工作经验（年）
            total_years = self._calculate_total_experience_years(work_experiences)
            
            # 获取规则要求
            required_years = rule_config.get("years", 0)
            operator = rule_config.get("operator", ">=")
            
            # 执行比较
            passed = self._compare_values(total_years, required_years, operator)
            
            return {
                "passed": passed,
                "reason": f"候选人工作经验: {total_years}年, 要求: {required_years}年, 操作符: {operator}",
                "matched_value": total_years,
                "expected_value": required_years
            }
            
        except Exception as e:
            logger.error(f"检查工作经验要求失败: {e}", exc_info=True)
            return {
                "passed": False,
                "reason": f"检查工作经验要求异常: {str(e)}",
                "matched_value": None,
                "expected_value": rule_config.get("years")
            }
    
    def _check_skill(self, rule_config: Dict[str, Any], resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """检查技能要求"""
        try:
            # 获取简历中的技能
            skills = resume_data.get("skills", {})
            technical_skills = skills.get("technical", {})
            explicit_skills = technical_skills.get("explicit", [])
            inferred_skills = technical_skills.get("inferred", [])
            all_skills = explicit_skills + inferred_skills
            
            # 获取规则要求
            required_skills = rule_config.get("skills", [])
            match_type = rule_config.get("match_type", "any")  # any: 任意一个, all: 全部
            
            if not required_skills:
                return {
                    "passed": True,
                    "reason": "规则未设置技能要求",
                    "matched_value": all_skills,
                    "expected_value": required_skills
                }
            
            # 转换为小写进行比较（不区分大小写）
            all_skills_lower = [s.lower() for s in all_skills]
            required_skills_lower = [s.lower() for s in required_skills]
            
            if match_type == "all":
                # 必须包含所有技能
                matched_skills = [s for s in required_skills_lower if s in all_skills_lower]
                passed = len(matched_skills) == len(required_skills_lower)
                reason = f"要求技能: {required_skills}, 匹配: {matched_skills}, 需要全部匹配"
            else:
                # 任意一个技能即可
                matched_skills = [s for s in required_skills_lower if s in all_skills_lower]
                passed = len(matched_skills) > 0
                reason = f"要求技能: {required_skills}, 匹配: {matched_skills}, 任意一个即可"
            
            return {
                "passed": passed,
                "reason": reason,
                "matched_value": matched_skills,
                "expected_value": required_skills
            }
            
        except Exception as e:
            logger.error(f"检查技能要求失败: {e}", exc_info=True)
            return {
                "passed": False,
                "reason": f"检查技能要求异常: {str(e)}",
                "matched_value": None,
                "expected_value": rule_config.get("skills")
            }
    
    def _check_age(self, rule_config: Dict[str, Any], resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """检查年龄要求"""
        try:
            # 获取简历中的年龄信息
            basic_info = resume_data.get("basic_info", {})
            birth_date = basic_info.get("birth_date") or basic_info.get("birthday")
            
            if not birth_date:
                return {
                    "passed": False,
                    "reason": "简历中无出生日期信息",
                    "matched_value": None,
                    "expected_value": rule_config.get("age_range")
                }
            
            # 计算年龄
            age = self._calculate_age(birth_date)
            
            # 获取规则要求
            age_range = rule_config.get("age_range")  # 格式: "25-35" 或 "30"
            operator = rule_config.get("operator", "in_range")
            
            if operator == "in_range":
                # 解析年龄范围
                if "-" in age_range:
                    min_age, max_age = map(int, age_range.split("-"))
                    passed = min_age <= age <= max_age
                    reason = f"候选人年龄: {age}岁, 要求范围: {age_range}岁"
                else:
                    # 单个年龄值，允许±2岁
                    target_age = int(age_range)
                    passed = abs(age - target_age) <= 2
                    reason = f"候选人年龄: {age}岁, 要求: {age_range}岁（允许±2岁）"
            else:
                # 使用操作符比较
                target_age = int(age_range) if age_range.isdigit() else 0
                passed = self._compare_values(age, target_age, operator)
                reason = f"候选人年龄: {age}岁, 要求: {age_range}岁, 操作符: {operator}"
            
            return {
                "passed": passed,
                "reason": reason,
                "matched_value": age,
                "expected_value": age_range
            }
            
        except Exception as e:
            logger.error(f"检查年龄要求失败: {e}", exc_info=True)
            return {
                "passed": False,
                "reason": f"检查年龄要求异常: {str(e)}",
                "matched_value": None,
                "expected_value": rule_config.get("age_range")
            }
    
    def _check_location(self, rule_config: Dict[str, Any], resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """检查地点要求"""
        try:
            # 获取简历中的地点信息
            basic_info = resume_data.get("basic_info", {})
            location = basic_info.get("location") or basic_info.get("current_location")
            
            # 获取规则要求
            required_locations = rule_config.get("locations", [])
            match_type = rule_config.get("match_type", "any")  # any: 任意一个, all: 全部
            
            if not required_locations:
                return {
                    "passed": True,
                    "reason": "规则未设置地点要求",
                    "matched_value": location,
                    "expected_value": required_locations
                }
            
            if not location:
                return {
                    "passed": False,
                    "reason": "简历中无地点信息",
                    "matched_value": None,
                    "expected_value": required_locations
                }
            
            # 地点匹配（支持模糊匹配，如"北京"匹配"北京市"）
            location_lower = location.lower()
            required_locations_lower = [loc.lower() for loc in required_locations]
            
            # 检查是否包含关键词
            matched = False
            matched_location = None
            for req_loc in required_locations_lower:
                if req_loc in location_lower or location_lower in req_loc:
                    matched = True
                    matched_location = req_loc
                    break
            
            return {
                "passed": matched,
                "reason": f"候选人地点: {location}, 要求: {required_locations}, 匹配: {matched_location if matched else '无'}",
                "matched_value": location,
                "expected_value": required_locations
            }
            
        except Exception as e:
            logger.error(f"检查地点要求失败: {e}", exc_info=True)
            return {
                "passed": False,
                "reason": f"检查地点要求异常: {str(e)}",
                "matched_value": None,
                "expected_value": rule_config.get("locations")
            }
    
    def _check_custom(self, rule_config: Dict[str, Any], resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """检查自定义规则"""
        try:
            # 自定义规则需要指定字段路径和比较逻辑
            field_path = rule_config.get("field_path")  # 如: "basic_info.name"
            operator = rule_config.get("operator", "==")
            expected_value = rule_config.get("value")
            
            if not field_path:
                return {
                    "passed": False,
                    "reason": "自定义规则未指定字段路径",
                    "matched_value": None,
                    "expected_value": expected_value
                }
            
            # 获取字段值
            matched_value = self._get_nested_value(resume_data, field_path)
            
            if matched_value is None:
                return {
                    "passed": False,
                    "reason": f"字段不存在: {field_path}",
                    "matched_value": None,
                    "expected_value": expected_value
                }
            
            # 执行比较
            passed = self._compare_values(matched_value, expected_value, operator)
            
            return {
                "passed": passed,
                "reason": f"字段 {field_path}: {matched_value}, 要求: {expected_value}, 操作符: {operator}",
                "matched_value": matched_value,
                "expected_value": expected_value
            }
            
        except Exception as e:
            logger.error(f"检查自定义规则失败: {e}", exc_info=True)
            return {
                "passed": False,
                "reason": f"检查自定义规则异常: {str(e)}",
                "matched_value": None,
                "expected_value": rule_config.get("value")
            }
    
    # ========== 辅助方法 ==========
    
    def _get_highest_degree(self, education_list: List[Dict[str, Any]]) -> str:
        """获取最高学历"""
        degree_levels = {
            "博士": 5, "硕士": 4, "本科": 3, "专科": 2, "高中": 1, "初中": 0
        }
        
        highest_level = -1
        highest_degree = "无"
        
        for edu in education_list:
            degree = edu.get("degree") or edu.get("education_level", "")
            level = degree_levels.get(degree, 0)
            if level > highest_level:
                highest_level = level
                highest_degree = degree
        
        return highest_degree
    
    def _calculate_total_experience_years(self, work_experiences: List[Dict[str, Any]]) -> float:
        """计算总工作经验（年）"""
        import datetime
        import re
        
        total_days = 0
        
        def parse_date(date_str: str) -> Optional[datetime.datetime]:
            """解析日期字符串（支持YYYY-MM格式）"""
            if not date_str:
                return None
            try:
                # 尝试解析YYYY-MM格式
                match = re.match(r'(\d{4})-(\d{1,2})', date_str)
                if match:
                    year, month = int(match.group(1)), int(match.group(2))
                    return datetime.datetime(year, month, 1)
                # 尝试解析YYYY.MM格式
                match = re.match(r'(\d{4})\.(\d{1,2})', date_str)
                if match:
                    year, month = int(match.group(1)), int(match.group(2))
                    return datetime.datetime(year, month, 1)
                return None
            except Exception:
                return None
        
        for exp in work_experiences:
            start_date_str = exp.get("start_date")
            end_date_str = exp.get("end_date")
            is_current = exp.get("is_current", False)
            
            if not start_date_str:
                continue
            
            try:
                # 解析开始日期
                start_date = parse_date(start_date_str)
                if not start_date:
                    continue
                
                # 解析结束日期
                if is_current or not end_date_str:
                    end_date = datetime.datetime.now()
                else:
                    end_date = parse_date(end_date_str)
                    if not end_date:
                        end_date = datetime.datetime.now()
                
                # 计算天数
                days = (end_date - start_date).days
                if days > 0:
                    total_days += days
                    
            except Exception as e:
                logger.warning(f"解析工作经历日期失败: {e}")
                continue
        
        # 转换为年（按365天计算）
        return round(total_days / 365.0, 1)
    
    def _calculate_age(self, birth_date: str) -> int:
        """计算年龄"""
        import datetime
        import re
        
        try:
            # 解析日期（支持YYYY-MM或YYYY.MM格式）
            match = re.match(r'(\d{4})[-.](\d{1,2})(?:[-.](\d{1,2}))?', birth_date)
            if match:
                year, month = int(match.group(1)), int(match.group(2))
                day = int(match.group(3)) if match.group(3) else 1
                birth = datetime.datetime(year, month, day)
            else:
                # 尝试其他格式
                return 0
            
            today = datetime.datetime.now()
            age = today.year - birth.year
            
            # 检查是否已过生日
            if (today.month, today.day) < (birth.month, birth.day):
                age -= 1
            
            return age
        except Exception as e:
            logger.warning(f"计算年龄失败: {e}")
            return 0
    
    def _compare_values(self, value1: Any, value2: Any, operator: str) -> bool:
        """比较两个值"""
        try:
            if operator == "==":
                return value1 == value2
            elif operator == "!=":
                return value1 != value2
            elif operator == ">":
                return value1 > value2
            elif operator == ">=":
                return value1 >= value2
            elif operator == "<":
                return value1 < value2
            elif operator == "<=":
                return value1 <= value2
            elif operator == "in":
                return value1 in value2 if isinstance(value2, (list, tuple)) else False
            elif operator == "not_in":
                return value1 not in value2 if isinstance(value2, (list, tuple)) else True
            else:
                logger.warning(f"未知的操作符: {operator}")
                return False
        except Exception as e:
            logger.error(f"比较值失败: {e}")
            return False
    
    def _get_nested_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """获取嵌套字段值"""
        try:
            keys = field_path.split(".")
            value = data
            for key in keys:
                if isinstance(value, dict):
                    value = value.get(key)
                else:
                    return None
            return value
        except Exception as e:
            logger.error(f"获取嵌套字段值失败: {e}")
            return None
    
    def _generate_summary(self, passed: bool, failed_rules: List[Dict], total_rules: int) -> str:
        """生成筛选摘要"""
        if passed:
            return f"通过所有筛选规则（共{total_rules}条）"
        else:
            failed_count = len(failed_rules)
            failed_names = [r["rule_name"] for r in failed_rules]
            return f"未通过{failed_count}条规则（共{total_rules}条）: {', '.join(failed_names)}"

