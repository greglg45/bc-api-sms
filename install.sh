#!/bin/bash
# Simple installation script for huawei-lte-api on Rocky Linux 9
# It installs dependencies, clones the repository, and performs automatic updates
# when a newer version is available.

set -e

REPO_URL="https://github.com/greglg45/bc-api-sms.git"
INSTALL_DIR="/data/bc-api-sms"
VERSION_FILE="$INSTALL_DIR/VERSION"

# Install required packages if missing
install_deps() {
    local pkgs=(git python3 python3-pip)
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

main() {
    install_deps
    update_repo

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
}

main "$@"
