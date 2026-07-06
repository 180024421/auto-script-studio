package com.autoscript.script.lua

import com.autoscript.core.accessibility.AccessibilityFinder
import com.autoscript.core.backend.AutomationBackend
import com.autoscript.core.capture.CaptureCache
import com.autoscript.core.perf.PerfMonitor
import com.autoscript.core.model.Rect
import com.autoscript.core.project.ProjectConfig
import com.autoscript.core.script.ScriptCancelToken
import com.autoscript.script.parseBgr
import com.autoscript.vision.VisionEngine
import kotlinx.coroutines.delay

/**
 * Lua 与 YAML 引擎共用的自动化能力（suspend）。
 */
class AutoScriptBridge(
    private val backend: AutomationBackend,
    private val vision: VisionEngine,
    private val config: ProjectConfig,
    private val onLog: (String) -> Unit,
    private val defaultYoloModel: String? = null,
) {
    private val captureCache = CaptureCache(config.perf.captureCacheTtlMs)

    suspend fun delaySeconds(seconds: Double) {
        val total = (seconds * 1000).toLong().coerceAtLeast(0)
        var elapsed = 0L
        val step = 100L
        while (elapsed < total) {
            ScriptCancelToken.check()
            val wait = minOf(step, total - elapsed)
            delay(wait)
            elapsed += wait
        }
    }

    suspend fun tap(x: Int, y: Int) {
        backend.tap(x, y)
    }

    suspend fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Int = 300) {
        backend.swipe(x1, y1, x2, y2, durationMs)
    }

    suspend fun longPress(x: Int, y: Int, durationMs: Int = 500) {
        backend.longPress(x, y, durationMs)
    }

    suspend fun findImage(path: String, opts: Map<String, Any?>): Pair<Int, Int>? {
        val threshold = LuaOpts.float(opts, "threshold", 0.9f)
        val timeout = LuaOpts.float(opts, "timeout", 20f)
        val click = LuaOpts.bool(opts, "click", false)
        val roi = LuaOpts.roi(opts)
        val tapDx = LuaOpts.int(opts, "tap_dx", 0)
        val tapDy = LuaOpts.int(opts, "tap_dy", 0)
        val interval = config.defaultIntervalMs.toLong()
        val deadline = System.currentTimeMillis() + (timeout * 1000).toLong()
        while (System.currentTimeMillis() < deadline) {
            ScriptCancelToken.check()
            val frame = captureCache.getOrCapture { backend.capture() }
            val m = vision.findTemplate(frame, path, threshold, roi)
            if (m != null) {
                onLog("找图命中 $path score=${m.score}")
                val cx = m.centerX + tapDx
                val cy = m.centerY + tapDy
                if (click) backend.tap(cx, cy)
                return cx to cy
            }
            delay(interval)
        }
        captureCache.invalidate()
        if (LuaOpts.bool(opts, "optional", false)) return null
        throw IllegalStateException("找图超时: $path")
    }

    suspend fun findColor(b: Int, g: Int, r: Int, opts: Map<String, Any?>): Pair<Int, Int>? {
        val bgr = Triple(b, g, r)
        val tol = LuaOpts.int(opts, "tol", 12)
        val timeout = LuaOpts.float(opts, "timeout", 15f)
        val click = LuaOpts.bool(opts, "click", false)
        val roi = LuaOpts.roi(opts)
        val tapDx = LuaOpts.int(opts, "tap_dx", 0)
        val tapDy = LuaOpts.int(opts, "tap_dy", 0)
        val deadline = System.currentTimeMillis() + (timeout * 1000).toLong()
        while (System.currentTimeMillis() < deadline) {
            ScriptCancelToken.check()
            val frame = captureCache.getOrCapture { backend.capture() }
            val pt = vision.findColor(frame, bgr, tol, roi)
            if (pt != null) {
                onLog("找色命中 $pt")
                val x = pt.first + tapDx
                val y = pt.second + tapDy
                if (click) backend.tap(x, y)
                return x to y
            }
            delay(config.defaultIntervalMs.toLong())
        }
        captureCache.invalidate()
        if (LuaOpts.bool(opts, "optional", false)) return null
        throw IllegalStateException("找色超时: $bgr")
    }

    suspend fun findColorBgr(bgr: List<*>, opts: Map<String, Any?>): Pair<Int, Int>? {
        val t = parseBgr(bgr)
        return findColor(t.first, t.second, t.third, opts)
    }

    suspend fun findText(target: String, opts: Map<String, Any?>): Pair<Int, Int>? {
        val mode = LuaOpts.str(opts, "match_mode", "contains")
        val timeout = LuaOpts.float(opts, "timeout", 20f)
        val minConf = LuaOpts.float(opts, "min_confidence", 0.5f)
        val click = LuaOpts.bool(opts, "click", false)
        val roi = LuaOpts.roi(opts)
        val index = LuaOpts.int(opts, "index", 0)
        val tapDx = LuaOpts.int(opts, "tap_dx", 0)
        val tapDy = LuaOpts.int(opts, "tap_dy", 0)
        val deadline = System.currentTimeMillis() + (timeout * 1000).toLong()
        while (System.currentTimeMillis() < deadline) {
            ScriptCancelToken.check()
            val t0 = System.nanoTime()
            val frame = captureCache.getOrCapture { backend.capture() }
            val hits = vision.findText(frame, target, mode, roi, minConf)
            PerfMonitor.recordOcr((System.nanoTime() - t0) / 1_000_000)
            if (hits.isNotEmpty()) {
                val h = hits[index.coerceIn(0, hits.lastIndex)]
                onLog("识字命中 ${h.text}")
                val x = h.centerX + tapDx
                val y = h.centerY + tapDy
                if (click) backend.tap(x, y)
                return x to y
            }
            delay(config.defaultIntervalMs.toLong())
        }
        captureCache.invalidate()
        if (LuaOpts.bool(opts, "optional", false)) return null
        throw IllegalStateException("识字超时: $target")
    }

    suspend fun findNode(opts: Map<String, Any?>): Pair<Int, Int>? {
        val text = LuaOpts.str(opts, "text")
        val resourceId = LuaOpts.str(opts, "id")
        val matchMode = LuaOpts.str(opts, "match_mode", "contains")
        val index = LuaOpts.int(opts, "index", 0)
        val click = LuaOpts.bool(opts, "click", false)
        val timeout = LuaOpts.float(opts, "timeout", 10f)
        val deadline = System.currentTimeMillis() + (timeout * 1000).toLong()
        while (System.currentTimeMillis() < deadline) {
            ScriptCancelToken.check()
            val hit = when {
                text.isNotBlank() -> AccessibilityFinder.findByText(text, matchMode, index)
                resourceId.isNotBlank() -> AccessibilityFinder.findById(resourceId, index)
                else -> null
            }
            if (hit != null) {
                onLog("控件命中 ${hit.text} @ (${hit.centerX},${hit.centerY})")
                if (click) backend.tap(hit.centerX, hit.centerY)
                return hit.centerX to hit.centerY
            }
            delay(config.defaultIntervalMs.toLong())
        }
        if (LuaOpts.bool(opts, "optional", false)) return null
        throw IllegalStateException("控件查找超时: text=$text id=$resourceId")
    }

    suspend fun recognizeText(opts: Map<String, Any?>): List<Map<String, Any>> {
        val minConf = LuaOpts.float(opts, "min_confidence", 0.5f)
        val roi = LuaOpts.roi(opts)
        val limit = LuaOpts.int(opts, "limit", 30)
        val frame = captureCache.getOrCapture { backend.capture() }
        val hits = vision.recognizeAll(frame, roi, minConf)
        onLog("识字共 ${hits.size} 条")
        return hits.take(limit).map {
            mapOf(
                "text" to it.text,
                "x" to it.centerX,
                "y" to it.centerY,
                "confidence" to it.confidence,
            )
        }
    }

    suspend fun yoloDetect(opts: Map<String, Any?>): List<Detection> {
        val model = resolveModel(opts)
        val className = LuaOpts.str(opts, "class_name", "")
        val conf = LuaOpts.float(opts, "conf", config.defaultYoloConf)
        val roi = LuaOpts.roi(opts)
        val t0 = System.nanoTime()
        val frame = captureCache.getOrCapture { backend.capture() }
        val dets = vision.yoloDetect(frame, model, conf, className, roi)
        PerfMonitor.recordYolo((System.nanoTime() - t0) / 1_000_000)
        return dets
    }

    suspend fun findYolo(opts: Map<String, Any?>): Pair<Int, Int>? {
        val model = resolveModel(opts)
        val className = LuaOpts.str(opts, "class_name", "")
        val conf = LuaOpts.float(opts, "conf", config.defaultYoloConf)
        val pick = LuaOpts.str(opts, "pick", "best_conf")
        val timeout = LuaOpts.float(opts, "timeout", 20f)
        val click = LuaOpts.bool(opts, "click", false)
        val roi = LuaOpts.roi(opts)
        val frac = LuaOpts.frac(opts)
        val tapDx = LuaOpts.int(opts, "tap_dx", 0)
        val tapDy = LuaOpts.int(opts, "tap_dy", 0)
        val delayBefore = LuaOpts.float(opts, "delay_before_click", 0f)
        val deadline = System.currentTimeMillis() + (timeout * 1000).toLong()
        while (System.currentTimeMillis() < deadline) {
            ScriptCancelToken.check()
            val frame = captureCache.getOrCapture { backend.capture() }
            val dets = vision.yoloDetect(frame, model, conf, className, roi)
            val det = vision.pickYolo(dets, pick, null)
            if (det != null) {
                onLog("YOLO 命中 ${det.className} conf=${det.confidence}")
                val pt = vision.yoloClickPoint(det, frac)
                val x = pt.first + tapDx
                val y = pt.second + tapDy
                if (click) {
                    if (delayBefore > 0f) delay((delayBefore * 1000).toLong())
                    backend.tap(x, y)
                }
                return x to y
            }
            delay(config.defaultIntervalMs.toLong())
        }
        if (LuaOpts.bool(opts, "optional", false)) return null
        throw IllegalStateException("YOLO 超时: class=$className")
    }

    suspend fun yoloSwipe(opts: Map<String, Any?>) {
        val model = resolveModel(opts)
        val className = LuaOpts.str(opts, "class_name", "")
        val conf = LuaOpts.float(opts, "conf", config.defaultYoloConf)
        val pick = LuaOpts.str(opts, "pick", "best_conf")
        val timeout = LuaOpts.float(opts, "timeout", 20f)
        val roi = LuaOpts.roi(opts)
        val distance = LuaOpts.int(opts, "distance", 400)
        val direction = LuaOpts.str(opts, "direction", "up").lowercase()
        val durationMs = LuaOpts.int(opts, "duration_ms", 350)
        val frac = LuaOpts.frac(opts)
        val deadline = System.currentTimeMillis() + (timeout * 1000).toLong()
        while (System.currentTimeMillis() < deadline) {
            ScriptCancelToken.check()
            val frame = captureCache.getOrCapture { backend.capture() }
            val dets = vision.yoloDetect(frame, model, conf, className, roi)
            val det = vision.pickYolo(dets, pick, null)
            if (det != null) {
                val (cx, cy) = vision.yoloClickPoint(det, frac)
                val (x2, y2) = when (direction) {
                    "down" -> cx to (cy + distance)
                    "left" -> (cx - distance) to cy
                    "right" -> (cx + distance) to cy
                    else -> cx to (cy - distance)
                }
                onLog("YOLO 滑动 $direction ($cx,$cy)->($x2,$y2)")
                backend.swipe(cx, cy, x2, y2, durationMs)
                return
            }
            delay(config.defaultIntervalMs.toLong())
        }
        throw IllegalStateException("YOLO 滑动超时: class=$className")
    }

    private fun resolveModel(opts: Map<String, Any?>): String {
        val m = LuaOpts.str(opts, "model")
            .ifBlank { LuaOpts.str(opts, "model_path") }
            .ifBlank { defaultYoloModel.orEmpty() }
            .ifBlank { config.defaultYoloModel.orEmpty() }
        if (m.isBlank()) throw IllegalStateException("未指定 yolo 模型（opts.model 或 project.json runtime.default_yolo_model）")
        return m
    }
}
