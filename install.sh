#!/usr/bin/env bash
set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=== Instalace Komorebi Desktop ===${NC}"

# Source directory
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Target directories (user-level, no root required)
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/komorebi-desktop"
BIN_DIR="$HOME/.local/bin"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"

echo -e "Instaluji do: ${YELLOW}$INSTALL_DIR${NC}"

mkdir -p "$INSTALL_DIR" "$BIN_DIR" "$APP_DIR" "$ICON_DIR"

# Build release binary with Cargo
if ! command -v cargo >/dev/null 2>&1; then
    echo -e "${RED}Chyba: cargo není nainstalováno! Nainstalujte Rust toolchain (rustup / cargo).${NC}"
    exit 1
fi

echo -e "Sestavuji nativní Rust binárku (--release)..."
cargo build --release --manifest-path "$SRC_DIR/Cargo.toml"

# Copy application files & compiled binary
mkdir -p "$INSTALL_DIR/assets"
cp "$SRC_DIR/target/release/komorebi-desktop" "$INSTALL_DIR/komorebi-desktop"
chmod +x "$INSTALL_DIR/komorebi-desktop"
cp -r "$SRC_DIR/assets/." "$INSTALL_DIR/assets/"
cp "$SRC_DIR/LICENSE" "$INSTALL_DIR/" 2>/dev/null || true

# Install icon
cp "$SRC_DIR/assets/icon.png" "$ICON_DIR/komorebi.png"
cp "$SRC_DIR/assets/icon.png" "$ICON_DIR/komorebi-desktop.png"
cp "$SRC_DIR/assets/icon.png" "$ICON_DIR/wallhaven-desktop.png"

# Create primary binary symlink
rm -f "$BIN_DIR/komorebi-desktop" "$BIN_DIR/wallhaven-desktop" "$BIN_DIR/komorebi" "$BIN_DIR/wallhaven"
ln -sf "$INSTALL_DIR/komorebi-desktop" "$BIN_DIR/komorebi-desktop"

# Symlinks for convenience and backwards compatibility
ln -sf "$BIN_DIR/komorebi-desktop" "$BIN_DIR/komorebi"
ln -sf "$BIN_DIR/komorebi-desktop" "$BIN_DIR/wallhaven-desktop"
ln -sf "$BIN_DIR/komorebi-desktop" "$BIN_DIR/wallhaven"

# Create desktop entry
cat > "$APP_DIR/komorebi.desktop" << EOF
[Desktop Entry]
Name=Komorebi Desktop
Comment=Prohlížení tapet (Wallhaven, MoeWalls, osu!) a profilovek (pfps.gg) pro Linux
Exec=$BIN_DIR/komorebi-desktop
Icon=komorebi
Terminal=false
Type=Application
Categories=Graphics;Photography;Utility;
Keywords=wallpaper;wallhaven;moewalls;osu;pfps;avatar;background;desktop;hyprland;images;
StartupWMClass=komorebi-desktop
EOF
chmod +x "$APP_DIR/komorebi.desktop"

# Backwards compatibility desktop entry
ln -sf "$APP_DIR/komorebi.desktop" "$APP_DIR/wallhaven-desktop.desktop"

# Update desktop & icon caches if available
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APP_DIR" || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" 2>/dev/null || true

echo -e "${GREEN}✓ Komorebi Desktop byl úspěšně nainstalován!${NC}"
echo -e "Aplikaci můžete spustit příkazem: ${YELLOW}komorebi${NC} nebo ${YELLOW}komorebi-desktop${NC} (nebo ${YELLOW}wallhaven${NC})"
echo -e "nebo z vašeho aplikačního launcheru (Rofi, Wofi, Hyprland)."
