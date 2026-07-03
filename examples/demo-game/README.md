# demo-game 示例

官方推荐的首个示例工程：演示 **找色**、**浮动面板**、**极简悬浮窗**。

## 快速运行

1. `.\start.cmd` 启动 Studio
2. 工程页 → 打开本目录
3. ADB 连接模拟器 → 抓抓页截图（可选）
4. 脚本页 → **PC 运行**

## 找图模板（可选）

找图需要 `image/` 下模板图：

1. 抓抓页框选区域 → 保存到 `image/`
2. 在 `main.lua` 中修改 `bot.findImage("image/你的图.png", ...)`

不放置模板图时，脚本仍可通过 **找色** 分支正常运行。

## 面板字段

- `mode`：普通 / 极速（见 `ui/layout.json`）
- 底部 **开始/停止** 控制脚本

## 打包

```powershell
python -m packager.packager_cli build examples/demo-game -o dist/demo-game.apk
```
