# 开发路线图

## 已完成（v0.2）

- [x] 项目结构：`studio` / `android-runtime` / `packager` / `tools` / `examples`
- [x] 脚本 DSL 文档（对齐 adb-ide `game.yaml`）
- [x] Android 运行时：无障碍点击、MediaProjection 截屏、YAML 脚本引擎
- [x] 找色（Kotlin）、找图（NCC 模板匹配，无 OpenCV）
- [x] **ML Kit 中文 OCR**（离线，manifest 打入 `ocr_chinese`）
- [x] **ONNX Runtime YOLO**（`models/*.onnx` + `.labels`）
- [x] PC Studio：新建/打开工程、校验、打包、**打包并安装**
- [x] PC **抓抓**：ADB 截图、取色、ROI 模板、识字/YOLO 测试、插入 YAML
- [x] `packager_cli.py`：工程 → assets → Gradle APK
- [x] `export_yolo_onnx.py` / `export_yolo_ncnn.py` 模型导出
- [x] **模拟器冒烟** `tools/run_emulator_test.py`（LDPlayer）
- [x] 测试模式：`auto_run` + `screenshot_mode: accessibility`（免录屏授权）
- [x] ADB 开启无障碍 + logcat 验证脚本执行

## 下一步（按优先级）

### P1 — 真机/云手机闭环
- [ ] 真机 MediaProjection 授权流程 UX 优化
- [ ] YOLO 端到端：导出 ONNX → 工程 models/ → APK 实测
- [ ] OCR 找字 YAML 在设备上回归

### P2 — Studio 增强
- [ ] YAML 语法高亮编辑器
- [ ] 抓抓页 OCR 命中一键插入「找字」YAML
- [ ] 设备列表选择（多开模拟器）

### P3 — 体积与性能
- [ ] OpenCV Mobile NDK 替换 Kotlin NCC（大模板加速）
- [ ] 截图 buffer 池化、ROI 降采样
- [ ] Release 混淆 + 模型 INT8 默认

### P4 — 云手机
- [ ] 前台保活策略
- [ ] Shizuku 触控备选
- [ ] 多 flow 选择、定时任务

## 构建说明

```powershell
# 1. 配置 SDK（复制并修改路径）
copy android-runtime\local.properties.example android-runtime\local.properties

# 2. 编译运行时
cd android-runtime
.\gradlew.bat :app:assembleDebug

# 3. 打包示例工程
cd ..
python -m packager.packager_cli build examples/demo-game -o dist/demo-game.apk

# 4. 模拟器全自动冒烟（需 LDPlayer + ADB）
python tools/run_emulator_test.py
```

若 Gradle 下载依赖失败，已配置阿里云 Maven 镜像；也可在 Android Studio 中打开 `android-runtime` 同步。

## 测试配置（project.json runtime）

| 字段 | 说明 |
|------|------|
| `auto_run` | 无障碍就绪后自动启动脚本（模拟器测试） |
| `screenshot_mode` | `media_projection`（默认）或 `accessibility`（API 30+ 免录屏） |
