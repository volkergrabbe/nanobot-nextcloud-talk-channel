#!/bin/bash
# Script to install all necessary tools for nanobot container

set -e

echo "🚀 Installing all necessary tools for nanobot container..."

# Create tools directory
sudo mkdir -p /opt/nanobot/tools
sudo chown -R $USER:$USER /opt/nanobot/tools

# Create installation script for container
cat > /opt/nanobot/tools/install_all.sh << 'EOF'
#!/bin/bash
set -e

echo "📦 Installing all necessary tools..."

# Install development tools
apt-get update -qq
apt-get install -y -qq \
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
    gnupg \
    ca-certificates \
    libssl-dev \
    python3-pip \
    python3-dev \
    python3-setuptools \
    python3-wheel \
    build-essential \
    2>&1 | grep -v "^Setting up"

echo "✅ All tools installed successfully!"
EOF

chmod +x /opt/nanobot/tools/install_all.sh

# Create tool verification script
cat > /opt/nanobot/tools/verify_tools.sh << 'EOF'
#!/bin/bash
echo "🔍 Verifying installed tools..."
echo ""

tools=(
    "curl"
    "git"
    "wget"
    "git-lfs"
    "rsync"
    "jq"
    "tree"
    "less"
    "nano"
    "vim"
    "htop"
    "net-tools"
    "ping"
    "python3"
)

missing=0
for tool in "${tools[@]}"; do
    if command -v $tool &> /dev/null; then
        version=$($tool --version 2>/dev/null | head -n1)
        echo "✅ $tool: $version"
    else
        echo "❌ $tool: NOT INSTALLED"
        missing=$((missing + 1))
    fi
done

echo ""
if [ $missing -eq 0 ]; then
    echo "✅ All tools are installed!"
    exit 0
else
    echo "❌ $missing tools are missing"
    exit 1
fi
EOF

chmod +x /opt/nanobot/tools/verify_tools.sh

# Create automation script to install tools and rebuild
cat > /opt/nanobot/tools/update_tools.sh << 'EOF'
#!/bin/bash
set -e

echo "🔧 Updating all tools..."

# Run installation
/opt/nanobot/tools/install_all.sh

# Verify installation
/opt/nanobot/tools/verify_tools.sh

# Rebuild Docker image
echo "🔨 Rebuilding Docker image..."
docker compose build --no-cache

echo "✅ All tools updated and image rebuilt!"
EOF

chmod +x /opt/nanobot/tools/update_tools.sh

# Create quick start script
cat > /opt/nanobot/tools/quick_setup.sh << 'EOF'
#!/bin/bash
set -e

echo "🚀 Quick Setup for Nanobot Container"

# Check if running inside container
if [ ! -f /.dockerenv ]; then
    echo "⚠️  This script is meant to be run INSIDE the container"
    echo "Run this: docker exec -it nanobot bash"
    exit 1
fi

# Install tools
echo "📦 Installing all necessary tools..."
apt-get update -qq
apt-get install -y -qq \
    curl \
    git \
    wget \
    git-lfs \
    vim \
    tmux \
    htop \
    jq \
    rsync \
    python3-pip \
    build-essential \
    2>&1 | grep -v "^Setting up"

# Verify Python
python3 --version
pip3 --version

echo ""
echo "✅ Quick setup completed!"

# Enable security tools
echo ""
echo "🔒 Enabling security features..."
setcap cap_net_bind_service=+ep $(which python3) 2>/dev/null || true

echo ""
echo "✅ Security features enabled!"
EOF

chmod +x /opt/nanobot/tools/quick_setup.sh

# Create file management script
cat > /opt/nanobot/tools/manage_files.sh << 'EOF'
#!/bin/bash

