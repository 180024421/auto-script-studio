# 参与贡献

感谢关注 auto-script-studio。

## 开发

```powershell
.\start.cmd          # 建 .venv + 装依赖（含 pytest / ruff）+ 启动 Studio
.\run-tests.cmd      # python -m pytest tests/ -q
ruff check studio packager tests tools
```

依赖分三层：`studio/requirements.txt`（范围）、`studio/requirements.lock.txt`（CI/复现用的精确版本）、
`studio/requirements-dev.txt`（pytest、ruff 固定版本）。改运行时依赖后请同步更新锁文件：

```powershell
.venv\Scripts\python.exe tools\freeze_lock.py
```

`.editorconfig` 规定缩进与换行（Python/Kotlin 4 空格、Lua 2 空格、JSON/YAML 2 空格、`.cmd` 保持 CRLF）。

## 提交 Issue

请说明：系统版本、模拟器/真机、复现步骤、日志截图。
Studio 崩溃/异常会落在 `.studio/logs/studio.log`；某次脚本运行的输出在
`.studio/logs/runs/` 下按时间命名，直接附上最相关的文件即可。

## PR

- 保持改动聚焦，匹配现有代码风格
- 涉及 API/布局契约时同步更新 `docs/`：`bot.*` 改动要同时更新 `docs/LUA.md` 能力矩阵与
  `studio/services/bot_command_catalog.py`；`layout.json` 字段改动要同时改
  `studio/services/layout_validate.py`、`schemas/layout.schema.json` 与 Kotlin 侧
  `core/overlay/LayoutConfig.kt`
- 新增示例工程后把 `validate` 命令加进 `.github/workflows/ci.yml`
