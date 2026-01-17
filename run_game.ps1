# Coveo Blitz - Run Bot on Actual Game Server
# Usage: .\run_game.ps1 -ServerUri "wss://your-game-server.com" -Token "your-token"

param(
    [string]$ServerUri = "ws://127.0.0.1:8765",
    [string]$Token = "",
    [string]$TeamName = "MyPythonicBot"
)

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "    Coveo Blitz Bot Launcher" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Set environment variables
$env:GAME_SERVER_URI = $ServerUri

if ($Token -ne "") {
    $env:TOKEN = $Token
    Write-Host "Running with TOKEN authentication" -ForegroundColor Green
} else {
    Remove-Item Env:\TOKEN -ErrorAction SilentlyContinue
    Write-Host "Running with team name: $TeamName" -ForegroundColor Yellow
}

Write-Host "Server URI: $ServerUri" -ForegroundColor Cyan
Write-Host ""
Write-Host "Starting bot..." -ForegroundColor Green
Write-Host ""

# Run the bot
& "C:/Users/raphb/Desktop/coveoBlitz/coveo-blitz/.venv/Scripts/python.exe" application.py
