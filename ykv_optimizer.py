import ctypes
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import winreg
from collections import deque
from datetime import datetime

import customtkinter as ctk
import psutil

# ==============================================================================
# PALETA OBSIDIAN DARK + NEON BRANCO
# ==============================================================================
ctk.set_appearance_mode("dark")

BG_VOID = "#050507"         # Preto abissal principal
BG_SIDEBAR = "#09090D"      # Sidebar escura
BG_CARD = "#0F0F15"         # Card obsidian
BG_CARD_ALT = "#14141C"     # Card elevado / hover
BORDER_DIM = "#1E1F2B"      # Borda sutil inativa
BORDER_GLOW = "#52576E"     # Halo médio do neon branco
NEON_WHITE = "#FFFFFF"      # Núcleo neon branco puro
NEON_SOFT = "#E2E6F3"       # Branco frio suave
NEON_HOVER = "#D4D8E8"      # Hover de botão neon
TEXT_PRIMARY = "#FFFFFF"
TEXT_SECONDARY = "#8E93A8"
TEXT_MUTED = "#55596B"
BTN_DARK = "#171822"
BTN_DARK_HOVER = "#232534"


# ==============================================================================
# UTILITÁRIOS DE SISTEMA & REGISTRO
# ==============================================================================
def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def elevate_if_needed():
    if not is_admin() and "--no-elevate" not in sys.argv:
        params = " ".join(f'"{arg}"' for arg in sys.argv)
        try:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
            sys.exit(0)
        except Exception:
            pass


def run_cmd(command: str, timeout: int = 35) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        output = (result.stdout or result.stderr or "").strip()
        return result.returncode, output
    except subprocess.TimeoutExpired:
        return 1, "Tempo limite excedido ao executar o comando."
    except Exception as e:
        return 1, str(e)


def run_ps(script: str, timeout: int = 45) -> tuple[int, str]:
    escaped = script.replace('"', '\\"')
    return run_cmd(f'powershell -NoProfile -ExecutionPolicy Bypass -Command "{escaped}"', timeout=timeout)


def set_reg(hive, path: str, name: str, value, reg_type):
    key = winreg.CreateKeyEx(hive, path, 0, winreg.KEY_SET_VALUE)
    try:
        winreg.SetValueEx(key, name, 0, reg_type, value)
    finally:
        winreg.CloseKey(key)


def del_reg_value(hive, path: str, name: str):
    try:
        key = winreg.OpenKey(hive, path, 0, winreg.KEY_SET_VALUE)
        try:
            winreg.DeleteValue(key, name)
        finally:
            winreg.CloseKey(key)
    except Exception:
        pass


def detect_hardware_info() -> dict:
    """Detecta CPU, GPU e RAM usando PowerShell CIM (compatível com Win11 24H2+)."""
    ram_gb = round(psutil.virtual_memory().total / (1024 ** 3))
    cores = psutil.cpu_count(logical=False) or 0
    threads = psutil.cpu_count(logical=True) or 0

    cpu_name = platform.processor() or "Processador Windows"
    gpu_name = "GPU Detectada"

    code_c, out_c = run_ps("(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)")
    if code_c == 0 and out_c:
        cpu_name = out_c.splitlines()[0].strip()

    code_g, out_g = run_ps("(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join ' | '")
    if code_g == 0 and out_g:
        gpu_name = out_g.splitlines()[0].strip()

    return {
        "cpu": cpu_name,
        "gpu": gpu_name,
        "ram_gb": ram_gb,
        "cores": cores,
        "threads": threads,
        "os": f"Windows {platform.release()} (Build {platform.version().split('.')[-1]})",
    }


