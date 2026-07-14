package com.autoscript.script.lua

import android.content.Context
import android.content.Intent
import android.os.Handler
import android.os.Looper
import android.widget.Toast
import com.autoscript.core.accessibility.AccessibilityFinder
import com.autoscript.core.backend.AutomationBackend
import com.autoscript.core.capture.CaptureCache
import com.autoscript.core.perf.PerfMonitor
import com.autoscript.core.model.Detection
import com.autoscript.core.model.Rect
import com.autoscript.core.project.ProjectConfig
import com.autoscript.core.script.ScriptCancelToken
import com.autoscript.core.script.ScriptTrace
import com.autoscript.script.parseBgr
import com.autoscript.vision.VisionEngine
import kotlinx.coroutines.delay
import kotlin.math.abs

/**
 * Lua 与 YAML 引擎共用的自动化能力（suspend）。
 */
class AutoScriptBridge(
    private val backend: AutomationBackend,
    private val vision: VisionEngine,
    private val config: ProjectConfig,
    private val onLog: (String) -> Unit,
    private val defaultYoloModel: String? = null,
    private val appContext: Context? = null,
) {
    private val captureCache = CaptureCache(config.perf.captureCacheTtlMs)

    /** 按包名打开应用（如钉钉 `com.alibaba.android.rimet`）。 */
    fun openApp(packageName: String): Boolean {
        val pkg = packageName.trim()
        if (pkg.isEmpty()) {
            onLog("openApp: 包名为空")
            return false
        }
        val ctx = appContext
        if (ctx == null) {
            onLog("openApp: 无 Context，仅真机 APK 可用")
            return false
        }
        val launch = ctx.packageManager.getLaunchIntentForPackage(pkg)
        if (launch == null) {
            onLog("openApp: 未安装或无法启动 $pkg")
            return false
        }
        launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            ctx.startActivity(launch)
            onLog("openApp: 已打开 $pkg")
            true
        } catch (e: Exception) {
            onLog("openApp 失败: ${e.message}")
            false
        }
    }

    /** 弹出 Toast 提醒（真机）。 */
    fun toast(message: String) {
        val msg = message.trim()
        if (msg.isEmpty()) return
        onLog(msg)
        val ctx = appContext ?: return
        Handler(Looper.getMainLooper()).post {
            Toast.makeText(ctx, msg, Toast.LENGTH_LONG).show()
        }
    }

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
        val step = LuaOpts.int(opts, "step", 2)
        val scaleMin = LuaOpts.float(opts, "scale_min", 1f)
        val scaleMax = LuaOpts.float(opts, "scale_max", 1f)
        val scaleStep = LuaOpts.float(opts, "scale_step", 0.1f)
        val interval = config.defaultIntervalMs.toLong()
        val deadline = System.currentTimeMillis() + (timeout * 1000).toLong()
        while (System.currentTimeMillis() < deadline) {
            ScriptCancelToken.check()
            val frame = captureCache.getOrCapture { backend.capture() }
            val m = vision.findTemplate(
                frame, path, threshold, roi, step, scaleMin, scaleMax, scaleStep,
            )
            if (m != null) {
                onLog("找图命中 $path score=${m.score}")
                ScriptTrace.trace("findImage", "$path @ (${m.centerX},${m.centerY}) score=${m.score}")
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

    suspend fun waitGoneImage(path: String, opts: Map<String, Any?>): Boolean {
        val threshold = LuaOpts.float(opts, "threshold", 0.92f)
        val timeout = LuaOpts.float(opts, "timeout", 45f)
        val roi = LuaOpts.roi(opts)
        val step = LuaOpts.int(opts, "step", 2)
        val deadline = System.currentTimeMillis() + (timeout * 1000).toLong()
        while (System.currentTimeMillis() < deadline) {
            ScriptCancelToken.check()
            val frame = captureCache.getOrCapture { backend.capture() }
            val m = vision.findTemplate(frame, path, threshold, roi, step)
            if (m == null) {
                onLog("模板已消失 $path")
                ScriptTrace.trace("waitGone", "gone $path")
                return true
            }
            delay(config.defaultIntervalMs.toLong())
        }
        if (LuaOpts.bool(opts, "optional", false)) return false
        throw IllegalStateException("等待模板消失超时: $path")
    }

    suspend fun waitStable(opts: Map<String, Any?>): Boolean {
        val timeout = LuaOpts.float(opts, "timeout", 12f)
        val maxDiff = LuaOpts.float(opts, "max_mean_diff", 4f)
        val samples = LuaOpts.int(opts, "stable_samples", 2)
        val deadline = System.currentTimeMillis() + (timeout * 1000).toLong()
        var stable = 0
        var prev: ByteArray? = null
        while (System.currentTimeMillis() < deadline) {
            ScriptCancelToken.check()
            val frame = captureCache.getOrCapture { backend.capture() }
            val cur = frame.bgr
            if (prev != null && meanDiff(prev, cur) <= maxDiff) {
                stable++
                if (stable >= samples) {
                    onLog("画面稳定")
                    ScriptTrace.trace("waitStable", "stable")
                    return true
                }
            } else {
                stable = 0
            }
            prev = if (frame.sharedBuffer) frame.bgr.copyOf() else frame.bgr
            delay(config.defaultIntervalMs.toLong())
        }
        if (LuaOpts.bool(opts, "optional", false)) return false
        throw IllegalStateException("等待画面稳定超时")
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

    suspend fun findMultiColor(points: List<Triple<Int, Int, Triple<Int, Int, Int>>>, opts: Map<String, Any?>): Pair<Int, Int>? {
        if (points.isEmpty()) throw IllegalArgumentException("points 不能为空")
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
            val pt = vision.findMultiPointColor(frame, points, tol, roi)
            if (pt != null) {
                onLog("多点找色命中 $pt")
                val x = pt.first + tapDx
                val y = pt.second + tapDy
                if (click) backend.tap(x, y)
                return x to y
            }
            delay(config.defaultIntervalMs.toLong())
        }
        captureCache.invalidate()
        if (LuaOpts.bool(opts, "optional", false)) return null
        throw IllegalStateException("多点找色超时")
    }

    suspend fun trace(tag: String, msg: String) {
        ScriptTrace.trace(tag, msg)
    }

    suspend fun warmupYolo() {
        val model = config.defaultYoloModel ?: return
        if (!config.perf.yoloWarmup) return
        runCatching {
            val frame = backend.capture()
            vision.yoloDetect(frame, model, 0.99f, "", null)
            onLog("YOLO 预热完成: $model")
        }.onFailure { onLog("YOLO 预热跳过: ${it.message}") }
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
        val maskMax = LuaOpts.int(opts, "mask_decode_max", config.perf.yoloMaxMaskDecode)
        val t0 = System.nanoTime()
        val frame = captureCache.getOrCapture { backend.capture() }
        val dets = vision.yoloDetect(frame, model, conf, className, roi, maxMaskDecode = maskMax)
        PerfMonitor.recordYolo((System.nanoTime() - t0) / 1_000_000)
        return dets
    }

    private fun resolveMaskDecodeMax(opts: Map<String, Any?>, pick: String): Int {
        if (LuaOpts.int(opts, "mask_decode_max", -1) >= 0) {
            return LuaOpts.int(opts, "mask_decode_max", config.perf.yoloMaxMaskDecode)
        }
        val wantMask = LuaOpts.bool(opts, "use_mask_center", false) || config.yoloAutoMaskCenter
        return when {
            pick == "largest_mask" -> maxOf(5, config.perf.yoloMaxMaskDecode)
            wantMask -> if (config.perf.yoloSegFast) 1 else config.perf.yoloMaxMaskDecode
            else -> 0
        }
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
            val dets = vision.yoloDetect(
                frame,
                model,
                conf,
                className,
                roi,
                maxMaskDecode = resolveMaskDecodeMax(opts, pick),
            )
            val det = vision.pickYolo(dets, pick, null)
            if (det != null) {
                val useMaskCenter = resolveUseMaskCenter(opts, det)
                onLog("YOLO 命中 ${det.className} conf=${det.confidence}")
                val pt = vision.yoloClickPoint(det, frac, useMaskCenter)
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
            val dets = vision.yoloDetect(
                frame,
                model,
                conf,
                className,
                roi,
                maxMaskDecode = resolveMaskDecodeMax(opts, pick),
            )
            val det = vision.pickYolo(dets, pick, null)
            if (det != null) {
                val useMaskCenter = resolveUseMaskCenter(opts, det)
                val (cx, cy) = vision.yoloClickPoint(det, frac, useMaskCenter)
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

    private fun resolveUseMaskCenter(opts: Map<String, Any?>, det: Detection): Boolean {
        if (LuaOpts.bool(opts, "use_box_center", false)) return false
        if (LuaOpts.bool(opts, "use_mask_center", false)) return true
        return config.yoloAutoMaskCenter && det.hasMask
    }

    private fun meanDiff(a: ByteArray, b: ByteArray): Float {
        val n = minOf(a.size, b.size) / 3
        if (n == 0) return 0f
        var sum = 0f
        for (i in 0 until n) {
            val j = i * 3
            sum += abs((a[j].toInt() and 0xFF) - (b[j].toInt() and 0xFF))
        }
        return sum / n
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
