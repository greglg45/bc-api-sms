#!/bin/bash
# Simple installation script for huawei-lte-api on Rocky Linux 9
# It installs dependencies, clones the repository, and performs automatic updates
# when a newer version is available.

set -e

# Prompt user for a value with an optional default.
prompt_var() {
    local var_name=$1
    local prompt=$2
    local default=$3
    local input
    read -r -p "$prompt [${default}]: " input
    if [ -z "$input" ]; then
        eval "$var_name=\"$default\""
    else
        eval "$var_name=\"$input\""
    fi
}

# Prompt user for a password (input hidden) with an optional default.
prompt_password_var() {
    local var_name=$1
    local prompt=$2
    local default=$3
    local input
    read -r -s -p "$prompt [${default}]: " input
    echo
    if [ -z "$input" ]; then
        eval "$var_name=\"$default\""
    else
        eval "$var_name=\"$input\""
    fi
}

REPO_URL="https://github.com/greglg45/bc-api-sms.git"
INSTALL_DIR="/data/bc-api-sms"
VERSION_FILE="$INSTALL_DIR/VERSION"
CONFIG_FILE=""

# Parameters used for the HTTP API service
ROUTER_URL="http://192.168.8.1/"
ROUTER_USERNAME="admin"
ROUTER_PASSWORD="password"
HOST="0.0.0.0"
PORT="80"
API_KEY=""
CERTFILE=""
KEYFILE=""

# Install required packages if missing
install_deps() {
    # Python virtualenv is used to isolate dependencies
    local pkgs=(git python3 python3-pip python-pip policycoreutils-python-utils)
    sudo dnf install -y "${pkgs[@]}"
}

# Stop the service if it exists and is currently running
stop_service() {
    if sudo systemctl status bc-api-sms.service >/dev/null 2>&1; then
        if sudo systemctl is-active --quiet bc-api-sms.service; then
            sudo systemctl stop bc-api-sms.service
        fi
    fi
}

# Clone or update the repository
update_repo() {
    if [ ! -d "$INSTALL_DIR" ]; then
        sudo git clone "$REPO_URL" "$INSTALL_DIR"
    elif [ -d "$INSTALL_DIR/.git" ]; then
        sudo git -C "$INSTALL_DIR" fetch --tags
        sudo git -C "$INSTALL_DIR" pull --ff-only
    else
        echo "Directory $INSTALL_DIR exists but is not a git repository; re-cloning" >&2
        sudo rm -rf "$INSTALL_DIR"
        sudo git clone "$REPO_URL" "$INSTALL_DIR"
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
    local pip_cmd="pip install -r '$INSTALL_DIR/requirements.txt'"
    if [ -n "$PIP_CERT" ]; then
        pip_cmd="pip install --cert \"$PIP_CERT\" -r '$INSTALL_DIR/requirements.txt'"
    fi
    sudo -E bash -c "source '$INSTALL_DIR/venv/bin/activate' && $pip_cmd"
}

# Adjust SELinux context for the virtual environment so systemd can
# execute the Python binary when SELinux is enforcing.
configure_selinux() {
    if command -v getenforce >/dev/null 2>&1 && [ "$(getenforce)" = "Enforcing" ]; then
        if ! command -v semanage >/dev/null 2>&1; then
            sudo dnf install -y policycoreutils-python-utils
        fi
        sudo semanage fcontext -a -t bin_t "$INSTALL_DIR/venv/bin(/.*)?"
        sudo restorecon -R "$INSTALL_DIR/venv/bin"
    fi
}

# Create and enable the systemd service for the HTTP API
setup_service() {
    local api_key_arg=""
    if [ -n "$API_KEY" ]; then
        api_key_arg=" --api-key $API_KEY"
    fi
    local https_args=""
    if [ -n "$CERTFILE" ] && [ -n "$KEYFILE" ]; then
        https_args=" --certfile $CERTFILE --keyfile $KEYFILE"
    fi
    sudo tee /etc/systemd/system/bc-api-sms.service >/dev/null <<EOF
[Unit]
Description=bc-api-sms HTTP API
After=network.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python sms_http_api.py \
    $ROUTER_URL --username $ROUTER_USERNAME --password $ROUTER_PASSWORD \
    --host $HOST --port $PORT$api_key_arg$https_args
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable bc-api-sms.service
    sudo systemctl restart bc-api-sms.service
}

main() {
    prompt_var INSTALL_DIR "Installation directory" "$INSTALL_DIR"
    VERSION_FILE="$INSTALL_DIR/VERSION"
    CONFIG_FILE="$INSTALL_DIR/install.conf"
    if [ -f "$CONFIG_FILE" ]; then
        # shellcheck disable=SC1090
        source "$CONFIG_FILE"
    fi
    prompt_var ROUTER_URL "Router URL" "$ROUTER_URL"
    prompt_var ROUTER_USERNAME "Router username" "$ROUTER_USERNAME"
    prompt_password_var ROUTER_PASSWORD "Router password" "$ROUTER_PASSWORD"
    prompt_var HOST "HTTP API host" "$HOST"
    prompt_var PORT "HTTP API port" "$PORT"
    prompt_var API_KEY "API key (blank to disable)" "$API_KEY"
    prompt_var CERTFILE "TLS certificate file (blank to disable HTTPS)" "$CERTFILE"
    prompt_var KEYFILE "TLS private key file" "$KEYFILE"

    install_deps
    stop_service
    update_repo
    # Ensure the Python environment is ready after updating the repository
    setup_venv
    configure_selinux

    local repo_version
    repo_version=$(get_repo_version)
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

    cat <<EOF | sudo tee "$CONFIG_FILE" >/dev/null
ROUTER_URL="$ROUTER_URL"
ROUTER_USERNAME="$ROUTER_USERNAME"
ROUTER_PASSWORD="$ROUTER_PASSWORD"
HOST="$HOST"
PORT="$PORT"
API_KEY="$API_KEY"
CERTFILE="$CERTFILE"
KEYFILE="$KEYFILE"
EOF
    sudo chmod 600 "$CONFIG_FILE"
}

main "$@"
