# 教程 01：找色入门

## 目标

在模拟器上用 `bot.findColor` 定位颜色并点击。

## 步骤

1. 打开 `examples/demo-game`
2. 抓抓页截图，用**取色**记下目标 RGB（如按钮灰色 `40,40,40`）
3. 在 `main.lua` 中设置 `bot.findColor(r,g,b, { tol=30 })`
4. 脚本页 **PC 运行** 验证
5. 命中后 `bot.tap(x,y)`

## 参数提示

| 参数 | 含义 |
|------|------|
| `tol` | 颜色容差，越大越宽松 |
| `timeout` | 等待秒数 |
| `optional` | 为 true 时找不到不抛错 |

## 下一步

[教程 02：浮动面板](tutorials/02-panel-form.md)
