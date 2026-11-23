import base64
import email.utils
import hashlib
import json
import os
import subprocess
import threading
import time
import winreg
from datetime import datetime, timezone

import customtkinter as ctk
import requests

# ==============================================================================
# CONFIGURAÇÃO DO REPOSITÓRIO (SEM TOKEN — SOMENTE LEITURA PÚBLICA!)
# ==============================================================================
GITHUB_OWNER = "SEU_USUARIO_GITHUB"   # <-- Troque pelo seu usuário do GitHub
GITHUB_REPO = "ykv-licenses"          # <-- Troque pelo nome do seu repositório
GITHUB_BRANCH = "main"
GITHUB_FILE = "licenses.json"

# Tema Obsidian + Neon Branco
BG_VOID = "#050507"
BG_CARD = "#0F0F15"
BORDER_DIM = "#1E1F2B"
BORDER_GLOW = "#626885"
NEON_WHITE = "#FFFFFF"
NEON_SOFT = "#E4E8F5"
NEON_HOVER = "#D6DAEB"
TEXT_SECONDARY = "#8E93A8"
BTN_DARK = "#171822"
BTN_DARK_HOVER = "#242636"
ERR_COLOR = "#FF6B7A"

LOCAL_LICENSE_DIR = os.path.join(os.environ.get("APPDATA", "."), "YKVOptimizer")
LOCAL_LICENSE_FILE = os.path.join(LOCAL_LICENSE_DIR, "license.key")


# ==============================================================================
# GERADOR DE HWID ÚNICO (COMPATÍVEL COM WINDOWS 11 24H2+ SEM WMIC)
# ==============================================================================
def _run_ps_quiet(cmd: str) -> str:
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=6,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return (r.stdout or "").strip()
    except Exception:
        return ""


def _get_machine_guid() -> str:
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        )
        val, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        return str(val).strip()
    except Exception:
        return ""


def get_machine_hwid() -> str:
    """Combina MachineGuid + UUID da Placa-Mãe + ID do Processador em um HWID único."""
    guid = _get_machine_guid()
    board_uuid = _run_ps_quiet("(Get-CimInstance Win32_ComputerSystemProduct).UUID")
    cpu_id = _run_ps_quiet("(Get-CimInstance Win32_Processor | Select-Object -First 1).ProcessorId")

    raw = f"YKV-HWID-V2|{guid}|{board_uuid}|{cpu_id}".encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest().upper()[:16]
    return f"YKV-{digest[0:4]}-{digest[4:8]}-{digest[8:12]}-{digest[12:16]}"


# ==============================================================================
# VALIDADOR ONLINE VIA GITHUB (ANTI-FRAUDE DE RELÓGIO)
# ==============================================================================
def _fetch_remote_licenses() -> tuple[bool, dict, datetime, str]:
    api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/{GITHUB_FILE}"
    headers = {"Accept": "application/vnd.github+json", "Cache-Control": "no-cache"}

    try:
        resp = requests.get(api_url, headers=headers, params={"ref": GITHUB_BRANCH}, timeout=12)
        if resp.status_code == 200:
            server_dt = _parse_http_date(resp.headers.get("Date"))
            raw_json = base64.b64decode(resp.json().get("content", "")).decode("utf-8")
            return True, json.loads(raw_json), server_dt, ""
    except requests.RequestException:
        pass

    # Fallback para Raw CDN caso o limite da API anônima (60 req/h) seja atingido no IP
    raw_url = (
        f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/"
        f"{GITHUB_BRANCH}/{GITHUB_FILE}?t={int(time.time())}"
    )
    try:
        resp = requests.get(raw_url, headers={"Cache-Control": "no-cache"}, timeout=12)
        if resp.status_code == 200:
            server_dt = _parse_http_date(resp.headers.get("Date"))
            return True, resp.json(), server_dt, ""
        return False, {}, datetime.now(timezone.utc), f"Servidor indisponível (HTTP {resp.status_code})."
    except requests.RequestException:
        return False, {}, datetime.now(timezone.utc), "Sem conexão com a internet para validar sua licença."


def _parse_http_date(date_hdr: str | None) -> datetime:
    if date_hdr:
        try:
            return email.utils.parsedate_to_datetime(date_hdr).astimezone(timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)


def verify_license_online(key_code: str, local_hwid: str) -> tuple[bool, str, dict]:
    key_code = key_code.strip().upper()
    if not key_code:
        return False, "Digite sua chave de ativação.", {}

    ok, db, server_now, err = _fetch_remote_licenses()
    if not ok:
        return False, err, {}

    licenses = db.get("licenses", {})
    lic = licenses.get(key_code)
    if not lic:
        return False, "Chave inválida ou não encontrada.", {}

    if lic.get("status") != "active":
        return False, "Esta licença foi suspensa pelo administrador.", {}

    allowed_hwid = str(lic.get("hwid", "")).strip().upper()
    if not allowed_hwid or allowed_hwid != local_hwid.strip().upper():
        return False, "Esta Key está vinculada a outro computador (HWID não autorizado).", {}

    expires_at = str(lic.get("expires_at", "LIFETIME")).strip().upper()
    if expires_at != "LIFETIME":
        try:
            exp_date = datetime.strptime(expires_at, "%Y-%m-%d").date()
            if server_now.date() > exp_date:
                return False, f"Licença expirada em {expires_at}. Contate o administrador.", {}
        except ValueError:
            return False, "Erro na data de validade da licença.", {}

    return True, f"Bem-vindo, {lic.get('client', 'Usuário')}!", lic


def save_local_key(key_code: str):
    try:
        os.makedirs(LOCAL_LICENSE_DIR, exist_ok=True)
        with open(LOCAL_LICENSE_FILE, "w", encoding="utf-8") as f:
            f.write(key_code.strip().upper())
    except Exception:
        pass


