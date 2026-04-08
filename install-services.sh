#!/usr/bin/env bash
# Generates systemd service files from the templates and installs them.
# Run this once after cloning the repo on a new machine.
# Usage: bash install-services.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Installing services as user: $USER (home: $HOME)"

for TEMPLATE in "$SCRIPT_DIR"/*.service.template; do
    SERVICE_NAME="$(basename "$TEMPLATE" .template)"
    OUTPUT="/etc/systemd/system/$SERVICE_NAME"

    echo "Generating $SERVICE_NAME..."
    sed -e "s|__USER__|$USER|g" -e "s|__HOME__|$HOME|g" "$TEMPLATE" \
        | sudo tee "$OUTPUT" > /dev/null

    echo "Installed to $OUTPUT"
done

sudo systemctl daemon-reload
sudo systemctl enable inverter-reader inverter-dashboard
sudo systemctl start inverter-reader inverter-dashboard

echo ""
echo "Done. Check status with:"
echo "  sudo systemctl status inverter-reader inverter-dashboard"
