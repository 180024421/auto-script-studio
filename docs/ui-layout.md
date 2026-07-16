# 浮动面板 ui/layout.json（v3）

按键精灵式自定义控制面板：全局水平 **界面标签** + 每页自由布局控件。打包进 APK 后：

- **主页面（MainActivity）**：渲染 `screens[]` 表单（`panel.title` 为蓝色标题栏）+ 固定外壳（设置 / 启停 / 运行日志）
- **悬浮窗（OverlayService）**：悬浮球 ▶/■ 启停（后台运行），不含完整表单

PC Studio「浮动面板」页：**手机画布 WYSIWYG** + 可选 **交互预览** / **APK 外壳预览**；「抓抓」页可叠加截图对照。

## 展示模式 `panel.display_mode`

| 值 | APK 主页面 | 悬浮窗 |
|----|-----------|--------|
| `host`（推荐默认） | layout 表单 + 设置/启停/日志 | 悬浮球 ▶/■ 启停 |
| `form` | 同 host（兼容旧工程） | 同 host |
| `minimal` | 有 screens 时仍显示表单 | 悬浮球 + 可选展开控制条 |

## 数据模型（v3）

```json
{
  "version": 3,
  "enabled": true,
  "panel": {
    "layout_mode": "free",
    "design_width": 720,
    "design_height": 1280,
    "active_screen": 0,
    "title": "脚本助手",
    "start_confirm_collapse": true
  },
  "screens": [
    { "title": "标签页1", "widgets": [{ "id": "hint", "type": "label", "text": "…", "layout_x": 24, "layout_y": 24, "layout_w": 672, "layout_h": 48 }] }
  ],
  "widgets": [
    { "id": "start", "type": "start_script", "label": "开始", "layout_x": 24, "layout_y": 4, "layout_w": 672, "layout_h": 52 }
  ]
}
```

- `screens[]`：各界面（原嵌套 `tabs` 已迁移为此结构）
- `widgets[]`（根级）：仅 chrome 动作按钮（**开始**等），不再混放表单控件；**自由布局不再放停止按钮**
- `layout_mode: "free"`：控件使用 `layout_x/y/w/h`（设计坐标，默认 720×1280）
- `layout_mode: "grid"`：沿用 `panel.columns` + 控件 `width` 占列

JSON Schema：`schemas/layout.schema.json`

## 产品能力对照

| 能力 | 状态 | 说明 |
|------|------|------|
| 多界面标签 + 每页自由布局 | ✅ | `screens[]` + `active_screen` |
| 布局向导（现代 free） | ✅ | 登录 / 运行 / 完整 / 提醒 / 双列；推荐入口 |
| 半自动流式排版 | ✅ | 添加自动落行；流式重排 / 左对齐 / 统一宽度 / 两列并排 |
| 主题预设 | ✅ | `light` 商务蓝 / `green` 清爽绿 / `gray` 中性灰 / `dark` |
| 分区卡片 `section` | ✅ | 圆角底 + 标题，叠在表单下方营造产品页层次 |
| 表单控件（含 switch/时间范围/滑条等） | ✅ | 见下表 |
| PC 拖动/缩放/吸附网格 | ✅ | 8px 网格；方向键微调；Delete 删除；Ctrl+D 复制 |
| 撤销/重做、复制/粘贴 | ✅ | 顶栏与画布右键 |
| 界面导入/导出 | ✅ | 单 screen JSON |
| 保存前校验 | ✅ | ID 唯一、坐标/尺寸 |
| 脚本读取控件值 | ✅ | `panel.*` Lua API |
| 实机设计模式（网格） | ✅ | 长按标题栏 |
| 实机 free 布局拖动保存 | ✅ | form 悬浮窗 / host 主页均支持；长按标题栏进设计模式 |
| 实机 layout 覆盖拉取 | ✅ | Studio「拉取实机布局」→ merge 工程 |
| PC 控件内容随框体缩放 | ✅ | 拖动缩放控件时字号/行高自适应 |
| 设计分辨率变更 | ✅ | 控件 layout 坐标等比缩放 |
| 旧版 grid「模板库」 | ⚠️ | 更多操作 → 旧版模板（不推荐） |
| 双指捏合缩放面板 | ✅ | 悬浮窗标题栏双指捏合 0.7–1.4 |
| `button_style` / `image`·`hero` | ✅ | 主/次/危险按钮；静态图与轻量 banner |

## 控件类型

### 表单控件

