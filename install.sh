#!/bin/bash
# Simple installation script for huawei-lte-api on Rocky Linux 9
# It installs dependencies, clones the repository, and performs automatic updates
# when a newer version is available.

set -e

REPO_URL="https://github.com/greglg45/bc-api-sms.git"
INSTALL_DIR="/data/bc-api-sms"
VERSION_FILE="$INSTALL_DIR/VERSION"

# Parameters used for the HTTP API service
ROUTER_URL="http://192.168.8.1/"
ROUTER_USERNAME="admin"
ROUTER_PASSWORD="password"
HOST="0.0.0.0"
PORT="80"

# Install required packages if missing
install_deps() {
    # Python virtualenv is used to isolate dependencies
    local pkgs=(git python3 python3-pip python3-virtualenv)
    for pkg in "${pkgs[@]}"; do
        if ! command -v ${pkg%%-*} >/dev/null 2>&1; then
            sudo dnf install -y "$pkg"
        fi
    done
}

# Clone or update the repository
update_repo() {
    if [ ! -d "$INSTALL_DIR" ]; then
        sudo git clone "$REPO_URL" "$INSTALL_DIR"
    else
        sudo git -C "$INSTALL_DIR" fetch --tags
        sudo git -C "$INSTALL_DIR" pull --ff-only
    fi
}

# Retrieve version from repository
get_repo_version() {
    grep "__version__" "$INSTALL_DIR/huawei_lte_api/__init__.py" | cut -d"'" -f2
}

# Install or upgrade the package using pip
install_package() {
    sudo pip3 install --upgrade "$INSTALL_DIR"
}

# Create the virtual environment and install requirements
setup_venv() {
    # Create venv only if it does not already exist
    if [ ! -d "$INSTALL_DIR/venv" ]; then
        sudo python3 -m venv "$INSTALL_DIR/venv"
    fi

    # Activate the venv in a subshell to install dependencies
    sudo bash -c "source '$INSTALL_DIR/venv/bin/activate' && pip install -r '$INSTALL_DIR/requirements.txt'"
}

# Create and enable the systemd service for the HTTP API
setup_service() {
    sudo tee /etc/systemd/system/bc-api-sms.service >/dev/null <<EOF
[Unit]
Description=bc-api-sms HTTP API
After=network.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python sms_http_api.py \
    $ROUTER_URL --username $ROUTER_USERNAME --password $ROUTER_PASSWORD \
    --host $HOST --port $PORT
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable --now bc-api-sms.service
}

main() {
    install_deps
    update_repo
    # Ensure the Python environment is ready after updating the repository
    setup_venv

    local repo_version=$(get_repo_version)
    local current_version=""
    if [ -f "$VERSION_FILE" ]; then
        current_version=$(cat "$VERSION_FILE")
    fi

    if [ "$repo_version" != "$current_version" ]; then
        echo "Installing version $repo_version (was $current_version)" >&2
        install_package
        echo "$repo_version" | sudo tee "$VERSION_FILE" >/dev/null
    else
        echo "Version $repo_version already installed" >&2
    fi

    # Write and enable the systemd service on every run
    setup_service
}

main "$@"
