# bot.* / panel.* 契约单源设计

日期：2026-09-22 · 状态：已获用户逐段确认，待实施
范围：契约单源三个子项目中的第一个（`bot.*` + `panel.*`）。`layout.json` 单源、saocheng 架构回归、行为缺陷清单各自另立。

## 问题

PC 联调（`studio/runtime/lua_runner.py` + `pc_bot.py`）与设备 APK（`android-runtime/.../lua/LuaBindings.kt` + `AutoScriptBridge.kt`）各自手写同一套 `bot.*` API。函数名当前恰好对齐（bot 27 个、panel 10 个），但**签名、opts 选项键、返回形状没有任何一处是机器可读的单一来源**：

- 唯一防线是 `lua_runner.py` 里六个 `raise RuntimeError("… 仅 APK 可用")`，只覆盖 26 个共享函数中的 6 个、且只保证「PC 有对应键」，不保证语义。
- 已实测漂移：`step`、`mask_decode_max`、`manifest` 只在设备端生效；`bot.findMultiColor` 的 `tap_dx`/`tap_dy` 只在设备端读；`model`/`model_path` 两端都读但 PC 不读 `manifest`。
- 返回形状两端不同：设备 `yoloDetect`/`recognizeText`/`recognizeDigits` 返回真 Lua 表，PC 返回 Python list/dict —— 在 lupa 里是 POBJECT userdata，脚本侧 `#dets`/`ipairs`/`pairs` 全部失效，索引从 0 开始；`panel.getTimeRange` 设备返回 `{start,end}` 表、PC 返回两个值。
- 工具箱 `bot_command_catalog.py`（445 行手写）与 `docs/LUA.md` 教的是错的键名：`waitStable` 写成 `stable_frames`/`diff_threshold`（真名 `stable_samples`/`max_mean_diff`）、`yoloDetect` 写 `limit`（该函数不读）。
- `LuaBindings.kt:537` 把 `has_mask` 写成 `1`/`0`，而 PC 的 `normalize_detection` 给的是布尔。

目标：**契约成为唯一来源，两端与文档都必须与它对上，且对不上时 CI 直接失败。**

## 决策记录（用户逐条选定）

1. 首个子项目选 `bot.*` 契约单源，不选 `layout.json`（涉及 ~40 个 Studio 文件，爆炸半径最大）。
2. 严格度：**修 PC 行为向设备看齐**；PC 侧未知选项键**只告警不 raise**。
3. 载体：**A 方案** —— `contract/lua_api.json` 为源，PC 端消费（驱动注册 + 返回 marshal）；Kotlin 侧**不引入代码生成**，由 CI 解析 Kotlin 源码做对账。
4. 覆盖：`bot.*` + `panel.*`；`mem.*` 本轮不入契约。
5. 工具箱 `bot_command_catalog.py` 与 `docs/LUA.md` **纳入 CI 校验，但不生成**。

## §1 契约表示

新文件 `contract/lua_api.json`，仓库根级（与 `schemas/`、`docs/` 同级；Studio 以源码树运行，无冻结打包规格，故按仓库相对路径解析即可）。

```json
{
  "version": 1,
  "api": {
    "bot.findImage": {
      "pc": "find_image",
      "availability": ["pc", "apk"],
      "args": [
        { "name": "path", "type": "string" },
        { "name": "opts", "type": "table" }
      ],
      "opts": {
        "threshold": { "type": "number", "default": 0.9 },
        "timeout":   { "type": "number", "default": 20 },
        "step":      { "type": "int", "default": 2, "sides": ["apk"] },
        "roi":       { "type": "roi" },
        "optional":  { "type": "bool", "default": false }
      },
      "returns": { "kind": "tuple", "items": ["int", "int"] }
    }
  }
}
```

约定：

- `args` 末位若为 `type: "table"` 即 opts 表；`opts` 只对这张表生效。
- `opts.<key>.sides` **省略 = 两端都支持**；显式列出 = 仅这些端支持（这就是「已知且允许」的单侧键记录处）。
- `returns.kind` 词表：`none` / `bool` / `number` / `string` / `tuple`（配 `items`）/ `table` / `array_of`（配 `item_fields`）/ `table_or_nil`。
- `availability` ⊆ `{pc, apk}`；`pc` 为 `PcBot`/`PanelState` 上的方法名；`internal: true` 标记不进文档/工具箱的内部名（如 `bot.__logRaw`）。
- `pc_missing: "nil" | "raise"`（仅对 `availability` 不含 `pc` 的名字有效）：`"nil"` 保留 `if bot.runSaocheng then` 的优雅降级惯例，`"raise"` 保留中文报错桩。本轮 `runSaocheng` = nil，其余 6 个设备专有名字 = raise。
- 默认值只在契约与设备端**都是字面量**时比对；设备端默认来自配置（如 `mask_decode_max` 的 `config.perf.yoloMaxMaskDecode`）时跳过。

