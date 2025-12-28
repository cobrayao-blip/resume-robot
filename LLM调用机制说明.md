# LLM 调用机制说明

## 概述

当系统中有多个 LLM provider（如 DeepSeek 和豆包）都处于开启状态时，系统**不会同时调用**两个模型，而是使用**顺序 fallback（故障转移）机制**，按优先级选择一个可用的 provider 进行调用。

## 调用顺序和优先级

### 1. 用户配置优先级（最高）

如果用户在前端个人设置中配置了 LLM provider，系统会**优先使用用户配置的 provider**。

**示例**：
- 用户配置了 DeepSeek 作为个人 LLM provider
- 即使系统配置中 DeepSeek 和豆包都开启，系统也会优先使用用户配置的 DeepSeek
- 只有当用户配置的 provider 不可用（已关闭或没有 API key）时，才会 fallback

### 2. 系统默认 Provider（次优先级）

如果没有用户配置，系统会使用初始化时指定的默认 provider。

**默认值**：`deepseek`（在 `LLMService.__init__` 中设置）

**代码位置**：
```python
def __init__(self, db_session=None, provider: str = "deepseek"):
    self.provider = provider.lower()  # 默认是 "deepseek"
```

### 3. Fallback 机制（当默认 provider 不可用时）

如果默认 provider 不可用（已关闭或没有 API key），系统会按顺序尝试其他可用的 provider。

**Fallback 顺序**：按照 `_provider_configs` 字典的定义顺序
1. `deepseek`（第一优先级）
2. `doubao`（第二优先级）

**Fallback 条件**：
- 当前 provider 已关闭（`llm.<provider>.enabled = false`）
- 当前 provider 没有配置 API key
- 当前 provider 的 API key 为空

**代码逻辑**（`_get_api_key` 方法）：
```python
# 只有在当前provider确实没有配置或已关闭，且用户也没有配置时，才进行fallback
if not has_user_config and (not current_provider_enabled or not current_provider_has_key):
    logger.info(f"[LLM] {current_provider.upper()} 不可用，尝试查找其他可用的provider...")
    for provider_name, provider_config in self._provider_configs.items():
        if provider_name == current_provider:
            continue  # 跳过当前provider
        # 检查provider是否启用
        if not self._is_provider_enabled(provider_name, db):
            continue
        fallback_api_key = config_service.get_setting(db, f"{provider_config['config_prefix']}.api_key")
        if fallback_api_key and fallback_api_key.strip():
            logger.info(f"[LLM] 找到可用的provider: {provider_name.upper()}，将使用该provider")
            self.provider = provider_name  # 更新当前provider
            return fallback_api_key
```

## 调用流程示例

### 场景 1：两个 provider 都开启，没有用户配置

**系统状态**：
- DeepSeek：开启，已配置 API key
- 豆包：开启，已配置 API key

**调用流程**：
1. 系统默认使用 `deepseek`（初始化时指定）
2. 检查 `deepseek` 是否启用 → ✅ 已启用
3. 检查 `deepseek` 是否有 API key → ✅ 有 API key
4. **直接使用 DeepSeek，不会尝试豆包**

**结果**：所有调用都使用 DeepSeek

---

### 场景 2：DeepSeek 关闭，豆包开启

**系统状态**：
- DeepSeek：关闭（`llm.deepseek.enabled = false`），已配置 API key
- 豆包：开启，已配置 API key

**调用流程**：
1. 系统默认使用 `deepseek`
2. 检查 `deepseek` 是否启用 → ❌ 已关闭
3. 触发 fallback 机制
4. 遍历其他 provider，找到 `doubao`
5. 检查 `doubao` 是否启用 → ✅ 已启用
6. 检查 `doubao` 是否有 API key → ✅ 有 API key
7. **使用豆包**

**结果**：所有调用都使用豆包

---

### 场景 3：DeepSeek 开启但没有 API key，豆包开启且有 API key

**系统状态**：
- DeepSeek：开启，**没有配置 API key**
- 豆包：开启，已配置 API key

