# 腾芝洋领主钓鱼辅助（移植中，暂不可运行）

把 PC 端 `lingzhu_pc.py`（`lingzhu_engine.py` / `lingzhu_fishing.py`）的钓鱼小游戏逻辑移植成 APK 工程：
YOLO 识别 → 圆弧量规控制器 → 连续按住收线。

> ⚠️ **当前状态：不能跑。** `main.lua` 调用了 3 个尚未实现的 `bot.*`：
> `bot.reelHold`（连续按住/抬起）、`bot.nowMs`（毫秒时钟）、`bot.screenSize`（屏幕尺寸）。
> 全仓检索确认设备端 `LuaBindings.kt`、PC 端 `pc_bot.py` 与 `docs/LUA.md` 都没有这三项，
> 运行会在第一次调用时报 `attempt to call a nil value`。
> 逻辑本身（量规控制器参数、状态迁移）可当参考实现读，跑通需要先补这几个 API 并在真机验证。

## 设计意图（读代码时对照）

- **识别与按住互不阻塞**：收线用 `bot.reelHold` 的重叠 swipe 语义（press 持续按住、release 立即抬起），
  而不是 `bot.longPress` 一次按住 —— 后者会把检测循环卡住。
- **分辨率自适应**：所有像素类常量以 720×1280 为基准（`ref_w`/`ref_h`），运行时按 `bot.screenSize()`
  缩放 pivot 偏移与像素余量，云手机分辨率不一。
- **模型**：`models/lingzhu.onnx`，类别见同目录 `.labels`；`bot.yoloDetect` 返回
  `x/y`=中心、`left/top`=左上、`width/height`、`class_name`、`confidence`。
- **量规控制器**：带鱼带中心权重、滑脱恢复、跳变抑制、弧端判定、接触冷却、收线锁、迟滞。

## 需要的环境

`project.json` → `input_mode: auto`、`screenshot_mode: media_projection`；
无障碍或 root 均可，无需 root。

## 待办（要跑通需要做的）

1. 设备端 `LuaBindings.kt` 注册 `reelHold` / `nowMs` / `screenSize`（`reelHold` 需要在
   `AutomationBackend` 上支持按下-保持-抬起的分段手势）。
2. PC 端 `studio/runtime/pc_bot.py` 同名实现，保持语义一致。
3. `docs/LUA.md` 能力矩阵与 `studio/services/bot_command_catalog.py` 补三条。
4. 真机回归后把本文件顶部的警告去掉，并加进 `examples/README.md` 的可运行列表。
