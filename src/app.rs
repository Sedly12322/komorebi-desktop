use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::AtomicBool;
use std::sync::Arc;
use std::thread;
use std::time::SystemTime;

use crossbeam_channel::{unbounded, Receiver, Sender};
use egui::{CornerRadius, ScrollArea, TextureHandle, TextureOptions};
use reqwest::blocking::Client;

use crate::cache::{cache_size_bytes, clean_old_cache_if_needed, clear_cache, ImageLoader};
use crate::config::AppConfig;
use crate::i18n::{tr, Lang};
use crate::installed::InstalledManager;
use crate::models::{CardSize, NavMode, PfpItem, SearchResult, WallpaperItem};
use crate::providers::{
    build_http_client, download_file, moewalls, osu, pfps,
    wallhaven::{self, WallhavenSearchParams},
};
use crate::theme::{apply_to_ctx, get_palette, matugen_mtime, ThemePalette};
use crate::ui::ambient::AmbientCanvas;
use crate::ui::detail_modal::{render_detail_modal, DetailAction, DetailModalState};
use crate::ui::filters::{render_filter_panel, FilterAction, FilterState};
use crate::ui::grid::{render_pfp_grid, render_wallpaper_grid, GridAction};
use crate::ui::pagination::{render_pagination, PageAction, PaginationState};
use crate::ui::pfp_modal::{render_pfp_modal, PfpAction, PfpModalState};
use crate::ui::settings_modal::{render_settings_modal, SettingsAction, SettingsModalState};
use crate::ui::sidebar::{render_sidebar, SidebarAction};
use crate::ui::toast::ToastManager;
use crate::updater::{check_github_release, UpdateInfo};
use crate::video_preview::VideoPreviewPlayer;
use crate::wallpaper::{
    get_available_monitors, get_available_wallpaper_setters, set_desktop_wallpaper, MonitorInfo,
    SetterOption,
};

enum DetailPayload {
    Wallhaven(WallpaperItem),
    MoeWalls {
        detail: moewalls::MoeDetail,
    },
}

enum BgEvent {
    SearchWallpapers {
        seq: u64,
        mode: NavMode,
        res: Result<SearchResult, String>,
    },
    SearchPfps {
        seq: u64,
        res: Result<(Vec<PfpItem>, bool), String>,
    },
    DetailLoaded {
        item_id: String,
        res: Result<DetailPayload, String>,
    },
    DownloadProgress {
        item_id: String,
        done: u64,
        total: u64,
    },
    DownloadFinished {
        item: WallpaperItem,
        dest: Result<PathBuf, String>,
        register_installed: bool,
        auto_set: bool,
        monitor_override: Option<String>,
    },
    SetWallpaperFinished(Result<String, String>),
    CopyImageFinished(Result<(), String>),
    PfpActionFinished {
        toast_msg: Result<String, String>,
    },
    InstalledScanned {
        added: usize,
        manager: InstalledManager,
    },
    UpdateChecked(Result<UpdateInfo, String>),
    MonitorsRefreshed(Vec<MonitorInfo>),
    SettersRefreshed(Vec<SetterOption>),
    HoverPreviewResolved {
        item_id: String,
        preview_url: String,
        download_url: String,
    },
}

#[derive(Default)]
struct HoverPreviewState {
    item_id: String,
    hovered_since: f64,
    resolving: bool,
    source_started: String,
    player: Option<VideoPreviewPlayer>,
    tex: Option<TextureHandle>,
}

impl HoverPreviewState {
    fn stop(&mut self) {
        if let Some(mut vp) = self.player.take() {
            vp.stop();
        }
        self.tex = None;
        self.item_id.clear();
        self.source_started.clear();
        self.resolving = false;
    }
}

pub struct KomorebiApp {
    client: Client,
    config: AppConfig,
    palette: ThemePalette,
    installed: InstalledManager,
    loader: ImageLoader,
    ambient: AmbientCanvas,
    toasts: ToastManager,
    filters: FilterState,
    pagination: PaginationState,
    mode: NavMode,
    page: usize,
    last_page: usize,
    total_results: usize,
    items: Vec<WallpaperItem>,
    pfp_items: Vec<PfpItem>,
    pfp_has_next: bool,
    loading: bool,
    search_seq: u64,
    random_seed: String,
    emblem_tex: Option<TextureHandle>,
    monitors: Vec<MonitorInfo>,
    setters: Vec<SetterOption>,
    update_info: Option<UpdateInfo>,
    detail_modal: Option<DetailModalState>,
    pfp_modal: Option<PfpModalState>,
    settings_modal: Option<SettingsModalState>,
    hover_preview: HoverPreviewState,
    download_cancel: Option<Arc<AtomicBool>>,
    last_matugen_check: f64,
    last_matugen_mtime: Option<SystemTime>,
    bg_tx: Sender<BgEvent>,
    bg_rx: Receiver<BgEvent>,
}