def load_local_key() -> str:
    try:
        if os.path.exists(LOCAL_LICENSE_FILE):
            with open(LOCAL_LICENSE_FILE, "r", encoding="utf-8") as f:
                return f.read().strip().upper()
    except Exception:
        pass
    return ""


# ==============================================================================
# TELA DE ATIVAÇÃO NEON BRANCO
# ==============================================================================
class YKVAuthWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")

        self.title("YKVOptimizer PRO — Ativação por HWID")
        self.geometry("500x430")
        self.resizable(False, False)
        self.configure(fg_color=BG_VOID)

        self.authorized = False
        self.license_info = {}
        self.local_hwid = get_machine_hwid()

        self._build_ui()

        # Se já tiver uma key salva, tenta validar online automaticamente
        saved = load_local_key()
        if saved:
            self.key_entry.insert(0, saved)
            self.after(250, self._start_validation)

    def _build_ui(self):
        card = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=18, border_width=1, border_color=BORDER_GLOW)
        card.pack(fill="both", expand=True, padx=22, pady=22)

        # Logo
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(pady=(24, 6))
        ctk.CTkLabel(head, text="YKV", font=ctk.CTkFont(size=30, weight="bold"), text_color=NEON_WHITE).pack(side="left")
        ctk.CTkLabel(
            head,
            text="AUTH",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#000000",
            fg_color=NEON_WHITE,
            corner_radius=6,
            width=48,
            height=22,
        ).pack(side="left", padx=(8, 0), pady=(4, 0))

        ctk.CTkLabel(
            card,
            text="Acesso exclusivo por HWID individual",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_SECONDARY,
        ).pack(pady=(0, 18))

        # Box HWID do PC
        ctk.CTkLabel(
            card, text="SEU HWID (ENVIE AO ADMINISTRADOR PARA LIBERAR)", font=ctk.CTkFont(size=10, weight="bold"), text_color=TEXT_SECONDARY
        ).pack(anchor="w", padx=24, pady=(0, 4))

        hwid_row = ctk.CTkFrame(card, fg_color="transparent")
        hwid_row.pack(fill="x", padx=24, pady=(0, 16))

        self.hwid_box = ctk.CTkEntry(
            hwid_row,
            height=40,
            fg_color=BG_VOID,
            border_color=BORDER_DIM,
            text_color=NEON_SOFT,
            font=ctk.CTkFont(family="Consolas", size=13, weight="bold"),
        )
        self.hwid_box.insert(0, self.local_hwid)
        self.hwid_box.configure(state="readonly")
        self.hwid_box.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ctk.CTkButton(
            hwid_row,
            text="Copiar",
            width=82,
            height=40,
            corner_radius=9,
            fg_color=BTN_DARK,
            hover_color=BTN_DARK_HOVER,
            text_color=NEON_WHITE,
            border_width=1,
            border_color=BORDER_GLOW,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._copy_hwid,
        ).pack(side="left")

        # Campo Key
        ctk.CTkLabel(
            card, text="SUA CHAVE DE LICENÇA (KEY)", font=ctk.CTkFont(size=10, weight="bold"), text_color=TEXT_SECONDARY
        ).pack(anchor="w", padx=24, pady=(0, 4))

        self.key_entry = ctk.CTkEntry(
            card,
            placeholder_text="YKV-XXXX-XXXX-XXXX-XXXX",
            height=42,
            fg_color=BG_VOID,
            border_color=BORDER_GLOW,
            text_color=NEON_WHITE,
            font=ctk.CTkFont(family="Consolas", size=14, weight="bold"),
        )
        self.key_entry.pack(fill="x", padx=24, pady=(0, 16))
        self.key_entry.bind("<Return>", lambda _e: self._start_validation())

        # Botão Desbloquear
        self.submit_btn = ctk.CTkButton(
            card,
            text="⚡ VALIDAR E DESBLOQUEAR",
            height=44,
            corner_radius=10,
            fg_color=NEON_WHITE,
            hover_color=NEON_HOVER,
            text_color="#000000",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._start_validation,
        )
        self.submit_btn.pack(fill="x", padx=24)

        # Feedback de status
        self.feedback_lbl = ctk.CTkLabel(
            card,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_SECONDARY,
            wraplength=410,
        )
        self.feedback_lbl.pack(pady=(14, 10), padx=20)

    def _copy_hwid(self):
        self.clipboard_clear()
        self.clipboard_append(self.local_hwid)
        self.feedback_lbl.configure(text="HWID copiado! Envie para o administrador liberar sua Key.", text_color=NEON_WHITE)

    def _start_validation(self):
        key_code = self.key_entry.get().strip().upper()
        self.submit_btn.configure(state="disabled", text="VALIDANDO NO SERVIDOR...")
        self.feedback_lbl.configure(text="Verificando licença e HWID...", text_color=TEXT_SECONDARY)

        def worker():
            ok, msg, info = verify_license_online(key_code, self.local_hwid)

            def done():
                if ok:
                    save_local_key(key_code)
                    self.authorized = True
                    self.license_info = info
                    self.feedback_lbl.configure(text=msg, text_color=NEON_WHITE)
                    self.after(450, self.destroy)
                else:
                    self.submit_btn.configure(state="normal", text="⚡ VALIDAR E DESBLOQUEAR")
                    self.feedback_lbl.configure(text=msg, text_color=ERR_COLOR)

            self.after(0, done)

        threading.Thread(target=worker, daemon=True).start()


def require_hwid_license() -> dict | None:
    """Abre a tela de login por HWID. Retorna os dados da licença se autorizada, ou None."""
    win = YKVAuthWindow()
    win.mainloop()
    return win.license_info if win.authorized else None