# Coveo Blitz Bot - Deployment Guide

## Running Your Bot

### Local Testing (Default)
```powershell
python application.py
```
This connects to `ws://127.0.0.1:8765` for local testing.

### Actual Game Server

#### Option 1: Using the PowerShell script
```powershell
.\run_game.ps1 -ServerUri "wss://blitz2024.coveo.com" -Token "your-token-here"
```

#### Option 2: Using environment variables
```powershell
$env:GAME_SERVER_URI = "wss://blitz2024.coveo.com"
$env:TOKEN = "your-token-here"
python application.py
```

#### Option 3: Direct command
```powershell
$env:GAME_SERVER_URI = "wss://your-game-server.com"; $env:TOKEN = "your-token"; python application.py
```

## Getting Your Game Server Details

1. **Server URI**: Get this from the Coveo Blitz competition dashboard
   - Usually looks like: `wss://blitz2024.coveo.com` or similar
   - May include a path like: `wss://server.com/game`

2. **TOKEN**: Get your unique token from your team's dashboard
   - This authenticates your bot to the game server
   - Keep it secret!

## Testing Before Deployment

1. Test locally first:
   ```powershell
   python application.py
   ```

2. Make sure your bot logic works as expected

3. Then connect to the actual game server

## Files to Deploy

The `ToPush` directory contains the files you need to submit:
- `application.py`
- `bot.py`
- `game_message.py`
- `requirements.txt`

Or use the `my-bot.zip` file that's already created.

## Common Issues

### Connection Refused
- Check if the game server URI is correct
- Verify your TOKEN is valid
- Make sure the game server is running

### Authentication Failed
- Verify your TOKEN is correct
- Check if you need to register your team first

### WebSocket Errors
- Ensure you're using `wss://` for secure connections (not `ws://`)
- Check firewall settings
