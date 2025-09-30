#!/bin/bash

# iVASMS Telegram Bot Deployment Script
# This script helps deploy the bot to a Linux server

set -e

# Configuration
BOT_USER="botuser"
INSTALL_DIR="/opt/ivasms-telegram-bot"
SERVICE_NAME="ivasms-bot"
PYTHON_VERSION="3.11"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

# Install system dependencies
install_dependencies() {
    log_info "Installing system dependencies..."
    
    apt-get update
    apt-get install -y \
        python${PYTHON_VERSION} \
        python${PYTHON_VERSION}-venv \
        python3-pip \
        git \
        wget \
        curl \
        gnupg \
        ca-certificates \
        fonts-liberation \
        libasound2 \
        libatk-bridge2.0-0 \
        libatk1.0-0 \
        libatspi2.0-0 \
        libcups2 \
        libdbus-1-3 \
        libdrm2 \
        libgtk-3-0 \
        libnspr4 \
        libnss3 \
        libwayland-client0 \
        libx11-6 \
        libx11-xcb1 \
        libxcb1 \
        libxcomposite1 \
        libxdamage1 \
        libxext6 \
        libxfixes3 \
        libxrandr2 \
        libxss1 \
        libxtst6 \
        xdg-utils
}

# Create bot user
create_user() {
    log_info "Creating bot user..."
    
    if ! id "$BOT_USER" &>/dev/null; then
        useradd --create-home --shell /bin/bash --system "$BOT_USER"
        log_info "Created user: $BOT_USER"
    else
        log_warn "User $BOT_USER already exists"
    fi
}

# Setup application directory
setup_directory() {
    log_info "Setting up application directory..."
    
    # Create directory
    mkdir -p "$INSTALL_DIR"
    
    # Copy application files
    if [[ -d "$(pwd)/src" ]]; then
        cp -r . "$INSTALL_DIR/"
    else
        log_error "Source code not found. Run this script from the project root."
        exit 1
    fi
    
    # Create necessary directories
    mkdir -p "$INSTALL_DIR"/{data,logs,screenshots,browser_state}
    
    # Set ownership
    chown -R "$BOT_USER:$BOT_USER" "$INSTALL_DIR"
    
    # Set permissions
    chmod +x "$INSTALL_DIR/main.py"
}

# Setup Python environment
setup_python() {
    log_info "Setting up Python virtual environment..."
    
    # Create virtual environment
    sudo -u "$BOT_USER" python${PYTHON_VERSION} -m venv "$INSTALL_DIR/venv"
    
    # Install Python dependencies
    sudo -u "$BOT_USER" "$INSTALL_DIR/venv/bin/pip" install --upgrade pip
    sudo -u "$BOT_USER" "$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"
    
    # Install Playwright browsers
    sudo -u "$BOT_USER" "$INSTALL_DIR/venv/bin/playwright" install chromium
}

# Setup environment file
setup_environment() {
    log_info "Setting up environment configuration..."
    
    if [[ ! -f "$INSTALL_DIR/.env" ]]; then
        cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
        chown "$BOT_USER:$BOT_USER" "$INSTALL_DIR/.env"
        chmod 600 "$INSTALL_DIR/.env"
        
        log_warn "Please edit $INSTALL_DIR/.env with your configuration"
        log_warn "Required: TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID, IVASMS_EMAIL, IVASMS_PASSWORD"
    else
        log_info "Environment file already exists"
    fi
}

# Install systemd service
install_service() {
    log_info "Installing systemd service..."
    
    # Copy service file
    cp "$INSTALL_DIR/ivasms-bot.service" "/etc/systemd/system/$SERVICE_NAME.service"
    
    # Reload systemd
    systemctl daemon-reload
    
    # Enable service
    systemctl enable "$SERVICE_NAME"
    
    log_info "Service installed and enabled"
}

# Start service
start_service() {
    log_info "Starting service..."
    
    systemctl start "$SERVICE_NAME"
    
    # Check status
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log_info "Service started successfully"
    else
        log_error "Service failed to start"
        systemctl status "$SERVICE_NAME"
        exit 1
    fi
}

# Show status
show_status() {
    log_info "Service status:"
    systemctl status "$SERVICE_NAME" --no-pager
    
    log_info "Recent logs:"
    journalctl -u "$SERVICE_NAME" --no-pager -n 10
}

# Main deployment function
deploy() {
    log_info "Starting iVASMS Telegram Bot deployment..."
    
    check_root
    install_dependencies
    create_user
    setup_directory
    setup_python
    setup_environment
    install_service
    
    log_info "Deployment completed successfully!"
    log_warn "Please configure $INSTALL_DIR/.env before starting the service"
    log_info "To start the service: sudo systemctl start $SERVICE_NAME"
    log_info "To check status: sudo systemctl status $SERVICE_NAME"
    log_info "To view logs: sudo journalctl -u $SERVICE_NAME -f"
}

# Uninstall function
uninstall() {
    log_info "Uninstalling iVASMS Telegram Bot..."
    
    # Stop and disable service
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    
    # Remove service file
    rm -f "/etc/systemd/system/$SERVICE_NAME.service"
    systemctl daemon-reload
    
    # Remove application directory
    rm -rf "$INSTALL_DIR"
    
    # Remove user (optional)
    read -p "Remove user $BOT_USER? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        userdel -r "$BOT_USER" 2>/dev/null || true
    fi
    
    log_info "Uninstallation completed"
}

# Update function
update() {
    log_info "Updating iVASMS Telegram Bot..."
    
    # Stop service
    systemctl stop "$SERVICE_NAME"
    
    # Backup current installation
    cp -r "$INSTALL_DIR" "$INSTALL_DIR.backup.$(date +%Y%m%d_%H%M%S)"
    
    # Update code
    setup_directory
    setup_python
    
    # Restart service
    systemctl start "$SERVICE_NAME"
    
    log_info "Update completed successfully"
}

# Help function
show_help() {
    echo "iVASMS Telegram Bot Deployment Script"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  deploy      Deploy the bot (default)"
    echo "  uninstall   Remove the bot installation"
    echo "  update      Update existing installation"
    echo "  status      Show service status"
    echo "  start       Start the service"
    echo "  stop        Stop the service"
    echo "  restart     Restart the service"
    echo "  logs        Show recent logs"
    echo "  help        Show this help message"
}

# Parse command line arguments
case "${1:-deploy}" in
    deploy)
        deploy
        ;;
    uninstall)
        check_root
        uninstall
        ;;
    update)
        check_root
        update
        ;;
    status)
        show_status
        ;;
    start)
        check_root
        systemctl start "$SERVICE_NAME"
        ;;
    stop)
        check_root
        systemctl stop "$SERVICE_NAME"
        ;;
    restart)
        check_root
        systemctl restart "$SERVICE_NAME"
        ;;
    logs)
        journalctl -u "$SERVICE_NAME" -f
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        log_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
