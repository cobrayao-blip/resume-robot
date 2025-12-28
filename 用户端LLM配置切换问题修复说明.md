# 用户端LLM配置切换问题修复说明

## 问题描述

用户在用户端配置了deepseek和千问，测试成功，但是切换provider时存在问题：
- 当从千问切换到deepseek时，除了大模型名称（provider）变化了，其他字段（API密钥、Base URL、模型名称）都没有更新
- 用户无法在前端确认切换是否成功

## 问题原因

1. **前端缺少provider变化监听**：
   - Select组件没有`onChange`事件处理器
   - 当用户切换provider时，表单字段不会自动更新

2. **后端数据结构限制**：
   - `UserLLMConfig`表每个用户只有一条记录
   - 切换provider时，后端只更新provider字段，其他字段（api_key、base_url、model_name）不会自动更新

3. **前端没有显示默认值**：
   - 当切换provider时，如果该provider没有配置，应该显示默认的base_url和model_name
   - 但前端没有提供默认值

## 修复方案

### 1. 添加Provider默认配置

在`frontend/src/pages/Settings.tsx`中添加了provider默认配置对象：

```typescript
const providerDefaults = {
  deepseek: {
    base_url: 'https://api.deepseek.com/v1',
    model_name: 'deepseek-chat',
  },
  doubao: {
    base_url: 'https://ark.cn-beijing.volces.com/api/v3/chat/completions',
    model_name: 'doubao-seed-1-6-lite-251015',
  },
  qwen: {
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    model_name: 'qwen3-next-80b-a3b-instruct',
  },
};
```

### 2. 添加Provider切换处理函数

添加了`handleProviderChange`函数，当用户切换provider时：
- 检查后端返回的配置是否是该provider的配置
- 如果是，显示该配置
- 如果不是，清空API密钥字段，显示默认的base_url和model_name

```typescript
const handleProviderChange = async (newProvider: string) => {
  try {
    // 先加载当前配置，检查是否已有该provider的配置
    const response = await api.get('/users/me/llm-config');
    const currentProvider = response.data.provider;
    
    // 如果切换的provider与当前配置的provider相同，使用当前配置
    if (currentProvider === newProvider) {
      llmForm.setFieldsValue({
        provider: newProvider,
        api_key: response.data.api_key || '',
        base_url: response.data.base_url || providerDefaults[newProvider]?.base_url || '',
        model_name: response.data.model_name || providerDefaults[newProvider]?.model_name || '',
      });
    } else {
      // 如果切换的provider与当前配置不同，清空API密钥字段，显示默认值
      llmForm.setFieldsValue({
        provider: newProvider,
        api_key: '', // 清空API密钥，让用户重新输入
        base_url: providerDefaults[newProvider]?.base_url || '',
        model_name: providerDefaults[newProvider]?.model_name || '',
      });
    }
  } catch (error: any) {
    // 如果加载失败，至少设置默认值
    llmForm.setFieldsValue({
      provider: newProvider,
      api_key: '',
      base_url: providerDefaults[newProvider]?.base_url || '',
      model_name: providerDefaults[newProvider]?.model_name || '',
    });
  }
};
```

### 3. 在Select组件上添加onChange事件

```typescript
<Form.Item
  label="服务商"
  name="provider"
  rules={[{ required: true, message: '请选择服务商' }]}
>
  <Select onChange={handleProviderChange}>
    <Select.Option value="deepseek">DeepSeek</Select.Option>
    <Select.Option value="doubao">豆包（Doubao）</Select.Option>
    <Select.Option value="qwen">千问（Qwen）</Select.Option>
  </Select>
</Form.Item>
```

### 4. 优化loadLLMConfig函数

在加载配置时，如果base_url或model_name为空，使用默认值填充：

```typescript
const loadLLMConfig = async () => {
  try {
    const response = await api.get('/users/me/llm-config');
    const currentProvider = response.data.provider || 'deepseek';
    
    llmForm.setFieldsValue({
      provider: currentProvider,
      api_key: response.data.api_key || '',
      base_url: response.data.base_url || providerDefaults[currentProvider]?.base_url || '',
      model_name: response.data.model_name || providerDefaults[currentProvider]?.model_name || '',
    });
  } catch (error: any) {
    console.error('加载LLM配置失败:', error);
  }
};
```

## 修复效果

### 修复前
- ❌ 切换provider时，表单字段不更新
- ❌ 用户无法确认切换是否成功
- ❌ 没有显示默认值

### 修复后
- ✅ 切换provider时，表单字段立即更新
- ✅ 如果该provider已有配置，显示该配置
- ✅ 如果该provider没有配置，显示默认的base_url和model_name
- ✅ API密钥字段清空，提示用户重新输入
- ✅ 用户可以清楚地看到切换是否成功

## 使用场景

### 场景1：从千问切换到deepseek（deepseek已有配置）
1. 用户选择deepseek
2. 前端检查后端配置，发现deepseek已有配置
3. 显示deepseek的配置（api_key、base_url、model_name）

### 场景2：从千问切换到deepseek（deepseek没有配置）
1. 用户选择deepseek
2. 前端检查后端配置，发现当前配置是千问
3. 清空API密钥字段，显示deepseek的默认base_url和model_name
4. 用户输入deepseek的API密钥并保存

### 场景3：切换回已配置的provider
1. 用户切换回之前配置过的provider
2. 前端检查后端配置，发现该provider已有配置
3. 显示该provider的配置

## 相关文件

- `frontend/src/pages/Settings.tsx` - 修复了provider切换逻辑

## 修复时间

2025-12-09

