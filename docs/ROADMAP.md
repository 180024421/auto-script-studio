# 开发路线图

## 已完成（v0.4）

- [x] 截屏与点击分离（`input_mode` + `screenshot_mode`）
- [x] YOLO 性能预设、`yolo_imgsz` / `yolo_nnapi` / 帧缓存 TTL
- [x] APK 设置页：授权、热更新、WiFi/夜间策略、性能统计
- [x] jiaoben 脚本发版管理（按项目、changelog、回滚/禁用、设备版本上报）
- [x] Studio 一键发版、打包预检、性能预设、识字点击插入脚本
- [x] Shizuku 触控、脚本热更新、定时/开机启动
- [x] Lua 为主 + 浮动面板 + PC Studio 全链路

## 已完成（v0.3）

- [x] Lua 为主脚本语言 + `lib/` require 模块
- [x] 按键精灵式浮动面板（`ui/layout.json` + `OverlayService`）
- [x] PC Studio 浮动面板布局编辑器
- [x] 截屏帧缓存、脚本取消令牌
- [x] 打包器增强校验 + Release keystore CLI
- [x] demo-game 可运行 Lua 示例

## 下一步

### P1 — 体验
- [x] 实机 free 布局拖动保存（APK 设计模式：`FreeOverlayDesignFrame` + `LayoutEditorOps.setWidgetRect`）
- [x] Studio 展示模式 UI、布局修复手动化、PC/Android 坐标与表单行对齐
- [ ] SCC Web UI 集成 jiaoben 发版按钮

### P2 — 性能
- [ ] OpenCV Mobile NDK 加速大模板（可选）
- [ ] Lua 协程桥接（减少 runBlocking）

### P3 — 生态
- [ ] script-control-center 远程调度 + 目标脚本版本
- [ ] 微调数据自动回流（lmstudio-finetune）