case "$1" in
    list)
        echo "📂 Available tools:"
        ls -la /opt/nanobot/tools/
        ;;
    verify)
        /opt/nanobot/tools/verify_tools.sh
        ;;
    install)
        /opt/nanobot/tools/install_all.sh
        ;;
    update-all)
        /opt/nanobot/tools/update_tools.sh
        ;;
    quick)
        /opt/nanobot/tools/quick_setup.sh
        ;;
    *)
        echo "Nanobot Tools Manager"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  list       - List available tools"
        echo "  verify     - Verify installed tools"
        echo "  install    - Install all tools"
        echo "  update-all - Update tools and rebuild Docker image"
        echo "  quick      - Quick setup (within container)"
        exit 1
        ;;
esac
EOF

chmod +x /opt/nanobot/tools/manage_files.sh

# Create comprehensive tool list
cat > /opt/nanobot/tools/TOOL_SUMMARY.md << 'EOF'
# Tools in Nanobot Container

This document lists all installed tools in the nanobot container for Docker.

## Development Tools

- **git**: Version control system
  ```bash
  git clone <repo>
  git status
  git pull
  ```

- **git-lfs**: Git Large File Storage for large files
  ```bash
  git lfs install
  git lfs track "*.env"
  ```

- **vim**: Advanced text editor
  ```bash
  vim /opt/nanobot/config/config.json
  ```

- **nano**: Simple text editor
  ```bash
  nano /opt/nanobot/config/config.json
  ```

- **tmux**: Terminal multiplexer for persistent sessions
  ```bash
  tmux new -s nanobot
  tmux attach -t nanobot
  ```

## System Monitoring

- **htop**: Interactive process viewer
  ```bash
  htop
  ```

## Network Tools

- **curl**: Transfer data from URLs
  ```bash
  curl -I https://cloud.example.com
  curl -X POST https://localhost:18790/webhook/nextcloud_talk
  ```

- **wget**: Download files
  ```bash
  wget https://example.com/file.tar.gz
  ```

- **net-tools**: Network utilities
  ```bash
  ifconfig
  netstat -tulpn
  ```

- **ping**: Test network connectivity
  ```bash
  ping cloud.example.com
  ```

## File Tools

- **tar**: Archive files
  ```bash
  tar -czf backup.tar.gz /opt/nanobot
  ```

- **gzip**: Compress/decompress files
  ```bash
  gzip config.json
  gunzip config.json.gz
  ```

- **rsync**: Remote file synchronization
  ```bash
  rsync -avz /opt/nanobot/config/ user@remote:/path/
  ```

- **jq**: JSON processor
  ```bash
  cat config.json | jq '.agents'
  jq '.providers.ollama.api_base' config.json
  ```

- **tree**: Display directory structure
  ```bash
  tree /opt/nanobot
  ```

## Python Environment

- **python3**: Python interpreter
  ```bash
  python3 --version
  python3 -c "import sys; print(sys.path)"
  ```

## Security Tools

- **gnupg**: GnuPG encryption
  ```bash
  gpg --version
  ```

## Automation Scripts

Pre-installed in `/opt/nanobot/tools/`:

1. **install_all.sh** - Install all necessary tools
2. **verify_tools.sh** - Verify installed tools
3. **update_tools.sh** - Update tools and rebuild Docker image
4. **quick_setup.sh** - Quick container setup
5. **manage_files.sh** - Tool manager script

## Usage Examples

### Check installed tools

```bash
/opt/nanobot/tools/verify_tools.sh
```

### Update all tools

```bash
docker exec -it nanobot bash /opt/nanobot/tools/update_tools.sh
```

### Install tools manually

```bash
docker exec -it nanobot bash /opt/nanobot/tools/install_all.sh
```

### Manage tools

```bash
docker exec -it nanobot bash /opt/nanobot/tools/manage_files.sh list
docker exec -it nanobot bash /opt/nanobot/tools/manage_files.sh verify
```

## Tool Versions

Check versions using:

```bash
tool --version
```

## Updating Tools

To update individual tools:

```bash
apt-get update && apt-get upgrade -y <tool-package>
```

## Additional Python Packages

To install additional Python packages:

```bash
pip3 install <package-name>
```

Example:

```bash
pip3 install requests
pip3 install beautifulsoup4
```

---

*Last updated: 25.02.2026*
