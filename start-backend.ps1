# 后端启动脚本
cd backend
$env:DEEPSEEK_API_KEY='test-key'
$env:DATABASE_URL='postgresql://resume_user:password@localhost:5432/resume_db'
$env:REDIS_URL='redis://localhost:6379'
$env:SECRET_KEY='your-secret-key-change-in-production'
$env:DEBUG='True'

Write-Host "Starting backend server..."
Write-Host "DATABASE_URL: $env:DATABASE_URL"
Write-Host "REDIS_URL: $env:REDIS_URL"

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