impl KomorebiApp {
    pub fn new(cc: &eframe::CreationContext<'_>) -> Self {
        let client = build_http_client();
        let config = AppConfig::load();
        let lang = Lang::from_code(&config.language);
        let palette = get_palette(&config.theme, lang);
        apply_to_ctx(&cc.egui_ctx, &palette);

        let installed = InstalledManager::load_default();
        let loader = ImageLoader::new(client.clone());
        let (bg_tx, bg_rx) = unbounded();
        let emblem_tex = load_emblem_texture(&cc.egui_ctx);

        let mut filters = FilterState::default();
        filters.wh_cat_general = config.categories.chars().next() == Some('1');
        filters.wh_cat_anime = config.categories.chars().nth(1) == Some('1');
        filters.wh_cat_people = config.categories.chars().nth(2) == Some('1');
        filters.wh_sfw = config.purity.chars().next() == Some('1');
        filters.wh_sketchy = config.purity.chars().nth(1) == Some('1');
        filters.wh_nsfw = config.purity.chars().nth(2) == Some('1');
        filters.wh_sorting = config.sorting.clone();
        filters.wh_top_range = config.top_range.clone();
        filters.wh_atleast = config.atleast.clone();
        filters.wh_ratios = config.ratios.clone();
        filters.wh_color = config.color.clone();
        filters.moe_category = config.moewalls_category.clone();

        let mut app = Self {
            client,
            config,
            palette,
            installed,
            loader,
            ambient: AmbientCanvas::new(),
            toasts: ToastManager::default(),
            filters,
            pagination: PaginationState::default(),
            mode: NavMode::Wallhaven,
            page: 1,
            last_page: 1,
            total_results: 0,
            items: Vec::new(),
            pfp_items: Vec::new(),
            pfp_has_next: false,
            loading: false,
            search_seq: 0,
            random_seed: String::new(),
            emblem_tex,
            monitors: vec![MonitorInfo {
                id: "all".into(),
                label: tr(lang, "monitor_all").into(),
            }],
            setters: get_available_wallpaper_setters(),
            update_info: None,
            detail_modal: None,
            pfp_modal: None,
            settings_modal: None,
            hover_preview: HoverPreviewState::default(),
            download_cancel: None,
            last_matugen_check: 0.0,
            last_matugen_mtime: matugen_mtime(),
            bg_tx,
            bg_rx,
        };

        // Background housekeeping: prune old cache, scan download directory, detect monitors, updates
        thread::spawn(|| {
            clean_old_cache_if_needed();
        });
        app.spawn_rescan_installed(&cc.egui_ctx);
        app.spawn_refresh_system(&cc.egui_ctx);
        if app.config.check_updates_on_launch {
            app.spawn_update_check(&cc.egui_ctx);
        }
        app.trigger_search(&cc.egui_ctx, 1);

        app
    }

    fn lang(&self) -> Lang {
        Lang::from_code(&self.config.language)
    }

    fn card_size(&self) -> CardSize {
        CardSize::from_str_lossy(&self.config.card_size)
    }

    fn refresh_theme(&mut self, ctx: &egui::Context, theme_id: &str) {
        self.palette = get_palette(theme_id, self.lang());
        apply_to_ctx(ctx, &self.palette);
    }

    fn spawn_rescan_installed(&self, ctx: &egui::Context) {
        let tx = self.bg_tx.clone();
        let ctx_c = ctx.clone();
        let dl_dir = self.config.effective_download_dir();
        thread::spawn(move || {
            let mut mgr = InstalledManager::load_default();
            let added = mgr.scan_directory(&dl_dir);
            let _ = tx.send(BgEvent::InstalledScanned {
                added,
                manager: mgr,
            });
            ctx_c.request_repaint();
        });
    }

    fn spawn_refresh_system(&self, ctx: &egui::Context) {
        let tx = self.bg_tx.clone();
        let ctx_c = ctx.clone();
        thread::spawn(move || {
            let mons = get_available_monitors();
            let _ = tx.send(BgEvent::MonitorsRefreshed(mons));
            let sets = get_available_wallpaper_setters();
            let _ = tx.send(BgEvent::SettersRefreshed(sets));
            ctx_c.request_repaint();
        });
    }

    fn spawn_update_check(&self, ctx: &egui::Context) {
        let tx = self.bg_tx.clone();
        let ctx_c = ctx.clone();
        let client = self.client.clone();
        thread::spawn(move || {
            let res = check_github_release(&client);
            let _ = tx.send(BgEvent::UpdateChecked(res));
            ctx_c.request_repaint();
        });
    }

    fn trigger_search(&mut self, ctx: &egui::Context, target_page: usize) {
        self.page = target_page.max(1);
        self.search_seq = self.search_seq.wrapping_add(1);
        let seq = self.search_seq;
        let mode = self.mode;

        if mode == NavMode::Installed {
            self.loading = false;
            self.refresh_installed_view();
            return;
        }

        if mode == NavMode::Osu {
            self.loading = false;
            let res = osu::search(&osu::OsuSearchParams {
                query: self.filters.query.clone(),
                season: self.filters.osu_season.clone(),
                theme: self.filters.osu_theme.clone(),
                sort: self.filters.osu_sort.clone(),
                clean_only: self.filters.osu_clean_only,
                page: self.page,
                per_page: self.config.per_page.max(24),
            });
            self.last_page = res.last_page.max(1);
            self.total_results = res.total;
            self.items = res.items;
            return;
        }

        self.loading = true;
        let tx = self.bg_tx.clone();
        let ctx_c = ctx.clone();
        let client = self.client.clone();
        let f = self.filters.clone();

        if mode == NavMode::Pfps {
            let page = self.page;
            thread::spawn(move || {
                let res = pfps::fetch_pfps(&client, &f.pfp_category, &f.pfp_sort, &f.query, page);
                let _ = tx.send(BgEvent::SearchPfps { seq, res });
                ctx_c.request_repaint();
            });
            return;
        }

        if mode == NavMode::MoeWalls {
            let page = self.page;
            thread::spawn(move || {
                let res = moewalls::search(
                    &client,
                    &moewalls::MoeSearchParams {
                        query: f.query,
                        category: f.moe_category,
                        resolution: f.moe_resolution,
                        page,
                    },
                );
                let _ = tx.send(BgEvent::SearchWallpapers { seq, mode, res });
                ctx_c.request_repaint();
            });
            return;
        }

        // Wallhaven
        if self.page == 1 || self.random_seed.is_empty() {
            self.random_seed = format!("{:06x}", (ctx.input(|i| i.time) * 1000.0) as u32 & 0xFFFFFF);
        }
        let seed = if f.wh_sorting == "random" {
            self.random_seed.clone()
        } else {
            String::new()
        };
        let categories = f.categories_bits();
        let purity = f.purity_bits();
        let params = WallhavenSearchParams {
            query: f.query,
            categories,
            purity,
            sorting: f.wh_sorting,
            order: "desc".into(),
            top_range: f.wh_top_range,
            atleast: f.wh_atleast,
            ratios: f.wh_ratios,
            color: f.wh_color,
            page: self.page,
            seed,
            api_key: self.config.api_key.clone(),
        };
        thread::spawn(move || {
            let res = wallhaven::search(&client, &params);
            let _ = tx.send(BgEvent::SearchWallpapers { seq, mode, res });
            ctx_c.request_repaint();
        });
    }

