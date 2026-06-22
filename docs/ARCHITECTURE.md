# 项目定位与分工

## 两个项目各管什么

| 项目 | 平台 | 脚本跑在哪 | 语言 |
|------|------|------------|------|
| **auto-script-studio** | **Android** | 打包 APK，在设备/云手机/模拟器上跑 | **Lua**（`main.lua`） |
| **adb-ide** | **Windows** | PC 本机（窗口截图、UIA 控件） | Python + 可选 YAML |

```
auto-script-studio                adb-ide
─────────────────                 ───────
PC Studio（抓抓/编辑/打包）        PC IDE（抓抓/编辑/运行）
       │                                 │
       ▼                                 ▼
  独立 APK + Lua                    本机 Python
       │                                 │
       ▼                                 ▼
 云手机 / 模拟器 / 真机              Windows 窗口 / 游戏
```

**不要混用职责：** Android 自动化以 `auto-script-studio` 为准；Windows 自动化以 `adb-ide` 为准。  
`auto-script-studio` 的 PC 端只负责 **开发、ADB 联调、打包**，不在 PC 上替代 APK 跑正式脚本（联调可用 `lua_runner`）。

---

## Android 输入/截屏模式（`project.json` → `runtime`）

| `input_mode` | 点击/滑动 | 截屏 | 适用场景 |
|--------------|-----------|------|----------|
| `auto`（默认） | 有 root 用 shell `input`，否则无障碍 | 有 root 用 `screencap`，否则录屏/无障碍截图 | 云手机 root、模拟器 |
| `accessibility` | 无障碍手势 | MediaProjection / API30+ 无障碍截图 | 无 root 真机 |
| `root` | `su -c input tap/swipe` | `su -c screencap` | 已 root 设备，免开无障碍 |

```json
{
  "entry": "main.lua",
  "script_language": "lua",
  "runtime": {
    "input_mode": "auto",
    "screenshot_mode": "media_projection",
    "auto_run": false
  }
}
```

- **无障碍**：用户手动在系统设置里开启本应用无障碍；雷电等模拟器可用 ADB 辅助开启（测试用）。
- **Root**：应用内检测 `su`；有 root 时 **不必开无障碍**，也 **不必授权录屏**（`input_mode: root` 或 `auto` 且检测到 root）。

---

## 脚本形态（Android）

- **唯一推荐脚本语言：Lua**（`bot.findImage` / `findColor` / `findText` / `findYolo` …）
- 打包：工程目录 → `packager` → APK（`assets/project/main.lua`）
- PC 联调：同一份 `main.lua` + `python -m studio.runtime.lua_runner`（ADB，非 APK）

YAML / Python 仅作历史兼容，新工程不要用。

---

## 与 adb-ide 的关系

| 能力 | auto-script-studio | adb-ide |
|------|-------------------|---------|
| Windows 找图/识字/YOLO | ❌ | ✅ |
| Android APK 离线跑 | ✅ | ❌（靠 PC+ADB 在线跑） |
| Lua 脚本进 APK | ✅ | ❌ |
| 可选复用 adb-ide UI | Studio 可挂载 adb-ide 抓抓界面做 Android 开发 | 主仓库 |

若已安装同级目录 `adb-ide`，`run-studio.cmd` 可打开完整抓抓 IDE +「打包 APK」菜单；**Windows 脚本请在 adb-ide 里做**。

---

## 推荐工作流（Android）

1. `auto-script-studio` 新建工程 → 编辑 `main.lua`
2. PC：`run-lua-pc.cmd` 或 Studio「PC 运行 Lua」ADB 联调
3. 打包 APK → 装到云手机/雷电
4. 设备上：`input_mode` 按环境选 `auto` / `root` / `accessibility`，运行脚本
