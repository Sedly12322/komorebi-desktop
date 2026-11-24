use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use crate::config::AppConfig;

pub fn shell_quote(s: &str) -> String {
    format!("'{}'", s.replace('\'', "'\"'\"'"))
}

pub fn expand_user_path(raw: &str) -> PathBuf {
    if let Some(rest) = raw.strip_prefix("~/") {
        if let Some(home) = dirs::home_dir() {
            return home.join(rest);
        }
    }
    PathBuf::from(raw)
}

pub fn command_exists(name: &str) -> bool {
    let p = expand_user_path(name);
    if p.is_absolute() && p.is_file() {
        return true;
    }
    #[cfg(target_os = "windows")]
    let which_cmd = "where";
    #[cfg(not(target_os = "windows"))]
    let which_cmd = "which";

    Command::new(which_cmd)
        .arg(name)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .status()
        .map(|s| s.success())
        .unwrap_or(false)
}

#[derive(Debug, Clone)]
pub struct MonitorInfo {
    pub id: String,
    pub label: String,
}

pub fn get_available_monitors() -> Vec<MonitorInfo> {
    let mut monitors = vec![MonitorInfo {
        id: "all".to_string(),
        label: "All Monitors".to_string(),
    }];

    #[cfg(target_os = "linux")]
    {
        if command_exists("hyprctl") {
            if let Ok(out) = Command::new("hyprctl").args(["monitors", "-j"]).output() {
                if out.status.success() {
                    if let Ok(arr) = serde_json::from_slice::<Vec<serde_json::Value>>(&out.stdout) {
                        for m in arr {
                            let name = m["name"].as_str().unwrap_or("");
                            if name.is_empty() {
                                continue;
                            }
                            let w = m["width"].as_u64().unwrap_or(0);
                            let h = m["height"].as_u64().unwrap_or(0);
                            let focused = m["focused"].as_bool().unwrap_or(false);
                            let suffix = if focused { " (focused)" } else { "" };
                            let label = if w > 0 && h > 0 {
                                format!("{name} ({w}x{h}){suffix}")
                            } else {
                                format!("{name}{suffix}")
                            };
                            monitors.push(MonitorInfo {
                                id: name.to_string(),
                                label,
                            });
                        }
                        return monitors;
                    }
                }
            }
        }

        if command_exists("xrandr") {
            if let Ok(out) = Command::new("xrandr").arg("--query").output() {
                if out.status.success() {
                    let text = String::from_utf8_lossy(&out.stdout);
                    for line in text.lines() {
                        if line.contains(" connected") {
                            if let Some(name) = line.split_whitespace().next() {
                                monitors.push(MonitorInfo {
                                    id: name.to_string(),
                                    label: name.to_string(),
                                });
                            }
                        }
                    }
                }
            }
        }
    }

    monitors
}

#[derive(Debug, Clone)]
pub struct SetterOption {
    pub id: String,
    pub label: String,
    pub available: bool,
}

pub fn get_available_wallpaper_setters() -> Vec<SetterOption> {
    let mut list = vec![SetterOption {
        id: "auto".to_string(),
        label: "Auto-detect".to_string(),
        available: true,
    }];

    #[cfg(target_os = "linux")]
    {
        let script_exists = expand_user_path("~/.config/hypr/scripts/set-wallpaper.sh").exists();
        list.push(SetterOption {
            id: "set-wallpaper.sh".to_string(),
            label: "set-wallpaper.sh (Hyprland + Matugen)".to_string(),
            available: script_exists,
        });

        let tools: &[(&str, &str)] = &[
            ("awww", "awww (Wayland)"),
            ("swww", "swww (Wayland)"),
            ("mpvpaper", "mpvpaper (Live Video)"),
            ("qs", "Quickshell (qs)"),
            ("waypaper", "waypaper"),
            ("hyprpaper", "hyprpaper"),
            ("swaybg", "swaybg"),
            ("plasma-apply-wallpaperimage", "KDE Plasma"),
            ("gsettings", "GNOME (gsettings)"),
            ("xfconf-query", "XFCE (xfconf-query)"),
            ("feh", "feh (X11)"),
            ("nitrogen", "nitrogen (X11)"),
            ("xwinwrap", "xwinwrap (X11 Video)"),
        ];
        for (id, label) in tools {
            list.push(SetterOption {
                id: (*id).to_string(),
                label: (*label).to_string(),
                available: command_exists(id),
            });
        }
    }

    #[cfg(target_os = "windows")]
    {
        list.push(SetterOption {
            id: "windows_api".to_string(),
            label: "Windows Desktop API".to_string(),
            available: true,
        });
        list.push(SetterOption {
            id: "lively".to_string(),
            label: "Lively Wallpaper".to_string(),
            available: find_lively_exe().is_some(),
        });
    }

    list
}

