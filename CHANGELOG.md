# Changelog

All notable changes to the iVASMS Telegram Bot project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-09-30

### Added
- Initial release of iVASMS Telegram Bot
- Web scraping functionality using Playwright for ivasms.com
- Telegram bot with comprehensive command set
- SQLite database for persistent storage
- Robust error handling and retry mechanisms
- Admin-only access control with credential masking
- Configurable polling intervals and behavior
- Health monitoring with heartbeat messages
- Automatic cleanup of old OTP records
- Docker support with multi-architecture builds
- GitHub Codespaces development environment
- Comprehensive test suite (unit and integration tests)
- CI/CD pipeline with GitHub Actions
- Systemd service configuration for Linux deployment
- Deployment script for easy server setup

### Features
- **Automated OTP Fetching**: Continuously monitors iVASMS for new messages
- **Real-time Notifications**: Instant Telegram notifications for new OTPs
- **Command Interface**: 11 admin commands for bot management
- **Persistent State**: SQLite database with automatic migrations
- **Security**: Environment variable configuration with validation
- **Logging**: Structured logging with configurable levels
- **Error Recovery**: Automatic retry with exponential backoff
- **Browser Automation**: Headless Chrome with session persistence
- **Data Privacy**: Local-only storage with automatic cleanup

### Commands
- `/start` - Show bot status and available commands
- `/status` - Display current bot status and statistics
- `/config` - Show current configuration (credentials masked)
- `/info` - Display deployment information
- `/recent_otps [N]` - Show last N OTP messages
- `/last_otp` - Show the most recent OTP message
- `/new_otp` - Force manual OTP fetch
- `/restart` - Restart the bot process
- `/stop` - Stop OTP monitoring
- `/start_monitor` - Resume OTP monitoring
- `/logs [lines]` - Show recent log entries

### Technical Details
- **Python 3.11+** with async/await support
- **Playwright** for reliable web scraping
- **python-telegram-bot** for Telegram integration
- **SQLite** with aiosqlite for async database operations
- **Tenacity** for retry logic with exponential backoff
- **Structlog** for structured logging
- **Pytest** with async support for testing
- **Docker** with multi-stage builds and security hardening
- **GitHub Actions** for CI/CD with security scanning

### Deployment Options
- **GitHub Codespaces**: One-click development environment
- **Docker**: Containerized deployment with docker-compose
- **Systemd**: Native Linux service with resource limits
- **Manual**: Virtual environment with pip installation

### Security Features
- Environment variable configuration
- Credential masking in command outputs
- Admin-only command access
- Non-root container execution
- Resource limits and security policies
- Automatic session management
- Local-only data storage

---

## Development Guidelines

### Version Numbering
- **Major** (X.0.0): Breaking changes, major feature additions
- **Minor** (0.X.0): New features, non-breaking changes
- **Patch** (0.0.X): Bug fixes, security updates

### Release Process
1. Update CHANGELOG.md with new version
2. Update version in relevant files
3. Create git tag with version number
4. Push to main branch to trigger CI/CD
5. Create GitHub release with changelog notes

### Contributing
- All changes should include appropriate tests
- Follow existing code style and conventions
- Update documentation for new features
- Add changelog entry for notable changes
