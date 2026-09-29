# 🌿 Komorebi Desktop
*(formerly Wallhaven Desktop)*

<div align="center">

[![Arch Linux](https://img.shields.io/badge/Arch%20Linux-1793D1?style=for-the-badge&logo=arch-linux&logoColor=white)](https://archlinux.org)
[![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/Sedly12322/wallhaven-desktop/releases)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-41CD52?style=for-the-badge&logo=qt&logoColor=white)](https://riverbankcomputing.com/software/pyqt/)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![GitHub Release](https://img.shields.io/github/v/release/Sedly12322/wallhaven-desktop?style=for-the-badge&logo=github)](https://github.com/Sedly12322/wallhaven-desktop/releases)
[![GitHub stars](https://img.shields.io/github/stars/Sedly12322/wallhaven-desktop?style=for-the-badge&logo=github&color=gold)](https://github.com/Sedly12322/wallhaven-desktop/stargazers)

**A modern, high-performance desktop wallpaper and avatar browser, downloader, and manager powered by Python & PyQt6.**  
Seamlessly integrates **Wallhaven.cc**, **MoeWalls (Live Video 4K/60FPS)**, **osu! Seasonal Art**, and **pfps.gg (Avatars & Animated GIFs)**.  
Fully supports **Arch Linux** (Wayland / Hyprland / Quickshell / Serpantinum / X11) and **Microsoft Windows 10 & 11**.

</div>

---

## 📥 Installation

### 🐧 Arch Linux

Choose any of the following convenient installation methods:

#### ⚡ Method 1: Quick Install Script (Recommended)

Clone the repository and run the installer script. It installs the application, icons, desktop entry, and commands to `~/.local/bin` without requiring `sudo`:

```bash
git clone https://github.com/Sedly12322/wallhaven-desktop.git
cd wallhaven-desktop
./install.sh
```

Launch the app from anywhere via terminal:
```bash
komorebi
# or:
komorebi-desktop
# (wallhaven and wallhaven-desktop are also preserved as symlinks)
```
Or launch it from your application launcher (**Rofi**, **Wofi**, **Hyprland menu**, **KDE**, **GNOME**).

---

#### 📦 Method 2: Native Arch Package (`makepkg`)

If you prefer managing packages via `pacman` and `makepkg`:

```bash
git clone https://github.com/Sedly12322/wallhaven-desktop.git
cd wallhaven-desktop
makepkg -si
```

---

#### 🐍 Method 3: Via `pipx`

```bash
pipx install git+https://github.com/Sedly12322/wallhaven-desktop.git
```

---

#### 🚀 Method 4: Run from Source (No installation)

```bash
git clone https://github.com/Sedly12322/wallhaven-desktop.git
cd wallhaven-desktop
./run.sh
```

---

### 🪟 Microsoft Windows (10 / 11)

Ready-to-use binaries are available on the [**GitHub Releases**](https://github.com/Sedly12322/wallhaven-desktop/releases) page:

1. **Installer (`.exe`):** Download and run **`Wallhaven-Desktop-Setup.exe`**.  
   *Installs the application and creates Start Menu & Desktop shortcuts, with a clean uninstaller.*
2. **Portable Version (`.zip`):** Download **`Wallhaven-Desktop-Portable.zip`**, extract anywhere, and run `Wallhaven-Desktop.exe` directly without installing.

*(Alternatively, run from source by double-clicking **`run.bat`**).*

---

## 🔄 Updating / Aktualizace

### 🐧 Arch Linux
To update your existing installation to the latest version:
```bash
cd ~/wallhaven-desktop
git pull
./install.sh
```
*(The script updates the application and Python environment in `~/.local/share/wallhaven-desktop/`. All your settings, API keys, and downloaded wallpapers are automatically preserved).*

If you installed via `makepkg` (Package Manager):
```bash
cd ~/wallhaven-desktop
git pull
makepkg -si
```

### 🪟 Microsoft Windows
- **Installer Version (`.exe`):** Download the latest [**`Wallhaven-Desktop-Setup.exe`**](https://github.com/Sedly12322/wallhaven-desktop/releases/latest) and run it. The installer will automatically update the previous version in place and preserve all your settings and cache.
- **Portable Version (`.zip`):** Download the latest [**`Wallhaven-Desktop-Portable.zip`**](https://github.com/Sedly12322/wallhaven-desktop/releases/latest) and extract the contents to replace your existing files.
- **From Source:** Run `git pull` in the repository folder and start with `run.bat`.

---

## ✨ Features

- **🎨 Modern Dark UI:**
  - Sleek interface tailored for modern Linux desktops, Hyprland dotfiles, and Windows dark mode.
  - Responsive grid layout with asynchronous image loading, memory caching, and badges indicating resolution (e.g. `4K UHD`, `2K`, `1080p`), category, and purity.

- **🎬 MoeWalls (Live / Animated Wallpapers):**
  - Dedicated tab featuring **20,000+ high-definition 2K / 4K 60FPS animated video wallpapers** from MoeWalls.
  - **Embedded Video Player:** Live preview loop in the detail dialog powered by QtMultimedia & FFmpeg with Play/Pause and Mute toggles.
  - **Direct MP4 Downloads:** Download pristine high-bitrate MP4 files with real-time download progress.
  - **Category, Resolution & Keyword Filtering:** Filter by resolution (**4K UHD 3840×2160**, **2K QHD 2560×1440**, **1080p FHD**, **Ultrawide 21:9 3440×1440**, **Super Ultrawide 32:9 5120×1440**, **Dual 4K 7680×2160**, **720p HD**), category (Anime, Games, Sci-Fi, Fantasy, Landscape, Pixel Art, Animals, Vehicles, Movies, etc.), and full-text search.
  - **Automatic Desktop Setup:** Seamlessly sets video wallpapers using Quickshell, `mpvpaper`, or custom commands.

- **🖼️ Comprehensive Linux & Windows Wallpaper Setting:**
  - Automatically sets downloaded wallpapers to your desktop background with zero hassle.
  - **Hyprland / Wayland with Quickshell:** Full native support for Quickshell IPC (`serpantinum` and `illogical-impulse`), setting both static images and live video (`.mp4`) wallpapers directly!
  - **Wayland Setters:** Native support for `mpvpaper` (animated video wallpapers), `swww`, `hyprpaper`, `waypaper`, and `swaybg`.
  - **KDE Plasma 5 & 6:** Built-in support via `plasma-apply-wallpaperimage`.
  - **GNOME / Cinnamon / MATE / XFCE:** Native integration via `gsettings` (with both light and dark theme background setting) and `xfconf-query`.
  - **X11 Window Managers:** Native support for `feh`, `nitrogen`, and `xwinwrap` + `mpv` for video backgrounds.
  - **Windows 10/11:** Native Windows API (`SystemParametersInfoW`) for static images and Lively Wallpaper CLI for animated wallpapers.
  - **Configurable in Settings:** Choose auto-detection or select your preferred setter from a dropdown, test it with one click, or define custom command lines with `{file}`.
  - Toggle on/off anytime using the **`🖼️ Auto Wallpaper`** button in the top bar.

- **🎯 osu! Seasonal Wallpapers (Official Contest Art):**
  - Dedicated tab featuring **1,699+ official seasonal contest wallpapers** directly from osu! fanart competitions (2020–2026).
  - Works offline instantly with zero API keys or authentication required.
  - **Filter by Season:** Spring 2026, Winter 2025, Halloween 2025, Summer 2025, and all past contests.
  - **Theme Chips:** 🌸 Spring, ☀️ Summer, 🍂 Autumn, ❄️ Winter, and 🎃 Halloween.
  - **Sorting:** 🏆 Top Voted (Official Contest Winners), 🕒 Newest Season, and 🎲 Random.
  - Search by artist username, illustration title, or season name.
  - Full metadata with artist credits, vote counts, winner badges, and direct links to official contest pages.

- **🎭 Avatars & Profile Pictures (pfps.gg Integration):**
  - Dedicated **`🎭 Avatars / 🎭 Profilovky`** tab featuring tens of thousands of aesthetic avatars and animated GIFs from [pfps.gg](https://pfps.gg).
  - **Category Browsing:** Anime, Animated GIF, Aesthetic, Gaming, Cute, Meme, Dark, Matching, Cool, Pixel Art, Discord, etc.
  - **Sorting:** Top Rated, Most Downloaded, Newest.
  - **Keyword Search:** Instant full-text search across pfps.gg avatars.
  - **👤 1-Click System Avatar Setter:** Sets any avatar directly as your Linux desktop / display manager user avatar (`~/.face`, `~/.face.icon`) and Serpantinum shell config (`~/.config/serpantinum/settings.json`)!
  - **📋 Quick Clipboard Copy:** Instantly copy avatar image to clipboard with one click — paste directly into Discord, Telegram, or any chat with `Ctrl+V`.
  - **💾 Download to Local Folder:** Download avatars to `~/Pictures/Avatars/` or `~/Obrázky/Avatary/`.
  - **Full Preview Dialog:** High-resolution preview with animated GIF playback via `QMovie`.

- **💾 Installed Wallpapers & Uninstallation (Správa nainstalovaných tapet):**
  - Dedicated **`💾 Installed / 💾 Nainstalované`** tab managing all wallpapers downloaded across all providers (**Wallhaven**, **MoeWalls**, and **osu! Seasonal**).
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

- **🔍 Full Detail Modal:**
  - Click any card to inspect the full preview image, exact dimensions, ratio, file size, format, views, and favorites count.
  - **Clickable Tags:** Click any tag pill to instantly search for similar wallpapers.
  - Dominant color swatches.
  - One-click **„Set as wallpaper now“** button.
  - Direct link to open the wallpaper page on Wallhaven.cc or osu!.

- **💾 Safe & Flexible Downloads:**
  - Prompt save dialog allowing you to choose destination and filename (pre-filled with suggested names).
  - Real-time download progress bar displaying MB downloaded, total size, and percentage.
  - "Open in folder" button to reveal the file in your default file manager upon download completion.

- **🌐 Multi-Language / Localization:**
  - Full support for **English** and **Czech (Čeština)**.
  - Automatically detects system locale on startup.
  - Switch languages on the fly in **Settings (⚙)** with instant UI update without restarting.

- **⚙️ Settings & Configuration:**
  - Store your Wallhaven API key to unlock NSFW wallpapers and your personal collections.
  - Configure default download directory.
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
sudo pacman -R wallhaven-desktop-git
```

If installed on Windows:
- Run the uninstaller from Windows **Settings → Apps → Installed apps**, or launch `unins000.exe` in the installation directory.

---

## 🌟 Star History

<div align="center">

<a href="https://star-history.com/#Sedly12322/wallhaven-desktop&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=Sedly12322/wallhaven-desktop&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=Sedly12322/wallhaven-desktop&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=Sedly12322/wallhaven-desktop&type=Date" />
 </picture>
</a>

</div>

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
