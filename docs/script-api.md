# 脚本 API（YAML 遗留）

本文定义 **YAML DSL**（遗留兼容）。**新工程请用 Lua**，见 [LUA.md](LUA.md)。  
PC Studio 与 APK 运行时共用同一套 action 语义（YAML 引擎仍可用）。

---

## 1. 工程入口

打包后运行时读取 `assets/project/`：

| 文件 | 说明 |
|------|------|
| `project.json` | 元数据 |
| `main.yaml` | 默认入口（可由 project.json.entry 指定） |
| `image/` | 模板图 |
| `models/` | YOLO ncnn（`.param` + `.bin`） |

---

## 2. 顶层结构

```yaml
includes:
  - common.yaml

defaults:
  retry: 2
  action:
    timeout: 20

yolo_model: models/ui.ncnn
yolo_conf: 0.35
yolo_roi: [0, 0, 1080, 1920]

actions:
  btn_start:
    type: template
    template: image/btn_start.png
    threshold: 0.9

flows:
  main:
    - btn_start
    - wait_confirm
```

| 字段 | 说明 |
|------|------|
| `includes` | 合并其他 yaml（actions/flows/defaults） |
| `actions` | 命名动作，flows 中引用 |
| `flows` | 流程列表，打包后默认执行 `main` |
| `yolo_model` | 默认 ncnn 模型前缀或目录名 |
| `yolo_conf` | 默认置信度 |
| `yolo_roi` | 默认 ROI `[x,y,w,h]` |

---

## 3. Action 类型

### 3.1 template — 找图并点击

```yaml
btn_fight:
  type: template
  template: image/btn_fight.png
  threshold: 0.9
  timeout: 15
  roi: [100, 200, 800, 400]
  tap_dx: 0
  tap_dy: 0
```

### 3.2 color — 找色并点击

```yaml
red_dot:
  type: color
  bgr: [0, 0, 255]    # OpenCV BGR
  tol: 12
  timeout: 10
  roi: [0, 0, 1080, 1920]
```

### 3.3 text — 识字并点击

```yaml
txt_confirm:
  type: text
  target: 确定
  match_mode: contains   # contains | exact
  timeout: 12
  min_confidence: 0.5
```

### 3.4 yolo — YOLO 检测并点击

```yaml
yolo_hand:
  type: yolo
  class_name: hand
  pick: largest          # best_conf | largest | nearest
  frac: [0.5, 0.3]       # 框内点击比例
  conf: 0.35
  model: models/hand.ncnn
```

### 3.5 yolo_swipe — YOLO 框内滑动

```yaml
swipe_up:
  type: yolo_swipe
  class_name: hand
  pick: largest
  direction: up          # up | down | left | right
  distance: 480
```

### 3.6 tap / swipe / long_press

```yaml
tap_center:
  type: tap
  x: 540
  y: 960

swipe_up:
  type: swipe
  x1: 540
  y1: 1600
  x2: 540
  y2: 400
  duration_ms: 350
```

### 3.7 gone_template — 等待模板消失

```yaml
wait_loading:
  type: gone_template
  template: image/loading.png
  timeout: 45
```

### 3.8 stable — 等待画面稳定

```yaml
wait_ready:
  type: stable
  timeout: 12
  max_mean_diff: 4.0
```

### 3.9 human_delay — 随机延迟

```yaml
pause:
  type: human_delay
  base: 0.5
  spread: 0.2
```

---

## 4. Flow 步骤类型（内联）

flows 中除 action 名外，也可内联步骤：

```yaml
flows:
  daily:
    - type: delay
      seconds: 1
    - type: wait_template
      template: image/btn.png
      threshold: 0.92
    - type: wait_click_text
      target: 确定
    - type: click_color
      bgr: [120, 80, 40]
      tol: 12
    - btn_fight          # 引用 actions
```

---

## 5. 坐标与 ROI

- 原点左上角，`(x, y)` 向右、向下
- ROI 统一 `[x, y, w, h]`
- 模板匹配返回中心点；点击可加 `tap_dx` / `tap_dy`

---

## 6. YOLO 模型格式

PC 训练导出（detect 与 seg 相同命令）：

```powershell
python tools/export_yolo_onnx.py --pt path/to/best.pt --out examples/demo-game/models/ui
```

工程内放置：

```
models/ui.onnx
models/ui.labels
```

或在 `project.json` / yaml 中指定 `default_yolo_model: models/ui.onnx`。

seg 模型额外支持 `has_mask`、`mask_center_x/y`；`pick=largest_mask`；`use_mask_center` / `runtime.yolo_auto_mask_center`。

---

## 7. 运行时能力矩阵

| 能力 | APK 运行时 | PC Studio 联调 |
|------|-----------|----------------|
| 找色 | ✅ Kotlin | ✅ OpenCV |
| 多点找色 | ✅ Kotlin | ✅ OpenCV |
| 找图 | ✅ NCC 模板匹配（多尺度） | ✅ OpenCV |
| 识字 | ✅ ML Kit 中文 | ✅ PaddleOCR（可选） |
| YOLO detect/seg | ✅ ONNX Runtime | ✅ Ultralytics（可选） |
| 等待稳定/消失 | ✅ Lua API | ✅ PC bot |
| 点击 | ✅ 无障碍 / root | ✅ ADB input |

---

## 8. 迁移到 Lua

旧 YAML 工程可用：

```powershell
python tools/yaml_to_lua.py examples/demo-game/main.yaml
```

生成 `main.lua` 后，将 `project.json` 的 `entry` 改为 `main.lua`。
