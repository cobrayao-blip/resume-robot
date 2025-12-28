# Docker 部署指南

本文档说明如何使用 Docker 部署 ResumeAI Platform 项目。

## 前置要求

- Docker Desktop（Windows/Mac）或 Docker Engine（Linux）
- Docker Compose v2.0+
- 至少 4GB 可用内存
- DeepSeek API Key

## 快速开始

### 1. 配置环境变量

复制环境变量示例文件并修改：

```bash
# Windows PowerShell
Copy-Item env.example .env

# Linux/Mac
cp env.example .env
```

编辑 `.env` 文件，至少需要设置以下变量：

```env
# 必需：DeepSeek API Key
DEEPSEEK_API_KEY=your-deepseek-api-key-here

# 推荐：生产环境密钥（至少32字符）
SECRET_KEY=your-secret-key-change-in-production-min-32-chars
```

### 2. 启动所有服务

```bash
# 构建并启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 3. 访问应用

- **前端应用**: http://localhost:5173
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

## 服务说明

### 数据库服务 (PostgreSQL)

- **容器名**: `resume_db`
- **端口**: `5432`
- **数据持久化**: Docker volume `db_data`
- **健康检查**: 自动检测数据库就绪状态

### Redis 服务

- **容器名**: `resume_redis`
- **端口**: `6379`
- **用途**: 缓存和会话存储

### MongoDB 服务

- **容器名**: `resume_mongodb`
- **端口**: `27017`
- **用途**: 存储岗位画像、简历解析结果、匹配详情等文档数据
- **数据持久化**: Docker volume `mongodb_data`

### Milvus 服务（向量数据库）

- **容器名**: `resume_milvus`
- **端口**: `19530` (API), `9091` (健康检查)
- **用途**: 向量相似度搜索（简历与岗位匹配）
- **依赖**: etcd (元数据存储), MinIO (对象存储)
- **数据持久化**: Docker volume `milvus_data`

### etcd 服务

- **容器名**: `resume_etcd`
- **用途**: Milvus 的元数据存储后端

### MinIO 服务

- **容器名**: `resume_minio`
- **用途**: Milvus 的对象存储后端

### 后端服务 (FastAPI)

- **容器名**: `resume_backend`
- **端口**: `8000`
- **功能**:
  - 自动运行数据库迁移
  - 提供 RESTful API
  - 集成 DeepSeek AI

### 前端服务 (React + Vite)

- **容器名**: `resume_frontend`
- **端口**: `5173`
- **功能**: 用户界面和模板设计器

## 常用命令

### 启动服务

```bash
# 启动所有服务（后台运行）
docker-compose up -d

# 启动并查看日志
docker-compose up

# 只启动数据库和 Redis
docker-compose up -d db redis
```

### 停止服务

```bash
# 停止所有服务
docker-compose stop

# 停止并删除容器
docker-compose down

# 停止并删除容器、卷（⚠️ 会删除数据库数据）
docker-compose down -v
```

### 查看日志

```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f db
```

### 重建服务

```bash
# 重建并启动所有服务
docker-compose up -d --build

# 只重建后端
docker-compose build backend
docker-compose up -d backend

# 只重建前端
docker-compose build frontend
docker-compose up -d frontend
```

### 执行命令

```bash
# 进入后端容器
docker-compose exec backend bash

# 运行数据库迁移
docker-compose exec backend alembic upgrade head

# 创建新的数据库迁移
docker-compose exec backend alembic revision --autogenerate -m "description"

# 进入数据库
docker-compose exec db psql -U resume_user -d resume_db
```

## 环境变量配置

### 必需变量

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | `sk-xxxxx` |

### 可选变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `DATABASE_URL` | 数据库连接字符串 | `postgresql://resume_user:password@db:5432/resume_db` |
| `REDIS_URL` | Redis 连接字符串 | `redis://redis:6379` |
| `MONGODB_URL` | MongoDB 连接字符串 | `mongodb://resume_user:password@mongodb:27017/resume_robot?authSource=admin` |
| `MILVUS_HOST` | Milvus 服务地址 | `milvus` |
| `MILVUS_PORT` | Milvus 服务端口 | `19530` |
| `MINIO_ACCESS_KEY` | MinIO 访问密钥 | `minioadmin` |
| `MINIO_SECRET_KEY` | MinIO 密钥 | `minioadmin` |
| `SECRET_KEY` | JWT 密钥 | 自动生成（不推荐生产环境） |
| `DEBUG` | 调试模式 | `True` |
| `CORS_ORIGINS` | CORS 允许的来源 | `http://localhost:3000,http://localhost:5173` |
| `VITE_API_BASE` | 前端 API 基础 URL | `http://localhost:8000/api/v1` |

