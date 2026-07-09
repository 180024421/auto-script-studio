# 常见问题

## Studio 打不开 / 缺依赖

```powershell
.\setup-studio.cmd
.\start.cmd
```

## adb devices 为空

- 模拟器是否已启动
- 是否安装 platform-tools 并加入 PATH
- 多开时尝试 `adb connect 127.0.0.1:5555`（端口以模拟器为准）

## 打包 Gradle 失败

见 [pack-guide.md](pack-guide.md)：JDK 17、`ANDROID_HOME`、`local.properties`。

## 无障碍 / 悬浮窗

APK 首次运行需在系统设置中手动开启，见打包指南「安装后权限」。

## adb-ide 训练的 seg 如何在 APK 里用（几十 ms）

1. **一键导入**（推荐）：Studio → YOLO 模型 → **从 adb-ide 导入**，选 `runs/xxx/weights/best.pt` 或 run 目录；默认按 **imgsz=320** 导出 ONNX 并应用 `yolo_seg_fast` 预设。
2. **命令行**：
   ```powershell
   python tools/import_adb_ide_yolo.py --project examples/demo-game --run D:/yolo/runs/my_seg --imgsz 320
   ```
3. adb-ide 训练常用 **640**，移动端须重新导出为 **320**（与 `runtime.perf.yolo_imgsz` 一致）；精度不够可试 416。
4. seg 点击：`runtime.yolo_auto_mask_center: true` 或 `bot.findYolo({ use_mask_center = true })`。
5. 性能项（`project.json` → `runtime.perf`）：
   - `yolo_nnapi: true`（失败自动回退 CPU）
   - `yolo_seg_fast: true` + `yolo_max_mask_decode: 1`（仅解码 Top1 掩码）
   - `yolo_warmup: true`（启动预热）
6. 目标耗时：**nano/s 模型 + 320 + NNAPI** 通常 **20–80ms/帧**（视机型与 ROI 而定）；`pick=largest_mask` 会解码更多掩码，略慢。

## YOLO seg 打包后点击不准

1. 确认导出的是 seg 模型：`python tools/export_yolo_onnx.py --pt best-seg.pt --out models/ui`
2. 脚本使用 `bot.findYolo({ use_mask_center = true })` 或 `project.json` 设 `runtime.yolo_auto_mask_center: true`
3. `runtime.perf.yolo_imgsz` 须与导出 `--imgsz` 一致（默认 320）
4. PC 抓抓页勾选「点击掩码质心」可对比框中心（橙十字）与掩码质心（绿十字）

## YOLO 模型过大 / 打包警告

打包预检会对超过 80MB 的 `.onnx` 给出警告。可换更小 backbone 或 INT8 量化后再导出。

## 定制开发

见 [services.md](services.md)。
