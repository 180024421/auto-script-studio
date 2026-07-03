# 快速上手（5 分钟）

## 环境

- Windows 10/11
- Python 3.11+（`start.cmd` 会自动创建 venv）
- [Android Platform Tools](https://developer.android.com/tools/releases/platform-tools)（`adb` 在 PATH）
- 模拟器（雷电 / MuMu 等）或真机，开启 USB/网络调试

## 1. 启动 Studio

```powershell
git clone <你的仓库地址>
cd auto-script-studio
.\start.cmd
```

## 2. 打开示例工程

1. 工程页 → **打开** → 选择 `examples/demo-game`
2. 或点击 **demo-game** 快捷按钮

## 3. 连接设备

1. 打开模拟器，确认 `adb devices` 能看到设备
2. 抓抓页 → 选择设备 → **截图**

## 4. 运行脚本

1. 脚本页 → 编辑 `main.lua`（可选）
2. **PC 运行** 在已连接设备上联调
3. 或工程页 → **打包安装** → 在设备上授权无障碍与悬浮窗后运行

## 5. 下一步

- [Lua API](LUA.md)
- [浮动面板](ui-layout.md)
- [打包 APK](pack-guide.md)
- [与按键精灵对比](comparison-anjian.md)
- [工具生态](ECOSYSTEM.md)

## 常见问题

**找不到 adb**  
将 platform-tools 加入 PATH，或重启终端。

**打包失败**  
安装 JDK 17 与 Android SDK，见 [pack-guide.md](pack-guide.md)。

**找图失败**  
在抓抓页框选模板保存到 `image/`，或先用找色 demo（不依赖模板图）。