fn substitute_placeholder(template: &str, file_path: &Path, monitor: &str) -> String {
    let abs = file_path.to_string_lossy();
    let quoted = shell_quote(&abs);
    let mut cmd = template.to_string();
    cmd = cmd.replace("\"{file}\"", &quoted);
    cmd = cmd.replace("'{file}'", &quoted);
    cmd = cmd.replace("{file}", &quoted);

    let mon = if monitor.is_empty() || monitor == "all" {
        String::new()
    } else {
        monitor.to_string()
    };
    cmd = cmd.replace("\"{monitor}\"", &shell_quote(&mon));
    cmd = cmd.replace("'{monitor}'", &shell_quote(&mon));
    cmd = cmd.replace("{monitor}", &shell_quote(&mon));
    cmd
}

#[cfg(target_os = "linux")]
fn run_shell(cmd: &str) -> Result<String, String> {
    let out = Command::new("sh")
        .args(["-c", cmd])
        .output()
        .map_err(|e| format!("Failed to launch command: {e}"))?;
    if out.status.success() {
        Ok(String::from_utf8_lossy(&out.stdout).trim().to_string())
    } else {
        let stderr = String::from_utf8_lossy(&out.stderr).trim().to_string();
        let stdout = String::from_utf8_lossy(&out.stdout).trim().to_string();
        let msg = if !stderr.is_empty() { stderr } else { stdout };
        Err(format!("Command failed ({}): {msg}", out.status))
    }
}

#[cfg(target_os = "linux")]
fn spawn_daemon(cmd: &str) -> Result<(), String> {
    Command::new("sh")
        .args(["-c", cmd])
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map(|_| ())
        .map_err(|e| format!("Failed to spawn daemon: {e}"))
}

pub fn trigger_matugen_refresh() {
    #[cfg(target_os = "linux")]
    {
        if command_exists("hyprctl") {
            let _ = Command::new("hyprctl")
                .arg("reload")
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn();
        }
        if command_exists("qs") {
            let _ = Command::new("qs")
                .args(["ipc", "call", "theme", "reload"])
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .spawn();
        }
    }
}

pub fn is_video_path(path: &Path) -> bool {
    path.extension()
        .and_then(|e| e.to_str())
        .map(|s| matches!(s.to_ascii_lowercase().as_str(), "mp4" | "webm" | "mkv" | "mov" | "avi"))
        .unwrap_or(false)
}

