# AGENTS.md — auto-script-studio

独立 Android 脚本工具链，**不依赖 adb-ide**。

## 职责

- `studio/` — PC 开发（工程、抓抓、浮动面板、Lua、打包）
- `android-runtime/` — APK 运行时（Lua、视觉、无障碍/root、浮动面板）
- `packager/` — 工程 → APK
- 新工程用 **Lua**（`main.lua`），YAML 仅遗留

## 启动

```powershell
.\start.cmd          # 安装依赖 + 启动 Studio
python -m packager.packager_cli build examples/demo-game -o dist/demo.apk
.\run-tests.cmd      # pytest tests/（131 项，约 20s；需要 .venv）
ruff check studio packager tests tools   # 版本固定于 studio/requirements-dev.txt
```

排障：Studio 崩溃与未捕获异常落在 `.studio/logs/studio.log`；每次 PC 运行的完整输出
归档在 `.studio/logs/runs/`（见 `studio/services/app_log.py`、`run_session_log.py`）。

## 禁止

- 不要 `import` 或 `sys.path` 引用 adb-ide
- 需要的能力应实现在 `studio/` 或 `android-runtime/` 内
- Windows 桌面自动化不在本仓库范围

## 文档

- [ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [LUA.md](docs/LUA.md)
- [change-routing 无] — 读 README + 模块 docs
