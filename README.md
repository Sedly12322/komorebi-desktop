# 🌿 Komorebi Desktop
*(formerly Wallhaven Desktop)*

<div align="center">

[![Arch Linux](https://img.shields.io/badge/Arch%20Linux-1793D1?style=for-the-badge&logo=arch-linux&logoColor=white)](https://archlinux.org)
[![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/Sedly12322/komorebi-desktop/releases)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-41CD52?style=for-the-badge&logo=qt&logoColor=white)](https://riverbankcomputing.com/software/pyqt/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![GitHub Release](https://img.shields.io/github/v/release/Sedly12322/komorebi-desktop?style=for-the-badge&logo=github)](https://github.com/Sedly12322/komorebi-desktop/releases)
[![GitHub stars](https://img.shields.io/github/stars/Sedly12322/komorebi-desktop?style=for-the-badge&logo=github&color=gold)](https://github.com/Sedly12322/komorebi-desktop/stargazers)

**A modern, ultra-fast desktop wallpaper and avatar browser, downloader, and manager powered by Python & PyQt6.**  
Seamlessly integrates **Wallhaven.cc**, **MoeWalls (Live Video 4K/60FPS)**, **osu! Seasonal Art**, and **pfps.gg (Avatars & Animated GIFs)**.  
Fully optimized for **Linux** (Arch Linux / Hyprland / Quickshell / Serpantinum / Wayland / X11) and **Microsoft Windows 10 & 11**.

</div>

---

## 📥 Installation

### 🐧 Arch Linux & Linux Distributions

Choose any of the following convenient installation methods:

#### ⚡ Method 1: Quick Install Script (Recommended)

Clone the repository and run the installer script. It installs the application, dependencies, icons, desktop entry, and commands to `~/.local/bin` without requiring `sudo`:

```bash
git clone https://github.com/Sedly12322/komorebi-desktop.git
cd komorebi-desktop
./install.sh
```

Launch the app from anywhere via terminal:
```bash
komorebi
# or:
komorebi-desktop
# (wallhaven and wallhaven-desktop are also preserved as backward-compatible aliases)
```
Or launch it from your application launcher (**Rofi**, **Wofi**, **Hyprland menu**, **KDE Application Launcher**, **GNOME**).

---

#### 📦 Method 2: Native Arch Package (`makepkg`)

If you prefer managing packages natively via `pacman` and `makepkg`:

```bash
git clone https://github.com/Sedly12322/komorebi-desktop.git
cd komorebi-desktop
makepkg -si
```

---

#### 🐍 Method 3: Via `pipx`

```bash
pipx install git+https://github.com/Sedly12322/komorebi-desktop.git
```

---

#### 🚀 Method 4: Run from Source (No installation)

```bash
git clone https://github.com/Sedly12322/komorebi-desktop.git
cd komorebi-desktop
./run.sh
```

---

### 🪟 Microsoft Windows (10 / 11)

Ready-to-use binaries are available on the [**GitHub Releases**](https://github.com/Sedly12322/komorebi-desktop/releases) page:

1. **Installer (`.exe`):** Download and run **`Wallhaven-Desktop-Setup.exe`** (or `Komorebi-Desktop-Setup.exe`).  
   *Installs the application and creates Start Menu & Desktop shortcuts, complete with an uninstaller.*
2. **Portable Version (`.zip`):** Download **`Wallhaven-Desktop-Portable.zip`**, extract anywhere, and run `Wallhaven-Desktop.exe` directly without installing.

*(Alternatively, run from source by double-clicking **`run.bat`**).*

---

## 🔄 Updates & In-App Updater

### ✨ In-App One-Click Updater
Komorebi Desktop features a built-in update manager:
- **Automatic Check on Startup:** Quietly checks GitHub Releases in the background when launched.
- **Floating Update Banner:** Displays a sleek glassmorphic banner when a new release is available.
- **Interactive Version Badge:** Click the version badge (`v...`) in the top-left sidebar to check for updates anytime.
- **One-Click Install & Restart:** Downloads the update archive or installer, replaces files, updates dependencies, and restarts the application seamlessly.
- **Settings Dialog Integration:** Manually check for updates, read the full changelog, or toggle automatic update checks.

### 🐧 Manual Terminal Update (Linux)
To update an existing installation to the latest commit:
```bash
cd komorebi-desktop
git pull
./install.sh
```
*(All your settings, API keys, and downloaded wallpapers are automatically preserved).*

If installed via `makepkg`:
```bash
cd komorebi-desktop
git pull
makepkg -si
```

### 🪟 Windows Manual Update
- **Installer Version (`.exe`):** Download the latest setup executable from [**GitHub Releases**](https://github.com/Sedly12322/komorebi-desktop/releases/latest) and run it. It updates the existing installation in-place.
- **Portable Version (`.zip`):** Download the latest portable `.zip` and extract it to your folder.

---

## ✨ Features

- **🎨 Ultra-Modern Multi-Theme Engine:**
  - Curated themes: **Wallhaven Dark**, **Catppuccin Mocha**, **Tokyo Night**, **Nord Frost**, **Dracula**, **Gruvbox Dark**, **Cyberpunk 2077**, **OLED Pure Black**, and **Matugen / Pywal** dynamic desktop palette synchronization.
  - Quick theme switcher in the bottom sidebar and settings modal.

- **🌌 Ambient Dynamic Background Effects:**
  - Ambient particle system with floating particles and animated multi-colored aurora glow.
  - Can be toggled on/off in Settings for maximum performance.

- **🧭 Modern Navigation Sidebar & Spotlight Search:**
  - Grouped navigation (*Explore* & *Library*) with an animated sliding indicator pill.
  - **Spotlight Search Bar:** Quick search with `Ctrl+K` or `/` hotkeys.
  - Floating pill pagination with instant page-jump popover.

- **🎬 MoeWalls (Live / Animated Video Wallpapers):**
  - Dedicated tab featuring **20,000+ high-definition 2K / 4K 60FPS animated video wallpapers** from MoeWalls.
  - **Embedded Video Player:** Live preview loop in the detail dialog powered by QtMultimedia & FFmpeg with Play/Pause and Mute toggles.
  - **Direct MP4 Downloads:** Download pristine high-bitrate MP4 files with real-time download progress.
  - **Category, Resolution & Keyword Filtering:** Filter by resolution (**4K UHD 3840×2160**, **2K QHD 2560×1440**, **1080p FHD**, **Ultrawide 21:9 3440×1440**, **Super Ultrawide 32:9 5120×1440**, **Dual 4K 7680×2160**, **720p HD**), category (Anime, Games, Sci-Fi, Fantasy, Landscape, Pixel Art, Animals, Vehicles, Movies, etc.), and full-text search.
  - **Automatic Desktop Setup:** Seamlessly sets video wallpapers using Quickshell, `mpvpaper`, or custom commands.

- **🖼️ Comprehensive Linux & Windows Wallpaper Setting:**
  - Automatically sets downloaded wallpapers to your desktop background with zero hassle.
  - **Hyprland / Wayland with Quickshell:** Full native support for Quickshell IPC (`serpantinum` and `illogical-impulse`), setting both static images and live video (`.mp4`) wallpapers directly.
  - **Wayland Setters:** Native support for `mpvpaper` (animated video wallpapers), `swww`, `hyprpaper`, `waypaper`, and `swaybg`.
  - **KDE Plasma 5 & 6:** Built-in support via `plasma-apply-wallpaperimage`.
  - **GNOME / Cinnamon / MATE / XFCE:** Native integration via `gsettings` (supporting both light and dark theme background settings) and `xfconf-query`.
  - **X11 Window Managers:** Native support for `feh`, `nitrogen`, and `xwinwrap` + `mpv` for video backgrounds.
  - **Windows 10/11:** Native Windows API (`SystemParametersInfoW`) for static images and registry wallpaper detection.
  - **Configurable in Settings:** Choose auto-detection or select your preferred setter from a dropdown, test it with one click, or define custom command lines with `{file}`.
  - Toggle on/off anytime using the **`🖼️ Auto Wallpaper`** button in the sidebar.

- **🎯 osu! Seasonal Wallpapers (Official Contest Art):**
  - Dedicated tab featuring **1,699+ official seasonal contest wallpapers** directly from osu! fanart competitions (2020–2026).
  - Works offline instantly with zero API keys or authentication required.
  - **Filter by Season:** Spring 2026, Winter 2025, Halloween 2025, Summer 2025, and all past contests.
  - **Theme Chips:** 🌸 Spring, ☀️ Summer, 🍂 Autumn, ❄️ Winter, and 🎃 Halloween.
  - **Sorting:** 🏆 Top Voted (Official Contest Winners), 🕒 Newest Season, and 🎲 Random.
  - Search by artist username, illustration title, or season name.
  - Full metadata with artist credits, vote counts, winner badges, and direct links to official contest pages.

- **🎭 Avatars & Profile Pictures (pfps.gg Integration):**
  - Dedicated **`🎭 PFPs`** tab featuring tens of thousands of aesthetic avatars and animated GIFs from [pfps.gg](https://pfps.gg).
  - **Category Browsing:** Anime, Animated GIF, Aesthetic, Gaming, Cute, Meme, Dark, Matching, Cool, Pixel Art, Discord, etc.
  - **Sorting:** Top Rated, Most Downloaded, Newest.
  - **Keyword Search:** Instant full-text search across pfps.gg avatars.
  - **👤 1-Click System Avatar Setter:**
    - On Linux: Sets any avatar directly as your user avatar (`~/.face`, `~/.face.icon`) and Serpantinum shell config (`~/.config/serpantinum/settings.json`).
    - On Windows: Sets user account picture in `%APPDATA%\Microsoft\Windows\AccountPictures` and `~/Pictures/Avatars`.
  - **📋 Quick Clipboard Copy:** Instantly copy avatar image to clipboard with one click — paste directly into Discord, Telegram, or any chat with `Ctrl+V`.
  - **💾 Download to Local Folder:** Download avatars to `~/Pictures/Avatars/`.
  - **Asynchronous Asset Loading:** Fast dialog opening with pre-cached thumbnail while high-resolution media and animated GIFs stream smoothly in the background.

- **💾 Installed Wallpapers & Uninstallation:**
  - Dedicated **`💾 Installed`** tab managing all wallpapers downloaded across all providers (**Wallhaven**, **MoeWalls**, and **osu! Seasonal**).
  - Automatically catalogs and syncs existing wallpapers from your wallpaper directory with offline support.
  - **Filter by Provider:** All, Wallhaven, MoeWalls Live, osu! Seasonal.
  - **Filter by Type:** Static Images or Animated Video Wallpapers.
  - **Sorting:** Newest first, Oldest first, Name (A-Z), and File Size.
  - **Disk Usage Stats:** Live summary of installed wallpapers and total disk usage (e.g. `156 wallpapers • 436.5 MB`).
  - **🗑️ Complete Uninstallation:** Safely uninstall and delete wallpapers from your system directly from card buttons or the detail dialog with confirmation.
  - **🖼️ Quick Desktop Setter:** Set any installed wallpaper to your desktop with one click without downloading again.
  - **📁 Open in Folder:** One-click button to reveal wallpapers in your system file manager.

- **🔍 Advanced Search & Filtering (Wallhaven):**
  - **Full-text Query:** Search by keywords, `@uploader`, or `#tags`.
  - **Categories:** Toggle *General*, *Anime*, and *People*.
  - **Purity:** *SFW*, *Sketchy*, and *NSFW* (with API key check and configuration prompt).
  - **Sorting:** *Toplist*, *Hot*, *Latest (Date Added)*, *Views*, *Favorites*, *Random*, and *Relevance*.
  - **Toplist Time Range:** 1 day, 3 days, 1 week, 1 month, 3 months, 1 year.
  - **Aspect Ratios:** Any, 16:9, 16:10, 21:9 Ultrawide, 32:9 Superwide, 9:16 Mobile/Portrait.
  - **Resolutions:** Any, 1080p, 1440p (2K), 4K UHD, 8K UHD.
  - **Color Palette (🎨 Colors):** Filter wallpapers by dominant color using 18 official Wallhaven shades.

- **🌐 Multi-Language / Localization:**
  - Full support for **English** (default) and **Czech (Čeština)**.
  - Automatically detects system locale on startup.
  - Switch languages on the fly in **Settings (⚙)** with instant UI update without restarting.

- **⚙️ Settings & Configuration:**
  - Store your Wallhaven API key to unlock NSFW wallpapers and your personal collections.
  - Configure default download directory.
  - In-app update checker and auto-check toggle.
  - Custom wallpaper command support (with `{file}` placeholder).
  - Inspect thumbnail cache size and purge cache with one click.

---

## 🗑️ Uninstallation

If installed via `./install.sh`:
```bash
./uninstall.sh
```

If installed via `makepkg -si`:
```bash
sudo pacman -R komorebi-desktop-git
```

If installed on Windows:
- Run the uninstaller from Windows **Settings → Apps → Installed apps**, or launch `unins000.exe` in the application directory.

---

## 🌟 Star History

<div align="center">

<a href="https://star-history.com/#Sedly12322/komorebi-desktop&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=Sedly12322/komorebi-desktop&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=Sedly12322/komorebi-desktop&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=Sedly12322/komorebi-desktop&type=Date" />
 </picture>
</a>

</div>

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
