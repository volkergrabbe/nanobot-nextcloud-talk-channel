# Multi-stage Dockerfile for Nanobot with all required tools

FROM python:3.11-slim as builder

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    wget \
    gnupg \
    openssh-client \
    jq \
    tree \
    less \
    nano \
    vim \
    tmux \
    htop \
    net-tools \
    iputils-ping \
    openssh-server \
    git-lfs \
    xz-utils \
    ca-certificates \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip setuptools wheel

# Install opencode
RUN pip install --no-cache-dir git+https://github.com/anomalyco/opencode.git

# Create non-root user for nanobot
RUN useradd -m -u 1000 -s /bin/bash nanobot && \
    mkdir -p /opt/nanobot/config /opt/nanobot/workspace && \
    chown -R nanobot:nanobot /opt/nanobot

USER nanobot
WORKDIR /home/nanobot

# Copy nanobot source code
COPY --chown=nanobot:nanobot . /home/nanobot

# Create required directories
RUN mkdir -p /home/nanobot/config /home/nanobot/workspace /home/nanobot/logs

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create entrypoint script
RUN cat > /home/nanobot/entrypoint.sh << 'EOF'
#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}======================================${NC}"
echo -e "${GREEN}   Nanobot Docker Container Starting   ${NC}"
echo -e "${GREEN}======================================${NC}"

# Make script executable
chmod +x /home/nanobot/update_nanobot.sh

# Source environment
export HOME=/home/nanobot
export PATH="/home/nanobot:/opt/nanobot/tools:$PATH"

# Run update check (called by cron)
/home/nanobot/update_nanobot.sh

# Check if config exists, if not create default
if [ ! -f "/home/nanobot/config/config.json" ]; then
    echo -e "${YELLOW}Config not found. Creating default config...${NC}"
    python /home/nanobot/scripts/config_sync.py init
fi

# Verify config
if ! python /home/nanobot/scripts/config_sync.py validate; then
    echo -e "${RED}Config validation failed!${NC}"
    echo -e "${YELLOW}Checking if we can restore from docker config...${NC}"
    python /home/nanobot/scripts/config_sync.py import-docker
fi

# Sync external config to container
python /home/nanobot/scripts/config_sync.py sync-to-docker

# Set environment variables for update mechanism
export UPDATE_CHECK_TIME=$(date +"%H:%M")
export AUTO_UPDATE_HOUR=00  # Midnight for auto-updates
export AUTO_UPDATE_MINUTE=15

# Start nanoprocess
echo -e "${GREEN}Starting Nanobot agent...${NC}"

exec python -m nanobot.agent.runner
EOF

chmod +x /home/nanobot/entrypoint.sh

# Create update script for daily updates
RUN cat > /home/nanobot/update_nanobot.sh << 'EOF'
#!/bin/bash
# Auto-update script for Nanobot

set -e

LOG_FILE="/home/nanobot/logs/update.log"
DATE=$(date +"%Y-%m-%d %H:%M:%S")
UPDATE_HOUR=00
UPDATE_MINUTE=15

# Get current time (hour:minute)
CURRENT_HOUR=$(date +"%H")
CURRENT_MINUTE=$(date +"%M")

