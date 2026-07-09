# YOLO 模型目录

本目录存放工程内 YOLO 推理资源，打包 APK 时会一并打入 `assets`。

## 文件约定

| 文件 | 说明 |
|------|------|
| `ui.onnx` | ONNX 模型（设备端 ONNX Runtime 推理，支持 detect 与 seg） |
| `ui.labels` | 类别名列表，每行一个，行号对应 class id |
| `ui.ncnn.param` / `.bin` | NCNN 导出（可选，`yolo_backend=ncnn`，运行时尚回退 ONNX） |

**detect 与 seg**：seg 在 `yoloDetect` 中返回 `has_mask`、`mask_center_x/y`；点击建议 `use_mask_center=true` 或 `runtime.yolo_auto_mask_center=true`。

## 从 adb-ide 训练导入（推荐）

```powershell
python tools/import_adb_ide_yolo.py --project examples/demo-game --run D:/yolo/runs/my_seg --imgsz 320
```

Studio → YOLO 模型 → **从 adb-ide 导入**，默认应用 `yolo_seg_fast` 预设（几十 ms 级）。

## 从 PyTorch 手动导出

```powershell
python tools/export_yolo_onnx.py --pt path/to/best.pt --out examples/demo-game/models/ui --imgsz 320
python tools/bench_yolo.py --onnx examples/demo-game/models/ui.onnx --imgsz 320
```

`runtime.perf.yolo_imgsz` 须与导出 `--imgsz` 一致。

## 性能相关配置（project.json）

```json
"perf": {
  "yolo_nnapi": true,
  "yolo_imgsz": 320,
  "yolo_seg_fast": true,
  "yolo_max_mask_decode": 1,
  "yolo_warmup": true,
  "yolo_backend": "onnx"
}
```

`pick=largest_mask` 比 `best_conf` 慢（需解码更多掩码）。

## PC Studio

脚本页 **模型** Tab：导入、从 adb-ide 导入、编辑 labels、设默认模型。