    fn refresh_installed_view(&mut self) {
        let all = self.installed.search(
            &self.filters.query,
            &self.filters.inst_media_type,
            &self.filters.inst_provider,
            &self.filters.inst_sort,
        );
        let per_page = self.config.per_page.max(24);
        self.total_results = all.len();
        self.last_page = all.len().div_ceil(per_page).max(1);
        self.page = self.page.clamp(1, self.last_page);
        let start = (self.page - 1) * per_page;
        let end = (start + per_page).min(all.len());
        self.items = if start < all.len() {
            all[start..end].to_vec()
        } else {
            Vec::new()
        };
    }

    fn open_detail_index(&mut self, ctx: &egui::Context, idx: usize) {
        if idx >= self.items.len() {
            return;
        }
        if let Some(prev) = &mut self.detail_modal {
            prev.stop_video();
        }
        let mut item = self.items[idx].clone();
        let local_path = if !item.local_path.is_empty() && Path::new(&item.local_path).exists() {
            item.local_path.clone()
        } else {
            self.installed.local_path_for_id(&item.id).unwrap_or_default()
        };
        let is_inst = !local_path.is_empty() || item.is_installed;
        if !local_path.is_empty() {
            item.local_path = local_path.clone();
            item.is_installed = true;
        }

        let mut modal = DetailModalState::new(
            item.clone(),
            idx,
            self.items.len(),
            is_inst,
            local_path,
            self.config.wallpaper_monitor.clone(),
        );

        let needs_fetch = (item.source.eq_ignore_ascii_case("wallhaven") && item.tags.is_empty())
            || (item.source.eq_ignore_ascii_case("moewalls")
                && (item.path.is_empty() || item.preview_video_url.is_empty()));

        if needs_fetch {
            modal.detail_loading = true;
            let tx = self.bg_tx.clone();
            let ctx_c = ctx.clone();
            let client = self.client.clone();
            let api_key = self.config.api_key.clone();
            let item_id = item.id.clone();
            let src = item.source.clone();
            let url = item.url.clone();
            thread::spawn(move || {
                let res = if src.eq_ignore_ascii_case("moewalls") {
                    moewalls::get_detail(&client, &url)
                        .map(|detail| DetailPayload::MoeWalls { detail })
                } else {
                    wallhaven::get_detail(&client, &item_id, &api_key)
                        .map(DetailPayload::Wallhaven)
                };
                let _ = tx.send(BgEvent::DetailLoaded { item_id, res });
                ctx_c.request_repaint();
            });
        }

        self.hover_preview.stop();
        self.detail_modal = Some(modal);
    }

    fn spawn_download_wallpaper(
        &mut self,
        ctx: &egui::Context,
        mut item: WallpaperItem,
        dest_path: PathBuf,
        register_installed: bool,
        auto_set: bool,
        monitor_override: Option<String>,
    ) {
        if let Some(prev) = &self.download_cancel {
            prev.store(true, std::sync::atomic::Ordering::Relaxed);
        }
        let cancel = Arc::new(AtomicBool::new(false));
        self.download_cancel = Some(Arc::clone(&cancel));
        if let Some(m) = &mut self.detail_modal {
            if m.item.id == item.id {
                m.download_progress = Some((0, item.file_size));
            }
        }

        let tx = self.bg_tx.clone();
        let ctx_c = ctx.clone();
        let client = self.client.clone();
        thread::spawn(move || {
            let url = if item.source.eq_ignore_ascii_case("moewalls") && item.path.is_empty() {
                match moewalls::get_download_url(&client, &mut item) {
                    Ok(u) => u,
                    Err(e) => {
                        let _ = tx.send(BgEvent::DownloadFinished {
                            item,
                            dest: Err(e),
                            register_installed,
                            auto_set,
                            monitor_override,
                        });
                        ctx_c.request_repaint();
                        return;
                    }
                }
            } else {
                item.path.clone()
            };

            if url.is_empty() {
                let _ = tx.send(BgEvent::DownloadFinished {
                    item,
                    dest: Err("Missing wallpaper download URL".into()),
                    register_installed,
                    auto_set,
                    monitor_override,
                });
                ctx_c.request_repaint();
                return;
            }

            let headers: Vec<(&str, &str)> = if item.source.eq_ignore_ascii_case("moewalls") {
                vec![("Referer", moewalls::BASE_URL)]
            } else {
                vec![]
            };

            let item_id = item.id.clone();
            let mut last_emit = 0u64;
            let res = download_file(
                &client,
                &url,
                &dest_path,
                &headers,
                |done, total| {
                    if done == total || done.saturating_sub(last_emit) >= 48 * 1024 {
                        last_emit = done;
                        let _ = tx.send(BgEvent::DownloadProgress {
                            item_id: item_id.clone(),
                            done,
                            total,
                        });
                        ctx_c.request_repaint();
                    }
                },
                &cancel,
            )
            .map(|_| dest_path);

            let _ = tx.send(BgEvent::DownloadFinished {
                item,
                dest: res,
                register_installed,
                auto_set,
                monitor_override,
            });
            ctx_c.request_repaint();
        });
    }

    fn spawn_set_wallpaper(&self, ctx: &egui::Context, file_path: PathBuf, is_video: bool, monitor_override: Option<String>) {
        let tx = self.bg_tx.clone();
        let ctx_c = ctx.clone();
        let cfg = self.config.clone();
        thread::spawn(move || {
            let res = set_desktop_wallpaper(&file_path, &cfg, is_video, monitor_override.as_deref());
            let _ = tx.send(BgEvent::SetWallpaperFinished(res));
            ctx_c.request_repaint();
        });
    }

