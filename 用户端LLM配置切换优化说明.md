# 用户端LLM配置切换优化说明

## 问题反馈

用户反馈：
1. 切换provider后，密钥空白，需要重新填写，很不方便
2. 用户的密钥是否储存在数据库，是否进行了脱敏处理？

## 问题分析

### 1. 密钥存储和脱敏

**确认**：
- ✅ 用户的API密钥**确实储存在数据库**中（`UserLLMConfig`表）
- ✅ 后端返回给前端时**进行了脱敏处理**：
  - 格式：前4位 + "****" + 后4位
  - 例如：`sk-1****abcd`
  - 代码位置：`backend/app/api/v1/endpoints/users.py` 第94-95行

### 2. 切换时密钥空白的问题

**原因**：
- 后端只存储**一个provider的配置**（每个用户只有一条`UserLLMConfig`记录）
- 当用户切换provider时：
  - 如果切换的provider与当前配置的provider**相同**，显示脱敏的密钥 ✅
  - 如果切换的provider与当前配置的provider**不同**，前端会清空API密钥字段 ❌

**问题场景**：
1. 用户配置了千问，切换到deepseek
2. 后端返回的还是千问的配置（脱敏的）
3. 前端检测到provider不同，清空了API密钥字段
4. 用户需要重新输入deepseek的密钥

## 优化方案

### 优化后的逻辑

1. **如果切换的provider与当前配置的provider相同**：
   - 显示后端返回的脱敏密钥（格式：`sk-1****abcd`）
   - 用户可以看到密钥已配置，不需要重新输入

2. **如果切换的provider与当前配置的provider不同**：
   - 检查用户是否正在输入密钥（不是脱敏值）
   - 如果用户正在输入，**保留用户输入的值**（避免丢失用户正在输入的内容）
   - 如果用户没有输入（或显示的是脱敏值），**清空字段**（因为那不是该provider的配置）

### 代码实现

```typescript
const handleProviderChange = async (newProvider: string) => {
  try {
    // 保存当前表单中用户已输入的值
    const currentFormValues = llmForm.getFieldsValue();
    const currentApiKey = currentFormValues.api_key || '';
    // 检查当前输入的密钥是否是脱敏值（包含"****"）
    const isMaskedKey = currentApiKey.includes('****');
    
    // 加载当前配置
    const response = await api.get('/users/me/llm-config');
    const currentProvider = response.data.provider;
    
    if (currentProvider === newProvider) {
      // 相同provider：显示脱敏的密钥
      llmForm.setFieldsValue({
        provider: newProvider,
        api_key: response.data.api_key || '',
        base_url: response.data.base_url || providerDefaults[newProvider]?.base_url || '',
        model_name: response.data.model_name || providerDefaults[newProvider]?.model_name || '',
      });
    } else {
      // 不同provider：保留用户输入的值（如果不是脱敏值），否则清空
      llmForm.setFieldsValue({
        provider: newProvider,
        api_key: (!isMaskedKey && currentApiKey) ? currentApiKey : '',
        base_url: providerDefaults[newProvider]?.base_url || '',
        model_name: providerDefaults[newProvider]?.model_name || '',
      });
    }
  } catch (error: any) {
    // 错误处理...
  }
};
```

## 优化效果

### 优化前
- ❌ 切换provider时，总是清空API密钥字段
- ❌ 用户需要每次都重新输入密钥
- ❌ 如果用户正在输入，切换时会丢失输入的内容

### 优化后
- ✅ 如果该provider已有配置，显示脱敏的密钥（`sk-1****abcd`）
- ✅ 用户可以看到密钥已配置，不需要重新输入
- ✅ 如果用户正在输入密钥，切换时保留用户输入的值
- ✅ 如果显示的是脱敏值（其他provider的配置），切换时清空字段

## 使用场景

### 场景1：切换回已配置的provider
1. 用户配置了千问，切换到deepseek
2. 用户切换回千问
3. **显示**：`sk-1****abcd`（脱敏的千问密钥）
4. 用户可以看到密钥已配置，不需要重新输入 ✅

### 场景2：切换到未配置的provider
1. 用户配置了千问，切换到deepseek
2. **显示**：API密钥字段为空（因为deepseek没有配置）
3. 用户输入deepseek的密钥并保存 ✅

### 场景3：用户正在输入时切换provider
1. 用户正在输入deepseek的密钥（输入了一半）
2. 用户切换到千问查看配置
3. **保留**：用户输入的deepseek密钥（避免丢失）
4. 用户切换回deepseek，可以继续输入 ✅

## 注意事项

1. **脱敏值识别**：
   - 如果API密钥包含"****"，说明是后端返回的脱敏值
   - 如果API密钥不包含"****"，说明是用户输入的完整密钥

2. **后端限制**：
   - 后端只存储一个provider的配置
   - 如果用户想为多个provider分别配置，需要：
     - 配置provider A → 保存
     - 切换到provider B → 输入密钥 → 保存
     - 切换回provider A → 显示脱敏密钥（已配置）

3. **安全性**：
   - 后端返回的密钥是脱敏的，前端无法获取完整密钥
   - 用户需要重新输入完整密钥才能保存新配置

## 相关文件

- `frontend/src/pages/Settings.tsx` - 优化了provider切换逻辑
- `backend/app/api/v1/endpoints/users.py` - 后端密钥脱敏处理

## 优化时间

2025-12-09

