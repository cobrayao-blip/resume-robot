# Docker 启动脚本 (PowerShell)
# 用于快速启动 ResumeAI Platform 的所有服务

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ResumeAI Platform - Docker 启动脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Docker 是否运行
Write-Host "[1/5] 检查 Docker 环境..." -ForegroundColor Yellow
try {
    docker --version | Out-Null
    docker-compose --version | Out-Null
    Write-Host "✓ Docker 环境正常" -ForegroundColor Green
} catch {
    Write-Host "✗ Docker 未安装或未运行，请先启动 Docker Desktop" -ForegroundColor Red
    exit 1
}

# 检查环境变量文件
Write-Host ""
Write-Host "[2/5] 检查环境变量配置..." -ForegroundColor Yellow
if (-Not (Test-Path ".env")) {
    Write-Host "⚠ 未找到 .env 文件，正在从 env.example 创建..." -ForegroundColor Yellow
    if (Test-Path "env.example") {
        Copy-Item "env.example" ".env"
        Write-Host "✓ 已创建 .env 文件，请编辑并设置 DEEPSEEK_API_KEY" -ForegroundColor Green
    } else {
        Write-Host "✗ 未找到 env.example 文件" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✓ 找到 .env 文件" -ForegroundColor Green
}

# 检查必需的环境变量
$envContent = Get-Content ".env" -Raw
if ($envContent -notmatch "DEEPSEEK_API_KEY\s*=\s*[^\s]") {
    Write-Host "⚠ 警告: .env 文件中未设置 DEEPSEEK_API_KEY" -ForegroundColor Yellow
    Write-Host "  请编辑 .env 文件并设置您的 DeepSeek API Key" -ForegroundColor Yellow
}

# 停止现有容器（如果有）
Write-Host ""
Write-Host "[3/5] 停止现有容器..." -ForegroundColor Yellow
docker-compose down 2>$null
Write-Host "✓ 完成" -ForegroundColor Green

# 构建镜像
Write-Host ""
Write-Host "[4/5] 构建 Docker 镜像..." -ForegroundColor Yellow
docker-compose build
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 镜像构建失败" -ForegroundColor Red
    exit 1
}
Write-Host "✓ 镜像构建完成" -ForegroundColor Green

# 启动服务
Write-Host ""
Write-Host "[5/5] 启动服务..." -ForegroundColor Yellow
docker-compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ 服务启动失败" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  服务启动成功！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "访问地址:" -ForegroundColor Yellow
Write-Host "  前端应用: http://localhost:5173" -ForegroundColor White
Write-Host "  后端 API: http://localhost:8000" -ForegroundColor White
Write-Host "  API 文档: http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "常用命令:" -ForegroundColor Yellow
Write-Host "  查看日志: docker-compose logs -f" -ForegroundColor White
Write-Host "  停止服务: docker-compose stop" -ForegroundColor White
Write-Host "  查看状态: docker-compose ps" -ForegroundColor White
Write-Host ""
Write-Host "正在显示服务日志（按 Ctrl+C 退出日志查看，服务将继续运行）..." -ForegroundColor Cyan
Write-Host ""

# 等待服务启动
Start-Sleep -Seconds 3

# 显示日志
docker-compose logs -f