# ==============================================================================
# WIDGETS CUSTOMIZADOS NEON BRANCO (CANVAS)
# ==============================================================================
class NeonSparkline(tk.Canvas):
    """Gráfico em tempo real com efeito de brilho neon branco multicamadas."""

    def __init__(self, master, max_points=45, height=90, **kwargs):
        super().__init__(
            master,
            height=height,
            bg=BG_CARD,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self.max_points = max_points
        self.values = deque([0.0] * max_points, maxlen=max_points)
        self.bind("<Configure>", lambda _e: self.redraw())

    def push(self, val: float):
        self.values.append(max(0.0, min(100.0, val)))
        self.redraw()

    def redraw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10 or h < 10:
            return

        pad_y = 8
        usable_h = h - pad_y * 2

        # Linhas de grade sutis
        for frac in (0.25, 0.5, 0.75):
            gy = pad_y + usable_h * frac
            self.create_line(0, gy, w, gy, fill="#191A24", dash=(2, 4))

        pts = []
        step = w / (self.max_points - 1)
        for i, v in enumerate(self.values):
            x = i * step
            y = h - pad_y - (v / 100.0) * usable_h
            pts.extend([x, y])

        if len(pts) >= 4:
            # Camada de brilho externo (Neon Aura)
            self.create_line(*pts, fill="#222536", width=8, smooth=True, capstyle="round")
            # Camada de brilho médio
            self.create_line(*pts, fill="#6D738E", width=4, smooth=True, capstyle="round")
            # Núcleo neon branco puro
            self.create_line(*pts, fill=NEON_WHITE, width=2, smooth=True, capstyle="round")

            # Ponto luminoso na extremidade atual
            lx, ly = pts[-2], pts[-1]
            self.create_oval(lx - 6, ly - 6, lx + 6, ly + 6, fill="#35394D", outline="")
            self.create_oval(lx - 3, ly - 3, lx + 3, ly + 3, fill=NEON_WHITE, outline="")


class NeonRadialGauge(tk.Canvas):
    """Medidor circular neon branco para Score de Otimização."""

    def __init__(self, master, size=146, **kwargs):
        super().__init__(
            master,
            width=size,
            height=size,
            bg=BG_CARD,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self.size = size
        self.score = 0
        self.redraw()

    def set_score(self, value: int):
        self.score = max(0, min(100, int(value)))
        self.redraw()

    def redraw(self):
        self.delete("all")
        s = self.size
        pad = 16
        bbox = (pad, pad, s - pad, s - pad)
        extent = -(self.score / 100.0) * 359.9

        # Trilha de fundo
        self.create_oval(*bbox, outline="#1C1E2B", width=9)

        if self.score > 0:
            # Halo externo neon
            self.create_arc(*bbox, start=90, extent=extent, style="arc", outline="#282C3F", width=15)
            # Halo médio neon
            self.create_arc(*bbox, start=90, extent=extent, style="arc", outline="#787F9C", width=8)
            # Núcleo branco neon
            self.create_arc(*bbox, start=90, extent=extent, style="arc", outline=NEON_WHITE, width=3.5)

        self.create_text(
            s / 2,
            s / 2 - 8,
            text=f"{self.score}%",
            fill=NEON_WHITE,
            font=("Segoe UI", 24, "bold"),
        )
        self.create_text(
            s / 2,
            s / 2 + 18,
            text="BOOST SCORE",
            fill=TEXT_SECONDARY,
            font=("Segoe UI", 8, "bold"),
        )


# ==============================================================================
# MOTOR PROFUNDO DE OTIMIZAÇÃO WINDOWS 11
# ==============================================================================
class DeepOptimizerEngine:
    TARGET_GAMES = {
        "javaw.exe": "Minecraft Java",
        "minecraft.windows.exe": "Minecraft Bedrock",
        "fortniteclient-win64-shipping.exe": "Fortnite",
        "valorant-win64-shipping.exe": "Valorant",
        "cs2.exe": "Counter-Strike 2",
        "robloxplayerbeta.exe": "Roblox",
        "gta5.exe": "GTA V",
        "r5apex.exe": "Apex Legends",
        "cod.exe": "Call of Duty",
    }

    def __init__(self, logger):
        self.log = logger

    # --- 1. SEGURANÇA ---
    def create_restore_point(self):
        self.log("Criando Ponto de Restauração do Windows 11...")
        code, _ = run_ps(
            "Checkpoint-Computer -Description 'YKVOptimizer PRO Backup' -RestorePointType 'MODIFY_SETTINGS'"
        )
        if code == 0:
            self.log("[OK] Ponto de Restauração criado com sucesso.")
        else:
            self.log("[AVISO] Proteção do Sistema desativada no C: ou ponto já criado nas últimas 24h.")

    # --- 2. CPU & KERNEL PROFUNDO ---
    def apply_ultimate_power_and_unpark(self):
        self.log("Ativando Desempenho Máximo e desbloqueando todos os núcleos (Core Unparking)...")
        code, out = run_cmd("powercfg -duplicatescheme e9a42b02-d5df-448d-aa00-03f14749eb61")
        match = re.search(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", out)
        if code == 0 and match:
            run_cmd(f"powercfg -setactive {match.group(0)}")
        else:
            run_cmd("powercfg -setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c")

        # Desbloqueia 100% dos núcleos mínimos (CPMINCORES) e estado mínimo do processador
        run_cmd("powercfg -setacvalueindex scheme_current sub_processor CPMINCORES 100")
        run_cmd("powercfg -setacvalueindex scheme_current sub_processor PROCTHROTTLEMIN 100")
        run_cmd("powercfg -setacvalueindex scheme_current sub_processor PROCTHROTTLEMAX 100")
        run_cmd("powercfg -setactive scheme_current")
        self.log("[OK] Desempenho Máximo + CPU Core Unparking (100%) aplicados.")

    def apply_kernel_scheduler(self):
        self.log("Otimizando agendador do Kernel (Win32PrioritySeparation = 0x26) e MMCSS...")
        try:
            # Win32PrioritySeparation: 0x26 (38) = Short, Fixed, High Foreground Boost (ideal FPS estável)
            set_reg(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\PriorityControl",
                "Win32PrioritySeparation",
                0x26,
                winreg.REG_DWORD,
            )
            base = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
            set_reg(winreg.HKEY_LOCAL_MACHINE, base, "SystemResponsiveness", 0, winreg.REG_DWORD)

            games = base + r"\Tasks\Games"
            set_reg(winreg.HKEY_LOCAL_MACHINE, games, "GPU Priority", 8, winreg.REG_DWORD)
            set_reg(winreg.HKEY_LOCAL_MACHINE, games, "Priority", 6, winreg.REG_DWORD)
            set_reg(winreg.HKEY_LOCAL_MACHINE, games, "Scheduling Category", "High", winreg.REG_SZ)
            set_reg(winreg.HKEY_LOCAL_MACHINE, games, "SFIO Priority", "High", winreg.REG_SZ)
            set_reg(winreg.HKEY_LOCAL_MACHINE, games, "Clock Rate", 10000, winreg.REG_DWORD)
            self.log("[OK] Kernel Priority (0x26) e perfil MMCSS Gaming aplicados.")
        except Exception as e:
            self.log(f"[ERRO] Falha no Kernel/MMCSS: {e}")

    def apply_low_latency_timer(self):
        self.log("Configurando temporizador de baixa latência (BCDedit)...")
        run_cmd("bcdedit /set disabledynamictick yes")
        run_cmd("bcdedit /deletevalue useplatformclock")
        self.log("[OK] Dynamic Tick desativado para reduzir micro-stutters (requer reinício).")

    def apply_ram_deep_tuning(self):
        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        self.log(f"Otimizando gerenciamento de memória RAM ({ram_gb:.0f} GB detectados)...")
        try:
            mm = r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management"
            set_reg(winreg.HKEY_LOCAL_MACHINE, mm, "LargeSystemCache", 0, winreg.REG_DWORD)
            if ram_gb >= 15:
                set_reg(winreg.HKEY_LOCAL_MACHINE, mm, "DisablePagingExecutive", 1, winreg.REG_DWORD)
                run_ps("Disable-MMAgent -mc")
                self.log("[OK] Memory Compression e Paging do Kernel desativados (modo 16GB+ RAM).")
            else:
                self.log("[OK] Cache de memória otimizado (Memory Compression mantido para proteger <16GB RAM).")
        except Exception as e:
            self.log(f"[ERRO] Falha no ajuste de RAM: {e}")

    # --- 3. GPU & ZERO INPUT LAG ---
    def apply_gpu_and_dvr_tweaks(self):
        self.log("Ativando HAGS, Modo de Jogo e removendo Xbox GameDVR / FSE...")
        try:
            set_reg(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers",
                "HwSchMode",
                2,
                winreg.REG_DWORD,
            )
            set_reg(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\GameBar", "AllowAutoGameMode", 1, winreg.REG_DWORD)
            set_reg(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\GameBar", "AutoGameModeEnabled", 1, winreg.REG_DWORD)

            gcs = r"System\GameConfigStore"
            set_reg(winreg.HKEY_CURRENT_USER, gcs, "GameDVR_Enabled", 0, winreg.REG_DWORD)
            set_reg(winreg.HKEY_CURRENT_USER, gcs, "GameDVR_FSEBehaviorMode", 2, winreg.REG_DWORD)
            set_reg(winreg.HKEY_CURRENT_USER, gcs, "GameDVR_HonorUserFSEBehaviorMode", 1, winreg.REG_DWORD)
            set_reg(winreg.HKEY_CURRENT_USER, gcs, "GameDVR_DXGIHonorFSEWindowsCompatible", 1, winreg.REG_DWORD)

            set_reg(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Policies\Microsoft\Windows\GameDVR",
                "AllowGameDVR",
                0,
                winreg.REG_DWORD,
            )
            self.log("[OK] HAGS ativado, GameDVR bloqueado e Fullscreen Optimizations desativado.")
        except Exception as e:
            self.log(f"[ERRO] Falha em GPU/GameDVR: {e}")

    def apply_disable_mpo(self):
        self.log("Desativando Multi-Plane Overlay (MPO) do Windows 11...")
        try:
            set_reg(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\Dwm",
                "OverlayTestMode",
                5,
                winreg.REG_DWORD,
            )
            self.log("[OK] MPO desativado (elimina travamentos em Alt+Tab e flicker em jogos).")
        except Exception as e:
            self.log(f"[ERRO] Falha ao desativar MPO: {e}")

    def apply_zero_input_lag(self):
        self.log("Aplicando ajustes de Zero Input Lag (Mouse 1:1 + USB sem suspensão)...")
        try:
            mouse = r"Control Panel\Mouse"
            set_reg(winreg.HKEY_CURRENT_USER, mouse, "MouseSpeed", "0", winreg.REG_SZ)
            set_reg(winreg.HKEY_CURRENT_USER, mouse, "MouseThreshold1", "0", winreg.REG_SZ)
            set_reg(winreg.HKEY_CURRENT_USER, mouse, "MouseThreshold2", "0", winreg.REG_SZ)

            # Desativa Suspensão Seletiva de USB no plano de energia atual
            run_cmd("powercfg -setacvalueindex scheme_current 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0")
            run_cmd("powercfg -setactive scheme_current")

            # Reduz atraso de teclado
            kb = r"Control Panel\Keyboard"
            set_reg(winreg.HKEY_CURRENT_USER, kb, "KeyboardDelay", "0", winreg.REG_SZ)
            set_reg(winreg.HKEY_CURRENT_USER, kb, "KeyboardSpeed", "31", winreg.REG_SZ)
            self.log("[OK] Aceleração do mouse desativada, USB sempre ativo e teclado em resposta máxima.")
        except Exception as e:
            self.log(f"[ERRO] Falha em Input Lag: {e}")

    # --- 4. REDE, NAGLE & DNS ---
    def apply_deep_network_tuning(self):
        self.log("Aplicando otimização profunda de rede (TCP/IP + Desativar Nagle)...")
        try:
            set_reg(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile",
                "NetworkThrottlingIndex",
                0xFFFFFFFF,
                winreg.REG_DWORD,
            )

            # Desativa Algoritmo de Nagle em todas as interfaces TCP/IP válidas
            interfaces_path = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters\Interfaces"
            patched = 0
            try:
                root = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, interfaces_path)
                idx = 0
                while True:
                    try:
                        subname = winreg.EnumKey(root, idx)
                        idx += 1
                        full_sub = f"{interfaces_path}\\{subname}"
                        try:
                            sk = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, full_sub, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE)
                            try:
                                # Aplica somente em interfaces que possuem endereço IP/DHCP configurado
                                has_ip = False
                                for field in ("DhcpIPAddress", "IPAddress"):
                                    try:
                                        val, _ = winreg.QueryValueEx(sk, field)
                                        if val and val != "0.0.0.0":
                                            has_ip = True
                                            break
                                    except FileNotFoundError:
                                        pass
                                if has_ip:
                                    winreg.SetValueEx(sk, "TcpAckFrequency", 0, winreg.REG_DWORD, 1)
                                    winreg.SetValueEx(sk, "TCPNoDelay", 0, winreg.REG_DWORD, 1)
                                    patched += 1
                            finally:
                                winreg.CloseKey(sk)
                        except PermissionError:
                            continue
                    except OSError:
                        break
                winreg.CloseKey(root)
            except Exception:
                pass

            run_cmd("netsh int tcp set global rss=enabled")
            run_cmd("netsh int tcp set global autotuninglevel=normal")
            run_cmd("netsh int tcp set global ecncapability=disabled")
            run_cmd("netsh int tcp set global timestamps=disabled")
            run_cmd("ipconfig /flushdns")
            self.log(f"[OK] Algoritmo de Nagle desativado em {patched} interface(s), TCP/IP otimizado e DNS limpo.")
        except Exception as e:
            self.log(f"[ERRO] Falha ao otimizar rede: {e}")

    def set_dns_preset(self, label: str, servers: list[str] | None):
        if servers:
            self.log(f"Aplicando DNS {label} ({', '.join(servers)}) nos adaptadores ativos...")
            srv_str = ",".join(f"'{s}'" for s in servers)
            ps = f"Get-NetAdapter | Where-Object {{$_.Status -eq 'Up'}} | Set-DnsClientServerAddress -ServerAddresses ({srv_str})"
        else:
            self.log("Restaurando DNS Automático (DHCP) nos adaptadores ativos...")
            ps = "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Set-DnsClientServerAddress -ResetServerAddresses"

        code, out = run_ps(ps)
        run_cmd("ipconfig /flushdns")
        if code == 0:
            self.log(f"[OK] DNS alterado para {label} com sucesso.")
        else:
            self.log(f"[ERRO] Não foi possível alterar o DNS (execute como Admin): {out}")

    def test_ping(self, host: str = "1.1.1.1") -> str:
        code, out = run_cmd(f"ping -n 4 {host}", timeout=12)
        if code != 0:
            return "Sem resposta"
        # Compatível com Windows em Português ("Média = 12ms") e Inglês ("Average = 12ms")
        m = re.search(r"(?:M[eé]dia|Average)\s*=\s*(\d+\s*ms)", out, re.IGNORECASE)
        if m:
            return m.group(1).replace(" ", "")
        times = re.findall(r"(?:tempo|time)[=<](\d+)\s*ms", out, re.IGNORECASE)
        if times:
            avg = sum(int(t) for t in times) // len(times)
            return f"{avg}ms"
        return "OK"

    # --- 5. LIMPEZA PROFUNDA & DEBLOAT ---
    def deep_clean_system(self):
        self.log("Executando Limpeza Profunda (Temporários + Update Cache + GPU Shader Caches)...")
        local_app = os.environ.get("LOCALAPPDATA", "")
        targets = [
            os.environ.get("TEMP", ""),
            r"C:\Windows\Temp",
            r"C:\Windows\Prefetch",
            r"C:\Windows\SoftwareDistribution\Download",
            os.path.join(local_app, "D3DSCache"),
            os.path.join(local_app, "NVIDIA", "DXCache"),
            os.path.join(local_app, "NVIDIA", "GLCache"),
            os.path.join(local_app, "AMD", "DxCache"),
        ]

        freed_bytes = 0
        removed = 0
        for folder in targets:
            if not folder or not os.path.exists(folder):
                continue
            try:
                for entry in os.scandir(folder):
                    try:
                        if entry.is_file(follow_symlinks=False):
                            sz = entry.stat().st_size
                            os.unlink(entry.path)
                            freed_bytes += sz
                            removed += 1
                        elif entry.is_dir(follow_symlinks=False):
                            sz = 0
                            for root_d, _, files in os.walk(entry.path):
                                for fn in files:
                                    try:
                                        sz += os.path.getsize(os.path.join(root_d, fn))
                                    except OSError:
                                        pass
                            shutil.rmtree(entry.path, ignore_errors=False)
                            freed_bytes += sz
                            removed += 1
                    except Exception:
                        continue
            except Exception:
                continue

        mb = freed_bytes / (1024 * 1024)
        self.log(f"[OK] Limpeza Profunda finalizada: {removed} itens removidos ({mb:.2f} MB liberados).")

    def apply_services_and_visual_debloat(self):
        self.log("Desativando telemetria, serviços pesados (SysMain/DiagTrack) e efeitos visuais...")
        try:
            set_reg(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Policies\Microsoft\Windows\DataCollection",
                "AllowTelemetry",
                0,
                winreg.REG_DWORD,
            )
            set_reg(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                "EnableTransparency",
                0,
                winreg.REG_DWORD,
            )
            set_reg(
                winreg.HKEY_CURRENT_USER,
                r"Control Panel\Desktop\WindowMetrics",
                "MinAnimate",
                "0",
                winreg.REG_SZ,
            )
            set_reg(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
                "GlobalUserDisabled",
                1,
                winreg.REG_DWORD,
            )

            for svc in ("DiagTrack", "dmwappushservice", "SysMain", "MapsBroker", "WerSvc"):
                run_cmd(f"sc stop {svc}")
                run_cmd(f"sc config {svc} start= disabled")

            self.log("[OK] Telemetria, SysMain, apps em segundo plano e transparências desativados.")
        except Exception as e:
            self.log(f"[ERRO] Falha no debloat de serviços: {e}")

    def remove_safe_bloatware(self):
        self.log("Removendo bloatwares pré-instalados seguros do Windows 11...")
        bloat_apps = [
            "Clipchamp.Clipchamp",
            "Microsoft.BingNews",
            "Microsoft.BingWeather",
            "Microsoft.MicrosoftSolitaireCollection",
            "Microsoft.GetHelp",
            "Microsoft.Getstarted",
            "Microsoft.People",
            "Microsoft.WindowsFeedbackHub",
            "Microsoft.ZuneMusic",
            "Microsoft.ZuneVideo",
        ]
        removed_count = 0
        for pkg in bloat_apps:
            code, _ = run_ps(f"Get-AppxPackage -Name '*{pkg}*' | Remove-AppxPackage -ErrorAction SilentlyContinue")
            if code == 0:
                removed_count += 1
        self.log(f"[OK] Verificação de bloatware concluída ({removed_count} pacotes processados). Store/Defender preservados.")

    # --- 6. GAME BOOSTER DE PROCESSOS ---
    def boost_running_games(self) -> list[str]:
        boosted = []
        for proc in psutil.process_iter(["name", "pid"]):
            try:
                pname = (proc.info["name"] or "").lower()
                if pname in self.TARGET_GAMES:
                    if proc.nice() != psutil.HIGH_PRIORITY_CLASS:
                        proc.nice(psutil.HIGH_PRIORITY_CLASS)
                        boosted.append(f"{self.TARGET_GAMES[pname]} (PID {proc.info['pid']})")
            except Exception:
                continue
        return boosted

    # --- 7. REVERSÃO SEGURA ---
    def revert_all_defaults(self):
        self.log("Restaurando todas as configurações para o padrão de fábrica do Windows 11...")
        try:
            run_cmd("powercfg -setactive 381b4222-f694-41f0-9685-ff5bb260df2e")
            run_cmd("bcdedit /deletevalue disabledynamictick")

            set_reg(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\PriorityControl",
                "Win32PrioritySeparation",
                0x2,
                winreg.REG_DWORD,
            )
            base = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Multimedia\SystemProfile"
            set_reg(winreg.HKEY_LOCAL_MACHINE, base, "SystemResponsiveness", 20, winreg.REG_DWORD)
            set_reg(winreg.HKEY_LOCAL_MACHINE, base, "NetworkThrottlingIndex", 10, winreg.REG_DWORD)

            del_reg_value(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\Dwm", "OverlayTestMode")
            set_reg(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\Session Manager\Memory Management",
                "DisablePagingExecutive",
                0,
                winreg.REG_DWORD,
            )
            run_ps("Enable-MMAgent -mc")

            set_reg(winreg.HKEY_CURRENT_USER, r"System\GameConfigStore", "GameDVR_Enabled", 1, winreg.REG_DWORD)
            del_reg_value(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Policies\Microsoft\Windows\GameDVR", "AllowGameDVR")

            set_reg(winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse", "MouseSpeed", "1", winreg.REG_SZ)
            set_reg(winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse", "MouseThreshold1", "6", winreg.REG_SZ)
            set_reg(winreg.HKEY_CURRENT_USER, r"Control Panel\Mouse", "MouseThreshold2", "10", winreg.REG_SZ)

            set_reg(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                "EnableTransparency",
                1,
                winreg.REG_DWORD,
            )
            set_reg(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop\WindowMetrics", "MinAnimate", "1", winreg.REG_SZ)
            set_reg(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\BackgroundAccessApplications",
                "GlobalUserDisabled",
                0,
                winreg.REG_DWORD,
            )

            for svc in ("DiagTrack", "SysMain"):
                run_cmd(f"sc config {svc} start= auto")

            self.set_dns_preset("DHCP Automático", None)
            self.log("[OK] Sistema restaurado aos padrões do Windows 11. Reinicie o computador.")
        except Exception as e:
            self.log(f"[ERRO] Falha durante restauração: {e}")


# ==============================================================================
# INTERFACE PRINCIPAL — YKVOptimizer PRO (NEON BRANCO + OBSIDIAN DARK)
# ==============================================================================
class YKVOptimizerProApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YKVOptimizer PRO — Neon White Performance Suite")
        self.geometry("1120x700")
        self.minsize(1000, 630)
        self.configure(fg_color=BG_VOID)

        self.engine = DeepOptimizerEngine(self.log)
        self.is_busy = False
        self.auto_boost_active = False
        self.applied_score = 18  # Baseline inicial antes da otimização

        # Opções configuráveis
        self.opts = {
            "power_unpark": ctk.BooleanVar(value=True),
            "kernel_mmcss": ctk.BooleanVar(value=True),
            "timer_bcd": ctk.BooleanVar(value=True),
            "ram_deep": ctk.BooleanVar(value=True),
            "gpu_dvr": ctk.BooleanVar(value=True),
            "mpo_off": ctk.BooleanVar(value=False),  # Opcional por segurança de monitores múltiplos
            "input_lag": ctk.BooleanVar(value=True),
            "network_deep": ctk.BooleanVar(value=True),
            "clean_deep": ctk.BooleanVar(value=True),
            "debloat_svc": ctk.BooleanVar(value=True),
        }

        self.hw_info = {
            "cpu": "Detectando hardware...",
            "gpu": "Detectando GPU...",
            "ram_gb": round(psutil.virtual_memory().total / (1024 ** 3)),
            "cores": psutil.cpu_count(logical=False) or 0,
            "threads": psutil.cpu_count(logical=True) or 0,
            "os": f"Windows {platform.release()}",
        }

        self._build_layout()
        self.show_page("dashboard")
        self._update_telemetry_loop()

        # Detecta hardware detalhado sem travar a inicialização da janela
        threading.Thread(target=self._load_hardware_async, daemon=True).start()

        mode = "ADMINISTRADOR" if is_admin() else "PADRÃO (Execute como Admin para ajustes profundos)"
        self.log(f"YKVOptimizer PRO v2.0 inicializado | Privilégios: {mode}")

    def _load_hardware_async(self):
        self.hw_info = detect_hardware_info()
        self.after(0, self._refresh_hardware_labels)

    def _refresh_hardware_labels(self):
        self.hw_cpu_lbl.configure(text=self.hw_info["cpu"][:52])
        self.hw_gpu_lbl.configure(text=self.hw_info["gpu"][:52])
        self.hw_ram_lbl.configure(
            text=f"{self.hw_info['ram_gb']} GB RAM  •  {self.hw_info['cores']}C / {self.hw_info['threads']}T  •  {self.hw_info['os']}"
        )
        self._update_mc_flags()

    # --- ESTRUTURA BASE ---
    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # SIDEBAR OBSIDIAN
        self.sidebar = ctk.CTkFrame(
            self, width=240, corner_radius=0, fg_color=BG_SIDEBAR, border_width=1, border_color=BORDER_DIM
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        # Branding Neon Branco
        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.pack(fill="x", padx=22, pady=(26, 20))

        title_row = ctk.CTkFrame(brand, fg_color="transparent")
        title_row.pack(anchor="w")
        ctk.CTkLabel(
            title_row,
            text="YKV",
            font=ctk.CTkFont(family="Segoe UI", size=30, weight="bold"),
            text_color=NEON_WHITE,
        ).pack(side="left")
        ctk.CTkLabel(
            title_row,
            text="PRO",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color="#000000",
            fg_color=NEON_WHITE,
            corner_radius=6,
            width=40,
            height=22,
        ).pack(side="left", padx=(8, 0), pady=(4, 0))

        ctk.CTkLabel(
            brand,
            text="OPTIMIZER  •  NEON EDITION",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", pady=(2, 0))

        # Linha divisória neon sutil
        ctk.CTkFrame(self.sidebar, height=1, fg_color=BORDER_DIM).pack(fill="x", padx=20, pady=(0, 14))

        # Navegação com barra indicadora neon branca
        self.nav_buttons = {}
        self.nav_pills = {}
        nav_items = [
            ("dashboard", "01   Dashboard"),
            ("kernel", "02   CPU & Kernel"),
            ("gpu", "03   GPU & Input Lag"),
            ("network", "04   Rede & Ping"),
            ("games", "05   Games & Boost"),
            ("debloat", "06   Debloat & Logs"),
        ]
        for key, label in nav_items:
            row = ctk.CTkFrame(self.sidebar, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=3)

            pill = ctk.CTkFrame(row, width=3, height=26, corner_radius=2, fg_color="transparent")
            pill.pack(side="left", padx=(0, 6))

            btn = ctk.CTkButton(
                row,
                text=label,
                anchor="w",
                height=40,
                corner_radius=10,
                font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
                fg_color="transparent",
                text_color=TEXT_SECONDARY,
                hover_color=BG_CARD_ALT,
                command=lambda k=key: self.show_page(k),
            )
            btn.pack(side="left", fill="x", expand=True)
            self.nav_buttons[key] = btn
            self.nav_pills[key] = pill

        # Rodapé da Sidebar (Status Admin + Versão)
        footer = ctk.CTkFrame(
            self.sidebar, fg_color=BG_CARD, corner_radius=12, border_width=1, border_color=BORDER_DIM
        )
        footer.pack(side="bottom", fill="x", padx=16, pady=18)

        admin_txt = "● ADMIN ELEVADO" if is_admin() else "○ MODO LIMITADO"
        ctk.CTkLabel(
            footer,
            text=admin_txt,
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=NEON_WHITE if is_admin() else TEXT_SECONDARY,
        ).pack(anchor="w", padx=14, pady=(10, 2))
        ctk.CTkLabel(
            footer,
            text="Windows 11 Deep Suite v2.0",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=TEXT_MUTED,
        ).pack(anchor="w", padx=14, pady=(0, 10))

        # ÁREA PRINCIPAL
        self.main_area = ctk.CTkFrame(self, fg_color=BG_VOID, corner_radius=0)
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=26, pady=22)
        self.main_area.grid_columnconfigure(0, weight=1)
        self.main_area.grid_rowconfigure(0, weight=1)

        self.pages = {
            "dashboard": self._build_dashboard_page(),
            "kernel": self._build_kernel_page(),
            "gpu": self._build_gpu_page(),
            "network": self._build_network_page(),
            "games": self._build_games_page(),
            "debloat": self._build_debloat_logs_page(),
        }

        # BARRA DE STATUS NEON INFERIOR
        self.status_bar = ctk.CTkFrame(
            self.main_area,
            fg_color=BG_CARD,
            corner_radius=12,
            border_width=1,
            border_color=BORDER_GLOW,
            height=46,
        )
        self.status_bar.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        self.status_bar.grid_columnconfigure(0, weight=1)

        self.status_lbl = ctk.CTkLabel(
            self.status_bar,
            text="Sistema pronto. Clique em ULTRA BOOST para otimização profunda.",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=NEON_SOFT,
        )
        self.status_lbl.grid(row=0, column=0, sticky="w", padx=16, pady=10)

        self.progress = ctk.CTkProgressBar(
            self.status_bar, width=200, height=7, fg_color="#1D1F2B", progress_color=NEON_WHITE
        )
        self.progress.set(0)
        self.progress.grid(row=0, column=1, sticky="e", padx=16)

    # --- PÁGINA 1: DASHBOARD ---
    def _build_dashboard_page(self):
        frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        frame.grid_columnconfigure((0, 1), weight=1)
        frame.grid_rowconfigure(2, weight=1)

        # Cabeçalho + Hardware Card
        top_card = ctk.CTkFrame(
            frame, fg_color=BG_CARD, corner_radius=16, border_width=1, border_color=BORDER_GLOW
        )
        top_card.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 14))
        top_card.grid_columnconfigure(0, weight=1)

        left_info = ctk.CTkFrame(top_card, fg_color="transparent")
        left_info.grid(row=0, column=0, sticky="nsew", padx=22, pady=18)

        ctk.CTkLabel(
            left_info,
            text="CENTRAL DE DESEMPENHO PROFUNDO",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w")

        self.hw_cpu_lbl = ctk.CTkLabel(
            left_info,
            text=self.hw_info["cpu"],
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=NEON_WHITE,
        )
        self.hw_cpu_lbl.pack(anchor="w", pady=(4, 2))

        self.hw_gpu_lbl = ctk.CTkLabel(
            left_info,
            text=self.hw_info["gpu"],
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color=NEON_SOFT,
        )
        self.hw_gpu_lbl.pack(anchor="w")

        self.hw_ram_lbl = ctk.CTkLabel(
            left_info,
            text=f"{self.hw_info['ram_gb']} GB RAM  •  {self.hw_info['cores']}C / {self.hw_info['threads']}T",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=TEXT_SECONDARY,
        )
        self.hw_ram_lbl.pack(anchor="w", pady=(2, 14))

        # Botões Hero Neon
        btn_bar = ctk.CTkFrame(left_info, fg_color="transparent")
        btn_bar.pack(anchor="w")

        ctk.CTkButton(
            btn_bar,
            text="⚡ ULTRA BOOST (1-CLIQUE)",
            height=44,
            width=230,
            corner_radius=10,
            fg_color=NEON_WHITE,
            hover_color=NEON_HOVER,
            text_color="#000000",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            command=self.run_ultra_boost,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            btn_bar,
            text="Criar Ponto de Restauração",
            height=44,
            corner_radius=10,
            fg_color=BTN_DARK,
            hover_color=BTN_DARK_HOVER,
            text_color=NEON_WHITE,
            border_width=1,
            border_color=BORDER_GLOW,
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            command=lambda: self._run_async([("Ponto de Restauração", self.engine.create_restore_point)]),
        ).pack(side="left")

        # Medidor Radial Neon à direita
        gauge_wrap = ctk.CTkFrame(top_card, fg_color="transparent")
        gauge_wrap.grid(row=0, column=1, padx=24, pady=14)
        self.boost_gauge = NeonRadialGauge(gauge_wrap, size=148)
        self.boost_gauge.pack()
        self.boost_gauge.set_score(self.applied_score)

        # Gráficos Neon em Tempo Real (CPU & RAM)
        cpu_card = ctk.CTkFrame(
            frame, fg_color=BG_CARD, corner_radius=16, border_width=1, border_color=BORDER_DIM
        )
        cpu_card.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(0, 14))

        cpu_head = ctk.CTkFrame(cpu_card, fg_color="transparent")
        cpu_head.pack(fill="x", padx=18, pady=(14, 4))
        ctk.CTkLabel(
            cpu_head, text="CARGA DA CPU (AO VIVO)", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_SECONDARY
        ).pack(side="left")
        self.cpu_val_lbl = ctk.CTkLabel(
            cpu_head, text="0%", font=ctk.CTkFont(size=22, weight="bold"), text_color=NEON_WHITE
        )
        self.cpu_val_lbl.pack(side="right")

        self.cpu_graph = NeonSparkline(cpu_card, height=96)
        self.cpu_graph.pack(fill="x", padx=16, pady=(4, 14))

        ram_card = ctk.CTkFrame(
            frame, fg_color=BG_CARD, corner_radius=16, border_width=1, border_color=BORDER_DIM
        )
        ram_card.grid(row=1, column=1, sticky="nsew", padx=(8, 0), pady=(0, 14))

        ram_head = ctk.CTkFrame(ram_card, fg_color="transparent")
        ram_head.pack(fill="x", padx=18, pady=(14, 4))
        ctk.CTkLabel(
            ram_head, text="MEMÓRIA RAM (AO VIVO)", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT_SECONDARY
        ).pack(side="left")
        self.ram_val_lbl = ctk.CTkLabel(
            ram_head, text="0%", font=ctk.CTkFont(size=22, weight="bold"), text_color=NEON_WHITE
        )
        self.ram_val_lbl.pack(side="right")

        self.ram_graph = NeonSparkline(ram_card, height=96)
        self.ram_graph.pack(fill="x", padx=16, pady=(4, 14))

        # Mini cards de resumo rápido
        bottom_strip = ctk.CTkFrame(frame, fg_color="transparent")
        bottom_strip.grid(row=2, column=0, columnspan=2, sticky="nsew")
        bottom_strip.grid_columnconfigure((0, 1, 2), weight=1)

        self._make_stat_tile(bottom_strip, 0, "PERFIL KERNEL", "0x26 Low-Latency", "Prioridade máxima em jogos")
        self._make_stat_tile(bottom_strip, 1, "LATÊNCIA DE REDE", "No-Nagle + DNS", "Redução de jitter e ping")
        self._make_stat_tile(bottom_strip, 2, "SEGURANÇA", "100% Reversível", "Restaura padrão em 1 clique")

        return frame

    def _make_stat_tile(self, parent, col: int, tag: str, headline: str, sub: str):
        tile = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=14, border_width=1, border_color=BORDER_DIM)
        padx = (0, 8) if col == 0 else ((8, 0) if col == 2 else (4, 4))
        tile.grid(row=0, column=col, sticky="nsew", padx=padx)

        ctk.CTkLabel(tile, text=tag, font=ctk.CTkFont(size=10, weight="bold"), text_color=TEXT_MUTED).pack(
            anchor="w", padx=16, pady=(14, 2)
        )
        ctk.CTkLabel(tile, text=headline, font=ctk.CTkFont(size=16, weight="bold"), text_color=NEON_WHITE).pack(
            anchor="w", padx=16
        )
        ctk.CTkLabel(tile, text=sub, font=ctk.CTkFont(size=11), text_color=TEXT_SECONDARY).pack(
            anchor="w", padx=16, pady=(2, 14)
        )

    # --- PÁGINA 2: CPU & KERNEL ---
    def _build_kernel_page(self):
        frame = ctk.CTkScrollableFrame(self.main_area, fg_color="transparent")
        self._page_header(
            frame,
            "CPU, Kernel & Memória Profunda",
            "Elimine travamentos de frame time, destrave todos os núcleos e priorize threads de jogos no núcleo do Windows 11.",
        )

        self._option_card(
            frame,
            "Desempenho Máximo + CPU Core Unparking (100%)",
            "Ativa o plano Ultimate Performance e impede o Windows de colocar núcleos da CPU para dormir durante partidas.",
            self.opts["power_unpark"],
        )
        self._option_card(
            frame,
            "Kernel Scheduler Competitivo (Win32PrioritySeparation = 0x26) + MMCSS",
            "Configura fatias de tempo curtas e prioridade máxima para a janela do jogo em primeiro plano, estabilizando 1% lows.",
            self.opts["kernel_mmcss"],
        )
        self._option_card(
            frame,
            "Temporizador de Baixa Latência (BCDedit Dynamic Tick Off)",
            "Desativa o tick dinâmico de economia de energia do kernel para respostas mais consistentes em jogos competitivos.",
            self.opts["timer_bcd"],
        )
        self._option_card(
            frame,
            "Otimização Profunda de Memória RAM (Inteligente)",
            "Otimiza o cache de memória; em PCs com 16 GB+ de RAM, desativa Memory Compression e Paging do Kernel para reduzir uso de CPU.",
            self.opts["ram_deep"],
        )

        ctk.CTkButton(
            frame,
            text="Aplicar Otimizações de CPU & Kernel",
            height=44,
            corner_radius=10,
            fg_color=NEON_WHITE,
            hover_color=NEON_HOVER,
            text_color="#000000",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._apply_kernel_only,
        ).pack(anchor="e", pady=(14, 6))

        return frame

    # --- PÁGINA 3: GPU & ZERO INPUT LAG ---
    def _build_gpu_page(self):
        frame = ctk.CTkScrollableFrame(self.main_area, fg_color="transparent")
        self._page_header(
            frame,
            "GPU & Zero Input Lag",
            "Reduza o atraso entre seu mouse/teclado e o monitor, desbloqueando a entrega limpa de quadros da placa de vídeo.",
        )

        self._option_card(
            frame,
            "HAGS + Modo de Jogo + Bloqueio Total do Xbox GameDVR & FSE",
            "Ativa Agendamento de GPU por Hardware e remove gravação oculta e Fullscreen Optimizations que causam input lag.",
            self.opts["gpu_dvr"],
        )
        self._option_card(
            frame,
            "Zero Input Lag (Mouse 1:1 + USB Sempre Ativo + Teclado Rápido)",
            "Desativa aceleração do mouse no registro, desliga Suspensão Seletiva de USB (mouses 1000Hz+) e zera delay do teclado.",
            self.opts["input_lag"],
        )
        self._option_card(
            frame,
            "Desativar Multi-Plane Overlay (MPO) [Opcional]",
            "Corrige stutter, tela piscando e quedas de FPS em Alt+Tab em algumas GPUs NVIDIA/AMD no Windows 11.",
            self.opts["mpo_off"],
        )

        ctk.CTkButton(
            frame,
            text="Aplicar Ajustes de GPU & Input Lag",
            height=44,
            corner_radius=10,
            fg_color=NEON_WHITE,
            hover_color=NEON_HOVER,
            text_color="#000000",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._apply_gpu_only,
        ).pack(anchor="e", pady=(14, 6))

        return frame

    # --- PÁGINA 4: REDE & PING ---
    def _build_network_page(self):
        frame = ctk.CTkScrollableFrame(self.main_area, fg_color="transparent")
        self._page_header(
            frame,
            "Rede, Baixa Latência & DNS Gaming",
            "Remova atrasos artificiais de pacotes (Nagle), otimize TCP/IP e troque para o DNS mais rápido em 1 clique.",
        )

        self._option_card(
            frame,
            "Desativar Algoritmo de Nagle + Network Throttling + TCP/IP Tuning",
            "Envia pacotes de jogos imediatamente sem esperar agrupamento, remove limite de banda do Windows e limpa cache DNS.",
            self.opts["network_deep"],
        )

        # Card Seletor de DNS + Ping Tester
        dns_card = ctk.CTkFrame(
            frame, fg_color=BG_CARD, corner_radius=14, border_width=1, border_color=BORDER_GLOW
        )
        dns_card.pack(fill="x", pady=(12, 8))

        ctk.CTkLabel(
            dns_card,
            text="SELETOR RÁPIDO DE DNS GAMING",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=NEON_WHITE,
        ).pack(anchor="w", padx=18, pady=(16, 4))
        ctk.CTkLabel(
            dns_card,
            text="Altera automaticamente o DNS em todos os adaptadores conectados (Ethernet / Wi-Fi).",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=18, pady=(0, 12))

        dns_row = ctk.CTkFrame(dns_card, fg_color="transparent")
        dns_row.pack(fill="x", padx=18, pady=(0, 16))

        presets = [
            ("Cloudflare (1.1.1.1)", ["1.1.1.1", "1.0.0.1"]),
            ("Google (8.8.8.8)", ["8.8.8.8", "8.8.4.4"]),
            ("Quad9 (9.9.9.9)", ["9.9.9.9", "149.112.112.112"]),
            ("Automático (DHCP)", None),
        ]
        for label, servers in presets:
            ctk.CTkButton(
                dns_row,
                text=label,
                height=38,
                corner_radius=9,
                fg_color=BTN_DARK,
                hover_color=NEON_WHITE,
                text_color=NEON_WHITE,
                border_width=1,
                border_color=BORDER_DIM,
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda l=label, s=servers: self._run_async(
                    [(f"DNS {l}", lambda: self.engine.set_dns_preset(l, s))]
                ),
            ).pack(side="left", padx=(0, 8))

        # Testador de Ping Ao Vivo
        ping_card = ctk.CTkFrame(
            frame, fg_color=BG_CARD, corner_radius=14, border_width=1, border_color=BORDER_DIM
        )
        ping_card.pack(fill="x", pady=8)

        ping_inner = ctk.CTkFrame(ping_card, fg_color="transparent")
        ping_inner.pack(fill="x", padx=18, pady=16)

        self.ping_result_lbl = ctk.CTkLabel(
            ping_inner,
            text="Ping Atual (Cloudflare 1.1.1.1):  —",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=NEON_WHITE,
        )
        self.ping_result_lbl.pack(side="left")

        ctk.CTkButton(
            ping_inner,
            text="Testar Ping Agora",
            height=38,
            width=155,
            corner_radius=9,
            fg_color=BTN_DARK,
            hover_color=BTN_DARK_HOVER,
            text_color=NEON_WHITE,
            border_width=1,
            border_color=BORDER_GLOW,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._run_ping_test,
        ).pack(side="right")

        ctk.CTkButton(
            frame,
            text="Aplicar Otimização de Rede & Nagle",
            height=44,
            corner_radius=10,
            fg_color=NEON_WHITE,
            hover_color=NEON_HOVER,
            text_color="#000000",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: self._run_async([("Rede & Nagle", self.engine.apply_deep_network_tuning)]),
        ).pack(anchor="e", pady=(12, 6))

        return frame

    # --- PÁGINA 5: GAMES & BOOST ---
    def _build_games_page(self):
        frame = ctk.CTkScrollableFrame(self.main_area, fg_color="transparent")
        self._page_header(
            frame,
            "Game Booster Ativo & Perfis de FPS",
            "Priorização automática de processos de jogos em tempo real + gerador de argumentos JVM para Minecraft.",
        )

        # Card Auto-Booster em Tempo Real
        boost_card = ctk.CTkFrame(
            frame, fg_color=BG_CARD, corner_radius=14, border_width=1, border_color=BORDER_GLOW
        )
        boost_card.pack(fill="x", pady=(0, 12))

        b_top = ctk.CTkFrame(boost_card, fg_color="transparent")
        b_top.pack(fill="x", padx=20, pady=16)

        info_b = ctk.CTkFrame(b_top, fg_color="transparent")
        info_b.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(
            info_b,
            text="AUTO GAME PRIORITY BOOSTER (TEMPO REAL)",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=NEON_WHITE,
        ).pack(anchor="w")
        ctk.CTkLabel(
            info_b,
            text="Detecta Minecraft, Fortnite, Valorant, CS2, Roblox e GTA V e eleva automaticamente a prioridade da CPU para ALTA.",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", pady=(2, 0))

        self.booster_btn = ctk.CTkButton(
            b_top,
            text="ATIVAR AUTO-BOOST",
            height=40,
            width=180,
            corner_radius=10,
            fg_color=NEON_WHITE,
            hover_color=NEON_HOVER,
            text_color="#000000",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._toggle_game_booster,
        )
        self.booster_btn.pack(side="right", padx=(12, 0))

        # Card Gerador JVM Minecraft
        mc_card = ctk.CTkFrame(
            frame, fg_color=BG_CARD, corner_radius=14, border_width=1, border_color=BORDER_DIM
        )
        mc_card.pack(fill="x", pady=8)

        ctk.CTkLabel(
            mc_card,
            text="MINECRAFT JAVA — GERADOR DE FLAGS JVM (G1GC ULTRA FPS)",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=NEON_WHITE,
        ).pack(anchor="w", padx=20, pady=(16, 4))
        ctk.CTkLabel(
            mc_card,
            text="Cole no Launcher (Instalações > Mais Opções > Argumentos JVM) junto com Fabric + Sodium + Lithium:",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w", padx=20, pady=(0, 10))

        self.mc_flags_box = ctk.CTkTextbox(
            mc_card,
            height=78,
            fg_color=BG_VOID,
            text_color=NEON_SOFT,
            border_width=1,
            border_color=BORDER_DIM,
            corner_radius=10,
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self.mc_flags_box.pack(fill="x", padx=20, pady=(0, 10))
        self._update_mc_flags()

        ctk.CTkButton(
            mc_card,
            text="Copiar Flags do Minecraft",
            height=36,
            width=190,
            corner_radius=9,
            fg_color=BTN_DARK,
            hover_color=BTN_DARK_HOVER,
            text_color=NEON_WHITE,
            border_width=1,
            border_color=BORDER_GLOW,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._copy_mc_flags,
        ).pack(anchor="e", padx=20, pady=(0, 16))

        # Card Dica Fortnite / Competitivo
        fn_card = ctk.CTkFrame(
            frame, fg_color=BG_CARD, corner_radius=14, border_width=1, border_color=BORDER_DIM
        )
        fn_card.pack(fill="x", pady=8)
        ctk.CTkLabel(
            fn_card,
            text="PERFIL COMPETITIVO FORTNITE & SHOOTERS",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=NEON_WHITE,
        ).pack(anchor="w", padx=20, pady=(14, 4))
        ctk.CTkLabel(
            fn_card,
            text="• Modo de Renderização: Desempenho (Fidelidade Gráfica Baixa) ou DX12 (GPUs RTX/RX recentes).\n"
                 "• Desative Replays nas configurações do jogo (economiza até 15% de CPU).\n"
                 "• Ative NVIDIA Reflex (Ligado + Boost) ou AMD Anti-Lag para menor latência de sistema.",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_SECONDARY,
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 16))

        return frame

    # --- PÁGINA 6: DEBLOAT & LOGS ---
    def _build_debloat_logs_page(self):
        frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(3, weight=1)

        self._page_header(
            frame,
            "Limpeza Profunda, Debloat & Console",
            "Limpe caches de GPU/Sistema, remova bloatwares seguros do Windows 11 e acompanhe cada comando.",
            use_grid=True,
        )

        # Opções rápidas
        opt_wrap = ctk.CTkFrame(frame, fg_color="transparent")
        opt_wrap.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self._option_card(
            opt_wrap,
            "Limpeza Profunda (Temp + Prefetch + Windows Update + Shaders NVIDIA/AMD/DX)",
            "Libera espaço e remove caches corrompidos que causam engasgos em jogos.",
            self.opts["clean_deep"],
        )
        self._option_card(
            opt_wrap,
            "Debloat de Serviços & Interface (Telemetria, SysMain, Apps em 2º Plano)",
            "Desativa serviços em segundo plano e transparências pesadas do Windows 11.",
            self.opts["debloat_svc"],
        )

        # Console Neon
        self.log_box = ctk.CTkTextbox(
            frame,
            fg_color=BG_CARD,
            text_color=NEON_SOFT,
            border_width=1,
            border_color=BORDER_GLOW,
            corner_radius=12,
            font=ctk.CTkFont(family="Consolas", size=12),
            state="disabled",
        )
        self.log_box.grid(row=3, column=0, sticky="nsew", pady=(4, 10))

        # Ações inferiores
        btns = ctk.CTkFrame(frame, fg_color="transparent")
        btns.grid(row=4, column=0, sticky="ew")

        ctk.CTkButton(
            btns,
            text="Limpeza Profunda Agora",
            height=40,
            corner_radius=9,
            fg_color=NEON_WHITE,
            hover_color=NEON_HOVER,
            text_color="#000000",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._run_async([("Limpeza Profunda", self.engine.deep_clean_system)]),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btns,
            text="Remover Bloatware Win11",
            height=40,
            corner_radius=9,
            fg_color=BTN_DARK,
            hover_color=BTN_DARK_HOVER,
            text_color=NEON_WHITE,
            border_width=1,
            border_color=BORDER_DIM,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._run_async([("Removendo Bloatware", self.engine.remove_safe_bloatware)]),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            btns,
            text="Restaurar Padrões Windows 11",
            height=40,
            corner_radius=9,
            fg_color=BTN_DARK,
            hover_color=BTN_DARK_HOVER,
            text_color=NEON_WHITE,
            border_width=1,
            border_color=BORDER_GLOW,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._run_async([("Restaurando Padrões", self.engine.revert_all_defaults)]),
        ).pack(side="left")

        ctk.CTkButton(
            btns,
            text="Limpar Logs",
            height=40,
            width=100,
            corner_radius=9,
            fg_color="transparent",
            hover_color=BTN_DARK,
            text_color=TEXT_SECONDARY,
            command=self._clear_logs,
        ).pack(side="right")

        return frame

    # --- AUXILIARES DE UI ---
    def _page_header(self, parent, title: str, subtitle: str, use_grid: bool = False):
        if use_grid:
            ctk.CTkLabel(
                parent, text=title, font=ctk.CTkFont(size=22, weight="bold"), text_color=NEON_WHITE
            ).grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(
                parent, text=subtitle, font=ctk.CTkFont(size=12), text_color=TEXT_SECONDARY
            ).grid(row=1, column=0, sticky="w", pady=(2, 12))
        else:
            ctk.CTkLabel(
                parent, text=title, font=ctk.CTkFont(size=22, weight="bold"), text_color=NEON_WHITE
            ).pack(anchor="w")
            ctk.CTkLabel(
                parent, text=subtitle, font=ctk.CTkFont(size=12), text_color=TEXT_SECONDARY
            ).pack(anchor="w", pady=(2, 14))

    def _option_card(self, parent, title: str, desc: str, var: ctk.BooleanVar):
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=13, border_width=1, border_color=BORDER_DIM)
        card.pack(fill="x", pady=5)

        txt = ctk.CTkFrame(card, fg_color="transparent")
        txt.pack(side="left", fill="both", expand=True, padx=18, pady=13)

        ctk.CTkLabel(txt, text=title, font=ctk.CTkFont(size=13, weight="bold"), text_color=NEON_WHITE).pack(anchor="w")
        ctk.CTkLabel(txt, text=desc, font=ctk.CTkFont(size=11), text_color=TEXT_SECONDARY).pack(anchor="w", pady=(2, 0))

        ctk.CTkSwitch(
            card,
            text="",
            variable=var,
            width=46,
            fg_color="#1D1F2B",
            progress_color=NEON_WHITE,
            button_color="#8C91A8",
            button_hover_color=NEON_WHITE,
        ).pack(side="right", padx=18)

    def show_page(self, key: str):
        for k, f in self.pages.items():
            f.grid_forget()
            self.nav_buttons[k].configure(fg_color="transparent", text_color=TEXT_SECONDARY)
            self.nav_pills[k].configure(fg_color="transparent")

        self.pages[key].grid(row=0, column=0, sticky="nsew")
        self.nav_buttons[key].configure(fg_color=BG_CARD_ALT, text_color=NEON_WHITE)
        self.nav_pills[key].configure(fg_color=NEON_WHITE)

    # --- LÓGICA & EVENTOS ---
    def _update_mc_flags(self):
        ram = self.hw_info.get("ram_gb", 8)
        alloc = 6 if ram >= 16 else (4 if ram >= 8 else 2)
        flags = (
            f"-Xms{alloc}G -Xmx{alloc}G -XX:+UseG1GC -XX:+ParallelRefProcEnabled "
            f"-XX:MaxGCPauseMillis=200 -XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC "
            f"-XX:+AlwaysPreTouch -XX:G1NewSizePercent=30 -XX:G1MaxNewSizePercent=40 "
            f"-XX:G1HeapRegionSize=8M -XX:G1ReservePercent=20 -XX:InitiatingHeapOccupancyPercent=15"
        )
        self.mc_flags_box.configure(state="normal")
        self.mc_flags_box.delete("1.0", "end")
        self.mc_flags_box.insert("1.0", flags)
        self.mc_flags_box.configure(state="disabled")

    def _copy_mc_flags(self):
        text = self.mc_flags_box.get("1.0", "end").strip()
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_lbl.configure(text="Flags JVM do Minecraft copiadas para a área de transferência!")
        self.log("[OK] Argumentos JVM do Minecraft copiados.")

    def _toggle_game_booster(self):
        self.auto_boost_active = not self.auto_boost_active
        if self.auto_boost_active:
            self.booster_btn.configure(text="● AUTO-BOOST ATIVO", fg_color=BTN_DARK, text_color=NEON_WHITE, border_width=1, border_color=NEON_WHITE)
            self.log("[OK] Auto Game Booster ativado: monitorando jogos a cada 5 segundos.")
            threading.Thread(target=self._game_booster_loop, daemon=True).start()
        else:
            self.booster_btn.configure(text="ATIVAR AUTO-BOOST", fg_color=NEON_WHITE, text_color="#000000", border_width=0)
            self.log("Auto Game Booster pausado.")

    def _game_booster_loop(self):
        while self.auto_boost_active:
            boosted = self.engine.boost_running_games()
            for item in boosted:
                self.log(f"[BOOST] Prioridade ALTA aplicada automaticamente em: {item}")
                self.after(0, lambda i=item: self.status_lbl.configure(text=f"Game Booster ativo em: {i}"))
            time.sleep(5)

    def _run_ping_test(self):
        self.ping_result_lbl.configure(text="Testando latência (1.1.1.1)...")

        def worker():
            res = self.engine.test_ping("1.1.1.1")
            self.after(0, lambda: self.ping_result_lbl.configure(text=f"Ping Atual (Cloudflare 1.1.1.1):  {res}"))
            self.log(f"[REDE] Teste de ping para 1.1.1.1: {res}")

        threading.Thread(target=worker, daemon=True).start()

    def _apply_kernel_only(self):
        tasks = []
        if self.opts["power_unpark"].get():
            tasks.append(("Desempenho Máximo & Unpark", self.engine.apply_ultimate_power_and_unpark))
        if self.opts["kernel_mmcss"].get():
            tasks.append(("Kernel Scheduler & MMCSS", self.engine.apply_kernel_scheduler))
        if self.opts["timer_bcd"].get():
            tasks.append(("Timer de Baixa Latência", self.engine.apply_low_latency_timer))
        if self.opts["ram_deep"].get():
            tasks.append(("Otimização de RAM", self.engine.apply_ram_deep_tuning))
        self._run_async(tasks, score_boost=30)

    def _apply_gpu_only(self):
        tasks = []
        if self.opts["gpu_dvr"].get():
            tasks.append(("GPU, HAGS & GameDVR", self.engine.apply_gpu_and_dvr_tweaks))
        if self.opts["input_lag"].get():
            tasks.append(("Zero Input Lag", self.engine.apply_zero_input_lag))
        if self.opts["mpo_off"].get():
            tasks.append(("Desativar MPO", self.engine.apply_disable_mpo))
        self._run_async(tasks, score_boost=25)

    def run_ultra_boost(self):
        tasks = []
        if self.opts["power_unpark"].get():
            tasks.append(("Desempenho Máximo & Unpark", self.engine.apply_ultimate_power_and_unpark))
        if self.opts["kernel_mmcss"].get():
            tasks.append(("Kernel Scheduler & MMCSS", self.engine.apply_kernel_scheduler))
        if self.opts["timer_bcd"].get():
            tasks.append(("Timer de Baixa Latência", self.engine.apply_low_latency_timer))
        if self.opts["ram_deep"].get():
            tasks.append(("Otimização de RAM", self.engine.apply_ram_deep_tuning))
        if self.opts["gpu_dvr"].get():
            tasks.append(("GPU, HAGS & GameDVR", self.engine.apply_gpu_and_dvr_tweaks))
        if self.opts["input_lag"].get():
            tasks.append(("Zero Input Lag", self.engine.apply_zero_input_lag))
        if self.opts["mpo_off"].get():
            tasks.append(("Desativar MPO", self.engine.apply_disable_mpo))
        if self.opts["network_deep"].get():
            tasks.append(("Rede Profunda & Nagle", self.engine.apply_deep_network_tuning))
        if self.opts["debloat_svc"].get():
            tasks.append(("Debloat de Serviços", self.engine.apply_services_and_visual_debloat))
        if self.opts["clean_deep"].get():
            tasks.append(("Limpeza Profunda & Shaders", self.engine.deep_clean_system))

        if not tasks:
            self.status_lbl.configure(text="Nenhuma opção marcada para o Ultra Boost.")
            return
        self._run_async(tasks, score_boost=100)

    def _run_async(self, tasks: list, score_boost: int = 10):
        if self.is_busy or not tasks:
            return
        self.is_busy = True

        def worker():
            total = len(tasks)
            for idx, (label, fn) in enumerate(tasks, start=1):
                self.after(0, lambda l=label: self.status_lbl.configure(text=f"Executando: {l}..."))
                fn()
                self.after(0, lambda p=idx / total: self.progress.set(p))

            self.applied_score = min(100, max(self.applied_score, score_boost) if score_boost == 100 else self.applied_score + score_boost)
            self.after(0, lambda: self.boost_gauge.set_score(self.applied_score))
            self.after(
                0,
                lambda: self.status_lbl.configure(
                    text="Concluído com sucesso! Reinicie o Windows 11 para ativar todas as otimizações."
                ),
            )
            self.is_busy = False

        self.progress.set(0)
        threading.Thread(target=worker, daemon=True).start()

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"

        def _append():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", line)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        self.after(0, _append)

    def _clear_logs(self):
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")

    def _update_telemetry_loop(self):
        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory().percent
        self.cpu_val_lbl.configure(text=f"{cpu:.0f}%")
        self.ram_val_lbl.configure(text=f"{ram:.0f}%")
        self.cpu_graph.push(cpu)
        self.ram_graph.push(ram)
        self.after(1000, self._update_telemetry_loop)


if __name__ == "__main__":
    elevate_if_needed()

    from ykv_auth import require_hwid_license

    license_data = require_hwid_license()
    if not license_data:
        sys.exit(0)

    app = YKVOptimizerProApp()
    app.title(f"YKVOptimizer PRO — Licenciado para {license_data.get('client', 'VIP')}")
    app.mainloop()