"""ADB 设备与截屏（PC Studio 联调）。"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import List, Optional


def _is_emulator_serial(serial: str) -> bool:
    s = serial.lower()
    return s.startswith("emulator-") or ":5555" in s or "127.0.0.1" in s


def _model_from_detail(detail: str) -> str:
    m = re.search(r"model:(\S+)", detail)
    return m.group(1) if m else ""


@dataclass
class AdbDevice:
    serial: str
    status: str
    detail: str = ""

    @property
    def label(self) -> str:
        tag = " [模拟器]" if _is_emulator_serial(self.serial) else ""
        extra = f" {self.detail}" if self.detail else ""
        return f"{self.serial}{tag} [{self.status}]{extra}"

    @property
    def combo_text(self) -> str:
        """下拉框短标签（左对齐展示，完整信息见 tooltip）。"""
        tag = "模拟器" if self.is_emulator else "真机"
        model = _model_from_detail(self.detail)
        if model:
            short = model if len(model) <= 18 else f"{model[:16]}…"
            return f"{short} [{tag}]"
        serial = self.serial
        if len(serial) > 22:
            serial = f"{serial[:20]}…"
        return f"{serial} [{tag}]"

    @property
    def is_emulator(self) -> bool:
        return _is_emulator_serial(self.serial)


class AdbService:
    def __init__(self, adb_path: str = "adb") -> None:
        self.adb_path = adb_path

    def _run(
        self,
        args: List[str],
        *,
        serial: Optional[str] = None,
        check: bool = True,
        timeout: int = 30,
        text: bool = False,
    ) -> subprocess.CompletedProcess:
        cmd = [self.adb_path]
        if serial:
            cmd.extend(["-s", serial])
        cmd.extend(args)
        return subprocess.run(
            cmd,
            capture_output=True,
            check=check,
            timeout=timeout,
            text=text,
            encoding="utf-8" if text else None,
            errors="ignore" if text else None,
        )

    def list_devices(self) -> List[AdbDevice]:
        proc = self._run(["devices", "-l"], check=False, text=True, timeout=15)
        out: List[AdbDevice] = []
        for line in proc.stdout.splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                detail = " ".join(parts[2:]) if len(parts) > 2 else ""
                out.append(AdbDevice(serial=parts[0], status=parts[1], detail=detail))
        out.sort(key=lambda d: (not d.is_emulator, d.serial))
        return out

    def default_serial(self) -> Optional[str]:
        devs = self.list_devices()
        if not devs:
            return None
        for d in devs:
            if d.is_emulator:
                return d.serial
        return devs[0].serial

    def capture_png(self, serial: Optional[str] = None) -> bytes:
        use_serial = serial or self.default_serial()
        args = ["exec-out", "screencap", "-p"]
        proc = self._run(args, serial=use_serial, check=False, timeout=30)
        if proc.returncode != 0 or not proc.stdout:
            err = (proc.stderr or b"").decode("utf-8", errors="ignore")
            raise RuntimeError(f"ADB 截屏失败: {err or proc.returncode}")
        return proc.stdout

    def get_screen_size(self, serial: Optional[str] = None) -> tuple[int, int]:
        use_serial = serial or self.default_serial()
        proc = self._run(["shell", "wm", "size"], serial=use_serial, text=True, timeout=10)
        text = proc.stdout or proc.stderr or ""
        m = re.search(r"(\d+)x(\d+)", text)
        if not m:
            raise RuntimeError(f"无法解析屏幕尺寸: {text.strip()}")
        return int(m.group(1)), int(m.group(2))

    def tap(self, serial: Optional[str], x: int, y: int) -> None:
        use_serial = serial or self.default_serial()
        self._run(["shell", "input", "tap", str(x), str(y)], serial=use_serial, timeout=10)

    def swipe(
        self,
        serial: Optional[str],
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 300,
    ) -> None:
        use_serial = serial or self.default_serial()
        self._run(
            [
                "shell",
                "input",
                "swipe",
                str(x1),
                str(y1),
                str(x2),
                str(y2),
                str(duration_ms),
            ],
            serial=use_serial,
            timeout=15,
        )

    def install_apk(self, apk_path: str, serial: Optional[str] = None, *, timeout: int = 300) -> None:
        use_serial = serial or self.default_serial()
        proc = self._run(
            ["install", "-r", apk_path],
            serial=use_serial,
            check=False,
            timeout=timeout,
            text=True,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0 or "Failure" in out:
            raise RuntimeError(f"ADB 安装失败: {out.strip() or proc.returncode}")

    def start_package(self, package_id: str, serial: Optional[str] = None) -> None:
        use_serial = serial or self.default_serial()
        self._run(
            [
                "shell",
                "monkey",
                "-p",
                package_id,
                "-c",
                "android.intent.category.LAUNCHER",
                "1",
            ],
            serial=use_serial,
            timeout=15,
        )

    def get_sdk_version(self, serial: Optional[str] = None) -> int:
        use_serial = serial or self.default_serial()
        proc = self._run(["shell", "getprop", "ro.build.version.sdk"], serial=use_serial, text=True, timeout=10)
        try:
            return int((proc.stdout or "28").strip())
        except ValueError:
            return 28

    def tap_projection_allow(self, serial: Optional[str] = None) -> None:
        """模拟器上点 MediaProjection「立即开始」/ Start now（API<30 测试用）。"""
        use_serial = serial or self.default_serial()
        w, h = self.get_screen_size(use_serial)
        for x, y in (
            (int(w * 0.72), int(h * 0.70)),
            (int(w * 0.62), int(h * 0.68)),
            (w // 2, int(h * 0.75)),
        ):
            self.tap(use_serial, x, y)
            import time

            time.sleep(0.6)

    def enable_accessibility(
        self,
        package_id: str,
        *,
        service: str = "com.autoscript.core.accessibility.AutomationAccessibilityService",
        serial: Optional[str] = None,
    ) -> bool:
        """通过 ADB 开启本应用无障碍服务（模拟器/测试用）。成功返回 True。"""
        import time

        use_serial = serial or self.default_serial()
        component = f"{package_id}/{service}"

        proc = self._run(
            ["shell", "settings", "get", "secure", "enabled_accessibility_services"],
            serial=use_serial,
            check=False,
            text=True,
            timeout=10,
        )
        current = (proc.stdout or "").strip()
        if current in ("", "null", "None"):
            services_value = component
        elif component in current.split(":"):
            services_value = current
        else:
            services_value = f"{current}:{component}"

        ok = True
        for args in (
            ["shell", "settings", "put", "secure", "enabled_accessibility_services", services_value],
            ["shell", "settings", "put", "secure", "accessibility_enabled", "1"],
        ):
            p = self._run(args, serial=use_serial, check=False, text=True, timeout=10)
            if p.returncode != 0:
                ok = False

        self._run(
            ["shell", "cmd", "accessibility", "enable-service", f"0:{component}"],
            serial=use_serial,
            check=False,
            timeout=10,
        )
        time.sleep(0.5)
        return ok

    def read_script_status(self, package_id: str, serial: Optional[str] = None) -> str:
        use_serial = serial or self.default_serial()
        paths = [
            f"/sdcard/Android/data/{package_id}/files/script_status.txt",
            f"/storage/emulated/0/Android/data/{package_id}/files/script_status.txt",
        ]
        for path in paths:
            proc = self._run(["shell", "cat", path], serial=use_serial, check=False, text=True, timeout=10)
            text = (proc.stdout or "").strip()
            if proc.returncode == 0 and text:
                return text
        return ""

    def wait_script_status(
        self,
        package_id: str,
        needle: str,
        *,
        serial: Optional[str] = None,
        timeout_sec: float = 90.0,
        poll_sec: float = 2.0,
    ) -> bool:
        import time

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            status = self.read_script_status(package_id, serial)
            if needle in status:
                return True
            time.sleep(poll_sec)
        return False

    def logcat_contains(
        self,
        needle: str,
        *,
        serial: Optional[str] = None,
        clear: bool = False,
        tag: str = "AutoScript",
    ) -> bool:
        use_serial = serial or self.default_serial()
        if clear:
            self._run(["logcat", "-c"], serial=use_serial, check=False, timeout=10)
        proc = self._run(
            ["logcat", "-d", "-s", f"{tag}:I", f"{tag}:E"],
            serial=use_serial,
            check=False,
            text=True,
            timeout=20,
        )
        text = (proc.stdout or "") + (proc.stderr or "")
        return needle in text

    def wait_logcat(
        self,
        needle: str,
        *,
        serial: Optional[str] = None,
        timeout_sec: float = 45.0,
        poll_sec: float = 1.5,
        tag: str = "AutoScript",
    ) -> bool:
        import time

        use_serial = serial or self.default_serial()
        self._run(["logcat", "-c"], serial=use_serial, check=False, timeout=10)
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            proc = self._run(
                ["logcat", "-d", "-s", f"{tag}:I", f"{tag}:E"],
                serial=use_serial,
                check=False,
                text=True,
                timeout=15,
            )
            text = (proc.stdout or "") + (proc.stderr or "")
            if needle in text:
                return True
            time.sleep(poll_sec)
        return False
