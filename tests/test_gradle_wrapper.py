"""Gradle 包装脚本回归。

CI 的 android-compile 作业和 packager 的非 Windows 分支都依赖
android-runtime/gradlew；这个文件历史上缺失，导致 Linux 作业永远跑不起来。
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNTIME = REPO / "android-runtime"


def test_posix_wrapper_exists_with_shebang():
    wrapper = RUNTIME / "gradlew"
    assert wrapper.is_file(), "缺少 POSIX gradlew，Linux/macOS 上 ./gradlew 会直接失败"
    assert wrapper.read_bytes().startswith(b"#!/bin/sh")


def test_posix_wrapper_is_lf():
    # CRLF 会让 Linux 报 /bin/sh^M: bad interpreter，是最难排查的一类 CI 故障
    data = (RUNTIME / "gradlew").read_bytes()
    assert b"\r" not in data, "gradlew 必须以 LF 存盘（见 .gitattributes 的 eol=lf）"


def test_wrapper_resources_present():
    assert (RUNTIME / "gradlew.bat").is_file()
    assert (RUNTIME / "gradle" / "wrapper" / "gradle-wrapper.jar").is_file()
    assert (RUNTIME / "gradle" / "wrapper" / "gradle-wrapper.properties").is_file()


def test_exec_bit_on_posix_filesystems():
    if os.name == "nt":
        return  # Windows 工作区没有 exec 位，靠 git index 的 100755 + CI chmod +x
    mode = (RUNTIME / "gradlew").stat().st_mode
    assert mode & stat.S_IXUSR, "gradlew 缺少可执行位"