    fn poll_bg_events(&mut self, ctx: &egui::Context) {
        let lang = self.lang();
        while let Ok(ev) = self.bg_rx.try_recv() {
            match ev {
                BgEvent::SearchWallpapers { seq, mode, res } => {
                    if seq != self.search_seq || mode != self.mode {
                        continue;
                    }
                    self.loading = false;
                    match res {
                        Ok(sr) => {
                            self.page = sr.current_page.max(1);
                            self.last_page = sr.last_page.max(1);
                            self.total_results = sr.total;
                            self.items = sr.items;
                        }
                        Err(e) => {
                            self.toasts.error(ctx, e);
                        }
                    }
                }
                BgEvent::SearchPfps { seq, res } => {
                    if seq != self.search_seq || self.mode != NavMode::Pfps {
                        continue;
                    }
                    self.loading = false;
                    match res {
                        Ok((list, has_next)) => {
                            self.pfp_items = list;
                            self.pfp_has_next = has_next;
                        }
                        Err(e) => {
                            self.toasts.error(ctx, e);
                        }
                    }
                }
                BgEvent::DetailLoaded { item_id, res } => {
                    if let Some(m) = &mut self.detail_modal {
                        if m.item.id == item_id {
                            m.detail_loading = false;
                            match res {
                                Ok(DetailPayload::Wallhaven(full)) => {
                                    let saved_local = m.item.local_path.clone();
                                    let saved_inst = m.item.is_installed;
                                    m.item = full;
                                    if saved_inst {
                                        m.item.local_path = saved_local;
                                        m.item.is_installed = true;
                                    }
                                }
                                Ok(DetailPayload::MoeWalls { detail, .. }) => {
                                    if !detail.preview_video_url.is_empty() {
                                        m.item.preview_video_url = detail.preview_video_url;
                                    }
                                    if !detail.download_url.is_empty() {
                                        m.item.path = detail.download_url;
                                    }
                                    if !detail.tags.is_empty() {
                                        m.item.tags = detail.tags;
                                    }
                                }
                                Err(e) => {
                                    self.toasts.warning(ctx, e);
                                }
                            }
                        }
                    }
                }
                BgEvent::DownloadProgress { item_id, done, total } => {
                    if let Some(m) = &mut self.detail_modal {
                        if m.item.id == item_id {
                            m.download_progress = Some((done, total));
                        }
                    }
                }
                BgEvent::DownloadFinished {
                    mut item,
                    dest,
                    register_installed,
                    auto_set,
                    monitor_override,
                } => {
                    if let Some(m) = &mut self.detail_modal {
                        if m.item.id == item.id {
                            m.download_progress = None;
                        }
                    }
                    match dest {
                        Ok(path) => {
                            if register_installed {
                                self.installed.register_download(&item, &path);
                                let abs = path.to_string_lossy().into_owned();
                                item.is_installed = true;
                                item.local_path = abs.clone();
                                if let Some(m) = &mut self.detail_modal {
                                    if m.item.id == item.id {
                                        m.is_installed = true;
                                        m.local_path = abs.clone();
                                        m.item.is_installed = true;
                                        m.item.local_path = abs.clone();
                                    }
                                }
                                if let Some(slot) = self.items.iter_mut().find(|w| w.id == item.id) {
                                    slot.is_installed = true;
                                    slot.local_path = abs;
                                }
                            }
                            self.toasts.success(
                                ctx,
                                format!(
                                    "Saved: {}",
                                    path.file_name().and_then(|s| s.to_str()).unwrap_or("wallpaper")
                                ),
                            );
                            if auto_set {
                                self.spawn_set_wallpaper(ctx, path, item.is_animated, monitor_override);
                            }
                        }
                        Err(e) => {
                            if e == "Download cancelled" {
                                self.toasts.info(ctx, tr(lang, "cancel"));
                            } else {
                                self.toasts.error(ctx, e);
                            }
                        }
                    }
                }
                BgEvent::SetWallpaperFinished(res) => match res {
                    Ok(msg) => {
                        self.toasts.success(ctx, msg);
                        if matches!(
                            self.config.theme.as_str(),
                            "matugen" | "auto" | "system" | "pywal"
                        ) {
                            self.refresh_theme(ctx, &self.config.theme.clone());
                        }
                    }
                    Err(e) => self.toasts.error(ctx, e),
                },
                BgEvent::CopyImageFinished(res) => match res {
                    Ok(()) => self.toasts.success(ctx, "Copied image to clipboard"),
                    Err(e) => self.toasts.error(ctx, e),
                },
                BgEvent::PfpActionFinished { toast_msg } => {
                    if let Some(m) = &mut self.pfp_modal {
                        m.busy = false;
                    }
                    match toast_msg {
                        Ok(msg) => self.toasts.success(ctx, msg),
                        Err(e) => self.toasts.error(ctx, e),
                    }
                }
                BgEvent::InstalledScanned { added, manager } => {
                    self.installed = manager;
                    if self.mode == NavMode::Installed {
                        self.refresh_installed_view();
                    }
                    if added > 0 {
                        self.toasts
                            .info(ctx, format!("Indexed {added} local wallpaper(s)"));
                    }
                }
                BgEvent::UpdateChecked(res) => {
                    if let Some(sm) = &mut self.settings_modal {
                        sm.checking_updates = false;
                        sm.update_status = Some(res.clone());
                    }
                    if let Ok(upd) = res {
                        self.update_info = Some(upd);
                    }
                }
                BgEvent::MonitorsRefreshed(mons) => {
                    self.monitors = mons.clone();
                    if let Some(sm) = &mut self.settings_modal {
                        sm.monitors = mons;
                    }
                }
                BgEvent::SettersRefreshed(sets) => {
                    self.setters = sets.clone();
                    if let Some(sm) = &mut self.settings_modal {
                        sm.setters = sets;
                    }
                }
                BgEvent::HoverPreviewResolved {
                    item_id,
                    preview_url,
                    download_url,
                } => {
                    if let Some(slot) = self.items.iter_mut().find(|w| w.id == item_id) {
                        if !preview_url.is_empty() {
                            slot.preview_video_url = preview_url.clone();
                        }
                        if slot.path.is_empty() && !download_url.is_empty() {
                            slot.path = download_url;
                        }
                    }
                    if self.hover_preview.item_id == item_id {
                        self.hover_preview.resolving = false;
                        if !preview_url.is_empty()
                            && self.hover_preview.source_started.is_empty()
                            && self.detail_modal.is_none()
                            && self.pfp_modal.is_none()
                            && self.settings_modal.is_none()
                        {
                            self.hover_preview.source_started = preview_url.clone();
                            self.hover_preview.player = Some(VideoPreviewPlayer::start(
                                self.client.clone(),
                                preview_url,
                                440,
                                260,
                                ctx.clone(),
                            ));
                        }
                    }
                }
            }
        }
    }