## 故障排查

### 1. 后端无法启动

**问题**: 后端容器启动失败

**解决方案**:
```bash
# 查看后端日志
docker-compose logs backend

# 检查环境变量
docker-compose exec backend env | grep DEEPSEEK_API_KEY

# 检查数据库连接
docker-compose exec backend python -c "from app.core.database import engine; print(engine)"
```

### 2. 数据库连接失败

**问题**: `could not connect to server`

**解决方案**:
```bash
# 检查数据库容器状态
docker-compose ps db

# 检查数据库日志
docker-compose logs db

# 等待数据库就绪（健康检查会自动处理）
docker-compose up -d db
# 等待 10-20 秒后再启动后端
```

### 3. 前端无法访问后端 API

**问题**: CORS 错误或网络请求失败

**解决方案**:
1. 检查 `VITE_API_BASE` 环境变量是否正确
2. 检查后端 CORS 配置
3. 确保后端服务已启动：`docker-compose ps backend`

### 4. 端口被占用

**问题**: `port is already allocated`

**解决方案**:
```bash
# Windows PowerShell - 查找占用端口的进程
netstat -ano | findstr :8000
netstat -ano | findstr :5173
netstat -ano | findstr :5432

# 修改 docker-compose.yml 中的端口映射
# 例如：将 "8000:8000" 改为 "8001:8000"
```

### 5. 数据库迁移失败

**问题**: `alembic upgrade head` 失败

**解决方案**:
```bash
# 手动运行迁移
docker-compose exec backend alembic upgrade head

# 查看迁移历史
docker-compose exec backend alembic history

# 回滚到上一个版本
docker-compose exec backend alembic downgrade -1
```

## 生产环境部署建议

### 1. 安全配置

- ✅ 修改默认数据库密码
- ✅ 设置强 `SECRET_KEY`（至少32字符）
- ✅ 设置 `DEBUG=False`
- ✅ 配置 HTTPS（使用 Nginx 反向代理）
- ✅ 限制 CORS 来源

### 2. 性能优化

- 使用生产级数据库配置
- 配置 Redis 持久化
- 启用后端服务的工作进程（Gunicorn + Uvicorn）
- 使用 CDN 加速前端资源

### 3. 监控和日志

- 配置日志收集（如 ELK Stack）
- 设置健康检查监控
- 配置资源使用告警

### 4. 备份策略

```bash
# 备份数据库
docker-compose exec db pg_dump -U resume_user resume_db > backup.sql

# 恢复数据库
docker-compose exec -T db psql -U resume_user resume_db < backup.sql
```

## 开发模式

开发模式下，代码通过 volume 挂载，修改代码后会自动重载：

- **后端**: FastAPI 的 `--reload` 模式会自动检测代码变化
- **前端**: Vite 的热模块替换（HMR）会自动更新

## 数据持久化

以下数据会持久化到 Docker volumes：

- `db_data`: PostgreSQL 数据库数据
- `redis_data`: Redis 数据
- `mongodb_data`: MongoDB 数据库数据
- `etcd_data`: etcd 元数据
- `minio_data`: MinIO 对象存储数据
- `milvus_data`: Milvus 向量数据库数据
- `backend_export`: 导出的 Word 文档

查看 volumes:
```bash
docker volume ls
docker volume inspect resume-ai-platform-v2_db_data
```

## 清理资源

```bash
# 停止并删除所有容器
docker-compose down

# 删除所有容器和数据卷（⚠️ 会删除数据库数据）
docker-compose down -v

# 删除未使用的镜像
docker image prune

# 清理所有未使用的资源
docker system prune -a
```

## 更新应用

```bash
# 1. 拉取最新代码
git pull

# 2. 重建并重启服务
docker-compose up -d --build

# 3. 运行数据库迁移（如果有）
docker-compose exec backend alembic upgrade head
```

## 支持

如有问题，请查看：
- 项目 README.md
- API 文档: http://localhost:8000/docs
- 服务日志: `docker-compose logs`