## §2 PC 端消费

新文件 `studio/runtime/lua_contract.py`：`load()`（带缓存）、结构自校验、`lookup(name)`、`marshal(lua, value, spec)`（递归 `lua.table_from`，把 list → 1 基数组表、dict → 哈希表）。

`install_bot(lua, bot)` 改为遍历契约生成绑定：入参按 `args` 逐项强转、`opts` 表转 dict 后做未知键告警、返回值按 `returns` marshal；`availability` 不含 `pc` 的名字按 `pc_missing` 决定不注册或注册报错桩。

**实施后 override 表收缩到只剩两项**（`panel.watch` / `panel.unwatch`，理由：Lua 函数代理每次身份不同，须用 `tostring(fn)` 建身份表才能去重与解绑）。设计阶段列的另外四项被通用 binder 吸收了：`delay` 靠契约的 `pc: "delay_seconds"` 映射；`swipe`/`longPress` 的可选末位参数缺省时直接落到 `PcBot` 自己的 300/500 默认值；`trace`/`open_app` 走 `args` 声明的 `string` 强转；`recognize_digits` 的 `hasattr` 探测换成通用的「缺方法即报 `需要 Studio 实现 PcBot.<method>`」。override 表里出现契约没有的名字会直接 raise，防止它悄悄变成第二份真源。

行为变更（决策 2「向设备看齐」的具体内容）：

- `yoloDetect` / `recognizeText` / `recognizeDigits` / `panel.values` / `panel.snapshot` 在 PC 返回**真 Lua 表**。已披露代价：PC 上 `dets[0]` 必须改 `dets[1]`。
- `panel.getTimeRange` 返回 `{start=…, end=…}`，不再返回两个值。
- opts 未知键：按 (函数, 键) 去重**告警一次**，不 raise；`sides: ["apk"]` 的键在 PC 传入时同样只告警。
- PC `normalize_detection` 补 `left`/`top`/`width`/`height` 四字段与设备对齐；Kotlin `LuaBindings.kt` 的 `has_mask` 改为真布尔（本轮唯一一处 Kotlin 改动）。

实施中新发现的既有缺陷（本轮一并修，均由上述 lupa 往返测试暴露）：

- `lua_values.lua_to_python()` 把 `lua_type()` 返回 `None` 当成 nil。lupa 2.x 会把 number/boolean/string **自动解包成 Python 标量**，于是 PC 侧 opts 里的 `threshold`/`click`/`timeout` 等**全部静默变成 None**，`PcBot` 一律退回默认值 —— 即 PC 联调一直没真正吃到脚本写的选项。改为「非 Lua 对象原样交回」。
- `panel.unwatch(id, fn)` 原先每次现造 `lambda v: fn(v)` 再按 `is` 比较，永远匹配不上注册时的那个闭包，即**解绑从未生效**。改由 `_CALLBACKS` 身份表持有同一包装。

本轮明确不动：PC `delay` 的取消令牌轮询、PC `trace` 的 tag 过滤 —— 登记为已知差异，不假装对齐。

## §3 设备端、PC 端与文档侧的 CI 对账

纯 Python 源码解析，落在新文件 `tools/lua_contract_check.py`，由 `tests/test_lua_contract_parity.py` 调用 → **CI 的 yml 一行不改**，`validate-and-lint` 已有的 pytest 步骤自动覆盖，本地 `run-tests.cmd` 信号一致。

