# 扫城 YOLO 模型

```powershell
cd D:\xiangmu\auto-script-studio
python tools/export_yolo_onnx.py --pt D:\yolo\runs\merge_ft_20260616_214108\weights\best.pt --out examples/saocheng-game/models/ui --imgsz 640
```

生成 `ui.onnx` + `ui.labels`，打包时自动打进 APK。