    fn handle_shortcuts(&mut self, ctx: &egui::Context) {
        let wants_kb = ctx.wants_keyboard_input();
        let any_modal =
            self.settings_modal.is_some() || self.detail_modal.is_some() || self.pfp_modal.is_some();
        ctx.input(|i| {
            if !any_modal && i.key_pressed(egui::Key::Escape) {
                self.pagination.jump_open = false;
            }
            if !wants_kb
                && ((i.modifiers.ctrl && i.key_pressed(egui::Key::K))
                    || i.key_pressed(egui::Key::Slash))
            {
                self.filters.focus_search = true;
            }
        });

        // Keyboard prev/next inside detail modal
        if self.detail_modal.is_some() && !wants_kb {
            let (left, right) = ctx.input(|i| {
                (
                    i.key_pressed(egui::Key::ArrowLeft),
                    i.key_pressed(egui::Key::ArrowRight),
                )
            });
            if left {
                if let Some(m) = &self.detail_modal {
                    if m.index_in_grid > 0 {
                        let target = m.index_in_grid - 1;
                        self.open_detail_index(ctx, target);
                    }
                }
            } else if right {
                if let Some(m) = &self.detail_modal {
                    if m.index_in_grid + 1 < m.total_in_grid {
                        let target = m.index_in_grid + 1;
                        self.open_detail_index(ctx, target);
                    }
                }
            }
        }
    }

    fn update_hover_preview(&mut self, ctx: &egui::Context, hovered_animated: Option<usize>, now: f64) {
        if self.detail_modal.is_some()
            || self.pfp_modal.is_some()
            || self.settings_modal.is_some()
            || !ctx.input(|i| i.focused)
        {
            self.hover_preview.stop();
            return;
        }

        let Some(idx) = hovered_animated else {
            self.hover_preview.stop();
            return;
        };

        let Some(item) = self.items.get(idx).cloned() else {
            self.hover_preview.stop();
            return;
        };

        if item.id != self.hover_preview.item_id {
            self.hover_preview.stop();
            self.hover_preview.item_id = item.id.clone();
            self.hover_preview.hovered_since = now;
        }

        if now - self.hover_preview.hovered_since < 0.25 {
            ctx.request_repaint_after(std::time::Duration::from_millis(40));
            return;
        }

        if self.hover_preview.source_started.is_empty() {
            let local = if !item.local_path.is_empty() && Path::new(&item.local_path).exists() {
                item.local_path.clone()
            } else {
                self.installed.local_path_for_id(&item.id).unwrap_or_default()
            };

            let src = if !local.is_empty() {
                local
            } else if !item.preview_video_url.is_empty() {
                item.preview_video_url.clone()
            } else {
                String::new()
            };

            if !src.is_empty() {
                self.hover_preview.source_started = src.clone();
                self.hover_preview.player = Some(VideoPreviewPlayer::start(
                    self.client.clone(),
                    src,
                    440,
                    260,
                    ctx.clone(),
                ));
            } else if item.source.eq_ignore_ascii_case("moewalls")
                && !item.url.is_empty()
                && !self.hover_preview.resolving
            {
                self.hover_preview.resolving = true;
                let tx = self.bg_tx.clone();
                let ctx_c = ctx.clone();
                let client = self.client.clone();
                let item_id = item.id.clone();
                let url = item.url.clone();
                thread::spawn(move || {
                    if let Ok(detail) = moewalls::get_detail(&client, &url) {
                        let _ = tx.send(BgEvent::HoverPreviewResolved {
                            item_id,
                            preview_url: detail.preview_video_url,
                            download_url: detail.download_url,
                        });
                        ctx_c.request_repaint();
                    }
                });
            }
        }
    }
}

impl eframe::App for KomorebiApp {
    fn on_exit(&mut self, _gl: Option<&eframe::glow::Context>) {
        if let Some(c) = &self.download_cancel {
            c.store(true, std::sync::atomic::Ordering::Relaxed);
        }
        self.hover_preview.stop();
        if let Some(mut m) = self.detail_modal.take() {
            m.stop_video();
        }
        let _ = self.config.save();
    }