1. **名字集合**：从 `LuaBindings.kt` 抽 `bot.set("name", …)` / `panel.set("name", …)`，与契约中 `availability` 含 `apk` 的名字双向比对（`mem.*` 本轮排除）。
2. **选项键归属**：`XxxFn` 类体内恰好一次 `bridge.<同名方法>(`；据此在 `AutoScriptBridge.kt` 里大括号配平扫出该 `fun` 体，收集 `LuaOpts.*(opts, "键"`。**两条必要扩展**：`FindMultiColorFn` 的 `points` 在 Fn 类里直读，故 Fn 类体一起扫；`resolveModel`/`resolveMaskDecodeMax`/`resolveUseMaskCenter`/`resolveDigitModel` 是私有 helper，凡签名含 `opts: Map<String` 者递归并入。解析不出来（重命名、一个 Fn 里两次 `bridge.` 调用）时必须 **attribution failed 直接 raise**，禁止静默通过 —— 这是本方案唯一的真实维护成本。
3. **检测行字段**：契约 `yoloDetect.item_fields` 与 `detectionsToLua` 里 `t.set("k", …)` 的键集合双向比对；PC 侧由 lupa 往返测试用 `normalize_detection` 的实际键断言。
4. **工具箱与文档**：`bot_command_catalog.py` 每条 `BotCommand` 的 `api`/`id` 名字须在契约中存在，`syntax` 形参个数须与 `args` 一致，`snippet` 里字面写出的 opts 键须是该函数合法键；`studio/services/lua_snippets.py` 生成的片段用同一校验器；`docs/LUA.md` 只校到名字与元数（`| \`bot.foo(...)\` |` 表格行 + 能力矩阵），要求文档提到的名字都在契约里、契约里每个非 internal 名字都在文档出现过。
5. **PC 端选项键**（`check_pc`）：解析 `studio/runtime/pc_bot.py` 与 `panel_state.py` 的方法体。契约里 `availability` 含 `pc` 的名字，其 `pc` 方法必须存在；声明支持 `pc` 的 opts 键必须在方法体（含并进来的 `self._resolve_*` 一层 helper）里被读到；反向只查**直接方法体**读到的键是否声明过，避免把 helper 里读 `project.json` 的配置键误报。这一路是「契约删掉一条 `sides` 就变红」的唯一机器证据 —— 设备端对 `step`/`mask_decode_max` 这类键本来就读得到，只有 PC 侧会说谎。解析不到函数体同样抛 `ParityError`。

代价与处理：**新增的对账项首跑必红**（正是为了抓出 §问题 列出的存量错误）。在同一轮改动里按契约把 catalog / snippets / LUA.md 改对，不留 xfail。

## §4 测试与验收

- `tests/test_lua_contract.py` —— 契约加载与自校验：名字前缀、`availability`/`sides`/`returns.kind`/参数类型词表、`pc_missing` 只对设备专有名字有效；schema 违规必须报错而不是宽容。
- `tests/test_lua_contract_runtime.py` —— lupa 往返（决定性验收）：`findImage` 命中返回两个整数、未命中 `nil`；`yoloDetect` 在 Lua 侧 `#dets == n`、`ipairs` 可用、`dets[1].class_name` 可读、`dets[1].has_mask` 是 boolean、`pairs` 能遍历；`recognizeDigits().chars[1].label`；`panel.getTimeRange("t")` 返回 `.start`/`.end`；未知键 `stable_frames` 产生一次告警且不 raise；`if bot.runSaocheng then` 为 false 而 `bot.listApps()` 抛中文错误。
- `tests/test_lua_contract_parity.py` —— §3 的五项对账（`all_issues`），外加四条**变异测试**证明守卫不空转：删掉 `bot.findImage.opts.step` 的 `sides`、凭空加一个 opts 键、漏声明 `waitStable.stable_samples`、写错 `pc` 方法名，每条都必须让 `all_issues` 变红；设备端改名一条走 `check_device`，Kotlin 指向不存在的类一条必须抛 `ParityError`。
- 回归：`run-tests.cmd` 全绿（本轮 210 项，其中契约相关 75 项）；ruff 干净；`python -m studio.runtime.lua_runner <工程>` 冒烟验证注册与 panel 往返（无设备时只到截屏那一步失败为止）。
- 验收判据（已自动化，不再依赖人工抽查）：`tests/test_lua_contract_parity.py` 断言 `lua_runner.py` 里不再出现按函数名手写的 `raise RuntimeError("bot./panel.…")` 桩，且「仅 APK 可用」文案在该文件里恰好出现一次（`pc_error` 缺失时的兜底）。

## §5 边界（本轮不做）

`layout.json` 契约单源（两套 schema 文件仍是死代码，另立子项目）；`mem.*` 入契约；Gradle/LuaJ 侧代码生成；设备端补 `bot.reelHold`/`nowMs`/`screenSize`（`examples/lingzhu-fishing` 调用了三端都不存在的函数，属行为缺陷清单）；saocheng 状态机移出 APK；巨型文件拆分；生产服务器 IP 与 `--ks-pass` 明文口令两项安全隐患。
