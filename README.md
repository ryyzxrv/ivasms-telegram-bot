# iVASMS Telegram Bot

A robust Telegram bot that automatically fetches OTP messages from [ivasms.com](https://www.ivasms.com) and forwards them to designated Telegram chats. The bot uses web scraping with Playwright to monitor the SMS received page and provides comprehensive management commands.

## 🚀 Features

- **Automated OTP Fetching**: Continuously monitors iVASMS for new OTP messages
- **Telegram Integration**: Sends real-time notifications to admin chats
- **Web Scraping**: Uses Playwright for reliable browser automation
- **Persistent Storage**: SQLite database for state management and OTP history
- **Admin Commands**: Comprehensive set of management commands
- **Error Handling**: Robust error handling with retry mechanisms
- **Security**: Admin-only access with credential masking
- **Logging**: Detailed logging with configurable levels
- **Health Monitoring**: Built-in health checks and heartbeat messages

## 📋 Prerequisites

- Python 3.11+
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- iVASMS account credentials
- Admin Telegram Chat ID

## 🛠️ Installation

### Option 1: GitHub Codespaces (Recommended)

1. **Fork this repository** to your GitHub account

2. **Open in Codespaces**:
   - Click the green "Code" button
   - Select "Codespaces" tab
   - Click "Create codespace on main"

3. **Wait for setup**: The devcontainer will automatically install dependencies

4. **Configure environment**:
   ```bash
   cp .env.example .env
   nano .env  # Edit with your credentials
   ```

5. **Install Playwright browsers**:
   ```bash
   playwright install
   ```

### Option 2: Local Development

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd ivasms-telegram-bot
   ```

2. **Create virtual environment**:
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   playwright install
   ```

4. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

## ⚙️ Configuration

### Required Environment Variables

Create a `.env` file with the following variables:

```env
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_ADMIN_CHAT_ID=123456789

# iVASMS Credentials  
IVASMS_EMAIL=your_email@example.com
IVASMS_PASSWORD=your_password_here

# Bot Configuration (Optional)
POLL_INTERVAL_SECONDS=15
HEADLESS=true
DRY_RUN=false
LOG_LEVEL=INFO
```

### Getting Your Telegram Chat ID

1. Start a chat with [@userinfobot](https://t.me/userinfobot)
2. Send any message
3. Copy the "Id" number (this is your chat ID)

### Configuration Options

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | *Required* | Bot token from @BotFather |
| `TELEGRAM_ADMIN_CHAT_ID` | *Required* | Admin chat ID (comma-separated for multiple) |
| `IVASMS_EMAIL` | *Required* | Your iVASMS account email |
| `IVASMS_PASSWORD` | *Required* | Your iVASMS account password |
| `POLL_INTERVAL_SECONDS` | `15` | How often to check for new OTPs |
| `HEADLESS` | `true` | Run browser in headless mode |
| `DRY_RUN` | `false` | Test mode - don't send notifications |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `DB_PATH` | `./data/state.db` | SQLite database path |
| `LOG_FILE` | `./logs/bot.log` | Log file path |
| `MAX_RETRIES` | `3` | Max retry attempts for failed operations |
| `HEARTBEAT_INTERVAL_HOURS` | `24` | Heartbeat message interval |

## 🚀 Usage

### Starting the Bot
```bash
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```bash
# Make sure you're in the project directory
python main.py
```

Or using the executable:
```bash
./main.py
```

### Bot Commands

Once the bot is running, use these commands in your Telegram chat:

| Command | Description |
|---------|-------------|
| `/start` | Show bot status and available commands |
| `/status` | Display current bot status and statistics |
| `/config` | Show current configuration (credentials masked) |
| `/info` | Display deployment information |
| `/recent_otps [N]` | Show last N OTP messages (default: 10) |
| `/last_otp` | Show the most recent OTP message |
| `/new_otp` | Force manual OTP fetch |
| `/restart` | Restart the bot process |
| `/stop` | Stop OTP monitoring |
| `/start_monitor` | Resume OTP monitoring |
| `/logs [lines]` | Show recent log entries (default: 20) |

### Example Usage

```
/start
🤖 iVASMS Telegram Bot

Status: 🟢 Running
Uptime: 2h 15m
Admin Chat ID: 123456789

Available commands:
• /status - Bot status
• /recent_otps - Recent OTPs
...
```

## 🏗️ Architecture

### Project Structure

```
ivasms-telegram-bot/
├── .devcontainer/          # GitHub Codespaces configuration
├── src/                    # Source code
│   ├── bot.py             # Main bot application
│   ├── config.py          # Configuration management
│   ├── monitor.py         # OTP monitoring logic
│   ├── playwright_client.py # Web scraping client
│   ├── storage.py         # Database operations
│   └── telegram_bot.py    # Telegram bot handlers
├── tests/                  # Unit and integration tests
├── data/                   # Database files (created at runtime)
├── logs/                   # Log files (created at runtime)
├── screenshots/            # Debug screenshots (created at runtime)
├── main.py                # Entry point
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

### Component Overview

- **Bot**: Main application coordinator
- **Config**: Environment variable management and validation
- **Monitor**: OTP polling and processing logic
- **PlaywrightClient**: Web scraping and browser automation
- **Storage**: SQLite database operations
- **TelegramBot**: Command handlers and message sending

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_storage.py

# Run with coverage
pytest --cov=src

# Run integration tests only
pytest -m integration
```

### Test Categories

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions
- **Mock Tests**: Test with simulated external dependencies

## 🔧 Development

### Setting Up Development Environment

1. **Install development dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Install pre-commit hooks** (optional):
   ```bash
   pre-commit install
   ```

3. **Run in development mode**:
   ```bash
   # Enable debug logging
   export LOG_LEVEL=DEBUG
   export HEADLESS=false  # See browser during development
   python main.py
   ```

### Code Style

The project uses:
- **Black** for code formatting
- **isort** for import sorting  
- **Pylint** for linting

```bash
# Format code
black src/ tests/
isort src/ tests/

# Lint code
pylint src/
```

## 🐳 Docker Deployment

### Building Docker Image

```bash
# Build image
docker build -t ivasms-telegram-bot .

# Run container
docker run -d \
  --name ivasms-bot \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  ivasms-telegram-bot
```

### Docker Compose

```yaml
version: '3.8'
services:
  ivasms-bot:
    build: .
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
```

## 📊 Monitoring & Logging

### Log Files

- **Location**: `./logs/bot.log` (configurable)
- **Rotation**: Manual (consider logrotate for production)
- **Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL

### Health Checks

The bot provides built-in health monitoring:

- **Heartbeat Messages**: Periodic status updates
- **Error Notifications**: Automatic error reporting
- **Statistics Tracking**: Login attempts, fetch success/failure rates

### Monitoring Commands

```bash
# View recent logs
tail -f logs/bot.log

# Check bot status via Telegram
/status

# Force health check
/info
```

## 🔒 Security Considerations

### Credential Protection

- **Environment Variables**: Never commit credentials to git
- **Masked Display**: Sensitive info is masked in `/config` output
- **Admin-Only Access**: All commands require admin authorization

### Network Security

- **HTTPS Only**: All external communications use HTTPS
- **User Agent**: Uses realistic browser user agent
- **Rate Limiting**: Respects site load with configurable intervals

### Data Privacy

- **Local Storage**: All data stored locally in SQLite
- **No Cloud Dependencies**: No external services except Telegram
- **Automatic Cleanup**: Old OTPs automatically deleted

## 🚨 Troubleshooting

### Common Issues

#### Bot Not Starting

```bash
# Check configuration
python -c "from src.config import get_config; print(get_config())"

# Check dependencies
pip install -r requirements.txt
playwright install
```

#### Login Failures

1. **Check credentials** in `.env` file
2. **Verify iVASMS account** is accessible
3. **Check for CAPTCHA** (may require manual intervention)
4. **Review logs** for specific error messages

#### No OTPs Received

1. **Check polling interval** (may be too long)
2. **Verify navigation** to SMS received page
3. **Check selectors** (site may have changed)
4. **Enable debug mode** to see screenshots

#### Telegram Commands Not Working

1. **Verify bot token** is correct
2. **Check admin chat ID** matches your Telegram ID
3. **Ensure bot is running** and connected

### Debug Mode

Enable debug mode for troubleshooting:

```bash
export LOG_LEVEL=DEBUG
export HEADLESS=false
export SAVE_SCREENSHOTS=true
python main.py
```

### Getting Help

1. **Check logs** in `./logs/bot.log`
2. **Review error messages** in Telegram
3. **Run health check** with `/status` command
4. **Check GitHub Issues** for known problems

## 📝 License

This project is provided as-is for educational and personal use. Please ensure you have permission from the website owner before using web scraping functionality.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## 📞 Support

For issues and questions:

1. Check the troubleshooting section above
2. Review existing GitHub Issues
3. Create a new issue with detailed information

---

**Note**: This bot requires explicit permission from the iVASMS website owner for web scraping activities. Ensure you have proper authorization before deployment.
