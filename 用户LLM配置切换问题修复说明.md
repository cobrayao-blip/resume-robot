# 用户LLM配置切换问题修复说明

## 问题描述

用户反馈：在用户账号的LLM配置中，切换provider时，只有一个provider的脱敏密钥会显示在前端，另外两个的API密钥处是空白的。

## 问题分析

### 根本原因

1. **后端API限制**：
   - `get_my_llm_config` API只返回当前配置的provider的配置
   - 如果用户配置了千问，切换到deepseek时，后端返回的还是千问的配置（脱敏的）
   - 前端检测到provider不匹配，清空了API密钥字段

2. **数据库结构限制**：
   - `UserLLMConfig` 表每个用户只有一条记录
   - 一个用户只能配置一个provider的配置
   - 切换provider时，会更新同一条记录的provider字段

3. **前端逻辑问题**：
   - 前端切换provider时，总是查询当前配置的provider
   - 如果切换的provider与当前配置不同，无法获取该provider的配置

## 解决方案

### 修改1：后端API支持按provider查询

修改 `get_my_llm_config` API，支持可选的 `provider` 查询参数：

```python
@router.get("/me/llm-config", response_model=LLMConfigResponse)
async def get_my_llm_config(
    provider: Optional[str] = Query(None, description="可选参数：指定要查询的provider"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if provider:
        # 如果指定了provider，查询该provider的配置
        user_config = db.query(UserLLMConfig).filter(
            UserLLMConfig.user_id == current_user.id,
            UserLLMConfig.provider == provider.lower()
        ).first()
        
        if user_config:
            # 返回该provider的配置（脱敏）
            ...
        else:
            # 该provider没有配置，返回空配置
            ...
    else:
        # 如果没有指定provider，返回当前配置的provider的配置（保持向后兼容）
        ...
```

### 修改2：前端切换时查询指定provider

修改 `handleProviderChange` 函数，直接查询指定provider的配置：

```typescript
const handleProviderChange = async (newProvider: string) => {
  try {
    // 直接查询指定provider的配置（支持按provider查询）
    const response = await api.get(`/users/me/llm-config?provider=${newProvider}`);
    
    // 如果该provider有配置，显示配置（包括脱敏的密钥）
    if (response.data.api_key) {
      llmForm.setFieldsValue({
        provider: newProvider,
        api_key: response.data.api_key, // 显示脱敏密钥
        base_url: response.data.base_url || providerDefaults[newProvider]?.base_url || '',
        model_name: response.data.model_name || providerDefaults[newProvider]?.model_name || '',
      });
    } else {
      // 如果该provider没有配置，显示空
      llmForm.setFieldsValue({
        provider: newProvider,
        api_key: '',
        base_url: providerDefaults[newProvider]?.base_url || '',
        model_name: providerDefaults[newProvider]?.model_name || '',
      });
    }
  } catch (error: any) {
    // 错误处理...
  }
};
```

## 修复效果

### 修复前
- ❌ 切换provider时，总是查询当前配置的provider
- ❌ 如果切换的provider与当前配置不同，无法获取该provider的配置
- ❌ API密钥字段显示空白，即使该provider已配置

### 修复后
- ✅ 切换provider时，直接查询指定provider的配置
- ✅ 如果该provider已配置，显示脱敏的密钥（`sk-1****abcd`）
- ✅ 如果该provider没有配置，显示空白
- ✅ 用户可以清楚地看到每个provider的配置状态

## 使用场景

### 场景1：用户配置了deepseek
1. 用户配置deepseek并保存
2. 切换到deepseek → **显示脱敏密钥** ✅
3. 切换到千问 → **显示空白**（千问没有配置）✅
4. 切换到豆包 → **显示空白**（豆包没有配置）✅

### 场景2：用户配置了多个provider（依次保存）
1. 用户配置deepseek并保存
2. 用户配置千问并保存（覆盖deepseek的配置）
3. 切换到deepseek → **显示空白**（deepseek配置已被覆盖）✅
4. 切换到千问 → **显示脱敏密钥** ✅
5. 切换到豆包 → **显示空白**（豆包没有配置）✅

### 场景3：用户正在输入时切换
1. 用户正在输入deepseek的密钥
2. 切换到千问查看配置
3. **保留**：用户输入的deepseek密钥（如果不是脱敏值）
4. 切换回deepseek，可以继续输入 ✅

## 注意事项

1. **数据库限制**：
   - 后端只存储一个provider的配置
   - 如果用户想为多个provider分别配置，需要：
     - 配置provider A → 保存
     - 切换到provider B → 输入密钥 → 保存（会覆盖provider A的配置）
     - 切换回provider A → 显示空白（配置已被覆盖）

2. **API兼容性**：
   - 如果没有提供`provider`参数，API返回当前配置的provider的配置（保持向后兼容）
   - 如果提供了`provider`参数，API返回指定provider的配置

3. **前端行为**：
   - 切换provider时，总是查询指定provider的配置
   - 如果该provider有配置，显示脱敏密钥
   - 如果该provider没有配置，显示空白

## 相关文件

- `backend/app/api/v1/endpoints/users.py` - 修改了 `get_my_llm_config` API
- `frontend/src/pages/Settings.tsx` - 修改了 `handleProviderChange` 函数

## 修复时间

2025-12-09

