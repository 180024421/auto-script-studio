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
- **host** 模式：表单在 MainActivity；长按标题可进设计模式（与悬浮窗一致），覆盖写入 `layout-overrides/`
- 拖动 **section** 时，几何中心落在卡片内的控件会一并平移（`LayoutEditorOps.offsetSectionContents`）
- 设备 design 覆盖存于 `layout-overrides/`，Studio「拉取实机布局」可 merge 回工程
- 自由布局控件内容随 `panel.width_dp` / 面板宽度与 `design_width` 比例缩放（Android `uiScale`）
- 悬浮窗标题栏支持双指捏合缩放（0.7–1.4）；PC 用预览宽度档位模拟机型密度

## 对齐字段

| 字段 | 说明 |
|------|------|
| `button_style` | `primary` / `secondary`（描边）/ `danger` |
| `text_style` | `title` / `hint` / `normal` |
| `src` | `image` / `hero` 相对工程路径 |
| `type=section` | 分区卡；几何包含随迁 |

## 变更检查

- 改 `panel_widget_factory.py` → 评估 Android `OverlayPanelBuilder.kt`
- 改 `layout.json` schema → 同步 `LayoutConfig.kt` 与 `docs/ui-layout.md`
