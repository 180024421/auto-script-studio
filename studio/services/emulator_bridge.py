"""雷电 / MuMu 等模拟器 ADB 端口扫描与自动 connect（Studio 用）。"""

from __future__ import annotations

import os
import re
import socket
import subprocess
from pathlib import Path
from typing import List

_DEFAULT_PORTS = [
    5555, 5557, 5559, 5561, 5563, 5565, 5567, 5569, 5571,
    62001, 21503, 7555,
]


def _popen_kwargs() -> dict:
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {
        "creationflags": subprocess.CREATE_NO_WINDOW,
        "startupinfo": startupinfo,
    }


def _port_open(host: str, port: int, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def scan_emulator_endpoints(host: str = "127.0.0.1") -> List[str]:
    ports = list(_DEFAULT_PORTS)
    if os.name == "nt":
        base = Path(os.environ.get("USERPROFILE", "")) / "Documents" / "leidian9"
        if base.is_dir():
            for cfg in base.glob("*.config"):
                try:
                    text = cfg.read_text(encoding="utf-8", errors="ignore")
                    for m in re.finditer(r'"statusSettings\.adbPort"\s*:\s*"?(\d+)"?', text):
                        ports.append(int(m.group(1)))
                except Exception:
                    continue
    seen: set[int] = set()
    out: List[str] = []
    for port in ports:
        if port in seen:
            continue
        seen.add(port)
        if _port_open(host, port):
            out.append(f"{host}:{port}")
    return out


def auto_connect_emulators(adb_path: str = "adb", host: str = "127.0.0.1") -> List[str]:
    connected: List[str] = []
    for ep in scan_emulator_endpoints(host):
        try:
            proc = subprocess.run(
                [adb_path, "connect", ep],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=12,
                **_popen_kwargs(),
            )
            text = ((proc.stdout or "") + (proc.stderr or "")).lower()
            if proc.returncode == 0 and ("connected" in text or "already" in text):
                connected.append(ep)
        except Exception:
            continue
    return connected
