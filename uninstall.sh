#!/usr/bin/env bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Uninstalling Komorebi Desktop ===${NC}"

INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/komorebi-desktop"
LEGACY_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/wallhaven-desktop"
BIN_DIR="$HOME/.local/bin"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"

rm -rf "$INSTALL_DIR" "$LEGACY_DIR"
rm -f "$BIN_DIR/komorebi" "$BIN_DIR/komorebi-desktop" "$BIN_DIR/wallhaven-desktop" "$BIN_DIR/wallhaven"
rm -f "$APP_DIR/komorebi.desktop" "$APP_DIR/wallhaven-desktop.desktop"
rm -f "$ICON_DIR/komorebi.png" "$ICON_DIR/komorebi-desktop.png" "$ICON_DIR/wallhaven-desktop.png"

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APP_DIR" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" 2>/dev/null || true

echo -e "${GREEN}✓ Komorebi Desktop was successfully uninstalled.${NC}"
