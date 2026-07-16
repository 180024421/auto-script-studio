# ASS 浮动面板：会话内存搜值锁定

日期：2026-07-16  
状态：已确认实现（名称自填 + 类型 + 三固定槽位）
仓库：auto-script-studio

## 目标

在浮动面板提供固定槽位（可自填名称），对每个槽位：

1. 选择类型（int32 / float / int64）  
2. 输入当前值 → 初搜  
3. 游戏内变数后输入新值 → 过滤锁定  
4. 本局脚本用锁定地址读数  
5. 下次启动重新搜（会话缓存，不持久化为永久基址）

## 范围

- 浮动面板：3 个固定槽位，名称用户自填  
- android-runtime：`MemoryReader` 搜值/精炼 + 会话地址表  
- Lua：`mem.search` / `mem.refine` / `mem.cache` / `mem.read_cached` / `mem.clear`  
- 示例 layout + lib 片段  
- 不改：Frida、写内存、永久 so 基址、PC Studio 真扫描（可 stub）

## 面板槽位字段（每个）

| 控件 id 模式 | 类型 | 含义 |
|--------------|------|------|
| `mem_name_{i}` | input | 用户命名，如 gold |
| `mem_type_{i}` | select | int32 / float / int64 |
| `mem_v1_{i}` | input | 当前值 |
| `mem_v2_{i}` | input | 变化后值 |
| `mem_status_{i}` | text | 状态：未搜/候选N/已锁定 |
| 按钮初搜 / 过滤锁定 / 清除 | lua | 调 snippet |

`i` = 1..3

## 运行时 API

```lua
mem.search(key, value, type?)      -- 返回候选数；key=名称
mem.refine(key, newValue)          -- 在候选上过滤并锁定唯一/首选
mem.read_cached(key, type?)        -- 读锁定地址
mem.get_address(key)               -- 返回地址或 nil
mem.clear(key?)                    -- 清一个或全部
mem.candidates(key)                -- 候选数量
```

扫描：`/proc/pid/maps` 可写匿名区 + `/proc/pid/mem` 按类型匹配；需 root 与 `bot.set_memory_pid`。

## 验收

1. 面板填名称 gold、类型 int32、值搜→变→锁定成功  
2. `mem.read_cached("gold")` 随游戏变化  
3. 重启脚本后需重新锁定  
4. 三个槽位互不干扰  
