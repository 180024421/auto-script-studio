# 开发路线图

## 已完成（v0.1 骨架）

- [x] 项目结构：`studio` / `android-runtime` / `packager` / `tools` / `examples`
- [x] 脚本 DSL 文档（对齐 adb-ide `game.yaml`）
- [x] Android 运行时：无障碍点击、MediaProjection 截屏、YAML 脚本引擎
- [x] 找色（Kotlin）、找图（NCC 模板匹配，无 OpenCV）
- [x] YOLO / OCR 接口占位（Stub，待 NCNN 集成）
- [x] PC Studio 最小 UI：新建/打开工程、校验、打包
- [x] `packager_cli.py`：工程 → assets → Gradle APK
- [x] `export_yolo_ncnn.py`：pt → ncnn 导出工具

## 下一步（按优先级）

### P1 — 可运行闭环
- [ ] NCNN YOLO 推理 JNI 集成（替换 StubYoloDetector）
- [ ] 打包后在雷电/夜神模拟器实测找色/找图/点击
- [ ] ScriptRunnerService 与 MainActivity 日志联动完善

### P2 — 识字
- [ ] PP-OCR mobile NCNN 或 ML Kit 离线包（懒加载）
- [ ] Studio PC 端 OCR 调试面板（可选接 PaddleOCR）

### P3 — Studio 增强
- [ ] ADB 抓屏、ROI、取色、存模板（移植 adb-ide 抓抓）
- [ ] YAML 语法高亮编辑器
- [ ] 一键 ADB 安装调试 APK

### P4 — 体积与性能
- [ ] OpenCV Mobile NDK 替换 Kotlin NCC（大模板加速）
- [ ] 截图 buffer 池化、ROI 降采样
- [ ] Release 混淆 + 模型 INT8 默认

### P5 — 云手机
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
```

若 Gradle 下载依赖失败，已配置阿里云 Maven 镜像；也可在 Android Studio 中打开 `android-runtime` 同步。
