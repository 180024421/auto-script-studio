"""Create Gitee repo and push (uses git credential, no secrets printed)."""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path


def git_credential(host: str) -> dict[str, str]:
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input=f"url=https://{host}\n\n",
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    out: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


def gitee_create_repo(name: str, desc: str, token: str) -> dict:
    qs = urllib.parse.urlencode({"access_token": token})
    url = f"https://gitee.com/api/v5/user/repos?{qs}"
    body = json.dumps(
        {"name": name, "description": desc, "private": False, "auto_init": False},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=UTF-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def github_create_repo(name: str, desc: str, token: str) -> dict:
    url = "https://api.github.com/user/repos"
    body = json.dumps(
        {"name": name, "description": desc, "private": False, "auto_init": False}
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    name = "auto-script-studio"
    desc = "Android script studio + APK packager (find image/color/text, YOLO)"

    # Try Gitee first (same account as adb-ide)
    cred = git_credential("gitee.com")
    token = cred.get("password", "")
    username = cred.get("username", "")
    if token:
        try:
            repo = gitee_create_repo(name, desc, token)
            print("GITEE_OK", repo.get("html_url", ""))
            return 0
        except Exception as exc:
            print("GITEE_FAIL", str(exc)[:200])

    # Fallback GitHub
    cred = git_credential("github.com")
    token = cred.get("password", "")
    if token:
        try:
            repo = github_create_repo(name, desc, token)
            print("GITHUB_OK", repo.get("html_url", ""))
            return 0
        except Exception as exc:
            print("GITHUB_FAIL", str(exc)[:200])

    print(
        "NEED_TOKEN: 请在 Gitee 设置 -> 私人令牌 生成 access_token，"
        "然后执行: git remote set-url origin https://oauth2:<TOKEN>@gitee.com/w1097529148/auto-script-studio.git"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
