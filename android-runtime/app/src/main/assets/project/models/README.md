# YOLO 模型目录

本目录存放工程内 YOLO 推理资源，打包 APK 时会一并打入 `assets`。

## 文件约定

| 文件 | 说明 |
|------|------|
| `ui.onnx` | ONNX 模型（设备端 NCNN/ONNX Runtime 推理） |
| `ui.labels` | 类别名列表，每行一个，行号对应 class id |

示例 `ui.labels` 已提供；`ui.onnx` 需自行训练导出后放入。

## 从 PyTorch 导出

```powershell
python tools/export_yolo_onnx.py --pt path/to/best.pt --out examples/demo-game/models/ui
```

会生成 `ui.onnx`；请同时维护 `ui.labels` 与训练类别一致。

## PC Studio

脚本页右侧 **模型** Tab：导入 `.onnx`、编辑 `.labels`、设默认模型。
