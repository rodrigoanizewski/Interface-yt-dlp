"""
yt-dlp GUI v4 — Post-Production Edition
=========================================
Dependencias:
    pip install customtkinter yt-dlp pillow requests

FFmpeg necessario para todas as conversoes de codec:
    Windows : winget install ffmpeg
    Linux   : sudo apt install ffmpeg
    Mac     : brew install ffmpeg
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
#  TEMA / PALETA
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
    "Titulo.ext":          "%(title)s.%(ext)s",
    "[Data] - Titulo.ext": "%(upload_date>%Y-%m-%d)s - %(title)s.%(ext)s",
    "Canal - Titulo.ext":  "%(channel)s - %(title)s.%(ext)s",
}

MAX_HISTORY = 5

# ── Perfis de saida para editores ─────────────────────────────────────────────
#
# Cada perfil define:
#   label        : nome exibido na UI
#   ext          : extensão do container final
#   description  : dica mostrada na UI
#   ffmpeg_args  : argumentos passados ao FFmpeg via postprocessor_args
#                  (None = sem re-encode; usar apenas para "Original")
#   needs_ffmpeg : bool – avisa o usuario se FFmpeg ausente
#   color        : badge color na UI
#
OUTPUT_PROFILES = {
    "Original (MP4/MKV)": {
        "ext":          None,   # usa container escolhido pelo usuario
        "description":  "H.264/HEVC - compatibilidade maxima",
        "ffmpeg_args":  None,
        "needs_ffmpeg": False,
        "color":        C["info"],
    },
    "ProRes 422 (DaVinci / Premiere)": {
        "ext":          "mov",
        "description":  "Apple ProRes 422 HQ - maxima qualidade para edicao offline",
        "ffmpeg_args":  [
            "-vcodec", "prores_ks",
            "-profile:v", "3",          # HQ = profile 3
            "-vendor",    "apl0",
            "-pix_fmt",   "yuv422p10le",
            "-acodec",    "pcm_s24le",  # PCM 24-bit junto com ProRes
        ],
        "needs_ffmpeg": True,
        "color":        C["purple"],
    },
    "DNxHR HQ (DaVinci / Avid)": {
        "ext":          "mov", # Trocado de mxf para mov para maior compatibilidade
        "description":  "Avid DNxHR HQ - Ideal para edição no Windows (DaVinci/Premiere)",
        "ffmpeg_args":  [
            "-vcodec",    "dnxhd",
            "-profile:v",  "dnxhr_hq",
            "-pix_fmt",    "yuv422p", # DNxHR HQ exige 4:2:2
            "-acodec",    "pcm_s24le",
        ],
        "needs_ffmpeg": True,
        "color":        C["gold"],
    },
    "H.264 CFR (DaVinci Resolve free)": {
        "ext":          "mp4",
        "description":  "H.264 + AAC CFR - maxima compatibilidade com DaVinci gratis",
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

FPS_OPTIONS   = ["Manter original", "23.976", "24", "25", "29.97", "30", "50", "60"]
AUDIO_FORMATS = ["mp3", "flac", "wav", "aac", "opus", "m4a"]


# ══════════════════════════════════════════════════════════════════════════════
#  MODELOS DE DADOS
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
#  UTILITARIOS
# ══════════════════════════════════════════════════════════════════════════════
def _find_ffmpeg() -> Optional[str]:
    # 1. Tenta via static-ffmpeg (Mais completo: tem ffprobe)
    try:
        import static_ffmpeg
        # O static-ffmpeg precisa ser "ativado" para localizar os binários
        # Ele retorna o caminho da pasta que contém tanto ffmpeg quanto ffprobe
        paths = static_ffmpeg.add_paths() 
        found_ffmpeg = shutil.which("ffmpeg")
        if found_ffmpeg:
            bin_dir = os.path.dirname(found_ffmpeg)
            _inject_ffmpeg(found_ffmpeg, bin_dir)
            return found_ffmpeg
    except ImportError:
        pass

    # 2. Fallback para imageio-ffmpeg (caso ainda esteja instalado)
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        if path and os.path.isfile(path):
            _inject_ffmpeg(path, os.path.dirname(path))
            return path
    except ImportError:
        pass

    # 3. Fallback final: FFmpeg no PATH global ou pasta local
    found = shutil.which("ffmpeg")
    if found:
        return os.path.abspath(found)

    return None


def _inject_ffmpeg(exe_path: str, bin_dir: str) -> None:
    """
    Injeta o diretorio do ffmpeg no PATH do processo.
    NUNCA toca em _ffmpeg_location nem em outros atributos internos do yt_dlp —
    eles esperam tipos especificos e quebram se receberem string diretamente.
    O correto e passar ffmpeg_location nas opts do YoutubeDL (ver _ydl_base_opts).
    """
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
         ("Video Privado",       "Este video e privado. Use cookies de uma conta com acesso.")),
        (("sign in", "login", "age-restricted"),
         ("Restricao de Acesso", "Conteudo restrito por idade ou login. Configure cookies.")),
        (("not available", "unavailable"),
         ("Indisponivel",        "Video removido ou nao disponivel na sua regiao.")),
        (("429", "too many requests"),
         ("Rate Limit",          "Muitas requisicoes. Aguarde alguns minutos.")),
        (("ffmpeg not found", "no ffmpeg", "ffmpeg: not found", "ffmpeg is not installed"),
         ("FFmpeg ausente",      "Instale o FFmpeg para conversoes e encode de codecs profissionais.")),
        (("network", "connection", "timed out", "errno"),
         ("Erro de Rede",        f"Falha na conexao: {exc}")),
        (("unsupported url",),
         ("URL nao suportada",   "O yt-dlp nao reconhece esta URL.")),
        (("requested format", "no video formats"),
         ("Formato indisponivel", "Resolucao/formato nao existe para este video.")),
    ]
    for keys, result in pairs:
        if any(k in msg for k in keys):
            return result
    return "Erro Desconhecido", str(exc)


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
        
        # --- CORREÇÃO AQUI ---
        # Usamos uma função simples para destruir a janela com segurança
        self.after(duration_ms, self._safe_destroy)

    def _safe_destroy(self):
        try:
            self.destroy()
        except:
            pass

    def _position(self, parent):
        self.update_idletasks()
        # Tenta posicionar no canto inferior direito do app pai
        try:
            x = parent.winfo_rootx() + parent.winfo_width()  - self.winfo_reqwidth()  - 20
            y = parent.winfo_rooty() + parent.winfo_height() - self.winfo_reqheight() - 20
            self.geometry(f"+{x}+{y}")
        except:
            # Fallback caso o parent não esteja disponível
            self.geometry("+100+100")


# ══════════════════════════════════════════════════════════════════════════════
#  PAINEL DE HISTORICO
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
        ctk.CTkLabel(h, text="HISTORICO DA SESSAO",
                     font=ctk.CTkFont(*FONTS["label"]),
                     text_color=C["sub"]).pack(side="left")
        ctk.CTkLabel(h, text=f"(ultimos {MAX_HISTORY})",
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
#  APP PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════
class YtDlpGUI(ctk.CTk):

    def __init__(self):
        super().__init__()
        self.title("yt-dlp GUI  v4  —  Post-Production Edition")
        self.geometry("920x1020")
        self.minsize(820, 860)
        self.configure(fg_color=C["bg"])
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── 1. ESTADOS ORIGINAIS ──────────────────────────────────────────
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
        self.name_template   = tk.StringVar(value="Titulo.ext")

        # ── 2. ESTADOS V4 (PERFIS E CORTES) ───────────────────────────────
        self.output_profile  = tk.StringVar(value="Original (MP4/MKV)")
        self.target_fps      = tk.StringVar(value="Manter original")
        self.remove_silence  = tk.BooleanVar(value=False)
        self.video_only      = tk.BooleanVar(value=False)
        self.audio_wav_pcm   = tk.BooleanVar(value=False)

        # ESTES SÃO OS QUE FALTAVAM (Eles precisam estar aqui, antes do build_ui)
        self.pl_start        = tk.StringVar(value="")
        self.pl_end          = tk.StringVar(value="")
        self.trim_start      = tk.StringVar(value="") # Tempo inicial
        self.trim_end        = tk.StringVar(value="")   # Tempo final

        # ── 3. ESTADOS INTERNOS ───────────────────────────────────────────
        self._thumb_ref:       Optional[ctk.CTkImage] = None
        self._is_analyzing:    bool = False
        self._is_downloading:  bool = False
        self._current_ydl:     Optional[yt_dlp.YoutubeDL] = None
        self._dl_thread:       Optional[threading.Thread] = None
        self._last_title:      str = "download"
        self._last_url:        str = ""

        # ── 4. AGORA SIM, CONSTRÓI A INTERFACE ────────────────────────────
        # Chamamos o build_ui só DEPOIS de ter criado todas as variáveis acima
        self._build_ui()
        self._check_ffmpeg_on_start()

    # ══════════════════════════════════════════════════════════════════════════
    #  LAYOUT GERAL
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
        self._section_pro(body)          # ← NOVO: perfis profissionais
        self._section_cookies(body)
        self._section_options(body)
        self._section_destination(body)
        self._section_download(body)
        self._section_history(body)

        self._build_log()

    # ── Cabecalho ─────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color=C["card"], corner_radius=0, height=60)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_propagate(False)
        hdr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(hdr, text="▼  yt-dlp",
                     font=ctk.CTkFont("Courier New", 20, "bold"),
                     text_color=C["accent"]).grid(row=0, column=0, padx=20, pady=10)

        ctk.CTkLabel(hdr, text="Post-Production Edition  v4",
                     font=ctk.CTkFont(size=12),
                     text_color=C["sub"]).grid(row=0, column=1, sticky="w")

        self.update_btn = ctk.CTkButton(
            hdr, text="⟳ Atualizar yt-dlp", width=150, height=30,
            fg_color="#1e1e1e", hover_color=C["border"],
            font=ctk.CTkFont(size=11), corner_radius=6,
            command=self._update_ytdlp)
        self.update_btn.grid(row=0, column=2, padx=(0, 10))

        ok = ffmpeg_ok()
        self.ffmpeg_badge = ctk.CTkLabel(
            hdr,
            text="  FFmpeg OK  " if ok else "  FFmpeg AUSENTE  ",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=C["success"] if ok else C["error"],
            fg_color="#192619" if ok else "#2a1616", corner_radius=6)
        self.ffmpeg_badge.grid(row=0, column=3, padx=(0, 16))

        self.global_status = ctk.CTkLabel(
            self, text="  Pronto.",
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
        ctk.CTkLabel(hrow, text="LOG / PIPELINE",
                     font=ctk.CTkFont("Courier New", 11, "bold"),
                     text_color=C["sub"]).pack(side="left")
        ctk.CTkButton(hrow, text="Limpar", width=60, height=22,
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
    #  SECOES
    # ══════════════════════════════════════════════════════════════════════════

    def _section_url(self, p):
        f = self._card(p, "URL DO VIDEO / PLAYLIST")
        r = ctk.CTkFrame(f, fg_color="transparent")
        r.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))
        r.grid_columnconfigure(0, weight=1)

        self.url_entry = ctk.CTkEntry(
            r, placeholder_text="Cole a URL aqui...",
            fg_color="#0d0d0d", border_color=C["border"], text_color=C["text"],
            height=42, font=ctk.CTkFont(size=13), corner_radius=8)
        self.url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.url_entry.bind("<Return>", lambda _: self._analyze_thread())

        self.analyze_btn = ctk.CTkButton(
            r, text="Analisar", width=110, height=42,
            fg_color=C["accent"], hover_color=C["ahvr"],
            font=ctk.CTkFont(size=13, weight="bold"), corner_radius=8,
            command=self._analyze_thread)
        self.analyze_btn.grid(row=0, column=1)

    def _section_info(self, p):
        f = self._card(p, "INFORMACOES DO VIDEO")
        r = ctk.CTkFrame(f, fg_color="transparent")
        r.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))
        r.grid_columnconfigure(1, weight=1)

        self.thumb_label = ctk.CTkLabel(
            r, text="sem\npreview", width=160, height=90,
            fg_color="#0d0d0d", corner_radius=8,
            font=ctk.CTkFont(size=10), text_color="#2a2a2a")
        self.thumb_label.grid(row=0, column=0, rowspan=4, padx=(0, 14))

        self.lbl_title = ctk.CTkLabel(
            r, text="—", anchor="w", wraplength=520,
            font=ctk.CTkFont(size=14, weight="bold"), text_color=C["text"])
        self.lbl_title.grid(row=0, column=1, sticky="ew", pady=(0, 3))

        self.lbl_channel = ctk.CTkLabel(r, text="Canal: —", anchor="w",
            font=ctk.CTkFont(size=12), text_color=C["sub"])
        self.lbl_channel.grid(row=1, column=1, sticky="ew")

        self.lbl_duration = ctk.CTkLabel(r, text="Duracao: —", anchor="w",
            font=ctk.CTkFont(size=12), text_color=C["sub"])
        self.lbl_duration.grid(row=2, column=1, sticky="ew", pady=(3, 0))

        self.lbl_extra = ctk.CTkLabel(r, text="", anchor="w",
            font=ctk.CTkFont(size=11), text_color="#444444")
        self.lbl_extra.grid(row=3, column=1, sticky="ew", pady=(2, 0))

    def _section_segments(self, p):
        f = self._card(p, "CONTROLE DE SEGMENTOS", "— selecione partes da playlist ou do vídeo")
        
        # --- Linha 1: Playlist Range ---
        r1 = ctk.CTkFrame(f, fg_color="transparent")
        r1.grid(row=1, column=0, sticky="ew", padx=14, pady=(5, 5))
        
        ctk.CTkLabel(r1, text="Playlist (Índice):", font=ctk.CTkFont(size=12), text_color=C["sub"], width=100, anchor="w").pack(side="left")
        
        ctk.CTkLabel(r1, text="De:", font=ctk.CTkFont(size=11)).pack(side="left")
        ctk.CTkEntry(r1, textvariable=self.pl_start, placeholder_text="1", width=60, height=28).pack(side="left", padx=5)
        
        ctk.CTkLabel(r1, text="Até:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(10, 0))
        ctk.CTkEntry(r1, textvariable=self.pl_end, placeholder_text="5", width=60, height=28).pack(side="left", padx=5)
        
        ctk.CTkLabel(r1, text=" (vazio = tudo)", font=ctk.CTkFont(size=10), text_color="#3a3a3a").pack(side="left", padx=10)

        # --- Linha 2: Trim Video (Tempo) ---
        r2 = ctk.CTkFrame(f, fg_color="transparent")
        r2.grid(row=2, column=0, sticky="ew", padx=14, pady=(5, 12))
        
        ctk.CTkLabel(r2, text="Corte (Tempo):", font=ctk.CTkFont(size=12), text_color=C["sub"], width=100, anchor="w").pack(side="left")
        
        ctk.CTkLabel(r2, text="Início:", font=ctk.CTkFont(size=11)).pack(side="left")
        ctk.CTkEntry(r2, textvariable=self.trim_start, placeholder_text="00:00:00", width=90, height=28).pack(side="left", padx=5)
        
        ctk.CTkLabel(r2, text="Fim:", font=ctk.CTkFont(size=11)).pack(side="left", padx=(10, 0))
        ctk.CTkEntry(r2, textvariable=self.trim_end, placeholder_text="00:05:00", width=90, height=28).pack(side="left", padx=5)
        
        ctk.CTkLabel(r2, text=" Formato: HH:MM:SS ou segundos (Ex: 01:30)", font=ctk.CTkFont(size=10), text_color=C["warn"]).pack(side="left", padx=10)

    def _section_format(self, p):
        f = self._card(p, "FORMATO BASE")

        # Tipo: video / audio
        tr = ctk.CTkFrame(f, fg_color="transparent")
        tr.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 8))
        for lbl, val in [("Video", "video"), ("Apenas Audio", "audio")]:
            ctk.CTkRadioButton(
                tr, text=lbl, variable=self.format_choice, value=val,
                font=ctk.CTkFont(size=13), fg_color=C["accent"],
                command=self._toggle_format).pack(side="left", padx=(0, 20))

        # Video opts
        self._video_opts_row = ctk.CTkFrame(f, fg_color="transparent")
        self._video_opts_row.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 4))
        for lbl, var, vals, w in [
            ("Resolucao:", self.resolution,
             ["2160p (4K)", "1440p", "1080p", "720p", "480p", "360p",
              "Melhor disponivel"], 165),
            ("Container:", self.container, ["mp4", "mkv"], 90),
        ]:
            ctk.CTkLabel(self._video_opts_row, text=lbl, text_color=C["sub"],
                         font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
            ctk.CTkOptionMenu(
                self._video_opts_row, values=vals, variable=var,
                fg_color="#1c1c1c", button_color=C["accent"],
                font=ctk.CTkFont(size=12), width=w).pack(side="left", padx=(0, 14))

        self._note_4k = ctk.CTkLabel(
            self._video_opts_row,
            text="  FFmpeg ausente — 4K indisponivel" if not ffmpeg_ok() else "",
            font=ctk.CTkFont(size=10), text_color=C["warn"])
        self._note_4k.pack(side="left")

        # Audio opts
        self._audio_opts_row = ctk.CTkFrame(f, fg_color="transparent")
        ctk.CTkLabel(self._audio_opts_row, text="Formato:", text_color=C["sub"],
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 5))
        ctk.CTkOptionMenu(
            self._audio_opts_row, values=AUDIO_FORMATS,
            variable=self.audio_format,
            fg_color="#1c1c1c", button_color=C["accent"],
            font=ctk.CTkFont(size=12), width=110).pack(side="left")

        # Template de nome
        nr = ctk.CTkFrame(f, fg_color="transparent")
        nr.grid(row=3, column=0, sticky="ew", padx=14, pady=(4, 12))
        ctk.CTkLabel(nr, text="Template de nome:", text_color=C["sub"],
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
                .replace("%(title)s", "<titulo>")
                .replace("%(upload_date>%Y-%m-%d)s", "<data>")
                .replace("%(channel)s", "<canal>")
                .replace("%(ext)s", "mp4"))
        self._tmpl_preview.configure(text=f"ex: {prev}")

    # ── SECAO PRO (NOVA) ──────────────────────────────────────────────────────
    def _section_pro(self, p):
        f = self._card(p, "PERFIL DE SAIDA PROFISSIONAL",
                       "— codec / container otimizado para edicao")

        # ── Linha 1: Perfil de codec ──────────────────────────────────────────
        pr = ctk.CTkFrame(f, fg_color="transparent")
        pr.grid(row=1, column=0, sticky="ew", padx=14, pady=(4, 0))

        ctk.CTkLabel(pr, text="Perfil:", text_color=C["sub"],
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))

        self._profile_menu = ctk.CTkOptionMenu(
            pr, values=list(OUTPUT_PROFILES.keys()),
            variable=self.output_profile,
            fg_color="#1c1c1c", button_color=C["accent"],
            font=ctk.CTkFont(size=12), width=280,
            command=self._on_profile_change)
        self._profile_menu.pack(side="left")

        # Badge colorido do perfil ativo
        self._profile_badge = ctk.CTkLabel(
            pr, text="", font=ctk.CTkFont(size=10, weight="bold"),
            corner_radius=5, padx=8, pady=2)
        self._profile_badge.pack(side="left", padx=(10, 0))

        # Descricao do perfil
        self._profile_desc = ctk.CTkLabel(
            f, text="", anchor="w",
            font=ctk.CTkFont(size=11), text_color="#4a4a4a")
        self._profile_desc.grid(row=2, column=0, sticky="ew",
                                padx=14, pady=(2, 0))

        # ── Linha 2: FPS target (CFR) ─────────────────────────────────────────
        fr = ctk.CTkFrame(f, fg_color="transparent")
        fr.grid(row=3, column=0, sticky="ew", padx=14, pady=(8, 0))

        ctk.CTkLabel(fr, text="FPS / CFR:", text_color=C["sub"],
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        ctk.CTkOptionMenu(
            fr, values=FPS_OPTIONS, variable=self.target_fps,
            fg_color="#1c1c1c", button_color=C["accent"],
            font=ctk.CTkFont(size=12), width=160).pack(side="left")

        self._fps_hint = ctk.CTkLabel(
            fr, text="  Forcara re-encode CFR — evita problemas de sincronia",
            font=ctk.CTkFont(size=10), text_color="#3a3a3a")
        self._fps_hint.pack(side="left")
        self.target_fps.trace_add("write", self._update_fps_hint)

        # ── Linha 3: Checkboxes pro ───────────────────────────────────────────
        cr = ctk.CTkFrame(f, fg_color="transparent")
        cr.grid(row=4, column=0, sticky="ew", padx=14, pady=(8, 14))

        pro_checks = [
            (self.video_only,   "Somente Video (sem audio)",
             "Melhor para B-Roll — download na resolucao maxima disponivel"),
            (self.remove_silence, "Remover Silencio Ini/Fim",
             "silenceremove via FFmpeg — util para voz / entrevistas"),
            (self.audio_wav_pcm,  "Audio WAV PCM 24-bit",
             "Fix DaVinci Resolve free — resolve Media Offline / audio mudo com HEVC+AAC"),
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

        # Inicializa badge/descricao
        self._on_profile_change(self.output_profile.get())

    def _on_profile_change(self, name: str):
        prof  = OUTPUT_PROFILES.get(name, {})
        color = prof.get("color", C["info"])
        desc  = prof.get("description", "")

        # Mapeia a cor de destaque para um fundo escuro compativel com CTkLabel
        # (CustomTkinter nao aceita hex com canal alpha, ex: #38bdf822)
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

        # Aviso FFmpeg se necessario
        if prof.get("needs_ffmpeg") and not ffmpeg_ok():
            self._profile_desc.configure(
                text=f"⚠  {desc}  —  FFmpeg NECESSARIO",
                text_color=C["warn"])

    def _update_fps_hint(self, *_):
        if self.target_fps.get() == "Manter original":
            self._fps_hint.configure(
                text="  FPS original preservado (VFR)",
                text_color="#3a3a3a")
        else:
            self._fps_hint.configure(
                text=f"  Re-encode CFR @ {self.target_fps.get()} fps — evita dessincronizacao",
                text_color=C["warn"])

    def _section_cookies(self, p):
        f = self._card(p, "GESTAO DE COOKIES",
                       "— evita bloqueios e acessa conteudo restrito")

        mr = ctk.CTkFrame(f, fg_color="transparent")
        mr.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 6))
        for lbl, val in [("Sem cookies", "none"),
                         ("Arquivo cookies.txt", "file"),
                         ("Cookies do navegador", "browser")]:
            ctk.CTkRadioButton(
                mr, text=lbl, variable=self.cookie_mode, value=val,
                font=ctk.CTkFont(size=12), fg_color=C["accent"],
                command=self._toggle_cookie_ui).pack(side="left", padx=(0, 16))

        self._cf_frame = ctk.CTkFrame(f, fg_color="transparent")
        self._cf_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(
            self._cf_frame, textvariable=self.cookie_file,
            placeholder_text="Caminho para cookies.txt...",
            fg_color="#0d0d0d", border_color=C["border"], text_color=C["text"],
            height=34, font=ctk.CTkFont(size=12), corner_radius=7
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(
            self._cf_frame, text="Procurar...", width=90, height=34,
            fg_color="#1c1c1c", hover_color=C["border"],
            font=ctk.CTkFont(size=12), corner_radius=7,
            command=self._choose_cookie_file).grid(row=0, column=1)

        self._cb_frame = ctk.CTkFrame(f, fg_color="transparent")
        ctk.CTkLabel(self._cb_frame, text="Navegador:", text_color=C["sub"],
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
        ctk.CTkOptionMenu(
            self._cb_frame,
            values=["chrome", "firefox", "brave", "edge", "opera", "safari"],
            variable=self.cookie_browser,
            fg_color="#1c1c1c", button_color=C["accent"],
            font=ctk.CTkFont(size=12), width=130).pack(side="left")
        ctk.CTkLabel(self._cb_frame,
                     text="  (feche o navegador antes de baixar)",
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
            title="Selecione cookies.txt",
            filetypes=[("Cookies", "*.txt"), ("Todos", "*.*")])
        if p:
            self.cookie_file.set(p)

    def _section_options(self, p):
        f = self._card(p, "OPCOES EXTRAS")
        r = ctk.CTkFrame(f, fg_color="transparent")
        r.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))

        for txt, var, hint in [
            ("Embutir Miniatura",    self.embed_thumb,
             "EmbedThumbnail — capa no arquivo"),
            ("Embutir Metadados",    self.embed_meta,   ""),
            ("Embutir Legendas",     self.embed_subs,   ""),
            ("Playlist Completa",    self.dl_playlist,  ""),
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
        f = self._card(p, "PASTA DE DESTINO")
        r = ctk.CTkFrame(f, fg_color="transparent")
        r.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))
        r.grid_columnconfigure(0, weight=1)

        ctk.CTkEntry(
            r, textvariable=self.dest_folder,
            fg_color="#0d0d0d", border_color=C["border"], text_color=C["text"],
            height=34, font=ctk.CTkFont(size=12), corner_radius=7
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            r, text="Procurar...", width=90, height=34,
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
            st, text="Aguardando...",
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
            btn_row, text="BAIXAR", height=52,
            fg_color=C["accent"], hover_color=C["ahvr"],
            font=ctk.CTkFont(size=16, weight="bold"), corner_radius=10,
            command=self._download_thread)
        self.dl_btn.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.open_folder_btn = ctk.CTkButton(
            btn_row, text="Abrir Pasta", width=130, height=52,
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
            self._log(
                "AVISO: FFmpeg nao encontrado.\n"
                "        ProRes, DNxHR, CFR, WAV PCM e conversoes nao funcionarao.\n"
                "        Windows : winget install ffmpeg\n"
                "        Linux   : sudo apt install ffmpeg\n"
                "        Mac     : brew install ffmpeg",
                "warn")
            self._set_global("FFmpeg ausente — perfis profissionais indisponiveis",
                             C["warn"])
        else:
            ver = ""
            try:
                r = subprocess.run(["ffmpeg", "-version"],
                                   capture_output=True, text=True)
                m = re.search(r"ffmpeg version (\S+)", r.stdout)
                ver = f" ({m.group(1)})" if m else ""
            except Exception:
                pass
            self._log(f"FFmpeg detectado{ver}. Perfis profissionais ativos.", "success")

    # ══════════════════════════════════════════════════════════════════════════
    #  ATUALIZACAO
    # ══════════════════════════════════════════════════════════════════════════
    def _update_ytdlp(self):
        self.update_btn.configure(text="Atualizando...", state="disabled")
        self._log("pip install -U yt-dlp ...", "info")

        def _run():
            try:
                r = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-U", "yt-dlp"],
                    capture_output=True, text=True, timeout=120)
                if r.returncode == 0:
                    m      = re.search(r"Successfully installed yt-dlp-(\S+)", r.stdout)
                    already = ("already up-to-date" in r.stdout.lower()
                               or "already satisfied" in r.stdout.lower())
                    if already:
                        self._log("yt-dlp ja esta na versao mais recente.", "success")
                        self.after(0, lambda: self._toast("yt-dlp ja atualizado!", "info"))
                    else:
                        ver = m.group(1) if m else "?"
                        self._log(f"yt-dlp atualizado para {ver}!", "success")
                        self.after(0, lambda v=ver: self._toast(
                            f"yt-dlp atualizado para {v}!", "success"))
                else:
                    self._log(f"Falha: {r.stderr[:300]}", "error")
            except Exception as e:
                self._log(f"Erro: {e}", "error")
            finally:
                self.after(0, lambda: self.update_btn.configure(
                    text="Atualizar yt-dlp", state="normal"))

        threading.Thread(target=_run, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════════
    #  ANALISE DE URL
    # ══════════════════════════════════════════════════════════════════════════
    def _analyze_thread(self):
        if self._is_analyzing:
            return
        self._is_analyzing = True
        self.analyze_btn.configure(text="...", state="disabled")
        threading.Thread(target=self._analyze, daemon=True).start()

    def _analyze(self):
        url = self.url_entry.get().strip()
        if not url:
            self._log("Cole uma URL primeiro.", "warn")
            self._finish_analyze()
            return

        self._log(f"Analisando: {url[:80]}", "info")
        self.after(0, lambda: self._set_global("Analisando...", C["info"]))

        _ff_path = ffmpeg_path()
        opts = {
            "quiet":            False,   # mostra erros reais no console
            "no_warnings":      False,
            "skip_download":    True,
            "noplaylist":       not self.dl_playlist.get(),
            "http_headers":     {"User-Agent": USER_AGENTS[0]},
            # Passa o caminho do ffmpeg diretamente — contorna qualquer problema de PATH
            **({"ffmpeg_location": os.path.dirname(_ff_path)} if _ff_path else {}),
        }

        # Adiciona cookies apenas se configurados corretamente
        try:
            cookie_opts = self._cookie_opts()
            opts.update(cookie_opts)
        except Exception as ce:
            self._log(f"Aviso: erro ao carregar cookies — {ce}", "warn")

        # ESSENCIAL: informa o caminho do ffmpeg ao yt_dlp via opts
        opts.update(self._ffmpeg_opts())

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                raw = ydl.extract_info(url, download=False)

            # Log do tipo retornado para debug
            self._log(f"Tipo retornado: {type(raw).__name__}", "dim")

            # Garante que temos um dict
            if raw is None:
                raise ValueError("yt_dlp retornou None — URL invalida ou bloqueada.")
            if not isinstance(raw, dict):
                raise ValueError(
                    f"Tipo inesperado: {type(raw).__name__} — "
                    f"conteudo: {str(raw)[:120]}"
                )

            # Playlist: usa primeiro entry valido para preview
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
            pl_str   = "  [PLAYLIST]" if is_pl else ""

            self._last_title = title
            self._last_url   = url

            self.after(0, lambda: self.lbl_title.configure(text=title + pl_str))
            self.after(0, lambda: self.lbl_channel.configure(text=f"Canal: {channel}"))
            self.after(0, lambda: self.lbl_duration.configure(text=f"Duracao: {dur_str}"))
            self.after(0, lambda: self.lbl_extra.configure(text=extra))
            self.after(0, lambda: self._set_global(f"Pronto — {title[:55]}", C["success"]))
            self._log(f"OK: {title} [{dur_str}]{pl_str}", "success")

            if thumb:
                threading.Thread(target=self._load_thumb, args=(thumb,),
                                 daemon=True).start()

        except Exception as e:
            # Mostra o erro REAL (tipo + mensagem completa) no log
            import traceback
            tb = traceback.format_exc()
            self._log(f"ERRO COMPLETO: {type(e).__name__}: {e}", "error")
            self._log(f"Traceback:\n{tb}", "error")
            short, detail = classify_error(e)
            self.after(0, lambda: self._set_global(f"Erro: {short}", C["error"]))
            self.after(0, lambda s=short, d=detail: messagebox.showerror(
                f"Erro ao analisar — {s}",
                f"{d}\n\nDetalhes no LOG abaixo."))
        finally:
            self._finish_analyze()

    def _finish_analyze(self):
        self._is_analyzing = False
        self.after(0, lambda: self.analyze_btn.configure(
            text="Analisar", state="normal"))

    def _load_thumb(self, url: str):
        try:
            r  = requests.get(url, timeout=10)
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
            self._log("Arquivo de cookies nao encontrado — ignorando.", "warn")
        elif mode == "browser":
            return {"cookiesfrombrowser": (self.cookie_browser.get(),)}
        return {}

    def _ffmpeg_opts(self) -> dict:
        """
        Retorna {"ffmpeg_location": "/caminho/bin"} se o ffmpeg foi encontrado.
        Este e o unico jeito correto de informar o caminho ao yt_dlp —
        passar via opts do YoutubeDL, nunca mexer em _ffmpeg_location diretamente.
        """
        fp = ffmpeg_path()
        if fp:
            # yt_dlp espera o DIRETORIO, nao o executavel completo
            return {"ffmpeg_location": os.path.dirname(fp)}
        return {}

    # ══════════════════════════════════════════════════════════════════════════
    #  CONSTRUCAO DAS OPCOES yt-dlp  (motor completo v4)
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

        # ── Ajuste de Container Profissional ──────────────────────────────────
        final_ext = prof_cfg.get("ext") or cont
        # PCM não cabe em MP4
        if self.audio_wav_pcm.get() and final_ext == "mp4":
            final_ext = "mov"

        # ── Formato de download ──────────────────────────────────────────────
        video_only = self.video_only.get() and fmt == "video"
        res_map = {"2160p (4K)": "2160", "1440p": "1440", "1080p": "1080", "720p": "720", "480p": "480", "360p": "360", "Melhor disponivel": "0"}
        h = res_map.get(res, "1080")
        
        if fmt == "audio":
            format_str = "bestaudio/best"
        elif video_only:
            format_str = f"bestvideo[height<={h}][ext=mp4]/bestvideo[height<={h}]/bestvideo" if h != "0" else "bestvideo"
        else:
            format_str = f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={h}]+bestaudio/best" if h != "0" else "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best"

        # ── Post-processors ───────────────────────────────────────────────────
        postprocs: list[dict] = []
        if self.embed_meta.get():
            postprocs.append({"key": "FFmpegMetadata", "add_metadata": True})

        if fmt == "audio":
            # Define codec e qualidade baseado na sua escolha da UI
            target_codec = "wav" if self.audio_wav_pcm.get() else aud
            
            # Se for MP3, força 320 (máximo). Se for WAV ou outros, "0" (melhor automático)
            target_quality = "320" if target_codec == "mp3" else "0"

            postprocs.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": target_codec,
                "preferredquality": target_quality,
            })
        
        # SÓ EMBUTE THUMBNAIL SE NÃO FOR DNxHR/PRORES (evita erros de conversão)
        is_pro_codec = profile.startswith("DNxHR") or profile.startswith("ProRes")
        if self.embed_thumb.get() and ffmpeg_ok() and not video_only and not is_pro_codec:
            postprocs.append({"key": "EmbedThumbnail"})
        
        if self.embed_subs.get() and not video_only:
            postprocs.append({"key": "FFmpegEmbedSubtitle"})

        # ── Lógica de Argumentos FFmpeg ───────────────────────────────────────
        pp_ffmpeg_args: list[str] = []
        
        # Filtros de vídeo: ESSENCIAL para DNxHR (Garante dimensões pares)
        video_filters = []
        if is_pro_codec or fps_val != "Manter original":
            # "trunc(iw/2)*2" força a largura/altura a serem números pares
            video_filters.append("scale='trunc(iw/2)*2:trunc(ih/2)*2'")
            if fps_val != "Manter original":
                video_filters.append(f"fps={fps_val}")
        
        if video_filters:
            pp_ffmpeg_args += ["-vf", ",".join(video_filters)]

        # Filtros de Áudio (PCM Fix)
        if self.audio_wav_pcm.get() and not video_only:
            pp_ffmpeg_args += ["-acodec", "pcm_s24le"]

        # Adiciona argumentos específicos do perfil, limpando duplicatas de áudio
        prof_args = prof_cfg.get("ffmpeg_args") or []
        for arg_idx, arg in enumerate(prof_args):
            if arg in ["-acodec", "-c:a"] and self.audio_wav_pcm.get():
                continue # Pula o comando se já adicionamos o PCM acima
            if arg_idx > 0 and prof_args[arg_idx-1] in ["-acodec", "-c:a"] and self.audio_wav_pcm.get():
                continue # Pula o valor do comando (ex: "pcm_s24le")
            if arg not in pp_ffmpeg_args: # Evita duplicar filtros
                pp_ffmpeg_args.append(arg)

        # Silenceremove
        if self.remove_silence.get():
            pp_ffmpeg_args += ["-af", "silenceremove=start_periods=1:start_threshold=-60dB:stop_periods=-1:stop_threshold=-60dB"]

        if fmt == "video" and ffmpeg_ok():
            postprocs.append({
                "key": "FFmpegVideoConvertor",
                "preferedformat": final_ext,
            })

        # ── Opções Finais ─────────────────────────────────────────────────────
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

        # --- INICIALIZAÇÃO SEGURA DE ARGUMENTOS EXTRAS ---
        opts["postprocessor_args"] = {}

        # 1. Se for áudio, configura alta qualidade (48kHz + ID3v3)
        if fmt == "audio":
            opts["postprocessor_args"]["ExtractAudio"] = [
                "-ar", "48000",
                "-id3v2_version", "3"
            ]

        # 2. Se houver argumentos de perfil (ProRes, DNxHR, CFR, etc)
        if pp_ffmpeg_args:
            # Aplica no conversor de vídeo
            opts["postprocessor_args"]["VideoConvertor"] = pp_ffmpeg_args
            # Aplica também no áudio se estiver convertendo vídeo com PCM
            if not video_only:
                opts["postprocessor_args"]["ExtractAudio"] = opts["postprocessor_args"].get("ExtractAudio", []) + pp_ffmpeg_args

        # 3. Lógica de Trim (Corte Cirúrgico)
        t_start = self.trim_start.get().strip()
        t_end   = self.trim_end.get().strip()

        if t_start or t_end:
            opts["external_downloader"] = "ffmpeg"
            ffmpeg_i_args = []
            if t_start: ffmpeg_i_args.extend(["-ss", t_start])
            if t_end:   ffmpeg_i_args.extend(["-to", t_end])
            
            opts["external_downloader_args"] = {'ffmpeg_i': ffmpeg_i_args}
            opts["fixup"] = "force"
            
            # Reset de timestamps para o player marcar o tempo correto
            if "ffmpeg" not in opts["postprocessor_args"]:
                opts["postprocessor_args"]["ffmpeg"] = []
            opts["postprocessor_args"]["ffmpeg"].extend(["-avoid_negative_ts", "make_zero"])

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
                f"  {fname}  {pct*100:.1f}%", C["accent"]))
            self.after(0, lambda s=speed_str: self._set_speed(s))

        elif status == "finished":
            self.after(0, lambda: self.progress_bar.set(1.0))
            self.after(0, lambda: self._set_status(
                "Encode / pos-processando...", C["warn"]))
            self.after(0, lambda: self._set_speed(""))

        elif status == "error":
            self.after(0, lambda: self._set_status(
                "Erro no hook de progresso", C["error"]))

    # ══════════════════════════════════════════════════════════════════════════
    #  DOWNLOAD
    # ══════════════════════════════════════════════════════════════════════════
    def _download_thread(self):
        if self._is_downloading:
            return
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("URL vazia", "Cole uma URL antes de baixar.")
            return

        prof     = OUTPUT_PROFILES.get(self.output_profile.get(), {})
        needs_ff = (self.format_choice.get() == "audio"
                    or self.resolution.get() == "2160p (4K)"
                    or self.embed_thumb.get()
                    or self.target_fps.get() != "Manter original"
                    or self.remove_silence.get()
                    or self.audio_wav_pcm.get()
                    or prof.get("needs_ffmpeg", False))

        # Re-verifica o ffmpeg a cada download (ignora cache)
        global _FFMPEG_CHECKED
        _FFMPEG_CHECKED = False
        ff = ffmpeg_path()
        if needs_ff and not ff:
            if not messagebox.askyesno(
                "FFmpeg ausente",
                "FFmpeg nao encontrado.\n\n"
                "Perfis profissionais, CFR, WAV PCM e conversoes requerem FFmpeg.\n"
                "Deseja tentar assim mesmo?"):
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
        self.dl_btn.configure(text="Baixando...", state="disabled",
                              fg_color="#2a2a2a")
        self.open_folder_btn.configure(state="disabled", fg_color="#1c1c1c")
        self.progress_bar.set(0)

        self._dl_thread = threading.Thread(
            target=self._download, args=(url, entry), daemon=True)
        self._dl_thread.start()

    def _download(self, url: str, entry: HistoryEntry):
        self._log(f"Iniciando: {url}", "info")
        prof_name = self.output_profile.get()
        self._log(f"Perfil: {prof_name}  |  FPS: {self.target_fps.get()}", "purple")
        if self.video_only.get():
            self._log("Modo B-Roll: stream de video puro (sem audio).", "gold")
        if self.audio_wav_pcm.get():
            self._log("Fix DaVinci: audio sera convertido para WAV PCM 24-bit.", "warn")
        self.after(0, lambda: self._set_global("Baixando...", C["accent"]))

        try:
            opts = self._build_ydl_opts()
            with yt_dlp.YoutubeDL(opts) as ydl:
                self._current_ydl = ydl
                ydl.download([url])

        except Exception as e:
            import traceback
            tb   = traceback.format_exc()
            real = f"{type(e).__name__}: {e}"
            self._log(f"ERRO REAL: {real}", "error")
            self._log(f"Traceback:\n{tb}", "error")
            short, detail = classify_error(e)
            # Se classify_error nao reconheceu, mostra o erro real
            if short == "Erro Desconhecido":
                detail = real
            self.after(0, lambda: self._set_status(f"Erro: {short}", C["error"]))
            self.after(0, lambda: self._set_global(f"Erro: {short}", C["error"]))
            self.after(0, lambda s=short, d=detail: messagebox.showerror(
                f"Falha — {s}", f"{d}\n\nVeja o LOG para detalhes."))
            entry.status = "error"
            entry.error  = short

        else:
            entry.status = "ok"
            self.after(0, lambda: self._set_status("Concluido!", C["success"]))
            self.after(0, lambda: self._set_global(
                f"Concluido: {entry.title[:50]}", C["success"]))
            self._log(f"Salvo em: {self.dest_folder.get()}", "success")
            self.after(0, lambda: self._toast(
                f"Download concluido!\n{entry.title[:45]}", "success"))
            self.after(0, lambda: self.open_folder_btn.configure(
                state="normal", fg_color="#1c3a1c",
                hover_color="#1e4a1e"))

        finally:
            self._current_ydl = None
            self._is_downloading = False
            self.after(0, lambda: self.dl_btn.configure(
                text="BAIXAR", state="normal", fg_color=C["accent"]))
            self.after(0, lambda e=entry: self.history_panel.add_or_update(e))

    # ══════════════════════════════════════════════════════════════════════════
    #  FECHAMENTO LIMPO (sem processos zumbi)
    # ══════════════════════════════════════════════════════════════════════════
    def _on_close(self):
        if self._is_downloading:
            if not messagebox.askyesno(
                "Download em andamento",
                "Ha um download em andamento.\n\n"
                "Deseja encerrar mesmo assim?\n"
                "(O arquivo parcial sera mantido na pasta de destino.)"):
                return

            self._log("Encerrando download por solicitacao...", "warn")
            if self._current_ydl is not None:
                with contextlib.suppress(Exception):
                    self._current_ydl.params["abort_on_unavailable_fragment"] = True
                    if hasattr(self._current_ydl, "_popen") and \
                       self._current_ydl._popen:
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