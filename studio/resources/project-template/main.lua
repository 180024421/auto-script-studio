-- Auto Script Studio 模板脚本（打包后在 APK 内由 Lua 引擎执行）

bot.log("脚本开始")

bot.delay(1)

-- 找图示例（需 image/sample.png）
-- local x, y = bot.findImage("image/sample.png", { threshold = 0.85, timeout = 10, click = true })
-- if not x then
--   bot.log("未找到模板")
-- end

-- 找色 BGR
-- bot.findColor(128, 128, 128, { tol = 20, timeout = 8, click = true })

-- 识字
-- local tx, ty = bot.findText("确定", { timeout = 15, click = true })

-- YOLO（需 models/*.onnx）
-- local hx, hy = bot.findYolo({ class_name = "hand", model = "models/ui.onnx", conf = 0.35, pick = "largest", click = true })

bot.log("脚本完成")
