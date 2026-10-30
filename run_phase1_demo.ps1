# Phase 1 PoC 一键启动脚本
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " 🚀 正在启动 Phase 1: Loki 日志清洗 PoC 演练环境" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. 检查并建立 Loki 端口转发 (3100)
$lokiConn = Get-NetTCPConnection -LocalPort 3100 -ErrorAction SilentlyContinue
if (-not $lokiConn) {
    Write-Host "[1/2] 正在后台启动 kubectl port-forward 到 Loki (3100)..." -ForegroundColor Yellow
    Start-Job -Name "LokiPortForward" -ScriptBlock { kubectl port-forward -n monitoring svc/loki 3100:3100 } | Out-Null
    Start-Sleep -Seconds 2
} else {
    Write-Host "[1/2] Loki 端口转发已处于监听状态 (Port 3100)" -ForegroundColor Green
}

# 2. 启动 FastAPI 交互式演示微服务 (8088)
Write-Host "[2/2] 正在启动 Loki Cleaner WebUI (Port 8088)..." -ForegroundColor Yellow
Write-Host "📍 WebUI 访问地址: http://localhost:8088" -ForegroundColor Green
python loki_cleaner_demo.py
