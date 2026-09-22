# 示例工程

| 目录 | 说明 | 能怎么跑 | 适合拍什么内容 |
|------|------|----------|----------------|
| [demo-game](demo-game/) | **推荐首跑**：找色 + 浮动面板 + 极简悬浮条 | PC 联调 / APK | 入门教程、效果展示 |
| [dingtalk-remind](dingtalk-remind/) | 定时提醒并打开钉钉（无 root，不代打卡） | PC 联调 / APK | 考勤提醒自用 |
| [mem-lock](mem-lock/) | 面板里「初搜 → 过滤」锁定内存地址，脚本按地址循环读数 | 仅 APK + **root** | 改数值/读挂机数据类需求 |
| [saocheng-game](saocheng-game/) | 整点扫城：YOLO 认界面 + 选将 + 出征 | 仅 APK（流程在 Kotlin 运行时里） | 看「原生状态机」路线长什么样 |
| [lingzhu-fishing](lingzhu-fishing/) | 钓鱼小游戏：YOLO + 圆弧量规控制器（纯 Lua） | **暂不可运行**，缺 `bot.reelHold` 等 3 个 API | 逻辑参考，跑通前别当模板 |
| [ldplayer-test](ldplayer-test/) | `tools/run_emulator_test.py` 与 CI 的冒烟工程，非教程向 | 仅命令行冒烟 | 开发者自测 |

「能怎么跑」指脚本用到的 `bot.*` / `mem.*` 在 PC 联调侧是否可用；完整能力矩阵见
[docs/LUA.md](../docs/LUA.md)。

## 运行 demo-game

```powershell
.\start.cmd
# 工程页 → 打开 examples/demo-game
```

详见 [demo-game/README.md](demo-game/README.md)。

## 校验某个工程是否合法（不需要设备）

```powershell
python -m packager.packager_cli validate examples/demo-game
```

CI 会校验除 `mem-lock` 外的全部示例（`mem-lock` 的 `ui/layout.json` 有 id 重复与
select 尺寸过小两处问题，见 `.github/workflows/ci.yml` 内注释）。

## 另存为自己的工程

工程页 → **另存为我的工程**，改副本而不是直接改示例，方便以后拉上游更新。