    fn update(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        self.loader.poll(ctx);
        self.poll_bg_events(ctx);

        // Live Matugen hot-reload watcher (every 1.5s)
        let now = ctx.input(|i| i.time);
        if now - self.last_matugen_check > 1.5 {
            self.last_matugen_check = now;
            if matches!(
                self.config.theme.as_str(),
                "matugen" | "auto" | "system" | "pywal" | "kde" | "gtk"
            ) {
                let mtime = matugen_mtime();
                if mtime != self.last_matugen_mtime {
                    self.last_matugen_mtime = mtime;
                    let t = self.config.theme.clone();
                    self.refresh_theme(ctx, &t);
                }
            }
        }

        self.handle_shortcuts(ctx);

        let lang = self.lang();
        let pal = self.palette.clone();
        let installed_ids = self.installed.installed_ids();
        let stats = self.installed.get_stats();
        let stats_text = format!(
            "{} items ({} static, {} live)  •  {}",
            stats.total,
            stats.static_count,
            stats.live_count,
            stats.total_size_human()
        );

        // SIDEBAR
        let mut sidebar_action = SidebarAction::None;
        egui::SidePanel::left("komorebi_sidebar")
            .resizable(false)
            .exact_width(252.0)
            .frame(egui::Frame::new().fill(pal.bg_surface))
            .show(ctx, |ui| {
                sidebar_action = render_sidebar(
                    ui,
                    &pal,
                    lang,
                    self.mode,
                    &self.config.theme,
                    self.config.auto_set_wallpaper,
                    stats.total,
                    self.emblem_tex.as_ref(),
                    self.update_info.as_ref(),
                );
            });

        match sidebar_action {
            SidebarAction::None => {}
            SidebarAction::SelectMode(m) => {
                if self.mode != m {
                    self.mode = m;
                    self.pfp_items.clear();
                    self.items.clear();
                    self.total_results = 0;
                    self.pagination.jump_open = false;
                    self.trigger_search(ctx, 1);
                }
            }
            SidebarAction::ChangeTheme(tid) => {
                self.config.theme = tid.clone();
                let _ = self.config.save();
                self.refresh_theme(ctx, &tid);
            }
            SidebarAction::ToggleAutoWallpaper(val) => {
                self.config.auto_set_wallpaper = val;
                let _ = self.config.save();
            }
            SidebarAction::OpenSettings => {
                let sz = cache_size_bytes();
                self.settings_modal = Some(SettingsModalState::new(
                    &self.config,
                    sz,
                    self.monitors.clone(),
                    self.setters.clone(),
                    self.update_info.as_ref(),
                ));
            }
            SidebarAction::OpenUpdateUrl(url) => {
                let _ = open::that(url);
            }
        }

        // MAIN CONTENT PANEL + AMBIENT CANVAS
        egui::CentralPanel::default()
            .frame(egui::Frame::new().fill(pal.bg_base).inner_margin(egui::Margin::same(14)))
            .show(ctx, |ui| {
                let panel_rect = ui.max_rect();
                let bg_painter = ui.painter().with_clip_rect(panel_rect);
                self.ambient
                    .paint(ctx, &bg_painter, panel_rect, &pal, self.config.background_effects);

                let content_w = ui.available_width().max(260.0);
                let card_sz = self.card_size();
                let has_api_key = !self.config.api_key.trim().is_empty();

                let filter_action = render_filter_panel(
                    ui,
                    &pal,
                    lang,
                    self.mode,
                    &mut self.filters,
                    card_sz,
                    content_w,
                    has_api_key,
                    &stats_text,
                );
                match filter_action {
                    FilterAction::None => {}
                    FilterAction::Search => {
                        self.trigger_search(ctx, 1);
                    }
                    FilterAction::SetCardSize(sz) => {
                        self.config.card_size = sz.as_str().to_string();
                        let _ = self.config.save();
                    }
                    FilterAction::NsfwBlockedNeedsApiKey => {
                        self.toasts.warning(ctx, tr(lang, "nsfw_req_msg"));
                    }
                    FilterAction::OpenDownloadFolder => {
                        let _ = open::that(self.config.effective_download_dir());
                    }
                    FilterAction::RescanInstalled => {
                        self.spawn_rescan_installed(ctx);
                    }
                }

                ui.add_space(10.0);

                // Scrollable gallery + pagination
                let has_pagination = match self.mode {
                    NavMode::Pfps => self.page > 1 || self.pfp_has_next,
                    _ => self.last_page > 1,
                };
                let scroll_h = if has_pagination {
                    (ui.available_height() - 48.0).max(160.0)
                } else {
                    ui.available_height()
                };
                let grid_w = (content_w - 14.0).max(260.0);

                if let Some(vp) = &self.hover_preview.player {
                    if let Some(img) = vp.try_next_frame() {
                        if let Some(tex) = &mut self.hover_preview.tex {
                            tex.set(img, TextureOptions::LINEAR);
                        } else {
                            self.hover_preview.tex = Some(ctx.load_texture(
                                format!("hover_live_{}", self.hover_preview.item_id),
                                img,
                                TextureOptions::LINEAR,
                            ));
                        }
                    }
                }

                let mut hovered_animated: Option<usize> = None;
                let mut grid_action = GridAction::None;
                let card_sz_grid = self.card_size();
                ScrollArea::vertical()
                    .id_salt("main_gallery_scroll")
                    .auto_shrink([false, false])
                    .max_height(scroll_h)
                    .show(ui, |ui| {
                        if self.mode == NavMode::Pfps {
                            grid_action = render_pfp_grid(
                                ui,
                                &pal,
                                lang,
                                card_sz_grid,
                                grid_w,
                                &self.pfp_items,
                                self.loading,
                                &mut self.loader,
                            );
                        } else {
                            let hover_video = self
                                .hover_preview
                                .tex
                                .as_ref()
                                .map(|t| (self.hover_preview.item_id.as_str(), t));
                            grid_action = render_wallpaper_grid(
                                ui,
                                &pal,
                                lang,
                                self.mode,
                                card_sz_grid,
                                grid_w,
                                &self.items,
                                &installed_ids,
                                self.loading,
                                &mut self.loader,
                                hover_video,
                                &mut hovered_animated,
                            );
                        }
                    });
                self.update_hover_preview(ctx, hovered_animated, now);

                match grid_action {
                    GridAction::None => {}
                    GridAction::OpenWallpaper(idx) => {
                        self.open_detail_index(ctx, idx);
                    }
                    GridAction::OpenPfp(idx) => {
                        if let Some(pfp) = self.pfp_items.get(idx).cloned() {
                            self.pfp_modal = Some(PfpModalState {
                                item: pfp,
                                busy: false,
                            });
                        }
                    }
                    GridAction::QuickDownload(idx) => {
                        if let Some(w) = self.items.get(idx).cloned() {
                            let existing = if !w.local_path.is_empty() && Path::new(&w.local_path).exists() {
                                Some(w.local_path.clone())
                            } else {
                                self.installed.local_path_for_id(&w.id)
                            };
                            if let Some(p) = existing {
                                self.toasts.info(ctx, format!("Already downloaded: {p}"));
                            } else {
                                let dest = self
                                    .config
                                    .effective_download_dir()
                                    .join(w.suggested_filename());
                                self.spawn_download_wallpaper(
                                    ctx,
                                    w,
                                    dest,
                                    true,
                                    self.config.auto_set_wallpaper,
                                    None,
                                );
                            }
                        }
                    }
                    GridAction::QuickSetWallpaper(idx) => {
                        if let Some(w) = self.items.get(idx).cloned() {
                            let path_str = if !w.local_path.is_empty() && Path::new(&w.local_path).exists() {
                                w.local_path.clone()
                            } else {
                                self.installed.local_path_for_id(&w.id).unwrap_or_default()
                            };
                            if !path_str.is_empty() {
                                self.spawn_set_wallpaper(ctx, PathBuf::from(path_str), w.is_animated, None);
                            } else {
                                let dest = self
                                    .config
                                    .effective_download_dir()
                                    .join(w.suggested_filename());
                                self.spawn_download_wallpaper(ctx, w, dest, true, true, None);
                            }
                        }
                    }
                    GridAction::QuickUninstallWallpaper(idx) => {
                        if let Some(w) = self.items.get(idx).cloned() {
                            let path_str = if !w.local_path.is_empty() {
                                w.local_path.clone()
                            } else {
                                self.installed.local_path_for_id(&w.id).unwrap_or_default()
                            };
                            if !path_str.is_empty() {
                                match self.installed.uninstall(&path_str, true) {
                                    Ok(()) => {
                                        self.toasts.info(ctx, "Wallpaper uninstalled");
                                        if self.mode == NavMode::Installed {
                                            self.refresh_installed_view();
                                        }
                                    }
                                    Err(e) => self.toasts.error(ctx, e),
                                }
                            }
                        }
                    }
                }

                if has_pagination {
                    let page_act = render_pagination(
                        ui,
                        &pal,
                        &mut self.pagination,
                        content_w,
                        self.page,
                        self.last_page,
                        self.total_results,
                        if self.mode == NavMode::Pfps {
                            Some(self.pfp_has_next)
                        } else {
                            None
                        },
                    );
                    if let PageAction::GoToPage(p) = page_act {
                        self.trigger_search(ctx, p);
                    }
                }
            });

        // MODALS
        if let Some(mut modal) = self.detail_modal.take() {
            let act = render_detail_modal(ctx, &pal, lang, &mut modal, &self.monitors, &mut self.loader);
            match act {
                DetailAction::None => {
                    self.detail_modal = Some(modal);
                }
                DetailAction::Close => {
                    modal.stop_video();
                }
                DetailAction::Prev => {
                    let prev_idx = modal.index_in_grid.saturating_sub(1);
                    modal.stop_video();
                    self.open_detail_index(ctx, prev_idx);
                }
                DetailAction::Next => {
                    let next_idx = modal.index_in_grid + 1;
                    modal.stop_video();
                    self.open_detail_index(ctx, next_idx);
                }
                DetailAction::StartVideoPreview(src) => {
                    modal.stop_video();
                    modal.video_source_started = src.clone();
                    modal.video_player = Some(VideoPreviewPlayer::start(
                        self.client.clone(),
                        src,
                        960,
                        540,
                        ctx.clone(),
                    ));
                    self.detail_modal = Some(modal);
                }
                DetailAction::Download => {
                    let dest = self
                        .config
                        .effective_download_dir()
                        .join(modal.item.suggested_filename());
                    let item_c = modal.item.clone();
                    let auto_set = self.config.auto_set_wallpaper;
                    let mon_ovr = Some(modal.selected_monitor.clone());
                    self.detail_modal = Some(modal);
                    self.spawn_download_wallpaper(ctx, item_c, dest, true, auto_set, mon_ovr);
                }
                DetailAction::SaveAs => {
                    let suggested = modal.item.suggested_filename();
                    let chosen = rfd::FileDialog::new()
                        .set_directory(self.config.effective_download_dir())
                        .set_file_name(&suggested)
                        .save_file();
                    if let Some(dest) = chosen {
                        if !modal.local_path.is_empty() && Path::new(&modal.local_path).exists() {
                            match std::fs::copy(&modal.local_path, &dest) {
                                Ok(_) => self.toasts.success(ctx, format!("Saved to {}", dest.display())),
                                Err(e) => self.toasts.error(ctx, e.to_string()),
                            }
                            self.detail_modal = Some(modal);
                        } else {
                            let item_c = modal.item.clone();
                            self.detail_modal = Some(modal);
                            self.spawn_download_wallpaper(ctx, item_c, dest, false, false, None);
                        }
                    } else {
                        self.detail_modal = Some(modal);
                    }
                }
                DetailAction::SetWallpaper(mon) => {
                    if !modal.local_path.is_empty() && Path::new(&modal.local_path).exists() {
                        self.spawn_set_wallpaper(
                            ctx,
                            PathBuf::from(&modal.local_path),
                            modal.item.is_animated,
                            Some(mon),
                        );
                    } else {
                        let dest = self
                            .config
                            .effective_download_dir()
                            .join(modal.item.suggested_filename());
                        let item_c = modal.item.clone();
                        self.detail_modal = Some(modal);
                        self.spawn_download_wallpaper(ctx, item_c, dest, true, true, Some(mon));
                        return;
                    }
                    self.detail_modal = Some(modal);
                }
                DetailAction::CopyImage => {
                    let local = modal.local_path.clone();
                    let url = modal.item.preview_image_url().to_string();
                    let client = self.client.clone();
                    let tx = self.bg_tx.clone();
                    let ctx_c = ctx.clone();
                    thread::spawn(move || {
                        let res = if !local.is_empty() && Path::new(&local).exists() {
                            pfps::copy_image_to_clipboard(Path::new(&local))
                        } else {
                            match client.get(&url).send().and_then(|r| r.bytes()) {
                                Ok(bytes) => pfps::copy_image_bytes_to_clipboard(&bytes),
                                Err(e) => Err(e.to_string()),
                            }
                        };
                        let _ = tx.send(BgEvent::CopyImageFinished(res));
                        ctx_c.request_repaint();
                    });
                    self.detail_modal = Some(modal);
                }
                DetailAction::OpenFolder => {
                    let folder = Path::new(&modal.local_path)
                        .parent()
                        .map(|p| p.to_path_buf())
                        .unwrap_or_else(|| self.config.effective_download_dir());
                    let _ = open::that(folder);
                    self.detail_modal = Some(modal);
                }
                DetailAction::OpenWeb(url) => {
                    let _ = open::that(url);
                    self.detail_modal = Some(modal);
                }
                DetailAction::OpenMpv(src) => {
                    let _ = Command::new("mpv")
                        .args(["--loop", "--no-terminal", &src])
                        .stdin(Stdio::null())
                        .stdout(Stdio::null())
                        .stderr(Stdio::null())
                        .spawn();
                    self.detail_modal = Some(modal);
                }
                DetailAction::Uninstall => {
                    let target = modal.local_path.clone();
                    modal.stop_video();
                    if !target.is_empty() {
                        match self.installed.uninstall(&target, true) {
                            Ok(()) => {
                                self.toasts.info(ctx, "Wallpaper uninstalled");
                                if self.mode == NavMode::Installed {
                                    self.refresh_installed_view();
                                }
                            }
                            Err(e) => self.toasts.error(ctx, e),
                        }
                    }
                }
                DetailAction::CancelDownload => {
                    if let Some(c) = &self.download_cancel {
                        c.store(true, std::sync::atomic::Ordering::Relaxed);
                    }
                    modal.download_progress = None;
                    self.detail_modal = Some(modal);
                }
                DetailAction::FilterByTag(tag) => {
                    modal.stop_video();
                    self.filters.query = tag;
                    self.trigger_search(ctx, 1);
                }
                DetailAction::FilterByColor(hex) => {
                    modal.stop_video();
                    self.mode = NavMode::Wallhaven;
                    self.filters.wh_color = hex;
                    self.filters.show_color_bar = true;
                    self.trigger_search(ctx, 1);
                }
            }
        }

        if let Some(mut modal) = self.pfp_modal.take() {
            let act = render_pfp_modal(ctx, &pal, lang, &modal, &mut self.loader);
            match act {
                PfpAction::None => {
                    self.pfp_modal = Some(modal);
                }
                PfpAction::Close => {}
                PfpAction::OpenWeb(url) => {
                    let _ = open::that(url);
                    self.pfp_modal = Some(modal);
                }
                PfpAction::SetSystemAvatar | PfpAction::CopyImage | PfpAction::Download => {
                    modal.busy = true;
                    let item = modal.item.clone();
                    let client = self.client.clone();
                    let tx = self.bg_tx.clone();
                    let ctx_c = ctx.clone();
                    self.pfp_modal = Some(modal);

                    thread::spawn(move || {
                        let cancel = AtomicBool::new(false);
                        let dir = pfps::default_avatar_dir();
                        let toast_msg = pfps::download_pfp(&client, &item, &dir, &cancel).and_then(|path| {
                            match act {
                                PfpAction::SetSystemAvatar => pfps::set_system_avatar(&path, &item.title)
                                    .map(|dst| format!("System avatar updated: {dst}")),
                                PfpAction::CopyImage => pfps::copy_image_to_clipboard(&path)
                                    .map(|_| tr(lang, "pfp_copied").to_string()),
                                PfpAction::Download => Ok(format!("Downloaded avatar: {}", path.display())),
                                _ => Ok(String::new()),
                            }
                        });
                        let _ = tx.send(BgEvent::PfpActionFinished { toast_msg });
                        ctx_c.request_repaint();
                    });
                }
            }
        }

        if let Some(mut sm) = self.settings_modal.take() {
            let act = render_settings_modal(ctx, &pal, lang, &mut sm);
            match act {
                SettingsAction::None => {
                    self.settings_modal = Some(sm);
                }
                SettingsAction::Save => {
                    self.config = sm.draft;
                    let _ = self.config.save();
                    let t = self.config.theme.clone();
                    self.refresh_theme(ctx, &t);
                    self.toasts.success(ctx, "Settings saved");
                    self.spawn_rescan_installed(ctx);
                }
                SettingsAction::Cancel => {
                    let orig_t = sm.original_theme.clone();
                    self.config.theme = orig_t.clone();
                    self.config.language = sm.original_lang;
                    self.refresh_theme(ctx, &orig_t);
                }
                SettingsAction::PreviewTheme(tid) => {
                    self.refresh_theme(ctx, &tid);
                    self.settings_modal = Some(sm);
                }
                SettingsAction::PreviewLanguage(lcode) => {
                    self.config.language = lcode;
                    let t = sm.draft.theme.clone();
                    self.refresh_theme(ctx, &t);
                    self.settings_modal = Some(sm);
                }
                SettingsAction::BrowseDownloadDir => {
                    if let Some(dir) = rfd::FileDialog::new()
                        .set_directory(Path::new(&sm.draft.default_download_dir))
                        .pick_folder()
                    {
                        sm.draft.default_download_dir = dir.to_string_lossy().into_owned();
                    }
                    self.settings_modal = Some(sm);
                }
                SettingsAction::ClearCache => {
                    match clear_cache() {
                        Ok(()) => {
                            self.loader.clear_memory();
                            sm.cache_bytes = cache_size_bytes();
                            self.toasts.success(ctx, "Disk cache cleared");
                        }
                        Err(e) => self.toasts.error(ctx, e),
                    }
                    self.settings_modal = Some(sm);
                }
                SettingsAction::TestSetter => {
                    let setter = sm.draft.wallpaper_setter.as_str();
                    let found = if setter == "auto" {
                        sm.setters.iter().any(|s| s.id != "auto" && s.available)
                    } else {
                        sm.setters
                            .iter()
                            .find(|s| s.id == setter)
                            .map(|s| s.available)
                            .unwrap_or(false)
                    };
                    if found {
                        self.toasts
                            .success(ctx, format!("Tool available: {setter}"));
                    } else {
                        self.toasts
                            .warning(ctx, format!("Tool not found on PATH: {setter}"));
                    }
                    self.settings_modal = Some(sm);
                }
                SettingsAction::CheckUpdates => {
                    sm.checking_updates = true;
                    self.settings_modal = Some(sm);
                    self.spawn_update_check(ctx);
                }
                SettingsAction::OpenUrl(url) => {
                    let _ = open::that(url);
                    self.settings_modal = Some(sm);
                }
            }
        }

        self.toasts.render(ctx, &self.palette);
        let _ = CornerRadius::same(1);
    }
}

fn load_emblem_texture(ctx: &egui::Context) -> Option<TextureHandle> {
    let bytes = include_bytes!("../assets/icon_emblem.png");
    let img = image::load_from_memory(bytes).ok()?.to_rgba8();
    let size = [img.width() as usize, img.height() as usize];
    let color_img = egui::ColorImage::from_rgba_unmultiplied(size, img.as_raw());
    Some(ctx.load_texture("komorebi_emblem", color_img, TextureOptions::LINEAR))
}
