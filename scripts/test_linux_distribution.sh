#!/bin/sh
set -eu

family="${1:-}"
case "$family" in
  debian)
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install --yes python3 python3-pip python3-venv systemd smartmontools
    ;;
  fedora)
    dnf install --assumeyes python3 python3-pip systemd smartmontools
    ;;
  arch)
    pacman --sync --refresh --noconfirm python python-pip systemd smartmontools pacman-contrib
    ;;
  *)
    echo "Unsupported Linux distribution family: $family" >&2
    exit 2
    ;;
esac

python3 -m venv /tmp/shuri-distro-test
/tmp/shuri-distro-test/bin/python -m pip install --disable-pip-version-check ".[dev]"
/tmp/shuri-distro-test/bin/python -m pytest
SHURI_RUN_NATIVE_INTEGRATION=1 \
  /tmp/shuri-distro-test/bin/python -m pytest tests/integration -m native_integration
/tmp/shuri-distro-test/bin/shuri version
/tmp/shuri-distro-test/bin/shuri scan
