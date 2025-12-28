#!/bin/bash
# Docker 启动脚本 (Bash)
# 用于快速启动 ResumeAI Platform 的所有服务

echo "========================================"
echo "  ResumeAI Platform - Docker 启动脚本"
echo "========================================"
echo ""

# 检查 Docker 是否运行
echo "[1/5] 检查 Docker 环境..."
if ! command -v docker &> /dev/null; then
    echo "✗ Docker 未安装，请先安装 Docker"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "✗ Docker 未运行，请先启动 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "✗ docker-compose 未安装"
    exit 1
fi

echo "✓ Docker 环境正常"

# 检查环境变量文件
echo ""
echo "[2/5] 检查环境变量配置..."
if [ ! -f ".env" ]; then
    echo "⚠ 未找到 .env 文件，正在从 env.example 创建..."
    if [ -f "env.example" ]; then
        cp env.example .env
        echo "✓ 已创建 .env 文件，请编辑并设置 DEEPSEEK_API_KEY"
    else
        echo "✗ 未找到 env.example 文件"
        exit 1
    fi
else
    echo "✓ 找到 .env 文件"
fi

# 检查必需的环境变量
if ! grep -q "DEEPSEEK_API_KEY=.*[^[:space:]]" .env 2>/dev/null; then
    echo "⚠ 警告: .env 文件中未设置 DEEPSEEK_API_KEY"
    echo "  请编辑 .env 文件并设置您的 DeepSeek API Key"
fi

# 停止现有容器（如果有）
echo ""
echo "[3/5] 停止现有容器..."
docker-compose down 2>/dev/null
echo "✓ 完成"

# 构建镜像
echo ""
echo "[4/5] 构建 Docker 镜像..."
docker-compose build
if [ $? -ne 0 ]; then
    echo "✗ 镜像构建失败"
    exit 1
fi
echo "✓ 镜像构建完成"

# 启动服务
echo ""
echo "[5/5] 启动服务..."
docker-compose up -d
if [ $? -ne 0 ]; then
    echo "✗ 服务启动失败"
    exit 1
fi

echo ""
echo "========================================"
echo "  服务启动成功！"
echo "========================================"
echo ""
echo "访问地址:"
echo "  前端应用: http://localhost:5173"
echo "  后端 API: http://localhost:8000"
echo "  API 文档: http://localhost:8000/docs"
echo ""
echo "常用命令:"
echo "  查看日志: docker-compose logs -f"
echo "  停止服务: docker-compose stop"
echo "  查看状态: docker-compose ps"
echo ""
echo "正在显示服务日志（按 Ctrl+C 退出日志查看，服务将继续运行）..."
echo ""

# 等待服务启动
sleep 3

# 显示日志
docker-compose logs -f

