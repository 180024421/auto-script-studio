# 快速上手（5 分钟）

## 环境

- Windows 10/11
- Python **3.10+**（推荐 3.11；`start.cmd` 会自动创建 venv）
- [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools)（`adb` 在 PATH）
- 模拟器（雷电 / MuMu 等）或真机，开启 USB/网络调试

## 两条路径

| 路径 | 目标 | 需要 |
|------|------|------|
| **A. 仅 PC 联调** | 抓抓截图、编辑 Lua、ADB 试跑 | Python + adb + 设备 |
| **B. 出 APK** | 打包安装到手机独立运行 | A + **JDK 17** + **ANDROID_HOME** + build-tools |

## 1. 启动 Studio

```powershell
cd auto-script-studio
.\start.cmd
```

- 首次会装依赖（约 5–15 分钟）；之后依赖未变会跳过 pip。
- 日常也可直接 `.\run-studio.cmd`（不检查依赖）。
- 强制重装依赖：`.\setup-studio.cmd`

## 2. 打开示例工程

1. 工程页 → **试玩示例**（打开 `examples/demo-game` 并可选 PC 试跑）
2. 或 **打开工程** → 选择 `examples/demo-game`

## 3. 连接设备（路径 A）

1. 打开模拟器，确认 `adb devices` 能看到设备
2. 抓抓页 → 选择设备 → **截图**

## 4. 运行脚本

1. 脚本页 → 编辑 `main.lua`（可选）
2. **PC 运行** 在已连接设备上联调
3. 注意：`mem.*` / `bot.listApps` 等仅 APK 可用，PC 会明确报错（见 [LUA.md](LUA.md) 能力矩阵）

## 5. 打包安装（路径 B）

1. 工程页勾选 **快速重打包（跳过 clean）**（日常迭代）
2. **打包并安装到当前设备**
3. 按权限弹窗开启无障碍 / 悬浮窗（可点「打开设置」深链）
4. 改 Lua/layout 后可用 **推送到设备（热替换）** 跳过 Gradle（需已装 debug APK）

或在脚本页选择运行目标：`PC 联调` / `热替换推送` / `打包安装`。

建议：试玩 demo 后点 **另存为我的工程**，再改自己的副本。

详见 [pack-guide.md](pack-guide.md)。

## 6. 下一步

- [Lua API](LUA.md)
- [浮动面板](ui-layout.md)
- [打包 APK](pack-guide.md)
- [与按键精灵对比](comparison-anjian.md)
- [工具生态](ECOSYSTEM.md)

## 常见问题

**找不到 adb**  
将 platform-tools 加入 PATH，或重启终端。

**打包失败**  
安装 JDK 17 与 Android SDK，见 [pack-guide.md](pack-guide.md)。Studio 打包前也会弹出环境检查。

**识字 / YOLO 点了没反应**  
PC 需另装：`pip install paddleocr paddlepaddle ultralytics`。抓抓页会提示是否已安装。

**找图失败**  
在抓抓页框选模板保存到 `image/`，或先用找色 demo（不依赖模板图）。