**调用流程**：
1. 系统默认使用 `deepseek`
2. 检查 `deepseek` 是否启用 → ✅ 已启用
3. 检查 `deepseek` 是否有 API key → ❌ 没有 API key
4. 触发 fallback 机制
5. 遍历其他 provider，找到 `doubao`
6. 检查 `doubao` 是否启用 → ✅ 已启用
7. 检查 `doubao` 是否有 API key → ✅ 有 API key
8. **使用豆包**

**结果**：所有调用都使用豆包

---

### 场景 4：用户配置了豆包，系统配置中两个都开启

**系统状态**：
- DeepSeek：开启，已配置 API key
- 豆包：开启，已配置 API key
- **用户个人配置**：使用豆包

**调用流程**：
1. 检查用户配置 → ✅ 用户配置了豆包
2. 检查用户配置的 provider（豆包）是否启用 → ✅ 已启用
3. **直接使用用户配置的豆包，不会尝试 DeepSeek**

**结果**：所有调用都使用豆包（用户配置优先）

---

### 场景 5：两个 provider 都关闭

**系统状态**：
- DeepSeek：关闭
- 豆包：关闭

**调用流程**：
1. 系统默认使用 `deepseek`
2. 检查 `deepseek` 是否启用 → ❌ 已关闭
3. 触发 fallback 机制
4. 遍历其他 provider，所有 provider 都已关闭
5. **抛出错误**：`所有LLM provider都已关闭，请至少启用一个provider`

**结果**：调用失败，返回错误

## 关键代码位置

### 1. Provider 选择逻辑
- **文件**：`backend/app/services/llm_service.py`
- **方法**：`_get_provider()`（第 338 行）
- **说明**：返回当前使用的 provider（优先用户配置）

### 2. API Key 获取和 Fallback 逻辑
- **文件**：`backend/app/services/llm_service.py`
- **方法**：`_get_api_key()`（第 201 行）
- **说明**：获取 API key，如果当前 provider 不可用，会 fallback 到其他 provider

### 3. Provider 启用状态检查
- **文件**：`backend/app/services/llm_service.py`
- **方法**：`_is_provider_enabled()`（第 168 行）
- **说明**：检查 provider 是否在系统配置中启用

### 4. 实际调用
- **文件**：`backend/app/services/llm_service.py`
- **方法**：`chat_completion()`（第 351 行）
- **说明**：执行实际的 LLM API 调用

## 重要说明

### ❌ 不是并发调用
系统**不会同时调用**两个模型，每次调用只会使用一个 provider。

### ✅ 是顺序 Fallback
如果第一个 provider 不可用，才会尝试第二个 provider。

### ✅ 用户配置优先
如果用户配置了个人 LLM provider，系统会优先使用用户配置，忽略系统默认设置。

### ✅ 一次调用只用一个 Provider
每次 `chat_completion` 调用只会使用一个 provider，不会在同一个调用中切换 provider。

## 日志示例

系统会在日志中记录 provider 选择过程：

```
[LLM] 调用开始: 3条消息, 模型: deepseek-chat, 请求大小: 2KB
[LLM DEEPSEEK] 调用成功，耗时: 1.23秒
```

如果发生 fallback：
```
[LLM] DEEPSEEK 已关闭，尝试查找其他可用的provider...
[LLM] 找到可用的provider: DOUBAO，将使用该provider
[LLM] 调用开始: 3条消息, 模型: doubao-seed-1-6-thinking-250715, 请求大小: 2KB
[LLM DOUBAO] 调用成功，耗时: 1.45秒
```

## 总结

1. **调用方式**：顺序调用，不是并发调用
2. **优先级**：用户配置 > 系统默认 > Fallback
3. **Fallback 触发**：当前 provider 不可用（已关闭或没有 API key）
4. **Fallback 顺序**：deepseek → doubao（按配置字典顺序）
5. **一次调用一个 Provider**：每次调用只使用一个 provider

