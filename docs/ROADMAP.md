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
- [x] Studio seg：use_mask_center UI、掩码质心可视化、训练样本导出
- [x] 动作录制 → Lua、设备 Profile、YOLO 模型类型展示
- [x] adb-ide 导入桥接、多点找色/多尺度找图 UI、指令工具箱补全
- [x] 训练样本 seg 格式 + dataset/data.yaml
- [ ] SCC Web UI 集成 jiaoben 发版按钮
- [ ] Android 双指捏合缩放面板

### P2 — 性能
- [x] YOLO 预热、seg 掩码解码优化、NNAPI 失败回退 CPU
- [x] LuaBridgeRunner 协程桥接（减少裸 runBlocking）
- [x] YOLO 分项耗时（截屏 vs 纯推理）、bench_yolo.py
- [x] NCNN 导出 + 运行占位（回退 ONNX）
- [ ] OpenCV Mobile NDK 加速大模板（可选）

### P3 — 生态
- [ ] script-control-center 远程调度 + 目标脚本版本
- [ ] 微调数据自动回流（lmstudio-finetune）
