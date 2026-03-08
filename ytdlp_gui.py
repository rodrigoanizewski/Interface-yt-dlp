"""
yt-dlp GUI v4 — Post-Production Edition  (i18n build)
=======================================================
Dependencias:
    pip install customtkinter yt-dlp pillow requests

FFmpeg required for all codec conversions:
    Windows : winget install ffmpeg
    Linux   : sudo apt install ffmpeg
    Mac     : brew install ffmpeg

Language system:
    Set LANG = "en" for English (default)
    Set LANG = "pt" for Portuguese
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import shutil
import subprocess
import sys
import threading
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import customtkinter as ctk
import requests
import tkinter as tk
from tkinter import filedialog, messagebox

import yt_dlp
from PIL import Image

# ══════════════════════════════════════════════════════════════════════════════
#  LANGUAGE / LEXICON
# ══════════════════════════════════════════════════════════════════════════════

LANG: str = "en"   # Change to "pt" for Portuguese


STRINGS: dict[str, dict[str, str]] = {

    # ── App title ─────────────────────────────────────────────────────────────
    "app_title": {
        "en": "yt-dlp GUI  v4  —  Post-Production Edition",
        "pt": "yt-dlp GUI  v4  —  Post-Production Edition",
    },
    "app_subtitle": {
        "en": "Post-Production Edition  v4",
        "pt": "Edição de Pós-Produção  v4",
    },

    # ── Header buttons / badges ───────────────────────────────────────────────
    "btn_update_ytdlp": {
        "en": "⟳ Update yt-dlp",
        "pt": "⟳ Atualizar yt-dlp",
    },
    "badge_ffmpeg_ok": {
        "en": "  FFmpeg OK  ",
        "pt": "  FFmpeg OK  ",
    },
    "badge_ffmpeg_missing": {
        "en": "  FFmpeg MISSING  ",
        "pt": "  FFmpeg AUSENTE  ",
    },
    "status_ready": {
        "en": "  Ready.",
        "pt": "  Pronto.",
    },

    # ── Section titles ────────────────────────────────────────────────────────
    "section_url": {
        "en": "VIDEO / PLAYLIST URL",
        "pt": "URL DO VIDEO / PLAYLIST",
    },
    "section_info": {
        "en": "VIDEO INFORMATION",
        "pt": "INFORMACOES DO VIDEO",
    },
    "section_segments": {
        "en": "SEGMENT CONTROL",
        "pt": "CONTROLE DE SEGMENTOS",
    },
    "section_segments_hint": {
        "en": "— select parts of the playlist or video",
        "pt": "— selecione partes da playlist ou do vídeo",
    },
    "section_format": {
        "en": "BASE FORMAT",
        "pt": "FORMATO BASE",
    },
    "section_pro": {
        "en": "PROFESSIONAL OUTPUT PROFILE",
        "pt": "PERFIL DE SAIDA PROFISSIONAL",
    },
    "section_pro_hint": {
        "en": "— codec / container optimized for editing",
        "pt": "— codec / container otimizado para edicao",
    },
    "section_cookies": {
        "en": "COOKIE MANAGEMENT",
        "pt": "GESTAO DE COOKIES",
    },
    "section_cookies_hint": {
        "en": "— bypass blocks and access restricted content",
        "pt": "— evita bloqueios e acessa conteudo restrito",
    },
    "section_options": {
        "en": "EXTRA OPTIONS",
        "pt": "OPCOES EXTRAS",
    },
    "section_destination": {
        "en": "DESTINATION FOLDER",
        "pt": "PASTA DE DESTINO",
    },
    "section_history": {
        "en": "SESSION HISTORY",
        "pt": "HISTORICO DA SESSAO",
    },
    "history_last_n": {
        "en": "(last {n})",
        "pt": "(ultimos {n})",
    },

    # ── URL section ───────────────────────────────────────────────────────────
    "url_placeholder": {
        "en": "Paste URL here...",
        "pt": "Cole a URL aqui...",
    },
    "btn_analyze": {
        "en": "Analyze",
        "pt": "Analisar",
    },
    "btn_analyzing": {
        "en": "...",
        "pt": "...",
    },

    # ── Video info section ────────────────────────────────────────────────────
    "info_no_preview": {
        "en": "no\npreview",
        "pt": "sem\npreview",
    },
    "info_channel_prefix": {
        "en": "Channel: ",
        "pt": "Canal: ",
    },
    "info_duration_prefix": {
        "en": "Duration: ",
        "pt": "Duracao: ",
    },
    "info_default_dash": {
        "en": "—",
        "pt": "—",
    },

    # ── Segment control section ───────────────────────────────────────────────
    "seg_playlist_label": {
        "en": "Playlist (Index):",
        "pt": "Playlist (Índice):",
    },
    "seg_from": {
        "en": "From:",
        "pt": "De:",
    },
    "seg_to": {
        "en": "To:",
        "pt": "Até:",
    },
    "seg_empty_note": {
        "en": " (empty = all)",
        "pt": " (vazio = tudo)",
    },
    "seg_trim_label": {
        "en": "Trim (Time):",
        "pt": "Corte (Tempo):",
    },
    "seg_start": {
        "en": "Start:",
        "pt": "Início:",
    },
    "seg_end": {
        "en": "End:",
        "pt": "Fim:",
    },
    "seg_format_hint": {
        "en": " Format: HH:MM:SS or seconds (e.g. 01:30)",
        "pt": " Formato: HH:MM:SS ou segundos (Ex: 01:30)",
    },

    # ── Format section ────────────────────────────────────────────────────────
    "fmt_video": {
        "en": "Video",
        "pt": "Video",
    },
    "fmt_audio_only": {
        "en": "Audio Only",
        "pt": "Apenas Audio",
    },
    "fmt_resolution_label": {
        "en": "Resolution:",
        "pt": "Resolucao:",
    },
    "fmt_container_label": {
        "en": "Container:",
        "pt": "Container:",
    },
    "fmt_audio_format_label": {
        "en": "Format:",
        "pt": "Formato:",
    },
    "fmt_name_template_label": {
        "en": "Name template:",
        "pt": "Template de nome:",
    },
    "fmt_note_4k_missing_ffmpeg": {
        "en": "  FFmpeg missing — 4K unavailable",
        "pt": "  FFmpeg ausente — 4K indisponivel",
    },
    "fmt_template_preview_prefix": {
        "en": "e.g.: ",
        "pt": "ex: ",
    },

    # ── Professional profile section ──────────────────────────────────────────
    "pro_profile_label": {
        "en": "Profile:",
        "pt": "Perfil:",
    },
    "pro_fps_label": {
        "en": "FPS / CFR:",
        "pt": "FPS / CFR:",
    },
    "pro_fps_hint_original": {
        "en": "  Original FPS preserved (VFR)",
        "pt": "  FPS original preservado (VFR)",
    },
    "pro_fps_hint_cfr": {
        "en": "  CFR re-encode @ {fps} fps — prevents desync",
        "pt": "  Re-encode CFR @ {fps} fps — evita dessincronizacao",
    },
    "pro_fps_hint_default": {
        "en": "  Will force CFR re-encode — avoids sync issues",
        "pt": "  Forcara re-encode CFR — evita problemas de sincronia",
    },
    "pro_check_video_only": {
        "en": "Video Only (no audio)",
        "pt": "Somente Video (sem audio)",
    },
    "pro_check_video_only_hint": {
        "en": "Best for B-Roll — downloads at max available resolution",
        "pt": "Melhor para B-Roll — download na resolucao maxima disponivel",
    },
    "pro_check_remove_silence": {
        "en": "Remove Start/End Silence",
        "pt": "Remover Silencio Ini/Fim",
    },
    "pro_check_remove_silence_hint": {
        "en": "silenceremove via FFmpeg — useful for voice / interviews",
        "pt": "silenceremove via FFmpeg — util para voz / entrevistas",
    },
    "pro_check_audio_wav": {
        "en": "Audio WAV PCM 24-bit",
        "pt": "Audio WAV PCM 24-bit",
    },
    "pro_check_audio_wav_hint": {
        "en": "DaVinci Resolve fix — solves Media Offline / muted audio with HEVC+AAC",
        "pt": "Fix DaVinci Resolve free — resolve Media Offline / audio mudo com HEVC+AAC",
    },
    "pro_ffmpeg_required_warning": {
        "en": "⚠  {desc}  —  FFmpeg REQUIRED",
        "pt": "⚠  {desc}  —  FFmpeg NECESSARIO",
    },

    # ── Cookies section ───────────────────────────────────────────────────────
    "cookie_none": {
        "en": "No cookies",
        "pt": "Sem cookies",
    },
    "cookie_file": {
        "en": "cookies.txt file",
        "pt": "Arquivo cookies.txt",
    },
    "cookie_browser": {
        "en": "Browser cookies",
        "pt": "Cookies do navegador",
    },
    "cookie_file_placeholder": {
        "en": "Path to cookies.txt...",
        "pt": "Caminho para cookies.txt...",
    },
    "cookie_browse_btn": {
        "en": "Browse...",
        "pt": "Procurar...",
    },
    "cookie_browser_label": {
        "en": "Browser:",
        "pt": "Navegador:",
    },
    "cookie_browser_hint": {
        "en": "  (close the browser before downloading)",
        "pt": "  (feche o navegador antes de baixar)",
    },
    "cookie_file_dialog_title": {
        "en": "Select cookies.txt",
        "pt": "Selecione cookies.txt",
    },

    # ── Extra options section ─────────────────────────────────────────────────
    "opt_embed_thumb": {
        "en": "Embed Thumbnail",
        "pt": "Embutir Miniatura",
    },
    "opt_embed_thumb_hint": {
        "en": "EmbedThumbnail — cover art in file",
        "pt": "EmbedThumbnail — capa no arquivo",
    },
    "opt_embed_meta": {
        "en": "Embed Metadata",
        "pt": "Embutir Metadados",
    },
    "opt_embed_subs": {
        "en": "Embed Subtitles",
        "pt": "Embutir Legendas",
    },
    "opt_dl_playlist": {
        "en": "Full Playlist",
        "pt": "Playlist Completa",
    },

    # ── Destination section ───────────────────────────────────────────────────
    "dest_browse_btn": {
        "en": "Browse...",
        "pt": "Procurar...",
    },

    # ── Download section ──────────────────────────────────────────────────────
    "status_waiting": {
        "en": "Waiting...",
        "pt": "Aguardando...",
    },
    "btn_download": {
        "en": "DOWNLOAD",
        "pt": "BAIXAR",
    },
    "btn_downloading": {
        "en": "Downloading...",
        "pt": "Baixando...",
    },
    "btn_open_folder": {
        "en": "Open Folder",
        "pt": "Abrir Pasta",
    },

    # ── Log panel ─────────────────────────────────────────────────────────────
    "log_title": {
        "en": "LOG / PIPELINE",
        "pt": "LOG / PIPELINE",
    },
    "log_clear_btn": {
        "en": "Clear",
        "pt": "Limpar",
    },

    # ── Global status messages ────────────────────────────────────────────────
    "global_analyzing": {
        "en": "Analyzing...",
        "pt": "Analisando...",
    },
    "global_downloading": {
        "en": "Downloading...",
        "pt": "Baixando...",
    },
    "global_ready": {
        "en": "Ready — {title}",
        "pt": "Pronto — {title}",
    },
    "global_done": {
        "en": "Done: {title}",
        "pt": "Concluido: {title}",
    },
    "global_error": {
        "en": "Error: {short}",
        "pt": "Erro: {short}",
    },
    "global_ffmpeg_missing": {
        "en": "FFmpeg missing — professional profiles unavailable",
        "pt": "FFmpeg ausente — perfis profissionais indisponiveis",
    },

    # ── Log messages ──────────────────────────────────────────────────────────
    "log_ffmpeg_missing_warn": {
        "en": (
            "WARNING: FFmpeg not found.\n"
            "        ProRes, DNxHR, CFR, WAV PCM and conversions will not work.\n"
            "        Windows : winget install ffmpeg\n"
            "        Linux   : sudo apt install ffmpeg\n"
            "        Mac     : brew install ffmpeg"
        ),
        "pt": (
            "AVISO: FFmpeg nao encontrado.\n"
            "        ProRes, DNxHR, CFR, WAV PCM e conversoes nao funcionarao.\n"
            "        Windows : winget install ffmpeg\n"
            "        Linux   : sudo apt install ffmpeg\n"
            "        Mac     : brew install ffmpeg"
        ),
    },
    "log_ffmpeg_detected": {
        "en": "FFmpeg detected{ver}. Professional profiles active.",
        "pt": "FFmpeg detectado{ver}. Perfis profissionais ativos.",
    },
    "log_paste_url_first": {
        "en": "Paste a URL first.",
        "pt": "Cole uma URL primeiro.",
    },
    "log_analyzing": {
        "en": "Analyzing: {url}",
        "pt": "Analisando: {url}",
    },
    "log_type_returned": {
        "en": "Type returned: {t}",
        "pt": "Tipo retornado: {t}",
    },
    "log_analyze_ok": {
        "en": "OK: {title} [{dur}]{pl}",
        "pt": "OK: {title} [{dur}]{pl}",
    },
    "log_analyze_error_full": {
        "en": "FULL ERROR: {err}",
        "pt": "ERRO COMPLETO: {err}",
    },
    "log_traceback": {
        "en": "Traceback:\n{tb}",
        "pt": "Traceback:\n{tb}",
    },
    "log_cookie_warn": {
        "en": "Warning: error loading cookies — {err}",
        "pt": "Aviso: erro ao carregar cookies — {err}",
    },
    "log_cookie_file_not_found": {
        "en": "Cookie file not found — ignoring.",
        "pt": "Arquivo de cookies nao encontrado — ignorando.",
    },
    "log_download_starting": {
        "en": "Starting: {url}",
        "pt": "Iniciando: {url}",
    },
    "log_download_profile": {
        "en": "Profile: {profile}  |  FPS: {fps}",
        "pt": "Perfil: {profile}  |  FPS: {fps}",
    },
    "log_broll_mode": {
        "en": "B-Roll mode: pure video stream (no audio).",
        "pt": "Modo B-Roll: stream de video puro (sem audio).",
    },
    "log_wav_pcm_fix": {
        "en": "DaVinci fix: audio will be converted to WAV PCM 24-bit.",
        "pt": "Fix DaVinci: audio sera convertido para WAV PCM 24-bit.",
    },
    "log_saved_to": {
        "en": "Saved to: {path}",
        "pt": "Salvo em: {path}",
    },
    "log_real_error": {
        "en": "REAL ERROR: {err}",
        "pt": "ERRO REAL: {err}",
    },
    "log_pip_update": {
        "en": "pip install -U yt-dlp ...",
        "pt": "pip install -U yt-dlp ...",
    },
    "log_ytdlp_already_updated": {
        "en": "yt-dlp is already on the latest version.",
        "pt": "yt-dlp ja esta na versao mais recente.",
    },
    "log_ytdlp_updated": {
        "en": "yt-dlp updated to {ver}!",
        "pt": "yt-dlp atualizado para {ver}!",
    },
    "log_ytdlp_update_failed": {
        "en": "Failure: {stderr}",
        "pt": "Falha: {stderr}",
    },
    "log_ytdlp_update_error": {
        "en": "Error: {err}",
        "pt": "Erro: {err}",
    },
    "log_closing_download": {
        "en": "Closing download on request...",
        "pt": "Encerrando download por solicitacao...",
    },

    # ── Progress / status labels ──────────────────────────────────────────────
    "progress_postprocessing": {
        "en": "Encoding / post-processing...",
        "pt": "Encode / pos-processando...",
    },
    "progress_done": {
        "en": "Done!",
        "pt": "Concluido!",
    },
    "progress_hook_error": {
        "en": "Error in progress hook",
        "pt": "Erro no hook de progresso",
    },
    "progress_error": {
        "en": "Error: {short}",
        "pt": "Erro: {short}",
    },

    # ── Toast notifications ───────────────────────────────────────────────────
    "toast_ytdlp_already": {
        "en": "yt-dlp already up to date!",
        "pt": "yt-dlp ja atualizado!",
    },
    "toast_ytdlp_updated": {
        "en": "yt-dlp updated to {ver}!",
        "pt": "yt-dlp atualizado para {ver}!",
    },
    "toast_download_done": {
        "en": "Download complete!\n{title}",
        "pt": "Download concluido!\n{title}",
    },

    # ── Messageboxes ──────────────────────────────────────────────────────────
    "msgbox_analyze_error_title": {
        "en": "Analysis error — {short}",
        "pt": "Erro ao analisar — {short}",
    },
    "msgbox_analyze_error_body": {
        "en": "{detail}\n\nDetails in the LOG below.",
        "pt": "{detail}\n\nDetalhes no LOG abaixo.",
    },
    "msgbox_url_empty_title": {
        "en": "Empty URL",
        "pt": "URL vazia",
    },
    "msgbox_url_empty_body": {
        "en": "Paste a URL before downloading.",
        "pt": "Cole uma URL antes de baixar.",
    },
    "msgbox_ffmpeg_missing_title": {
        "en": "FFmpeg missing",
        "pt": "FFmpeg ausente",
    },
    "msgbox_ffmpeg_missing_body": {
        "en": (
            "FFmpeg not found.\n\n"
            "Professional profiles, CFR, WAV PCM and conversions require FFmpeg.\n"
            "Do you want to try anyway?"
        ),
        "pt": (
            "FFmpeg nao encontrado.\n\n"
            "Perfis profissionais, CFR, WAV PCM e conversoes requerem FFmpeg.\n"
            "Deseja tentar assim mesmo?"
        ),
    },
    "msgbox_download_fail_title": {
        "en": "Failure — {short}",
        "pt": "Falha — {short}",
    },
    "msgbox_download_fail_body": {
        "en": "{detail}\n\nSee the LOG for details.",
        "pt": "{detail}\n\nVeja o LOG para detalhes.",
    },
    "msgbox_close_title": {
        "en": "Download in progress",
        "pt": "Download em andamento",
    },
    "msgbox_close_body": {
        "en": (
            "A download is in progress.\n\n"
            "Do you want to quit anyway?\n"
            "(The partial file will be kept in the destination folder.)"
        ),
        "pt": (
            "Ha um download em andamento.\n\n"
            "Deseja encerrar mesmo assim?\n"
            "(O arquivo parcial sera mantido na pasta de destino.)"
        ),
    },

    # ── Playlist tag shown in title ───────────────────────────────────────────
    "info_playlist_tag": {
        "en": "  [PLAYLIST]",
        "pt": "  [PLAYLIST]",
    },

    # ── yt_dlp None / type errors ─────────────────────────────────────────────
    "ytdlp_none_error": {
        "en": "yt_dlp returned None — invalid or blocked URL.",
        "pt": "yt_dlp retornou None — URL invalida ou bloqueada.",
    },
    "ytdlp_type_error": {
        "en": "Unexpected type: {t} — content: {c}",
        "pt": "Tipo inesperado: {t} — conteudo: {c}",
    },

    # ── Error classifier ──────────────────────────────────────────────────────
    "err_private_title": {
        "en": "Private Video",
        "pt": "Video Privado",
    },
    "err_private_detail": {
        "en": "This video is private. Use cookies from an account with access.",
        "pt": "Este video e privado. Use cookies de uma conta com acesso.",
    },
    "err_login_title": {
        "en": "Access Restricted",
        "pt": "Restricao de Acesso",
    },
    "err_login_detail": {
        "en": "Age-restricted or login-required content. Configure cookies.",
        "pt": "Conteudo restrito por idade ou login. Configure cookies.",
    },
    "err_unavailable_title": {
        "en": "Unavailable",
        "pt": "Indisponivel",
    },
    "err_unavailable_detail": {
        "en": "Video removed or not available in your region.",
        "pt": "Video removido ou nao disponivel na sua regiao.",
    },
    "err_ratelimit_title": {
        "en": "Rate Limit",
        "pt": "Rate Limit",
    },
    "err_ratelimit_detail": {
        "en": "Too many requests. Wait a few minutes.",
        "pt": "Muitas requisicoes. Aguarde alguns minutos.",
    },
    "err_ffmpeg_title": {
        "en": "FFmpeg missing",
        "pt": "FFmpeg ausente",
    },
    "err_ffmpeg_detail": {
        "en": "Install FFmpeg for conversions and professional codec encoding.",
        "pt": "Instale o FFmpeg para conversoes e encode de codecs profissionais.",
    },
    "err_network_title": {
        "en": "Network Error",
        "pt": "Erro de Rede",
    },
    "err_network_detail": {
        "en": "Connection failed: {exc}",
        "pt": "Falha na conexao: {exc}",
    },
    "err_unsupported_url_title": {
        "en": "Unsupported URL",
        "pt": "URL nao suportada",
    },
    "err_unsupported_url_detail": {
        "en": "yt-dlp does not recognize this URL.",
        "pt": "O yt-dlp nao reconhece esta URL.",
    },
    "err_format_title": {
        "en": "Format unavailable",
        "pt": "Formato indisponivel",
    },
    "err_format_detail": {
        "en": "Resolution/format does not exist for this video.",
        "pt": "Resolucao/formato nao existe para este video.",
    },
    "err_unknown_title": {
        "en": "Unknown Error",
        "pt": "Erro Desconhecido",
    },
}


def T(key: str, **kwargs) -> str:
    """Return the string for the current LANG, with optional .format(**kwargs)."""
    entry = STRINGS.get(key, {})
    text  = entry.get(LANG, entry.get("en", f"[{key}]"))
    return text.format(**kwargs) if kwargs else text


# ══════════════════════════════════════════════════════════════════════════════
#  THEME / PALETTE
# ══════════════════════════════════════════════════════════════════════════════
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

C = {
    "bg":      "#0b0b0b",
    "card":    "#141414",
    "card2":   "#1a1a1a",
    "border":  "#262626",
    "accent":  "#3b82f6",
    "ahvr":    "#2563eb",
    "text":    "#efefef",
    "sub":     "#666666",
    "success": "#22c55e",
    "error":   "#ef4444",
    "warn":    "#f59e0b",
    "info":    "#38bdf8",
    "purple":  "#a78bfa",
    "gold":    "#fbbf24",
}

FONTS = {
    "mono_lg": ("Courier New", 13, "bold"),
    "mono_sm": ("Courier New", 11),
    "label":   (None, 11, "bold"),
}

USER_AGENTS = [
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
     "AppleWebKit/537.36 (KHTML, like Gecko) "
     "Chrome/124.0.0.0 Safari/537.36"),
]

NAME_TEMPLATES = {
    "Title.ext":            "%(title)s.%(ext)s",
    "[Date] - Title.ext":   "%(upload_date>%Y-%m-%d)s - %(title)s.%(ext)s",
    "Channel - Title.ext":  "%(channel)s - %(title)s.%(ext)s",
}

MAX_HISTORY = 5

# ── Professional output profiles ─────────────────────────────────────────────
OUTPUT_PROFILES = {
    "Original (MP4/MKV)": {
        "ext":          None,
        "description":  {
            "en": "H.264/HEVC - maximum compatibility",
            "pt": "H.264/HEVC - compatibilidade maxima",
        },
        "ffmpeg_args":  None,
        "needs_ffmpeg": False,
        "color":        C["info"],
    },
    "ProRes 422 (DaVinci / Premiere)": {
        "ext":          "mov",
        "description":  {
            "en": "Apple ProRes 422 HQ - maximum quality for offline editing",
            "pt": "Apple ProRes 422 HQ - maxima qualidade para edicao offline",
        },
        "ffmpeg_args":  [
            "-vcodec", "prores_ks",
            "-profile:v", "3",
            "-vendor",    "apl0",
            "-pix_fmt",   "yuv422p10le",
            "-acodec",    "pcm_s24le",
        ],
        "needs_ffmpeg": True,
        "color":        C["purple"],
    },
    "DNxHR HQ (DaVinci / Avid)": {
        "ext":          "mov",
        "description":  {
            "en": "Avid DNxHR HQ - ideal for editing on Windows (DaVinci/Premiere)",
            "pt": "Avid DNxHR HQ - Ideal para edição no Windows (DaVinci/Premiere)",
        },
        "ffmpeg_args":  [
            "-vcodec",    "dnxhd",
            "-profile:v",  "dnxhr_hq",
            "-pix_fmt",    "yuv422p",
            "-acodec",    "pcm_s24le",
        ],
        "needs_ffmpeg": True,
        "color":        C["gold"],
    },
    "H.264 CFR (DaVinci Resolve free)": {
        "ext":          "mp4",
        "description":  {
            "en": "H.264 + AAC CFR - maximum compatibility with free DaVinci",
            "pt": "H.264 + AAC CFR - maxima compatibilidade com DaVinci gratis",
        },
        "ffmpeg_args":  [
            "-vcodec", "libx264",
            "-preset", "slow",
            "-crf",    "18",
            "-acodec", "aac",
            "-b:a",    "320k",
        ],
        "needs_ffmpeg": True,
        "color":        C["success"],
    },
}

FPS_OPTIONS   = ["Keep original", "23.976", "24", "25", "29.97", "30", "50", "60"]
AUDIO_FORMATS = ["mp3", "flac", "wav", "aac", "opus", "m4a"]


def _profile_desc(name: str) -> str:
    """Return the localized description for an OUTPUT_PROFILES entry."""
    entry = OUTPUT_PROFILES.get(name, {})
    desc  = entry.get("description", {})
    if isinstance(desc, dict):
        return desc.get(LANG, desc.get("en", ""))
    return str(desc)


# ══════════════════════════════════════════════════════════════════════════════
#  DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class HistoryEntry:
    title:   str
    url:     str
    fmt:     str
    status:  str   # "ok" | "error" | "downloading"
    ts:      str   = field(default_factory=lambda: datetime.now().strftime("%H:%M"))
    error:   str   = ""


# ══════════════════════════════════════════════════════════════════════════════
#  UTILITIES
# ══════════════════════════════════════════════════════════════════════════════
def _find_ffmpeg() -> Optional[str]:
    try:
        import static_ffmpeg
        paths = static_ffmpeg.add_paths()
        found_ffmpeg = shutil.which("ffmpeg")
        if found_ffmpeg:
            bin_dir = os.path.dirname(found_ffmpeg)
            _inject_ffmpeg(found_ffmpeg, bin_dir)
            return found_ffmpeg
    except ImportError:
        pass

    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.isfile(path):
            _inject_ffmpeg(path, os.path.dirname(path))
            return path
    except ImportError:
        pass

    found = shutil.which("ffmpeg")
    if found:
        return os.path.abspath(found)

    return None


def _inject_ffmpeg(exe_path: str, bin_dir: str) -> None:
    bin_dir = os.path.normpath(bin_dir)
    cur = os.environ.get("PATH", "")
    if bin_dir.lower() not in cur.lower():
        os.environ["PATH"] = bin_dir + os.pathsep + cur


_FFMPEG_PATH: Optional[str] = None
_FFMPEG_CHECKED: bool = False


def ffmpeg_ok() -> bool:
    global _FFMPEG_PATH, _FFMPEG_CHECKED
    if not _FFMPEG_CHECKED:
        _FFMPEG_PATH    = _find_ffmpeg()
        _FFMPEG_CHECKED = True
    return _FFMPEG_PATH is not None


def ffmpeg_path() -> Optional[str]:
    ffmpeg_ok()
    return _FFMPEG_PATH


def fmt_bytes(n: float) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


def classify_error(exc: Exception) -> tuple[str, str]:
    msg = str(exc).lower()
    pairs = [
        (("private video",),
         (T("err_private_title"), T("err_private_detail"))),
        (("sign in", "login", "age-restricted"),
         (T("err_login_title"), T("err_login_detail"))),
        (("not available", "unavailable"),
         (T("err_unavailable_title"), T("err_unavailable_detail"))),
        (("429", "too many requests"),
         (T("err_ratelimit_title"), T("err_ratelimit_detail"))),
        (("ffmpeg not found", "no ffmpeg", "ffmpeg: not found", "ffmpeg is not installed"),
         (T("err_ffmpeg_title"), T("err_ffmpeg_detail"))),
        (("network", "connection", "timed out", "errno"),
         (T("err_network_title"), T("err_network_detail", exc=exc))),
        (("unsupported url",),
         (T("err_unsupported_url_title"), T("err_unsupported_url_detail"))),
        (("requested format", "no video formats"),
         (T("err_format_title"), T("err_format_detail"))),
    ]
    for keys, result in pairs:
        if any(k in msg for k in keys):
            return result
    return T("err_unknown_title"), str(exc)


def open_folder(path: str) -> None:
    if sys.platform == "win32":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])


# ══════════════════════════════════════════════════════════════════════════════
#  TOAST NOTIFICATION
# ══════════════════════════════════════════════════════════════════════════════
class Toast(ctk.CTkToplevel):
    def __init__(self, parent, message: str, kind: str = "success",
                 duration_ms: int = 4000):
        super().__init__(parent)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(fg_color=C["card"])

        color = {"success": C["success"], "error": C["error"],
                 "warn": C["warn"], "info": C["info"]}.get(kind, C["info"])
        icon  = {"success": "✔", "error": "✘",
                 "warn": "⚠", "info": "ℹ"}.get(kind, "ℹ")

        ctk.CTkFrame(self, fg_color=color, width=4,
                     corner_radius=0).pack(side="left", fill="y")

        inner = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=0)
        inner.pack(side="left", fill="both", expand=True,
                   padx=(12, 16), pady=12)

        ctk.CTkLabel(inner, text=f"{icon}  {message}",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=color, wraplength=330,
                     justify="left").pack(anchor="w")

        self._position(parent)
        self.after(duration_ms, self._safe_destroy)

    def _safe_destroy(self):
        try:
            self.destroy()
        except Exception:
            pass

    def _position(self, parent):
        self.update_idletasks()
        try:
            x = parent.winfo_rootx() + parent.winfo_width()  - self.winfo_reqwidth()  - 20
            y = parent.winfo_rooty() + parent.winfo_height() - self.winfo_reqheight() - 20
            self.geometry(f"+{x}+{y}")
        except Exception:
            self.geometry("+100+100")


# ══════════════════════════════════════════════════════════════════════════════
#  HISTORY PANEL
# ══════════════════════════════════════════════════════════════════════════════
class HistoryPanel(ctk.CTkFrame):
    SC = {"ok": C["success"], "error": C["error"],
          "downloading": C["accent"], "cancelled": C["warn"]}
    SI = {"ok": "✔", "error": "✘", "downloading": "⬇", "cancelled": "—"}

    def __init__(self, parent, **kw):
        super().__init__(parent, fg_color=C["card"], corner_radius=10,
                         border_width=1, border_color=C["border"], **kw)
        self.grid_columnconfigure(0, weight=1)
        self._entries: list[HistoryEntry] = []
        self._rows: list[ctk.CTkFrame]    = []
        self._build_header()

    def _build_header(self):
        h = ctk.CTkFrame(self, fg_color="transparent")
        h.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        ctk.CTkLabel(h, text=T("section_history"),
                     font=ctk.CTkFont(*FONTS["label"]),
                     text_color=C["sub"]).pack(side="left")
        ctk.CTkLabel(h, text=T("history_last_n", n=MAX_HISTORY),
                     font=ctk.CTkFont(size=10),
                     text_color="#3a3a3a").pack(side="left", padx=4)

    def add_or_update(self, entry: HistoryEntry):
        for i, e in enumerate(self._entries):
            if e.url == entry.url:
                self._entries[i] = entry
                self._redraw()
                return
        self._entries.insert(0, entry)
        if len(self._entries) > MAX_HISTORY:
            self._entries.pop()
        self._redraw()

    def _redraw(self):
        for row in self._rows:
            row.destroy()
        self._rows.clear()

        for idx, e in enumerate(self._entries):
            color = self.SC.get(e.status, C["sub"])
            icon  = self.SI.get(e.status, "?")
            title = (e.title[:50] + "…") if len(e.title) > 50 else e.title

            row = ctk.CTkFrame(self,
                               fg_color=C["card2"] if idx % 2 == 0 else C["card"],
                               corner_radius=0)
            row.grid(row=idx + 1, column=0, sticky="ew")
            row.grid_columnconfigure(1, weight=1)

            ctk.CTkLabel(row, text=icon,
                         font=ctk.CTkFont(size=13, weight="bold"),
                         text_color=color, width=24).grid(
                row=0, column=0, padx=(10, 4), pady=5)
            ctk.CTkLabel(row, text=title, anchor="w",
                         font=ctk.CTkFont(size=11),
                         text_color=C["text"]).grid(
                row=0, column=1, sticky="ew")
            ctk.CTkLabel(row, text=f"{e.fmt}  {e.ts}",
                         font=ctk.CTkFont(size=10),
                         text_color=C["sub"]).grid(
                row=0, column=2, padx=(4, 12))
            self._rows.append(row)

        pad = ctk.CTkFrame(self, fg_color="transparent", height=6)
        pad.grid(row=len(self._entries) + 1, column=0)
        self._rows.append(pad)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN APP
# ══════════════════════════════════════════════════════════════════════════════
class YtDlpGUI(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title(T("app_title"))
        self.geometry("920x1020")
        self.minsize(820, 860)
        self.configure(fg_color=C["bg"])
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── 1. ORIGINAL STATES ────────────────────────────────────────────
        self.dest_folder     = tk.StringVar(value=os.path.expanduser("~/Downloads"))
        self.format_choice   = tk.StringVar(value="video")
        self.resolution      = tk.StringVar(value="1080p")
        self.audio_format    = tk.StringVar(value="mp3")
        self.container       = tk.StringVar(value="mp4")
        self.embed_subs      = tk.BooleanVar(value=False)
        self.embed_meta      = tk.BooleanVar(value=True)
        self.embed_thumb     = tk.BooleanVar(value=True)
        self.dl_playlist     = tk.BooleanVar(value=False)
        self.cookie_mode     = tk.StringVar(value="none")
        self.cookie_file     = tk.StringVar(value="")
        self.cookie_browser  = tk.StringVar(value="chrome")
        self.name_template   = tk.StringVar(value="Title.ext")

        # ── 2. V4 STATES (PROFILES & CUTS) ───────────────────────────────
        self.output_profile  = tk.StringVar(value="Original (MP4/MKV)")
        self.target_fps      = tk.StringVar(value="Keep original")
        self.remove_silence  = tk.BooleanVar(value=False)
        self.video_only      = tk.BooleanVar(value=False)
        self.audio_wav_pcm   = tk.BooleanVar(value=False)

        self.pl_start        = tk.StringVar(value="")
        self.pl_end          = tk.StringVar(value="")
        self.trim_start      = tk.StringVar(value="")
        self.trim_end        = tk.StringVar(value="")

        # ── 3. INTERNAL STATES ────────────────────────────────────────────
        self._thumb_ref:       Optional[ctk.CTkImage] = None
        self._is_analyzing:    bool = False
        self._is_downloading:  bool = False
        self._current_ydl:     Optional[yt_dlp.YoutubeDL] = None
        self._dl_thread:       Optional[threading.Thread] = None
        self._last_title:      str = "download"
        self._last_url:        str = ""

        # ── 4. BUILD UI ───────────────────────────────────────────────────
        self._build_ui()
        self._check_ffmpeg_on_start()

    # ══════════════════════════════════════════════════════════════════════════
    #  LAYOUT
    # ══════════════════════════════════════════════════════════════════════════
    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()

        body = ctk.CTkScrollableFrame(self, fg_color=C["bg"], corner_radius=0)
        body.grid(row=2, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)

        self._section_url(body)
        self._section_info(body)
        self._section_segments(body)
        self._section_format(body)
        self._section_pro(body)
        self._section_cookies(body)
        self._section_options(body)
        self._section_destination(body)
        self._section_download(body)
        self._section_history(body)

        self._build_log()

    # ── Header ────────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=0, height=60)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hdr, text="▼  yt-dlp",
                     font=ctk.CTkFont("Courier New", 20, "bold"),
                     text_color=C["accent"]).grid(row=0, column=0, padx=20, pady=10)

        ctk.CTkLabel(hdr, text=T("app_subtitle"),
                     font=ctk.CTkFont(size=12),
                     text_color=C["sub"]).grid(row=0, column=1, sticky="w")

        self.update_btn = ctk.CTkButton(
            hdr, text=T("btn_update_ytdlp"), width=150, height=30,
            fg_color="#1e1e1e", hover_color=C["border"],
            font=ctk.CTkFont(size=11), corner_radius=6,
            command=self._update_ytdlp)
        self.update_btn.grid(row=0, column=2, padx=(0, 10))

        ok = ffmpeg_ok()
        self.ffmpeg_badge = ctk.CTkLabel(
            hdr,
            text=T("badge_ffmpeg_ok") if ok else T("badge_ffmpeg_missing"),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=C["success"] if ok else C["error"],
            fg_color="#192619" if ok else "#2a1616", corner_radius=6)
        self.ffmpeg_badge.grid(row=0, column=3, padx=(0, 16))

        self.global_status = ctk.CTkLabel(
            self, text=T("status_ready"),
            font=ctk.CTkFont(size=11), text_color=C["sub"],
            fg_color=C["card2"], anchor="w", height=22)
        self.global_status.grid(row=1, column=0, sticky="ew")

    # ── Log ───────────────────────────────────────────────────────────────────
    def _build_log(self):
        lf = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=0, height=145)
        lf.grid(row=3, column=0, sticky="ew")
        lf.grid_propagate(False)
        lf.grid_columnconfigure(0, weight=1)
        lf.grid_rowconfigure(1, weight=1)

        hrow = ctk.CTkFrame(lf, fg_color="transparent")
        hrow.grid(row=0, column=0, sticky="ew", padx=12, pady=(6, 0))
        ctk.CTkLabel(hrow, text=T("log_title"),
                     font=ctk.CTkFont("Courier New", 11, "bold"),
                     text_color=C["sub"]).pack(side="left")
        ctk.CTkButton(hrow, text=T("log_clear_btn"), width=60, height=22,
                      fg_color="transparent", hover_color=C["border"],
                      font=ctk.CTkFont(size=10), text_color=C["sub"],
                      command=self._clear_log).pack(side="right")

        self.log_box = ctk.CTkTextbox(
            lf, fg_color="#080808", text_color="#999999",
            font=ctk.CTkFont("Courier New", 11),
            corner_radius=0, border_width=0)
        self.log_box.grid(row=1, column=0, sticky="nsew")
        self.log_box.configure(state="disabled")

        for tag, color in [
            ("error",   C["error"]),   ("success", C["success"]),
            ("warn",    C["warn"]),    ("info",    C["info"]),
            ("dim",     C["sub"]),     ("purple",  C["purple"]),
            ("gold",    C["gold"]),
        ]:
            self.log_box._textbox.tag_configure(tag, foreground=color)

    # ── Card helper ───────────────────────────────────────────────────────────
    def _card(self, parent, title: str, hint: str = "") -> ctk.CTkFrame:
        f = ctk.CTkFrame(parent, fg_color=C["card"], corner_radius=10,
                         border_width=1, border_color=C["border"])
        f.grid_columnconfigure(0, weight=1)
        f.pack(fill="x", padx=16, pady=(0, 10))
        h = ctk.CTkFrame(f, fg_color="transparent")
        h.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 2))
        ctk.CTkLabel(h, text=title,
                     font=ctk.CTkFont(*FONTS["label"]),
                     text_color=C["sub"]).pack(side="left")
        if hint:
            ctk.CTkLabel(h, text=f"  {hint}",
                         font=ctk.CTkFont(size=10),
                         text_color="#363636").pack(side="left")
        return f

    # ══════════════════════════════════════════════════════════════════════════
    #  SECTIONS
    # ══════════════════════════════════════════════════════════════════════════

    def _section_url(self, p):
        f = self._card(p, T("section_url"))
        r = ctk.CTkFrame(f, fg_color="transparent")
        r.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))
        r.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            r, placeholder_text=T("url_placeholder"),
            fg_color="#0d0d0d", border_color=C["border"], text_color=C["text"],
            height=42, font=ctk.CTkFont(size=13), corner_radius=8)
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.url_entry.bind("<Return>", lambda _: self._analyze_thread())

        self.analyze_btn = ctk.CTkButton(
            r, text=T("btn_analyze"), width=110, height=42,
            fg_color=C["accent"], hover_color=C["ahvr"],
            font=ctk.CTkFont(size=13, weight="bold"), corner_radius=8,
            command=self._analyze_thread)
        self.analyze_btn.grid(row=0, column=1)

    def _section_info(self, p):
        f = self._card(p, T("section_info"))
        r = ctk.CTkFrame(f, fg_color="transparent")
        r.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))
        r.grid_columnconfigure(1, weight=1)

        self.thumb_label = ctk.CTkLabel(
            r, text=T("info_no_preview"), width=160, height=90,
            fg_color="#0d0d0d", corner_radius=8,
            font=ctk.CTkFont(size=10), text_color="#2a2a2a")
        self.thumb_label.grid(row=0, column=0, rowspan=4, padx=(0, 14))

        self.lbl_title = ctk.CTkLabel(
            r, text=T("info_default_dash"), anchor="w", wraplength=520,
            font=ctk.CTkFont(size=14, weight="bold"), text_color=C["text"])
        self.lbl_title.grid(row=0, column=1, sticky="ew", pady=(0, 3))

        self.lbl_channel = ctk.CTkLabel(
            r, text=T("info_channel_prefix") + "—", anchor="w",
            font=ctk.CTkFont(size=12), text_color=C["sub"])
        self.lbl_channel.grid(row=1, column=1, sticky="ew")

        self.lbl_duration = ctk.CTkLabel(
            r, text=T("info_duration_prefix") + "—", anchor="w",
            font=ctk.CTkFont(size=12), text_color=C["sub"])
        self.lbl_duration.grid(row=2, column=1, sticky="ew", pady=(3, 0))

        self.lbl_extra = ctk.CTkLabel(
            r, text="", anchor="w",
            font=ctk.CTkFont(size=11), text_color="#444444")
        self.lbl_extra.grid(row=3, column=1, sticky="ew", pady=(2, 0))

    def _section_segments(self, p):
        f = self._card(p, T("section_segments"), T("section_segments_hint"))

        # --- Row 1: Playlist Range ---
        r1 = ctk.CTkFrame(f, fg_color="transparent")
        r1.grid(row=1, column=0, sticky="ew", padx=14, pady=(5, 5))

        ctk.CTkLabel(r1, text=T("seg_playlist_label"),
                     font=ctk.CTkFont(size=12), text_color=C["sub"],
                     width=110, anchor="w").pack(side="left")

        ctk.CTkLabel(r1, text=T("seg_from"),
                     font=ctk.CTkFont(size=11)).pack(side="left")
        ctk.CTkEntry(r1, textvariable=self.pl_start,
                     placeholder_text="1", width=60, height=28).pack(side="left", padx=5)

        ctk.CTkLabel(r1, text=T("seg_to"),
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(10, 0))
        ctk.CTkEntry(r1, textvariable=self.pl_end,
                     placeholder_text="5", width=60, height=28).pack(side="left", padx=5)

        ctk.CTkLabel(r1, text=T("seg_empty_note"),
                     font=ctk.CTkFont(size=10), text_color="#3a3a3a").pack(side="left", padx=10)

        # --- Row 2: Trim Video (Time) ---
        r2 = ctk.CTkFrame(f, fg_color="transparent")
        r2.grid(row=2, column=0, sticky="ew", padx=14, pady=(5, 12))

        ctk.CTkLabel(r2, text=T("seg_trim_label"),
                     font=ctk.CTkFont(size=12), text_color=C["sub"],
                     width=110, anchor="w").pack(side="left")

        ctk.CTkLabel(r2, text=T("seg_start"),
                     font=ctk.CTkFont(size=11)).pack(side="left")
        ctk.CTkEntry(r2, textvariable=self.trim_start,
                     placeholder_text="00:00:00", width=90, height=28).pack(side="left", padx=5)

        ctk.CTkLabel(r2, text=T("seg_end"),
                     font=ctk.CTkFont(size=11)).pack(side="left", padx=(10, 0))
        ctk.CTkEntry(r2, textvariable=self.trim_end,
                     placeholder_text="00:05:00", width=90, height=28).pack(side="left", padx=5)

        ctk.CTkLabel(r2, text=T("seg_format_hint"),
                     font=ctk.CTkFont(size=10), text_color=C["warn"]).pack(side="left", padx=10)

    def _section_format(self, p):
        f = self._card(p, T("section_format"))

        # Type: video / audio
        tr = ctk.CTkFrame(f, fg_color="transparent")
        tr.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8))
        for lbl, val in [(T("fmt_video"), "video"), (T("fmt_audio_only"), "audio")]:
            ctk.CTkRadioButton(
                tr, text=lbl, variable=self.format_choice, value=val,
                font=ctk.CTkFont(size=13), fg_color=C["accent"],
                command=self._toggle_format).pack(side="left", padx=(0, 20))

        # Video opts
        self._video_opts_row = ctk.CTkFrame(f, fg_color="transparent")
        self._video_opts_row.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 4))
        for lbl, var, vals, w in [
            (T("fmt_resolution_label"), self.resolution,
             ["2160p (4K)", "1440p", "1080p", "720p", "480p", "360p",
              "Best available"], 165),
            (T("fmt_container_label"), self.container, ["mp4", "mkv"], 90),
        ]:
            ctk.CTkLabel(self._video_opts_row, text=lbl, text_color=C["sub"],
                         font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
            ctk.CTkOptionMenu(
                self._video_opts_row, values=vals, variable=var,
                fg_color="#1c1c1c", button_color=C["accent"],
                font=ctk.CTkFont(size=12), width=w).pack(side="left", padx=(0, 14))

        self._note_4k = ctk.CTkLabel(
            self._video_opts_row,
            text=T("fmt_note_4k_missing_ffmpeg") if not ffmpeg_ok() else "",
            font=ctk.CTkFont(size=10), text_color=C["warn"])
        self._note_4k.pack(side="left")

        # Audio opts
        self._audio_opts_row = ctk.CTkFrame(f, fg_color="transparent")
        ctk.CTkLabel(self._audio_opts_row, text=T("fmt_audio_format_label"),
                     text_color=C["sub"],
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
        ctk.CTkOptionMenu(
            self._audio_opts_row, values=AUDIO_FORMATS,
            variable=self.audio_format,
            fg_color="#1c1c1c", button_color=C["accent"],
            font=ctk.CTkFont(size=12), width=110).pack(side="left")

        # Name template
        nr = ctk.CTkFrame(f, fg_color="transparent")
        nr.grid(row=3, column=0, sticky="ew", padx=14, pady=(4, 12))
        ctk.CTkLabel(nr, text=T("fmt_name_template_label"), text_color=C["sub"],
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        ctk.CTkOptionMenu(
            nr, values=list(NAME_TEMPLATES.keys()),
            variable=self.name_template,
            fg_color="#1c1c1c", button_color=C["accent"],
            font=ctk.CTkFont(size=12), width=200).pack(side="left")

        self._tmpl_preview = ctk.CTkLabel(
            nr, text="", font=ctk.CTkFont(size=10), text_color="#3a3a3a")
        self._tmpl_preview.pack(side="left", padx=(10, 0))
        self.name_template.trace_add("write", self._update_tmpl_preview)
        self._update_tmpl_preview()

    def _toggle_format(self):
        if self.format_choice.get() == "video":
            self._audio_opts_row.grid_forget()
            self._video_opts_row.grid(row=2, column=0, sticky="ew",
                                      padx=14, pady=(0, 4))
        else:
            self._video_opts_row.grid_forget()
            self._audio_opts_row.grid(row=2, column=0, sticky="ew",
                                      padx=14, pady=(0, 4))

    def _update_tmpl_preview(self, *_):
        key  = self.name_template.get()
        tmpl = NAME_TEMPLATES.get(key, "")
        prev = (tmpl
                .replace("%(title)s", "<title>")
                .replace("%(upload_date>%Y-%m-%d)s", "<date>")
                .replace("%(channel)s", "<channel>")
                .replace("%(ext)s", "mp4"))
        self._tmpl_preview.configure(text=T("fmt_template_preview_prefix") + prev)

    # ── PROFESSIONAL SECTION ──────────────────────────────────────────────────
    def _section_pro(self, p):
        f = self._card(p, T("section_pro"), T("section_pro_hint"))

        # Row 1: Codec profile
        pr = ctk.CTkFrame(f, fg_color="transparent")
        pr.grid(row=1, column=0, sticky="ew", padx=14, pady=(4, 0))

        ctk.CTkLabel(pr, text=T("pro_profile_label"), text_color=C["sub"],
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))

        self._profile_menu = ctk.CTkOptionMenu(
            pr, values=list(OUTPUT_PROFILES.keys()),
            variable=self.output_profile,
            fg_color="#1c1c1c", button_color=C["accent"],
            font=ctk.CTkFont(size=12), width=280,
            command=self._on_profile_change)
        self._profile_menu.pack(side="left")

        self._profile_badge = ctk.CTkLabel(
            pr, text="", font=ctk.CTkFont(size=10, weight="bold"),
            corner_radius=5, padx=8, pady=2)
        self._profile_badge.pack(side="left", padx=(10, 0))

        self._profile_desc = ctk.CTkLabel(
            f, text="", anchor="w",
            font=ctk.CTkFont(size=11), text_color="#4a4a4a")
        self._profile_desc.grid(row=2, column=0, sticky="ew", padx=14, pady=(2, 0))

        # Row 2: FPS target (CFR)
        fr = ctk.CTkFrame(f, fg_color="transparent")
        fr.grid(row=3, column=0, sticky="ew", padx=14, pady=(8, 0))

        ctk.CTkLabel(fr, text=T("pro_fps_label"), text_color=C["sub"],
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        ctk.CTkOptionMenu(
            fr, values=FPS_OPTIONS, variable=self.target_fps,
            fg_color="#1c1c1c", button_color=C["accent"],
            font=ctk.CTkFont(size=12), width=160).pack(side="left")

        self._fps_hint = ctk.CTkLabel(
            fr, text=T("pro_fps_hint_default"),
            font=ctk.CTkFont(size=10), text_color="#3a3a3a")
        self._fps_hint.pack(side="left")
        self.target_fps.trace_add("write", self._update_fps_hint)

        # Row 3: Pro checkboxes
        cr = ctk.CTkFrame(f, fg_color="transparent")
        cr.grid(row=4, column=0, sticky="ew", padx=14, pady=(8, 14))

        pro_checks = [
            (self.video_only,
             T("pro_check_video_only"),
             T("pro_check_video_only_hint")),
            (self.remove_silence,
             T("pro_check_remove_silence"),
             T("pro_check_remove_silence_hint")),
            (self.audio_wav_pcm,
             T("pro_check_audio_wav"),
             T("pro_check_audio_wav_hint")),
        ]

        for var, txt, hint in pro_checks:
            col = ctk.CTkFrame(cr, fg_color="transparent")
            col.pack(side="left", padx=(0, 24))
            ctk.CTkCheckBox(
                col, text=txt, variable=var,
                fg_color=C["accent"], hover_color=C["ahvr"],
                font=ctk.CTkFont(size=12)).pack(anchor="w")
            ctk.CTkLabel(
                col, text=hint,
                font=ctk.CTkFont(size=9), text_color="#3a3a3a").pack(anchor="w")

        self._on_profile_change(self.output_profile.get())

    def _on_profile_change(self, name: str):
        prof  = OUTPUT_PROFILES.get(name, {})
        color = prof.get("color", C["info"])
        desc  = _profile_desc(name)

        badge_bg = {
            C["info"]:    "#0f2233",
            C["purple"]:  "#1e1428",
            C["gold"]:    "#2a1f0a",
            C["success"]: "#0f2a14",
            C["warn"]:    "#2a1e08",
            C["error"]:   "#2a0f0f",
        }.get(color, "#1c1c1c")

        self._profile_badge.configure(
            text=f"  {name.split('(')[0].strip()}  ",
            text_color=color, fg_color=badge_bg)
        self._profile_desc.configure(text=desc, text_color="#4a4a4a")

        if prof.get("needs_ffmpeg") and not ffmpeg_ok():
            self._profile_desc.configure(
                text=T("pro_ffmpeg_required_warning", desc=desc),
                text_color=C["warn"])

    def _update_fps_hint(self, *_):
        fps = self.target_fps.get()
        if fps == "Keep original":
            self._fps_hint.configure(
                text=T("pro_fps_hint_original"),
                text_color="#3a3a3a")
        else:
            self._fps_hint.configure(
                text=T("pro_fps_hint_cfr", fps=fps),
                text_color=C["warn"])

    def _section_cookies(self, p):
        f = self._card(p, T("section_cookies"), T("section_cookies_hint"))

        mr = ctk.CTkFrame(f, fg_color="transparent")
        mr.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 6))
        for lbl, val in [
            (T("cookie_none"),    "none"),
            (T("cookie_file"),    "file"),
            (T("cookie_browser"), "browser"),
        ]:
            ctk.CTkRadioButton(
                mr, text=lbl, variable=self.cookie_mode, value=val,
                font=ctk.CTkFont(size=12), fg_color=C["accent"],
                command=self._toggle_cookie_ui).pack(side="left", padx=(0, 16))

        self._cf_frame = ctk.CTkFrame(f, fg_color="transparent")
        self._cf_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(
            self._cf_frame, textvariable=self.cookie_file,
            placeholder_text=T("cookie_file_placeholder"),
            fg_color="#0d0d0d", border_color=C["border"], text_color=C["text"],
            height=34, font=ctk.CTkFont(size=12), corner_radius=7
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(
            self._cf_frame, text=T("cookie_browse_btn"), width=90, height=34,
            fg_color="#1c1c1c", hover_color=C["border"],
            font=ctk.CTkFont(size=12), corner_radius=7,
            command=self._choose_cookie_file).grid(row=0, column=1)

        self._cb_frame = ctk.CTkFrame(f, fg_color="transparent")
        ctk.CTkLabel(self._cb_frame, text=T("cookie_browser_label"),
                     text_color=C["sub"],
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        ctk.CTkOptionMenu(
            self._cb_frame,
            values=["chrome", "firefox", "brave", "edge", "opera", "safari"],
            variable=self.cookie_browser,
            fg_color="#1c1c1c", button_color=C["accent"],
            font=ctk.CTkFont(size=12), width=130).pack(side="left")
        ctk.CTkLabel(self._cb_frame,
                     text=T("cookie_browser_hint"),
                     font=ctk.CTkFont(size=10),
                     text_color="#3a3a3a").pack(side="left")

        ctk.CTkFrame(f, fg_color="transparent", height=4).grid(row=3, column=0)

    def _toggle_cookie_ui(self):
        self._cf_frame.grid_forget()
        self._cb_frame.grid_forget()
        mode = self.cookie_mode.get()
        if mode == "file":
            self._cf_frame.grid(row=2, column=0, sticky="ew",
                                padx=14, pady=(0, 10))
        elif mode == "browser":
            self._cb_frame.grid(row=2, column=0, sticky="ew",
                                padx=14, pady=(0, 10))

    def _choose_cookie_file(self):
        p = filedialog.askopenfilename(
            title=T("cookie_file_dialog_title"),
            filetypes=[("Cookies", "*.txt"), ("All files", "*.*")])
        if p:
            self.cookie_file.set(p)

    def _section_options(self, p):
        f = self._card(p, T("section_options"))
        r = ctk.CTkFrame(f, fg_color="transparent")
        r.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))

        for txt, var, hint in [
            (T("opt_embed_thumb"), self.embed_thumb, T("opt_embed_thumb_hint")),
            (T("opt_embed_meta"),  self.embed_meta,   ""),
            (T("opt_embed_subs"),  self.embed_subs,   ""),
            (T("opt_dl_playlist"), self.dl_playlist,  ""),
        ]:
            col = ctk.CTkFrame(r, fg_color="transparent")
            col.pack(side="left", padx=(0, 20))
            ctk.CTkCheckBox(
                col, text=txt, variable=var,
                fg_color=C["accent"], hover_color=C["ahvr"],
                font=ctk.CTkFont(size=13)).pack(anchor="w")
            if hint:
                ctk.CTkLabel(
                    col, text=hint,
                    font=ctk.CTkFont(size=9), text_color="#3a3a3a").pack(anchor="w")

    def _section_destination(self, p):
        f = self._card(p, T("section_destination"))
        r = ctk.CTkFrame(f, fg_color="transparent")
        r.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))
        r.grid_columnconfigure(0, weight=1)

        ctk.CTkEntry(
            r, textvariable=self.dest_folder,
            fg_color="#0d0d0d", border_color=C["border"], text_color=C["text"],
            height=34, font=ctk.CTkFont(size=12), corner_radius=7
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            r, text=T("dest_browse_btn"), width=90, height=34,
            fg_color="#1c1c1c", hover_color=C["border"],
            font=ctk.CTkFont(size=12), corner_radius=7,
            command=lambda: self.dest_folder.set(
                filedialog.askdirectory(initialdir=self.dest_folder.get())
                or self.dest_folder.get())
        ).grid(row=0, column=1)

    def _section_download(self, p):
        outer = ctk.CTkFrame(p, fg_color="transparent")
        outer.pack(fill="x", padx=16, pady=(0, 10))
        outer.grid_columnconfigure(0, weight=1)

        self.progress_bar = ctk.CTkProgressBar(
            outer, fg_color="#1c1c1c", progress_color=C["accent"],
            height=6, corner_radius=3)
        self.progress_bar.grid(row=0, column=0, columnspan=2,
                               sticky="ew", pady=(0, 8))
        self.progress_bar.set(0)

        st = ctk.CTkFrame(outer, fg_color="transparent")
        st.grid(row=1, column=0, columnspan=2, sticky="ew")
        st.grid_columnconfigure(0, weight=1)

        self.status_label = ctk.CTkLabel(
            st, text=T("status_waiting"),
            font=ctk.CTkFont("Courier New", 11),
            text_color=C["sub"], anchor="w")
        self.status_label.grid(row=0, column=0, sticky="w")

        self.speed_label = ctk.CTkLabel(
            st, text="",
            font=ctk.CTkFont("Courier New", 11),
            text_color=C["sub"], anchor="e")
        self.speed_label.grid(row=0, column=1, sticky="e")

        btn_row = ctk.CTkFrame(outer, fg_color="transparent")
        btn_row.grid(row=2, column=0, columnspan=2,
                     sticky="ew", pady=(12, 0))
        btn_row.grid_columnconfigure(0, weight=1)

        self.dl_btn = ctk.CTkButton(
            btn_row, text=T("btn_download"), height=52,
            fg_color=C["accent"], hover_color=C["ahvr"],
            font=ctk.CTkFont(size=16, weight="bold"), corner_radius=10,
            command=self._download_thread)
        self.dl_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.open_folder_btn = ctk.CTkButton(
            btn_row, text=T("btn_open_folder"), width=130, height=52,
            fg_color="#1c1c1c", hover_color=C["border"],
            font=ctk.CTkFont(size=13), corner_radius=10,
            state="disabled",
            command=lambda: open_folder(self.dest_folder.get()))
        self.open_folder_btn.grid(row=0, column=1)

    def _section_history(self, p):
        self.history_panel = HistoryPanel(p)
        self.history_panel.pack(fill="x", padx=16, pady=(0, 16))

    # ══════════════════════════════════════════════════════════════════════════
    #  LOG / STATUS HELPERS
    # ══════════════════════════════════════════════════════════════════════════
    def _ts(self) -> str:
        return datetime.now().strftime("%H:%M:%S")

    def _log(self, msg: str, tag: str = ""):
        def _do():
            self.log_box.configure(state="normal")
            self.log_box._textbox.insert("end", f"[{self._ts()}] {msg}\n", tag)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        with contextlib.suppress(Exception):
            self.after(0, _do)

    def _clear_log(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _set_status(self, msg: str, color: str = C["text"]):
        self.status_label.configure(text=msg, text_color=color)

    def _set_speed(self, msg: str):
        self.speed_label.configure(text=msg)

    def _set_global(self, msg: str, color: str = C["sub"]):
        self.global_status.configure(text=f"  {msg}", text_color=color)

    def _toast(self, msg: str, kind: str = "success"):
        Toast(self, msg, kind)

    # ══════════════════════════════════════════════════════════════════════════
    #  FFMPEG CHECK
    # ══════════════════════════════════════════════════════════════════════════
    def _check_ffmpeg_on_start(self):
        if not ffmpeg_ok():
            self._log(T("log_ffmpeg_missing_warn"), "warn")
            self._set_global(T("global_ffmpeg_missing"), C["warn"])
        else:
            ver = ""
            try:
                r = subprocess.run(["ffmpeg", "-version"],
                                   capture_output=True, text=True)
                m = re.search(r"ffmpeg version (\S+)", r.stdout)
                ver = f" ({m.group(1)})" if m else ""
            except Exception:
                pass
            self._log(T("log_ffmpeg_detected", ver=ver), "success")

    # ══════════════════════════════════════════════════════════════════════════
    #  UPDATE
    # ══════════════════════════════════════════════════════════════════════════
    def _update_ytdlp(self):
        self.update_btn.configure(text=T("btn_analyzing"), state="disabled")
        self._log(T("log_pip_update"), "info")

        def _run():
            try:
                r = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
                    capture_output=True, text=True, timeout=120)
                if r.returncode == 0:
                    m       = re.search(r"Successfully installed yt-dlp-(\S+)", r.stdout)
                    already = ("already up-to-date" in r.stdout.lower()
                               or "already satisfied" in r.stdout.lower())
                    if already:
                        self._log(T("log_ytdlp_already_updated"), "success")
                        self.after(0, lambda: self._toast(T("toast_ytdlp_already"), "info"))
                    else:
                        ver = m.group(1) if m else "?"
                        self._log(T("log_ytdlp_updated", ver=ver), "success")
                        self.after(0, lambda v=ver: self._toast(
                            T("toast_ytdlp_updated", ver=v), "success"))
                else:
                    self._log(T("log_ytdlp_update_failed",
                                stderr=r.stderr[:300]), "error")
            except Exception as e:
                self._log(T("log_ytdlp_update_error", err=e), "error")
            finally:
                self.after(0, lambda: self.update_btn.configure(
                    text=T("btn_update_ytdlp"), state="normal"))

        threading.Thread(target=_run, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    #  URL ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    def _analyze_thread(self):
        if self._is_analyzing:
            return
        self._is_analyzing = True
        self.analyze_btn.configure(text=T("btn_analyzing"), state="disabled")
        threading.Thread(target=self._analyze, daemon=True).start()

    def _analyze(self):
        url = self.url_entry.get().strip()
        if not url:
            self._log(T("log_paste_url_first"), "warn")
            self._finish_analyze()
            return

        self._log(T("log_analyzing", url=url[:80]), "info")
        self.after(0, lambda: self._set_global(T("global_analyzing"), C["info"]))

        _ff_path = ffmpeg_path()
        opts = {
            "quiet":            False,
            "no_warnings":      False,
            "skip_download":    True,
            "noplaylist":       not self.dl_playlist.get(),
            "http_headers":     {"User-Agent": USER_AGENTS[0]},
            **({"ffmpeg_location": os.path.dirname(_ff_path)} if _ff_path else {}),
        }

        try:
            cookie_opts = self._cookie_opts()
            opts.update(cookie_opts)
        except Exception as ce:
            self._log(T("log_cookie_warn", err=ce), "warn")

        opts.update(self._ffmpeg_opts())

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                raw = ydl.extract_info(url, download=False)

            self._log(T("log_type_returned", t=type(raw).__name__), "dim")

            if raw is None:
                raise ValueError(T("ytdlp_none_error"))
            if not isinstance(raw, dict):
                raise ValueError(T("ytdlp_type_error",
                                   t=type(raw).__name__, c=str(raw)[:120]))

            is_pl = raw.get("_type") == "playlist"
            if is_pl:
                entries = [e for e in (raw.get("entries") or [])
                           if isinstance(e, dict) and e.get("title")]
                info = entries[0] if entries else raw
            else:
                info = raw

            title    = str(info.get("title") or raw.get("title") or "—")
            channel  = str(info.get("channel") or info.get("uploader")
                           or raw.get("channel") or raw.get("uploader") or "—")
            duration = int(info.get("duration") or 0)
            thumb    = str(info.get("thumbnail") or raw.get("thumbnail") or "")
            views    = info.get("view_count")
            date     = str(info.get("upload_date") or "")
            fps_src  = info.get("fps")

            m, s = divmod(duration, 60)
            h, m = divmod(m, 60)
            dur_str  = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
            date_str = (f"{date[:4]}-{date[4:6]}-{date[6:]}"
                        if len(date) == 8 else "")
            view_str = f"{views:,} views".replace(",", ".") if views else ""
            fps_str  = f"{fps_src} fps" if fps_src else ""
            extra    = "  |  ".join(filter(None, [date_str, view_str, fps_str]))
            pl_str   = T("info_playlist_tag") if is_pl else ""

            self._last_title = title
            self._last_url   = url

            self.after(0, lambda: self.lbl_title.configure(text=title + pl_str))
            self.after(0, lambda: self.lbl_channel.configure(
                text=T("info_channel_prefix") + channel))
            self.after(0, lambda: self.lbl_duration.configure(
                text=T("info_duration_prefix") + dur_str))
            self.after(0, lambda: self.lbl_extra.configure(text=extra))
            self.after(0, lambda: self._set_global(
                T("global_ready", title=title[:55]), C["success"]))
            self._log(T("log_analyze_ok", title=title, dur=dur_str, pl=pl_str), "success")

            if thumb:
                threading.Thread(target=self._load_thumb, args=(thumb,),
                                 daemon=True).start()

        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self._log(T("log_analyze_error_full",
                        err=f"{type(e).__name__}: {e}"), "error")
            self._log(T("log_traceback", tb=tb), "error")
            short, detail = classify_error(e)
            self.after(0, lambda: self._set_global(
                T("global_error", short=short), C["error"]))
            self.after(0, lambda s=short, d=detail: messagebox.showerror(
                T("msgbox_analyze_error_title", short=s),
                T("msgbox_analyze_error_body", detail=d)))
        finally:
            self._finish_analyze()

    def _finish_analyze(self):
        self._is_analyzing = False
        self.after(0, lambda: self.analyze_btn.configure(
            text=T("btn_analyze"), state="normal"))

    def _load_thumb(self, url: str):
        try:
            r   = requests.get(url, timeout=10)
            img = Image.open(io.BytesIO(r.content)).resize((160, 90))
            ci  = ctk.CTkImage(light_image=img, dark_image=img, size=(160, 90))
            self._thumb_ref = ci
            self.after(0, lambda: self.thumb_label.configure(image=ci, text=""))
        except Exception:
            pass

    # ══════════════════════════════════════════════════════════════════════════
    #  COOKIES
    # ══════════════════════════════════════════════════════════════════════════
    def _cookie_opts(self) -> dict:
        mode = self.cookie_mode.get()
        if mode == "file":
            path = self.cookie_file.get().strip()
            if path and os.path.isfile(path):
                return {"cookiefile": path}
            self._log(T("log_cookie_file_not_found"), "warn")
        elif mode == "browser":
            return {"cookiesfrombrowser": (self.cookie_browser.get(),)}
        return {}

    def _ffmpeg_opts(self) -> dict:
        fp = ffmpeg_path()
        if fp:
            return {"ffmpeg_location": os.path.dirname(fp)}
        return {}

    # ══════════════════════════════════════════════════════════════════════════
    #  BUILD YDL OPTIONS  (full v4 engine — logic unchanged)
    # ══════════════════════════════════════════════════════════════════════════
    def _build_ydl_opts(self) -> dict:
        dest     = self.dest_folder.get()
        fmt      = self.format_choice.get()
        res      = self.resolution.get()
        cont     = self.container.get()
        aud      = self.audio_format.get()
        tmpl_key = self.name_template.get()
        profile  = self.output_profile.get()
        fps_val  = self.target_fps.get()
        prof_cfg = OUTPUT_PROFILES.get(profile, OUTPUT_PROFILES["Original (MP4/MKV)"])

        tmpl    = NAME_TEMPLATES.get(tmpl_key, "%(title)s.%(ext)s")
        outtmpl = os.path.join(dest, tmpl)

        # ── Professional Container Adjustment ────────────────────────────────
        final_ext = prof_cfg.get("ext") or cont
        if self.audio_wav_pcm.get() and final_ext == "mp4":
            final_ext = "mov"

        # ── Download format ──────────────────────────────────────────────────
        video_only = self.video_only.get() and fmt == "video"
        res_map = {
            "2160p (4K)": "2160", "1440p": "1440", "1080p": "1080",
            "720p": "720", "480p": "480", "360p": "360",
            "Best available": "0",
        }
        h = res_map.get(res, "1080")

        if fmt == "audio":
            format_str = "bestaudio/best"
        elif video_only:
            format_str = (
                f"bestvideo[height<={h}][ext=mp4]/bestvideo[height<={h}]/bestvideo"
                if h != "0" else "bestvideo"
            )
        else:
            format_str = (
                f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/"
                f"bestvideo[height<={h}]+bestaudio/best"
                if h != "0"
                else "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"
            )

        # ── Post-processors ───────────────────────────────────────────────────
        postprocs: list[dict] = []
        if self.embed_meta.get():
            postprocs.append({"key": "FFmpegMetadata", "add_metadata": True})

        if fmt == "audio":
            target_codec   = "wav" if self.audio_wav_pcm.get() else aud
            target_quality = "320" if target_codec == "mp3" else "0"
            postprocs.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec":    target_codec,
                "preferredquality":  target_quality,
            })

        is_pro_codec = profile.startswith("DNxHR") or profile.startswith("ProRes")
        if self.embed_thumb.get() and ffmpeg_ok() and not video_only and not is_pro_codec:
            postprocs.append({"key": "EmbedThumbnail"})

        if self.embed_subs.get() and not video_only:
            postprocs.append({"key": "FFmpegEmbedSubtitle"})

        # ── FFmpeg argument logic ─────────────────────────────────────────────
        pp_ffmpeg_args: list[str] = []

        video_filters = []
        if is_pro_codec or fps_val != "Keep original":
            video_filters.append("scale='trunc(iw/2)*2:trunc(ih/2)*2'")
            if fps_val != "Keep original":
                video_filters.append(f"fps={fps_val}")

        if video_filters:
            pp_ffmpeg_args += ["-vf", ",".join(video_filters)]

        if self.audio_wav_pcm.get() and not video_only:
            pp_ffmpeg_args += ["-acodec", "pcm_s24le"]

        prof_args = prof_cfg.get("ffmpeg_args") or []
        for arg_idx, arg in enumerate(prof_args):
            if arg in ["-acodec", "-c:a"] and self.audio_wav_pcm.get():
                continue
            if (arg_idx > 0
                    and prof_args[arg_idx - 1] in ["-acodec", "-c:a"]
                    and self.audio_wav_pcm.get()):
                continue
            if arg not in pp_ffmpeg_args:
                pp_ffmpeg_args.append(arg)

        if self.remove_silence.get():
            pp_ffmpeg_args += [
                "-af",
                "silenceremove=start_periods=1:start_threshold=-60dB:"
                "stop_periods=-1:stop_threshold=-60dB",
            ]

        if fmt == "video" and ffmpeg_ok():
            postprocs.append({
                "key": "FFmpegVideoConvertor",
                "preferedformat": final_ext,
            })

        # ── Final options ─────────────────────────────────────────────────────
        ff = ffmpeg_path()
        opts = {
            "format":               format_str,
            "outtmpl":              outtmpl,
            "restrictfilenames":    False,
            "windowsfilenames":     True,
            "noplaylist":           not self.dl_playlist.get(),
            "writesubtitles":       self.embed_subs.get() and not video_only,
            "embedsubtitles":       self.embed_subs.get() and not video_only,
            "writethumbnail":       self.embed_thumb.get() and not video_only,
            "postprocessors":       postprocs,
            "progress_hooks":       [self._progress_hook],
            "quiet":                True,
            "no_warnings":          True,
            "http_headers":         {"User-Agent": USER_AGENTS[0]},
            "add_metadata":         True,
            "merge_output_format":  final_ext,
            **({"ffmpeg_location": os.path.dirname(ff)} if ff else {}),
            **self._cookie_opts(),
        }

        opts["postprocessor_args"] = {}

        if fmt == "audio":
            opts["postprocessor_args"]["ExtractAudio"] = [
                "-ar", "48000",
                "-id3v2_version", "3",
            ]

        if pp_ffmpeg_args:
            opts["postprocessor_args"]["VideoConvertor"] = pp_ffmpeg_args
            if not video_only:
                opts["postprocessor_args"]["ExtractAudio"] = (
                    opts["postprocessor_args"].get("ExtractAudio", []) + pp_ffmpeg_args
                )

        t_start = self.trim_start.get().strip()
        t_end   = self.trim_end.get().strip()

        if t_start or t_end:
            opts["external_downloader"] = "ffmpeg"
            ffmpeg_i_args = []
            if t_start:
                ffmpeg_i_args.extend(["-ss", t_start])
            if t_end:
                ffmpeg_i_args.extend(["-to", t_end])
            opts["external_downloader_args"] = {"ffmpeg_i": ffmpeg_i_args}
            opts["fixup"] = "force"
            if "ffmpeg" not in opts["postprocessor_args"]:
                opts["postprocessor_args"]["ffmpeg"] = []
            opts["postprocessor_args"]["ffmpeg"].extend(
                ["-avoid_negative_ts", "make_zero"])

        return opts

    # ══════════════════════════════════════════════════════════════════════════
    #  PROGRESS HOOK
    # ══════════════════════════════════════════════════════════════════════════
    def _progress_hook(self, d: dict):
        status = d.get("status")
        if status == "downloading":
            total      = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)
            speed      = d.get("speed") or 0
            eta        = d.get("eta") or 0
            pct        = downloaded / total if total else 0
            fname      = os.path.basename(d.get("filename", ""))[:48]
            speed_str  = f"{fmt_bytes(speed)}/s  ETA {eta}s" if speed else ""

            self.after(0, lambda p=pct: self.progress_bar.set(p))
            self.after(0, lambda: self._set_status(
                f"  {fname}  {pct * 100:.1f}%", C["accent"]))
            self.after(0, lambda s=speed_str: self._set_speed(s))

        elif status == "finished":
            self.after(0, lambda: self.progress_bar.set(1.0))
            self.after(0, lambda: self._set_status(
                T("progress_postprocessing"), C["warn"]))
            self.after(0, lambda: self._set_speed(""))

        elif status == "error":
            self.after(0, lambda: self._set_status(
                T("progress_hook_error"), C["error"]))

    # ══════════════════════════════════════════════════════════════════════════
    #  DOWNLOAD
    # ══════════════════════════════════════════════════════════════════════════
    def _download_thread(self):
        if self._is_downloading:
            return
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning(T("msgbox_url_empty_title"),
                                   T("msgbox_url_empty_body"))
            return

        prof     = OUTPUT_PROFILES.get(self.output_profile.get(), {})
        needs_ff = (self.format_choice.get() == "audio"
                    or self.resolution.get() == "2160p (4K)"
                    or self.embed_thumb.get()
                    or self.target_fps.get() != "Keep original"
                    or self.remove_silence.get()
                    or self.audio_wav_pcm.get()
                    or prof.get("needs_ffmpeg", False))

        global _FFMPEG_CHECKED
        _FFMPEG_CHECKED = False
        ff = ffmpeg_path()
        if needs_ff and not ff:
            if not messagebox.askyesno(T("msgbox_ffmpeg_missing_title"),
                                       T("msgbox_ffmpeg_missing_body")):
                return

        title     = self._last_title if self._last_url == url else url[:40]
        prof_name = self.output_profile.get().split("(")[0].strip()
        fmt_label = (f"Audio {self.audio_format.get().upper()}"
                     if self.format_choice.get() == "audio"
                     else f"{self.resolution.get()} · {prof_name}")

        entry = HistoryEntry(title=title, url=url,
                             fmt=fmt_label, status="downloading")
        self.after(0, lambda e=entry: self.history_panel.add_or_update(e))

        self._is_downloading = True
        self.dl_btn.configure(text=T("btn_downloading"), state="disabled",
                              fg_color="#2a2a2a")
        self.open_folder_btn.configure(state="disabled", fg_color="#1c1c1c")
        self.progress_bar.set(0)

        self._dl_thread = threading.Thread(
            target=self._download, args=(url, entry), daemon=True)
        self._dl_thread.start()

    def _download(self, url: str, entry: HistoryEntry):
        self._log(T("log_download_starting", url=url), "info")
        self._log(T("log_download_profile",
                    profile=self.output_profile.get(),
                    fps=self.target_fps.get()), "purple")
        if self.video_only.get():
            self._log(T("log_broll_mode"), "gold")
        if self.audio_wav_pcm.get():
            self._log(T("log_wav_pcm_fix"), "warn")
        self.after(0, lambda: self._set_global(T("global_downloading"), C["accent"]))

        try:
            opts = self._build_ydl_opts()
            with yt_dlp.YoutubeDL(opts) as ydl:
                self._current_ydl = ydl
                ydl.download([url])

        except Exception as e:
            import traceback
            tb   = traceback.format_exc()
            real = f"{type(e).__name__}: {e}"
            self._log(T("log_real_error", err=real), "error")
            self._log(T("log_traceback", tb=tb), "error")
            short, detail = classify_error(e)
            if short == T("err_unknown_title"):
                detail = real
            self.after(0, lambda: self._set_status(
                T("progress_error", short=short), C["error"]))
            self.after(0, lambda: self._set_global(
                T("global_error", short=short), C["error"]))
            self.after(0, lambda s=short, d=detail: messagebox.showerror(
                T("msgbox_download_fail_title", short=s),
                T("msgbox_download_fail_body", detail=d)))
            entry.status = "error"
            entry.error  = short

        else:
            entry.status = "ok"
            self.after(0, lambda: self._set_status(T("progress_done"), C["success"]))
            self.after(0, lambda: self._set_global(
                T("global_done", title=entry.title[:50]), C["success"]))
            self.after(0, lambda: self._log(
                T("log_saved_to", path=self.dest_folder.get()), "success"))
            self.after(0, lambda: self._toast(
                T("toast_download_done", title=entry.title[:45]), "success"))
            self.after(0, lambda: self.open_folder_btn.configure(
                state="normal", fg_color="#1c3a1c", hover_color="#1e4a1e"))

        finally:
            self._current_ydl    = None
            self._is_downloading = False
            self.after(0, lambda: self.dl_btn.configure(
                text=T("btn_download"), state="normal", fg_color=C["accent"]))
            self.after(0, lambda e=entry: self.history_panel.add_or_update(e))

    # ══════════════════════════════════════════════════════════════════════════
    #  CLEAN CLOSE
    # ══════════════════════════════════════════════════════════════════════════
    def _on_close(self):
        if self._is_downloading:
            if not messagebox.askyesno(T("msgbox_close_title"),
                                       T("msgbox_close_body")):
                return

            self._log(T("log_closing_download"), "warn")
            if self._current_ydl is not None:
                with contextlib.suppress(Exception):
                    self._current_ydl.params["abort_on_unavailable_fragment"] = True
                    if (hasattr(self._current_ydl, "_popen")
                            and self._current_ydl._popen):
                        with contextlib.suppress(Exception):
                            self._current_ydl._popen.kill()

            if self._dl_thread and self._dl_thread.is_alive():
                self._dl_thread.join(timeout=3.0)

        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = YtDlpGUI()
    app.mainloop()