| type | 说明 | 主要字段 |
|------|------|----------|
| `text` | 文字框（提示/说明，只读） | `text`, `text_style`（title/hint/normal）, `align`, `layout_*` |
| `label` | 标签/说明（兼容旧版） | `text`, `layout_*` |
| `section` | 分区卡片（圆角背景+标题） | `text`（标题）, `layout_*`；拖动时几何包含的表单会随迁 |
| `image` | 静态图 | `src`（相对工程路径）, `layout_*` |
| `hero` | 轻量 banner | `src`, `text`（叠加文案）, `layout_*` |
| `input` | 输入框 | `label`, `placeholder`, `default`, `id`, `required`, `min`, `max` |
| `select` | 下拉 | `label`, `options[]`, `default`, `id`；`options_source: launchable_apps` 时自动填充已安装应用（存包名） |
| `radio` | 单选 | `label`, `options[]`, `default`, `id` |
| `multiselect` | 多选 | `label`, `options[]`, `default`(逗号分隔), `id` |
| `switch` | 开关 | `label`, `default`（true/false）, `id` |
| `time_range` | 时间范围 | `label`, `default_start`, `default_end`, `id` |
| `slider` | 滑条 | `label`, `min`, `max`, `default`, `id` |
| `stepper` | 步进器 | `label`, `min`, `max`, `default`, `id` |
| `textarea` | 多行文本 | `label`, `placeholder`, `rows`, `default`, `id` |
| `divider` | 分隔线 | `text`（可选） |

### 动作按钮（chrome / 界面内）

| type | 说明 |
|------|------|
| `start_script` | 启动主脚本（见两步启动）；实机显示 **▶** 图标 |
| `stop_script` | 仅旧版 grid 布局；**free 模式已移除**，改由悬浮球 **■** 停止 |
| `tap` / `swipe` / `long_press` | 坐标动作 |
| `lua` | Lua 片段 |
| `collapse` | 收起面板（**▼** 图标） |

动作按钮可选字段：`button_style`=`primary`|`secondary`|`danger`（次要=描边），以及 `color` 覆盖色。

旧版嵌套 `tabs` 控件会在加载时自动迁移为 `screens[]`。

## 默认开始 / 停止（两步启动 + 悬浮球）

`panel.start_confirm_collapse` 默认为 `true`：

1. 用户填好参数，点底部 **▶ 开始**
2. 面板收起为悬浮球（不立即跑脚本）
3. 点悬浮球 **▶**（绿色）→ 执行 `main.lua`，面板保持收起
4. 脚本运行中悬浮球变为 **■**（红色），点击即停止；停止后若已收起可自动展开面板

自由布局（`layout_mode: free`）加载时会自动去掉 chrome 里的 `stop_script`；停止统一走悬浮球。

## Lua API（`panel` 全局表）

| 方法 | 说明 |
|------|------|
| `panel.get(id)` | 读取控件当前值 |
| `panel.set(id, value)` | 写入控件值 |
| `panel.is(id, expected)` | 是否等于某值 |
| `panel.has(id, option)` | 多选是否含某项 |
| `panel.isOn(id)` | 开关是否为开 |
| `panel.getTimeRange(id)` | 返回 `start, end` 两个时间字符串 |
| `panel.values()` | 全部 id→value |
| `panel.snapshot()` | 同 `values()`，语义化别名 |
| `panel.watch(id, fn)` | 值变化回调 |
| `panel.unwatch(id [, fn])` | 取消监听 |

```lua
if panel.isOn("notify") then bot.log("通知开") end
local s, e = panel.getTimeRange("work_hours")
bot.log(s .. " - " .. e)
```

## PC Studio 编辑器

### 手机自由布局

- 顶栏 **布局 → 手机自由**
- 左侧：界面标签编辑、控件列表、撤销/重做、导入导出界面
- 中间：**720×1280** 画布 — 拖动、右下角缩放、标签切换界面
- 勾选 **交互预览**：控件区内可操作表单，顶部色条仍可拖动
- 画布 **右键**：添加控件 / 复制 / 删除
- 快捷键：`Delete` 删除；`Ctrl+D` 复制；方向键 1px 移动（Shift+方向 10px）

### 网格布局

- `panel.columns`（1–3）+ 控件 `width`
- 勾选 **网格设计**：拖灰条排序、右缘拉宽

## 面板字段

| 字段 | 说明 |
|------|------|
| `width_dp` | 面板宽度（dp，网格/free 均有效） |
| `design_width` / `design_height` | 自由布局设计分辨率 |
| `active_screen` | 当前界面索引 |
| `start_x` / `start_y` | 屏幕像素位置 |
| `theme` | `light` / `dark` |
| `allow_design` | 实机是否可进设计模式 |
| `start_confirm_collapse` | 开始是否先收球再确认 |

## 权限与焦点

含输入类控件时面板可获焦点；**拖拽面板请按住标题栏**。
