# demo-game 示例

官方推荐的首个示例工程：演示 **浮动面板**、**PC 试跑**、**找色**（可选）。

## 最快体验（不用截图）

1. `.\start.cmd` 启动 Studio
2. 工程页 → **试玩示例**（或首次引导里点「打开示例并试跑」）
3. 自动打开 demo 并在 **脚本页 PC 运行**，看下方日志

## 实机安装

1. USB 连接模拟器/真机（ADB 正常）
2. 工程页 → **打包并安装到当前设备**
3. 按弹窗提示在手机上开 **无障碍 / 悬浮窗 / 录屏** 权限
4. 主界面填表，点悬浮球 **▶** 运行脚本

## 浮动面板说明

- 模式：**主界面表单 + 悬浮球启停**（不是面板里的开始/停止按钮）
- 字段见 `ui/layout.json`，脚本用 `panel.get("account")` 等读取
- `mode`：普通 / 极速 / 省电

## 找图模板（可选）

1. 抓抓页截屏 → 框选 → 保存到 `image/`
2. 在 `main.lua` 里写 `bot.findImage("image/xxx.png", ...)`

不放置模板图时，脚本仍可通过 **找色**（`optional=true`）正常运行。

## 打包（命令行）

```powershell
python -m packager.packager_cli build examples/demo-game -o dist/demo-game.apk
```
