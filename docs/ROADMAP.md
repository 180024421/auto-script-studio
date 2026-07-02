# 开发路线图

## 已完成（v0.3）

- [x] Lua 为主脚本语言 + `lib/` require 模块
- [x] **按键精灵式浮动面板**（`ui/layout.json` + `OverlayService`）
- [x] PC Studio 浮动面板布局编辑器
- [x] Lua 语法高亮、`bot.findNode` 无障碍控件
- [x] 截屏帧缓存、脚本取消令牌、JSON 状态文件
- [x] 打包器增强校验 + Release keystore CLI
- [x] `tools/yaml_to_lua.py` YAML 迁移
- [x] CI（validate + pytest + Android compile）
- [x] demo-game 可运行 Lua 示例

## 已完成（v0.2）

- [x] 项目结构：`studio` / `android-runtime` / `packager` / `tools` / `examples`
- [x] Android 运行时：无障碍、截屏、YAML/Lua 双引擎
- [x] 找色、NCC 找图、ML Kit OCR、ONNX YOLO
- [x] PC Studio 抓抓、打包并安装
- [x] 模拟器冒烟 `tools/run_emulator_test.py`

## 下一步

### P1 — 体验
- [x] 浮动面板在 Studio 内实时预览（叠加截图）
- [ ] OCR 测试结果点击插入 `findText`
- [ ] Shizuku 触控备选

### P2 — 性能
- [ ] OpenCV Mobile NDK 加速大模板
- [ ] YOLO NNAPI delegate
- [ ] Lua 协程桥接（减少 runBlocking）

### P3 — 生态
- [ ] script-control-center 远程调度 APK 脚本
- [ ] 脚本热更新（仅 assets）
- [ ] 定时任务 / 开机启动
