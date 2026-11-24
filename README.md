# 🌿 Komorebi Desktop *(v3.0.0 — Rust Rewrite)*
*(formerly Wallhaven Desktop)*

<div align="center">

[![Rust](https://img.shields.io/badge/Rust-2021-orange?style=for-the-badge&logo=rust&logoColor=white)](https://www.rust-lang.org)
[![GUI](https://img.shields.io/badge/GUI-egui%20%2F%20eframe%20(glow)-38bdf8?style=for-the-badge)](https://github.com/emilk/egui)
[![Arch Linux](https://img.shields.io/badge/Arch%20Linux-Hyprland%20%2F%20Wayland-1793D1?style=for-the-badge&logo=arch-linux&logoColor=white)](https://archlinux.org)
[![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/Sedly12322/komorebi-desktop/releases)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/Sedly12322/komorebi-desktop?style=for-the-badge&logo=github&color=gold)](https://github.com/Sedly12322/komorebi-desktop/stargazers)

**An ultra-fast, native desktop wallpaper and avatar browser, downloader, and manager written in Rust using GPU-accelerated `egui` / `eframe`.**  
Integrates **Wallhaven.cc**, **MoeWalls (Live Video Wallpapers)**, **osu! Seasonal Art**, **pfps.gg (Avatars & Animated GIFs)**, and your **Local Wallpaper Library**.

</div>

---

## ⚡ Why Rust (`v3.0.0` on `rust-rewrite`)

- **Single Native Binary:** Compiled with release LTO & symbol stripping (~20 MB binary) — zero Python/Qt runtime overhead and instant startup.
- **GPU-Accelerated Immediate-Mode UI:** Smooth scrolling and crisp typography (`NotoSans` + automatic `JetBrainsMonoNerdFont` monospace switching for Terminal themes) rendered with `eframe` + `glow`.
- **Non-Blocking Background Architecture:** Network requests (`reqwest` + `rustls-tls`), `rayon` 6-thread parallel image/GIF decoding, `ffmpeg` video previews, local disk indexing, and `hyprctl` monitor detection all run off the UI thread.
- **Wayland / Hyprland First-Class Citizen:** Non-blocking buffer swaps on Linux (`vsync: false` for composited Wayland) with focus-aware animations, preventing hidden-workspace hangs and CPU spin.
- **Zero-Data-Loss Migration:** Fully compatible with existing `~/.config/komorebi-desktop/{config.json,installed.json}` schemas from `v2.x` (preserving extra/unknown JSON keys).

---

## 📦 Requirements

### Build Dependencies
- **Rust toolchain** (`cargo` and `rustc` via `rustup` or system packages)
- **OpenGL libraries** (`libgl` / Mesa drivers for GPU `glow` backend)

### Optional Runtime Tools
| Tool | Purpose |
| :--- | :--- |
| `ffmpeg` + `ffprobe` | Live video wallpaper playback (`VideoPreviewPlayer`), looping card hover previews, and local video thumbnail extraction |
| `mpvpaper` | Live/animated `.mp4`/`.webm` desktop wallpapers on Wayland (Hyprland / wlroots) |
| `awww` / `swww` / `hyprpaper` / `swaybg` / `waypaper` | Static & animated image wallpaper backends on Wayland |
| `wl-copy` | Persistent clipboard image copy on Wayland sessions (with `arboard` fallback) |
| `mpv` | External video preview window via the **Open in MPV** button |

---

## 📥 Installation & Usage

### 🐧 Linux (Arch Linux / Hyprland / Wayland / X11)

#### ⚡ Quick Install (Recommended)
Compiles the optimized release binary and installs to `~/.local/share/komorebi-desktop` with symlinks in `~/.local/bin` and a `.desktop` launcher entry (no `sudo` needed):

```bash
git clone -b rust-rewrite https://github.com/Sedly12322/komorebi-desktop.git
cd komorebi-desktop
./install.sh
```

Launch from anywhere:
```bash
komorebi
# or:
komorebi-desktop
# (backward-compatible symlinks: wallhaven, wallhaven-desktop)
```

#### 🚀 Run Directly from Source
```bash
./run.sh
# or directly via Cargo:
cargo run --release
```

#### 🧪 Build & Run Unit Tests
```bash
cargo test
cargo build --release
```

#### 🔄 Updating an Existing Install
```bash
cd komorebi-desktop
git pull
./install.sh
```
*(Your `config.json`, `installed.json`, API keys, and downloaded wallpapers are untouched.)*

### 🪟 Windows (10 / 11)
Install the Rust toolchain (MSVC or GNU target) and build/run directly:
```powershell
git clone -b rust-rewrite https://github.com/Sedly12322/komorebi-desktop.git
cd komorebi-desktop
cargo build --release
.\target\release\komorebi-desktop.exe
```

---

## ✨ Features

- **🎨 15 Curated Themes + Dynamic Desktop Sync:**
  - **Terminal CRT Series** *(automatic monospace typography)*: `terminal` (Hacker CRT), `terminal_amber` (Amber Phosphor), `terminal_ice` (Ice CRT).
  - **Curated Themes:** `dark` (Wallhaven Dark), `catppuccin`, `tokyo_night`, `nord`, `dracula`, `gruvbox`, `cyberpunk`, `oled` (OLED Pure Black), `rose_pine`, `everforest`, `kanagawa`, `synthwave`.
  - **Dynamic System Sync:** Auto hot-reloading integration for **Matugen** (`~/.cache/quickshell/matugen.json`, `~/.local/state/serpantinum/qs_colors.json`, `~/.config/matugen/colors.json`), **GTK 3/4**, **KDE Plasma** (`~/.config/kdeglobals`), and **Pywal** (`~/.cache/wal/colors.json`).
  - Live theme preview inside Settings with automatic rollback on Cancel/Escape.

- **🌌 Ambient Komorebi Canvas:**
  - Subtle atmospheric top glow, soft breathing center bloom, and gently drifting light motes that pause automatically when unfocused and can be toggled in Settings.

- **🖼️ Wallhaven.cc:**
  - Spotlight search (`Ctrl+K` or `/`), categories (*General*, *Anime*, *People*), purity (*SFW*, *Sketchy*, *NSFW* with API key check), sorting (*Toplist*, *Hot*, *Latest*, *Views*, *Favorites*, *Random*, *Relevance*), toplist time ranges, aspect ratios, minimum resolutions, and a collapsible 18-color Wallhaven palette bar.
  - Resolution badges (`[4K]` gold, `[2K]` cyan, `[WxH]`), card palette swatches, favorite/view counters, `[INSTALLED]` status badges, clickable modal color chips/tags, and scroll-to-zoom / drag-pan preview.

- **🎬 MoeWalls (Live Video Wallpapers):**
  - Search and filter live video wallpapers by category and resolution (*4K UHD*, *2K QHD*, *1080p FHD*, *21:9 Ultrawide*, *32:9 Superwide*, *Dual 4K*, *720p HD*).
  - **Card Hover Live Preview:** Hovering any animated card starts a smooth `ffmpeg` RGBA preview stream (`440×260` @ 24 fps) after a `0.25s` debounce and cleans up immediately when unfocused or closed.
  - **Detail Modal Video Player:** Looping video playback with Play/Pause toggle, **Open in MPV**, and direct MP4 downloads with cancelable streaming progress bar.

- **🎯 osu! Seasonal Artworks (Offline Embedded):**
  - **271 embedded official osu! seasonal contest artworks** bundled directly in the binary (`assets/osu_seasonal.json`) for instant zero-latency offline browsing.
  - Filter by **Season**, **Theme** (*Spring*, *Summer*, *Autumn*, *Winter*, *Halloween*), **No Logo** toggle, and sort by *Winners (Votes)*, *Newest*, or *Contest Rank*.

- **🎭 pfps.gg (Avatars & Animated GIFs):**
  - Browse and search profile pictures by category (*Anime*, *Animated GIFs*, *Aesthetic*, *Gaming*, *Cute*, *Meme*, *Dark*, *Matching*, etc.) and sorting (*Latest*, *Most Downloaded*, *Oldest*).
  - Animated GIF playback on both grid cards and modal preview.
  - **1-Click System Avatar:** Writes `~/.face` & `~/.face.icon` (auto-converting GIF/WebP first frame to PNG for lockscreens/DM compatibility) and updates Serpantinum config if present.
  - **Clipboard Copy & Download:** Copies images persistently on Wayland via `wl-copy` (`arboard` fallback) or downloads to `~/Pictures/Komorebi/Avatars`.

- **💾 Installed Library & Local Scanner:**
  - Automatically indexes wallpapers from your download directory (`image_dimensions` + `ffprobe` for videos) alongside `installed.json`.
  - Filter by provider (*Wallhaven*, *MoeWalls*, *osu!*, *Local*), media type (*Images* / *Video*), and sort by *Newest*, *Name*, or *File Size*.
  - Live storage summary, **Open Folder**, 1-click **Set as Wallpaper**, and **Uninstall**.

- **🖥️ Multi-Monitor & Wallpaper Setter Support:**
  - Detects active displays via `hyprctl monitors -j` or `xrandr --query`.
  - **Linux:** `~/.config/hypr/scripts/set-wallpaper.sh`, `awww`, `swww`, `mpvpaper` (`-vs -o "no-audio --loop" '*'`), Quickshell (`qs ipc`), `waypaper`, `hyprpaper`, `swaybg`, KDE `plasma-apply-wallpaperimage`, GNOME `gsettings`, XFCE `xfconf-query`, `feh`, `nitrogen`, `xwinwrap`, plus custom `{file}` / `{monitor}` commands.
  - **Windows:** Native `SystemParametersInfo` (static) and **Lively Wallpaper** CLI (video), plus custom commands.

- **🌐 Localization & Updates:**
  - Instant UI switching between **English** and **Czech (Čeština)**.
  - Optional background GitHub Releases check (`Sedly12322/komorebi-desktop`) with notification pill in the sidebar and manual check inside Settings.

---

## ⌨️ Keyboard Shortcuts & Controls

| Shortcut / Action | Behavior |
| :--- | :--- |
| `Ctrl+K` or `/` | Focus Spotlight search bar |
| `←` / `→` | Navigate Previous / Next wallpaper while Detail Modal is open |
| `Esc` | Close active popup/modal (or close page-jump popover) |
| Mouse Wheel (in Detail) | Zoom static wallpaper (`100%` – `500%`) |
| Drag / Double-Click (in Detail) | Pan zoomed image / Reset zoom to fit |

---

## 📁 Configuration, Cache & Project Structure

- **User Config & Library Manifest:** `~/.config/komorebi-desktop/{config.json,installed.json}`
- **Disk Cache (750 MB max, 400 MB anim loop cache):** `~/.cache/komorebi-desktop/{thumbnails,previews,anim}`

```text
komorebi-desktop/
├── Cargo.toml
├── assets/                 # App icons, emblems, and embedded osu_seasonal.json
├── src/
│   ├── main.rs             # Window bootstrap, fonts, Linux vsync config
│   ├── app.rs              # Async workers, hover video previews, state management
│   ├── config.rs           # AppConfig (v2.x backward-compatible)
│   ├── models.rs           # WallpaperItem, PfpItem, CardSize, NavMode
│   ├── theme.rs            # 15 curated themes + Matugen/GTK/KDE/Pywal hot-reload
│   ├── i18n.rs             # EN / CS translations
│   ├── cache.rs            # rayon parallel loader, LRU GPU textures, disk cache
│   ├── video_preview.rs    # Non-blocking ffmpeg/ffprobe streaming RGBA player
│   ├── installed.rs        # Local manifest & folder scanner
│   ├── wallpaper.rs        # Wayland / X11 / Windows setters & monitor detection
│   ├── updater.rs          # GitHub Releases semver check
│   ├── providers/          # wallhaven.rs, moewalls.rs, osu.rs, pfps.rs, mod.rs
│   └── ui/                 # sidebar, filters, grid, detail_modal, pfp_modal, settings_modal, pagination, toast, ambient
├── install.sh              # Build release & install to ~/.local
├── run.sh                  # cargo run --release wrapper
└── uninstall.sh            # Remove installed binaries, icons, and .desktop files
```

---

## 🗑️ Uninstallation

```bash
./uninstall.sh
```
*(Removes `~/.local/share/komorebi-desktop`, symlinks in `~/.local/bin`, desktop entries, and icons while keeping your `~/.config/komorebi-desktop` config and downloaded wallpapers.)*

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
