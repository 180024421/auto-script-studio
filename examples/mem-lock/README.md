# 内存会话锁定示例

浮动面板 3 个槽位，**名称自填**，类型可选 `int32` / `float` / `int64`。

## 流程

1. **目标应用**下拉选择游戏（只需选一次，会记住；新装应用可点「刷新」）
2. 打开游戏  
3. 槽位填写名称（如 `gold`）、类型、当前画面值 → **初搜**  
4. 游戏内让数值变化，填新值 → **过滤锁定**  
5. 点 **开始读数循环**（`main.lua` 按锁定地址循环 `mem.read_cached`）  
6. 下次启动脚本需重新搜锁定（会话缓存，不跨进程永久保存）

## 需要

- Root（读 `/proc/<pid>/mem`）  
- 目标为「跟着界面变」的显示值即可（只读场景）

## 面板字段

| id | 说明 |
|----|------|
| `game_pkg` | 下拉选应用，存包名，`options_source: launchable_apps` |
| `mem_name_*` | 自填名称，作为 `mem.search` 的 key |
| `mem_type_*` | int32 / float / int64 |

```powershell
python -m packager.packager_cli build examples/mem-lock -o dist/mem-lock.apk
```
