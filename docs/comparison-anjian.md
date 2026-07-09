# 与按键精灵等工具对比（诚实版）

| 能力 | 按键精灵 / 商业工具 | auto-script-studio |
|------|---------------------|---------------------|
| 浮动控制面板 | ✅ 成熟 | ✅ `ui/layout.json` + 极简悬浮条 |
| 抓抓取色/框图 | ✅ | ✅ Studio 抓抓页 |
| 找图找色 | ✅ | ✅ `bot.findImage` / `bot.findColor` / 多点找色 |
| 找图多尺度 | 部分 | ✅ `scale_min/max/step` |
| OCR / YOLO seg | 插件/版本相关 | ✅ ML Kit + ONNX seg（掩码质心点击） |
| adb-ide 训练闭环 | ❌ | ✅ 导入 best.pt → ONNX + data.yaml |
| 脚本语言 | 自有语法 / Lua | **Lua**（`bot.*`） |
| 打包独立 APK | 部分支持 | ✅ 一键 Gradle 打包 |
| 动作录制回放 | ✅ | ⚠️ 基础 tap/swipe/YOLO 步骤（抓抓页） |
| 脚本市场 | ✅ | ❌ 开源自行分发 |
| 云控 / 多机群控 | 商业方案 | 见 script-control-center（规划中） |
| 授权/发卡 | 商业 | 可对接 jiaoben |
| 费用 | 年费/按量 | **开源免费**（MIT） |

## 适合用本项目的场景

- 希望脚本**可改、可审计、可打包**
- 模拟器 / 云手机 / 部分真机（无障碍）
- 在 adb-ide 训 YOLO seg，APK 端几十 ms 推理点击
- 愿意学一点 Lua，或委托定制

## 不太适合的场景

- 完全零代码、依赖完整录制回放
- 需要官方脚本市场一键下载
- 强依赖大漠等闭源插件生态

## 路线图

见 [ROADMAP.md](ROADMAP.md)（NCNN 原生运行时、云控、双指缩放面板等）。
