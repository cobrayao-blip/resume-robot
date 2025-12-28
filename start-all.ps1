# 启动所有服务的脚本
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "启动 Resume AI Platform 服务" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan

# 1. 启动数据库和 Redis
Write-Host "[1/3] 启动数据库和 Redis..." -ForegroundColor Yellow
cd $PSScriptRoot
docker-compose up -d db redis
Start-Sleep -Seconds 2
Write-Host "  ✓ 数据库和 Redis 已启动`n" -ForegroundColor Green

# 2. 启动后端服务
Write-Host "[2/3] 启动后端服务..." -ForegroundColor Yellow
$backendScript = @"
cd '$PSScriptRoot\backend'
`$env:DEEPSEEK_API_KEY='test-key'
`$env:DATABASE_URL='postgresql://resume_user:password@localhost:5432/resume_db'
`$env:REDIS_URL='redis://localhost:6379'
`$env:SECRET_KEY='your-secret-key-change-in-production'
`$env:DEBUG='True'
Write-Host '后端服务启动中...' -ForegroundColor Cyan
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
"@
Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendScript
Start-Sleep -Seconds 3
Write-Host "  ✓ 后端服务窗口已打开`n" -ForegroundColor Green

# 3. 启动前端服务
Write-Host "[3/3] 启动前端服务..." -ForegroundColor Yellow
$frontendScript = @"
cd '$PSScriptRoot\frontend'
Write-Host '前端服务启动中...' -ForegroundColor Cyan
npm run dev
"@
Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendScript
Start-Sleep -Seconds 3
Write-Host "  ✓ 前端服务窗口已打开`n" -ForegroundColor Green

# 等待服务启动
Write-Host "等待服务启动..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# 检查服务状态
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "服务访问地址" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan
Write-Host "后端 API:     http://localhost:8000" -ForegroundColor Yellow
Write-Host "API 文档:     http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "前端应用:     http://localhost:5173" -ForegroundColor Yellow
Write-Host "`n测试连接..." -ForegroundColor Cyan

# 测试后端
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 3
    Write-Host "  ✓ 后端服务正常 (状态码: $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ 后端服务可能还在启动中，请稍后访问" -ForegroundColor Yellow
}

# 测试前端
try {
    $response = Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -TimeoutSec 3
    Write-Host "  ✓ 前端服务正常 (状态码: $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "  ⚠ 前端服务可能还在启动中，请查看前端窗口" -ForegroundColor Yellow
}

Write-Host "`n提示: 服务在独立的 PowerShell 窗口中运行" -ForegroundColor Gray
Write-Host "      如需停止服务，请关闭对应的窗口`n" -ForegroundColor Gray