pub fn set_desktop_wallpaper(
    file_path: &Path,
    config: &AppConfig,
    is_video: bool,
    monitor_override: Option<&str>,
) -> Result<String, String> {
    if !file_path.exists() {
        return Err(format!("Wallpaper file not found: {}", file_path.display()));
    }

    let is_video = is_video || is_video_path(file_path);
    let monitor = monitor_override.unwrap_or(&config.wallpaper_monitor);
    let custom = if is_video {
        config.custom_video_wallpaper_cmd.trim()
    } else {
        config.custom_wallpaper_cmd.trim()
    };

    #[cfg(target_os = "linux")]
    {
        if !custom.is_empty() {
            let cmd = substitute_placeholder(custom, file_path, monitor);
            if cmd.starts_with("mpvpaper") || cmd.starts_with("swaybg") || cmd.starts_with("xwinwrap")
            {
                spawn_daemon(&cmd)?;
                return Ok("Custom daemon started".to_string());
            }
            let _ = run_shell(&cmd)?;
            return Ok("Applied with custom command".to_string());
        }

        let is_specific = !monitor.is_empty() && monitor != "all";
        let mut setter = config.wallpaper_setter.as_str();
        if setter.is_empty() || setter == "auto" {
            let script = expand_user_path("~/.config/hypr/scripts/set-wallpaper.sh");
            if is_video && is_specific && command_exists("mpvpaper") {
                setter = "mpvpaper";
            } else if script.exists() && !(is_video && is_specific) {
                setter = "set-wallpaper.sh";
            } else if is_video {
                if command_exists("mpvpaper") {
                    setter = "mpvpaper";
                } else if command_exists("xwinwrap") {
                    setter = "xwinwrap";
                } else {
                    return Err("No live wallpaper backend found (install mpvpaper)".to_string());
                }
            } else if command_exists("awww") {
                setter = "awww";
            } else if command_exists("swww") {
                setter = "swww";
            } else if command_exists("waypaper") {
                setter = "waypaper";
            } else if command_exists("swaybg") {
                setter = "swaybg";
            } else if command_exists("plasma-apply-wallpaperimage") {
                setter = "plasma-apply-wallpaperimage";
            } else if command_exists("gsettings") {
                setter = "gsettings";
            } else if command_exists("feh") {
                setter = "feh";
            } else {
                return Err("No wallpaper backend detected on system".to_string());
            }
        }

        let quoted = shell_quote(&file_path.to_string_lossy());
        let mon_flag = if !monitor.is_empty() && monitor != "all" {
            format!(" -o {}", shell_quote(monitor))
        } else {
            String::new()
        };

        let result_msg = match setter {
            "set-wallpaper.sh" => {
                let script = expand_user_path("~/.config/hypr/scripts/set-wallpaper.sh");
                if !script.exists() {
                    return Err("set-wallpaper.sh not found".to_string());
                }
                let cmd = format!("{} {quoted}", shell_quote(&script.to_string_lossy()));
                let _ = run_shell(&cmd)?;
                "Wallpaper applied via set-wallpaper.sh".to_string()
            }
            "awww" => {
                if is_video {
                    if command_exists("mpvpaper") {
                        let target = if monitor.is_empty() || monitor == "all" {
                            "*"
                        } else {
                            monitor
                        };
                        let _ = run_shell("pkill -x mpvpaper 2>/dev/null || true; awww clear 000000ff 2>/dev/null || true");
                        spawn_daemon(&format!(
                            "mpvpaper -vs -o \"no-audio --loop\" {} {quoted}",
                            shell_quote(target)
                        ))?;
                        return Ok("Live wallpaper started via mpvpaper".to_string());
                    }
                    return Err("awww only supports images/GIFs; mpvpaper not found".to_string());
                }
                let _ = run_shell("pgrep -x awww-daemon >/dev/null || (awww-daemon & sleep 0.4)");
                let cmd = format!(
                    "awww img {quoted}{mon_flag} --transition-type grow --transition-duration 1.0"
                );
                let _ = run_shell(&cmd)?;
                "Wallpaper applied via awww".to_string()
            }
            "swww" => {
                let _ = run_shell("pgrep -x swww-daemon >/dev/null || (swww-daemon & sleep 0.4)");
                let cmd = format!(
                    "swww img {quoted}{mon_flag} --transition-type grow --transition-duration 1.0"
                );
                let _ = run_shell(&cmd)?;
                "Wallpaper applied via swww".to_string()
            }
            "mpvpaper" => {
                let target = if monitor.is_empty() || monitor == "all" {
                    "*"
                } else {
                    monitor
                };
                let _ = run_shell("pkill -x mpvpaper 2>/dev/null || true; awww clear 000000ff 2>/dev/null || true");
                spawn_daemon(&format!(
                    "mpvpaper -vs -o \"no-audio --loop\" {} {quoted}",
                    shell_quote(target)
                ))?;
                "Live wallpaper started via mpvpaper".to_string()
            }
            "qs" => {
                let cmd = format!("qs ipc call wallpaper set {quoted}");
                let _ = run_shell(&cmd)?;
                "Wallpaper applied via Quickshell".to_string()
            }
            "waypaper" => {
                let _ = run_shell(&format!("waypaper --wallpaper {quoted}"))?;
                "Wallpaper applied via waypaper".to_string()
            }
            "hyprpaper" => {
                let abs = file_path.to_string_lossy();
                let target = if monitor.is_empty() || monitor == "all" {
                    String::new()
                } else {
                    monitor.to_string()
                };
                let cmd = format!(
                    "hyprctl hyprpaper preload {} && hyprctl hyprpaper wallpaper {},{}",
                    shell_quote(&abs),
                    shell_quote(&target),
                    shell_quote(&abs)
                );
                let _ = run_shell(&cmd)?;
                "Wallpaper applied via hyprpaper".to_string()
            }
            "swaybg" => {
                let _ = run_shell("pkill -x swaybg 2>/dev/null || true");
                spawn_daemon(&format!("swaybg{mon_flag} -i {quoted} -m fill"))?;
                "Wallpaper applied via swaybg".to_string()
            }
            "plasma-apply-wallpaperimage" => {
                let _ = run_shell(&format!("plasma-apply-wallpaperimage {quoted}"))?;
                "Wallpaper applied via KDE Plasma".to_string()
            }
            "gsettings" => {
                let uri = shell_quote(&format!("file://{}", file_path.to_string_lossy()));
                let _ = run_shell(&format!(
                    "gsettings set org.gnome.desktop.background picture-uri {uri}; gsettings set org.gnome.desktop.background picture-uri-dark {uri}"
                ))?;
                "Wallpaper applied via GNOME".to_string()
            }
            "xfconf-query" => {
                let _ = run_shell(&format!(
                    "for p in $(xfconf-query -c xfce4-desktop -l | grep last-image); do xfconf-query -c xfce4-desktop -p \"$p\" -s {quoted}; done"
                ))?;
                "Wallpaper applied via XFCE".to_string()
            }
            "feh" => {
                let _ = run_shell(&format!("feh --bg-fill {quoted}"))?;
                "Wallpaper applied via feh".to_string()
            }
            "nitrogen" => {
                let _ = run_shell(&format!("nitrogen --set-zoom-fill --save {quoted}"))?;
                "Wallpaper applied via nitrogen".to_string()
            }
            "xwinwrap" => {
                let _ = run_shell("pkill -x xwinwrap 2>/dev/null || true");
                spawn_daemon(&format!(
                    "xwinwrap -fs -fdt -ni -b -nf -un -o 1.0 -- mpv -wid WID --loop --no-audio {quoted}"
                ))?;
                "Live wallpaper started via xwinwrap".to_string()
            }
            other => return Err(format!("Unsupported wallpaper setter: {other}")),
        };

        trigger_matugen_refresh();
        Ok(result_msg)
    }

    #[cfg(target_os = "windows")]
    {
        if !custom.is_empty() {
            let cmd = substitute_placeholder(custom, file_path, monitor);
            Command::new("cmd")
                .args(["/C", &cmd])
                .status()
                .map_err(|e| format!("Custom command failed: {e}"))?;
            return Ok("Applied with custom command".to_string());
        }
        if is_video {
            if let Some(lively) = find_lively_exe() {
                Command::new(lively)
                    .args(["setwp", "--file", &file_path.to_string_lossy()])
                    .spawn()
                    .map_err(|e| format!("Lively launch failed: {e}"))?;
                return Ok("Live wallpaper applied via Lively".to_string());
            }
            return Err("Live wallpapers on Windows require Lively Wallpaper or a custom command".to_string());
        }
        set_windows_static_wallpaper(file_path)?;
        Ok("Wallpaper applied via Windows API".to_string())
    }
}

#[cfg(target_os = "windows")]
fn find_lively_exe() -> Option<PathBuf> {
    if let Ok(local) = std::env::var("LOCALAPPDATA") {
        let p = PathBuf::from(local).join("Programs/Lively Wallpaper/Livelycu.exe");
        if p.exists() {
            return Some(p);
        }
    }
    None
}

#[cfg(target_os = "windows")]
fn set_windows_static_wallpaper(path: &Path) -> Result<(), String> {
    let ps = format!(
        "Add-Type -TypeDefinition 'using System.Runtime.InteropServices; public class W {{ [DllImport(\"user32.dll\", CharSet=CharSet.Unicode)] public static extern int SystemParametersInfo(int uAction, int uParam, string lpvParam, int fuWinIni); }}'; [W]::SystemParametersInfo(20, 0, '{}', 3) | Out-Null",
        path.to_string_lossy().replace('\'', "''")
    );
    let out = Command::new("powershell")
        .args(["-NoProfile", "-Command", &ps])
        .output()
        .map_err(|e| format!("PowerShell failed: {e}"))?;
    if out.status.success() {
        Ok(())
    } else {
        Err(String::from_utf8_lossy(&out.stderr).into_owned())
    }
}
