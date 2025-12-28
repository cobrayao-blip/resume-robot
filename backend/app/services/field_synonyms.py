"""
字段同义词映射表
用于帮助AI识别不同表达方式但含义相同的字段
"""
FIELD_SYNONYMS = {
    # 基本信息
    "name": ["姓名", "名字", "name", "姓名", "全名", "真实姓名"],
    "phone": ["电话", "手机", "手机号", "联系电话", "phone", "mobile", "telephone", "联系方式", "联系电话", "手机号码"],
    "email": ["邮箱", "电子邮件", "email", "e-mail", "电子邮箱", "邮件地址", "邮箱地址"],
    "location": ["地址", "所在地", "居住地", "location", "address", "城市", "现居地", "现居住地", "居住地址"],
    "current_location": ["现居地", "现居住地", "current_location", "当前所在地", "居住地", "location"],
    "work_location": ["工作地点", "工作地址", "work_location", "工作所在地", "办公地点"],
    "birthday": ["出生日期", "出生年月", "生日", "birthday", "出生时间", "出生年月日", "出生年", "出生年月", "birth_date", "出生日期", "出生年月日"],
    "birth_date": ["出生日期", "出生年月", "生日", "birthday", "出生时间", "出生年月日", "出生年", "出生年月", "birth_date", "出生日期", "出生年月日"],
    "gender": ["性别", "gender", "性別", "性别", "性", "男", "女"],
    "website": ["个人网站", "网站", "website", "主页", "个人主页", "website_url", "个人网址"],
    "website_url": ["个人网站", "网站", "website", "主页", "个人主页", "website_url", "个人网址"],
    "github": ["github", "GitHub", "代码仓库", "GitHub地址"],
    "linkedin": ["linkedin", "LinkedIn", "领英", "linkedin_url"],
    "linkedin_url": ["linkedin", "LinkedIn", "领英", "linkedin_url"],
    "hometown": ["籍贯", "hometown", "户籍", "原籍", "祖籍"],
    "marital_status": ["婚育状态", "婚姻状况", "marital_status", "婚育", "婚姻", "婚否"],
    "family_location": ["家庭所在", "家庭所在地", "family_location", "家庭地址", "家庭住址"],
    "current_work_location": ["现工作地", "当前工作地", "current_work_location", "工作所在地", "现工作地点"],
    "current_location": ["现工作地", "当前工作地", "current_location", "工作所在地", "现工作地点", "current_work_location"],
    "wechat": ["微信", "微信号", "wechat", "WeChat", "微信账号"],
    "onboard_date": ["入职时间", "onboard_date", "entry_time", "入职日期", "到岗时间", "可入职时间"],
    "other_info": ["其他信息", "other_info", "备注", "其他", "补充信息", "附加信息"],
    
    # 工作经历
    "company": ["公司", "公司名称", "企业", "单位", "company", "employer", "工作单位", "就职公司"],
    "position": ["职位", "岗位", "工作名称", "职务", "position", "job_title", "title", "职位名称", "工作岗位"],
    "start_date": ["开始时间", "入职时间", "start_date", "入职日期", "开始日期", "起始时间"],
    "end_date": ["结束时间", "离职时间", "end_date", "离职日期", "结束日期", "终止时间"],
    "period": ["时间", "时间段", "工作期间", "period", "工作年限", "在职时间"],
    "responsibilities": ["工作职责", "职责", "responsibilities", "工作内容", "主要工作", "负责内容"],
    "achievements": ["工作业绩", "业绩", "achievements", "工作成果", "成就", "主要成就"],
    "reason_for_leaving": ["离职原因", "离职", "reason_for_leaving", "离开原因", "辞职原因"],
    "report_to": ["汇报对象", "上级", "report_to", "直属领导", "汇报人"],
    "team_size": ["团队规模", "下属团队", "team_size", "团队人数", "管理团队"],
    
    # 教育背景
    "school": ["学校", "学校名称", "院校", "school", "university", "college", "毕业院校", "就读学校"],
    "major": ["专业", "专业名称", "major", "所学专业", "专业方向"],
    "degree": ["学位", "degree", "学术学位"],
    "education_level": ["学历", "教育水平", "education_level", "学历层次", "教育程度", "教育层次"],
    # 教育背景的时间字段（注意：start_date和end_date在工作经历中也有定义，这里添加教育背景特有的同义词）
    "education_start_date": ["入学时间", "就读时间", "入学日期", "就读日期", "开始时间", "start_date"],
    "education_end_date": ["毕业时间", "毕业日期", "毕业年月", "毕业年份", "结束时间", "end_date", "graduation_date"],
    "graduation_date": ["毕业时间", "毕业日期", "graduation_date", "毕业年月", "毕业年份"],
    
    # 技能
    "technical": ["技术技能", "专业技能", "technical", "技术能力", "专业技能"],
    "soft": ["软技能", "soft", "通用技能", "综合素质"],
    "languages": ["语言", "语言能力", "languages", "外语能力", "语言技能"],
    
    # 项目
    "project_name": ["项目名称", "项目", "project_name", "项目名"],
    "description": ["描述", "项目描述", "description", "简介", "项目简介"],
    "role": ["角色", "担任角色", "role", "职责", "在项目中的角色"],
    "outcome": ["成果", "项目成果", "outcome", "成果", "项目产出"],
    
    # 评价
    "overall": ["总体评价", "综合评价", "overall", "整体评价"],
    "advantages": ["优势", "优点", "advantages", "强项"],
    "risks": ["风险", "不足", "risks", "劣势"],
    "advice": ["建议", "建议", "advice", "推荐建议"],
    
    # 薪资
    "expected_salary": ["期望薪资", "期望工资", "expected_salary", "期望薪酬"],
    "current_salary": ["当前薪资", "现薪资", "current_salary", "当前工资"],
    "target_salary": ["目标薪资", "目标工资", "target_salary", "目标薪酬"],
}

def get_field_synonyms(field_name: str) -> list:
    """
    获取字段的同义词列表
    返回包含字段本身及其所有同义词的列表
    """
    field_lower = field_name.lower().strip()
    
    # 直接匹配
    if field_lower in FIELD_SYNONYMS:
        return FIELD_SYNONYMS[field_lower]
    
    # 反向查找：检查字段名是否在某个同义词列表中
    for key, synonyms in FIELD_SYNONYMS.items():
        if field_name in synonyms or field_lower in [s.lower() for s in synonyms]:
            return synonyms
    
    # 如果没有找到，返回字段名本身
    return [field_name]

def normalize_field_name(field_name: str) -> str:
    """
    将字段名标准化为规范形式
    返回最常用的标准字段名
    """
    field_lower = field_name.lower().strip()
    
    # 直接匹配
    if field_lower in FIELD_SYNONYMS:
        return field_lower
    
    # 反向查找
    for key, synonyms in FIELD_SYNONYMS.items():
        if field_name in synonyms or field_lower in [s.lower() for s in synonyms]:
            return key
    
    # 如果没有找到，返回原字段名
    return field_name

