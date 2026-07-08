# PC / Android 浮动面板一致性（Layout Parity）

## 必须一致

| 项 | PC (`panel_widget_factory`) | Android (`OverlayPanelBuilder`) |
|----|------------------------------|--------------------------------|
| free 坐标 | `layout_x/y/w/h` 绝对定位 | `OverlayScreenPanelBuilder` 绝对定位 |
| 表单行 | 标签左 · 控件右 | `fieldWrap` 横向 |
| 开关 | `#PanelSwitch` 44×24 缩放 | 同主题 switch |
| host 模式 | 无 chrome 按钮区 | `includeChrome=false` |

## 已知差异（文档化）

- PC 预览为 Qt 控件，Android 为原生 View，像素级可能有 1–2dp 偏差
- grid 模式实机设计模式仅支持排序/列宽，free 模式支持拖动坐标（设计模式）

## 变更检查

- 改 `panel_widget_factory.py` → 评估 Android `OverlayPanelBuilder.kt`
- 改 `layout.json` schema → 同步 `LayoutConfig.kt` 与 `docs/ui-layout.md`
