# LDPlayer 冒烟测试工程

**不是教程示例**。给 `tools/run_emulator_test.py` 用的最小工程：打包 → 装到雷电模拟器 →
跑一遍找色/找图/点击，验证「截屏 + 触控 + 视觉」链路没断。

## 谁在用

| 使用方 | 用途 |
|--------|------|
| `tools/run_emulator_test.py` | 截当前模拟器画面 → 按实际分辨率**重写** `main.lua` 的中心色与 `image/center_tpl.png`、回写 `project.json` 的 `runtime`（SDK≥30 用 `accessibility`，否则 `media_projection`）→ 打包 APK → 安装 → 开无障碍 → 启动并等 `ldplayer-test 完成` 日志（90s 超时） |
| `tests/test_packager_validate.py::test_validate_ldplayer_test` | 断言本工程能通过 `validate_project` |
| `.github/workflows/ci.yml` | `packager_cli validate` 的目标之一（只校验工程合法性，不跑模拟器） |

## 内容

- `main.lua` —— 找色（`222,222,222`）→ 找图 `image/center_tpl.png` → 命中就点、否则点屏幕中心
- `main.yaml` —— 同一流程的**遗留 YAML 版**，新工程请用 Lua（见 `AGENTS.md`）
- `project.json` —— `auto_run: true`，装完即跑，便于无人值守冒烟

## 手动跑一次

前置：已启动雷电模拟器（`emulator-5554` / `127.0.0.1:5555` 可被 `emulator_bridge` 自动发现），
并且有 JDK 17 + Android SDK（见 `docs/pack-guide.md`）。

```powershell
.\start.cmd                       # 或先 setup-studio.cmd 装依赖
.\run-emulator-test.cmd
```

## 只验证工程合法性（不需要设备/JDK）

```powershell
python -m packager.packager_cli validate examples/ldplayer-test
```
