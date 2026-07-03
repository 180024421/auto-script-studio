"""Studio 启动环境预检：adb / Java / Android SDK。"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class CheckItem:
    name: str
    ok: bool
    detail: str
    hint: str = ""


@dataclass
class PreflightReport:
    items: List[CheckItem] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return all(i.ok for i in self.items)

    @property
    def blocking_issues(self) -> List[CheckItem]:
        return [i for i in self.items if not i.ok]


def _run_version(cmd: List[str], timeout: int = 8) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=timeout,
        )
        out = (proc.stdout or proc.stderr or "").strip()
        return proc.returncode == 0, out.splitlines()[0] if out else ""
    except FileNotFoundError:
        return False, "未找到可执行文件"
    except Exception as exc:
        return False, str(exc)


def run_preflight(adb_path: str = "adb") -> PreflightReport:
    report = PreflightReport()

    adb = adb_path or "adb"
    ok, ver = _run_version([adb, "version"])
    report.items.append(
        CheckItem(
            name="ADB",
            ok=ok,
            detail=ver or adb,
            hint="安装 Android Platform Tools 并加入 PATH，或在设置中指定 adb 路径",
        )
    )

    java_home = os.environ.get("JAVA_HOME", "").strip()
    java_exe = "java"
    if java_home:
        candidate = Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java")
        if candidate.is_file():
            java_exe = str(candidate)
    ok, ver = _run_version([java_exe, "-version"])
    report.items.append(
        CheckItem(
            name="Java",
            ok=ok,
            detail=ver or java_exe,
            hint="安装 JDK 17+ 并设置 JAVA_HOME（打包 APK 需要）",
        )
    )

    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or ""
    sdk_ok = bool(sdk) and Path(sdk).is_dir()
    build_tools = ""
    if sdk_ok:
        bt_root = Path(sdk) / "build-tools"
        if bt_root.is_dir():
            versions = sorted([p.name for p in bt_root.iterdir() if p.is_dir()], reverse=True)
            build_tools = versions[0] if versions else ""
    report.items.append(
        CheckItem(
            name="Android SDK",
            ok=sdk_ok and bool(build_tools),
            detail=f"{sdk} (build-tools {build_tools or '缺失'})" if sdk else "未设置 ANDROID_HOME",
            hint="安装 Android SDK，设置 ANDROID_HOME，并安装 build-tools",
        )
    )

    gradle_ok = shutil.which("gradle") is not None
    report.items.append(
        CheckItem(
            name="Gradle（可选）",
            ok=gradle_ok or sdk_ok,
            detail="已安装" if gradle_ok else "使用工程自带 gradlew",
            hint="",
        )
    )

    return report


def format_report_text(report: PreflightReport) -> str:
    lines = []
    for item in report.items:
        mark = "✓" if item.ok else "✗"
        lines.append(f"{mark} {item.name}: {item.detail}")
        if not item.ok and item.hint:
            lines.append(f"    → {item.hint}")
    return "\n".join(lines)