# Check if it's time for update (midnight, or specific hour/minute)
if [ "$CURRENT_HOUR" == "$UPDATE_HOUR" ] && [ "$CURRENT_MINUTE" == "$UPDATE_MINUTE" ]; then
    echo "[$DATE] Starting daily update check..." >> "$LOG_FILE"
    
    # Backup current nanobot version
    echo "[$DATE] Backing up current installation..." >> "$LOG_FILE"
    cd /home/nanobot
    git fetch origin main 2>> "$LOG_FILE" || echo "[$DATE] Git fetch failed, skipping update" >> "$LOG_FILE"
    
    # Get current commit hash
    CURRENT_COMMIT=$(git rev-parse HEAD)
    REMOTE_BRANCH=$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || echo "")
    
    if [ -n "$REMOTE_BRANCH" ]; then
        # Check if there are updates
        if [ "$CURRENT_COMMIT" != "$(git rev-parse HEAD@{upstream})" ]; then
            echo "[$DATE] Updates available! Current: $CURRENT_COMMIT" >> "$LOG_FILE"
            echo "[$DATE] Pulling latest changes..." >> "$LOG_FILE"
            
            # Pull updates
            git pull origin main 2>> "$LOG_FILE"
            
            # Upgrade pip packages
            echo "[$DATE] Upgrading pip packages..." >> "$LOG_FILE"
            pip install --upgrade pip --break-system-packages 2>> "$LOG_FILE"
            pip install --upgrade -r requirements.txt --break-system-packages 2>> "$LOG_FILE"
            
            # Reinstall opencode
            echo "[$DATE] Reinstalling opencode..." >> "$LOG_FILE"
            pip install --force-reinstall --no-cache-dir git+https://github.com/anomalyco/opencode.git --break-system-packages 2>> "$LOG_FILE"
            
            echo "[$DATE] Update completed successfully!" >> "$LOG_FILE"
            echo "[$DATE] Rebooting container for changes to take effect..." >> "$LOG_FILE"
            exit 0  # Exit with 0 to trigger container restart
        else
            echo "[$DATE] No updates available. Installation is up to date." >> "$LOG_FILE"
        fi
    else
        echo "[$DATE] Not tracking a remote branch. Skipping update." >> "$LOG_FILE"
    fi
else
    # Just log the current time
    echo "[$DATE] Update check scheduled for $UPDATE_HOUR:$UPDATE_MINUTE" >> "$LOG_FILE"
fi

exit 0
EOF

chmod +x /home/nanobot/update_nanobot.sh

# Create cron job for daily update
RUN echo "0 $UPDATE_MINUTE $UPDATE_HOUR * * cd /home/nanobot && bash update_nanobot.sh >> /home/nanobot/logs/update_cron.log 2>&1" | crontab -


# Stage 2: Production container with all necessary tools installed
FROM python:3.11-slim

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/nanobot/tools:$PATH"

# Install all necessary system tools in the container (as per your request)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Development tools
    curl \
    git \
    wget \
    git-lfs \
    xz-utils \
    gzip \
    tar \
    unzip \
    rsync \
    jq \
    tree \
    less \
    nano \
    vim \
    tmux \
    htop \
    net-tools \
    iputils-ping \
    openssh-client \
    openssh-server \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create necessary directories
RUN mkdir -p /opt/nanobot/config /opt/nanobot/workspace /opt/nanobot/logs

# Copy entrypoint and setup scripts
COPY --chown=nanobot:nanobot --from=builder /home/nanobot/entrypoint.sh /home/nanobot/
COPY --chown=nanobot:nanobot --from=builder /home/nanobot/update_nanobot.sh /home/nanobot/
COPY --chown=nanobot:nanobot --from=builder /home/nanobot/scripts/config_sync.py /home/nanobot/scripts/

# Create tools directory for nanobot-specific tools
RUN mkdir -p /opt/nanobot/tools && \
    chown -R nanobot:nanobot /opt/nanobot

USER nanobot
WORKDIR /home/nanobot

# Copy nanobot source code
COPY --chown=nanobot:nanobot . /home/nanobot

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Setup cron for auto-update
RUN echo "0 00 00 * * cd /home/nanobot && bash /home/nanobot/update_nanobot.sh >> /home/nanobot/logs/update_cron.log 2>&1" > /home/nanobot/update_cron.txt && \
    crontab /home/nanobot/update_cron.txt

# Create workspace directory
RUN mkdir -p /home/nanobot/workspace && \
    mkdir -p /home/nanobot/logs && \
    chmod 755 /home/nanobot/logs

# Expose port for gateway
EXPOSE 18790

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Use entrypoint
ENTRYPOINT ["/home/nanobot/entrypoint.sh"]