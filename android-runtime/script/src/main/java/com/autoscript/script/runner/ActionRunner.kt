package com.autoscript.script.runner

import com.autoscript.core.backend.AutomationBackend
import com.autoscript.core.capture.CaptureCache
import com.autoscript.core.project.ProjectConfig
import com.autoscript.script.parseBgr
import com.autoscript.script.parseRoi
import com.autoscript.vision.VisionEngine
import com.autoscript.vision.yolo.YoloPick
import kotlinx.coroutines.delay
import kotlin.random.Random

class ActionRunner(
    private val backend: AutomationBackend,
    private val vision: VisionEngine,
    private val config: ProjectConfig,
    private val onLog: (String) -> Unit,
) {
    private val captureCache = CaptureCache(config.perf.captureCacheTtlMs)

    suspend fun runAction(action: Map<String, Any?>, workflow: Map<String, Any?>) {
        val type = str(action["type"]).lowercase()
        when (type) {
            "template" -> runTemplate(action, workflow, click = true)
            "color" -> runColor(action, workflow, click = true)
            "text" -> runText(action, workflow, click = true)
            "yolo" -> runYolo(action, workflow, click = true)
            "yolo_swipe" -> runYoloSwipe(action, workflow)
            "tap" -> backend.tap(num(action["x"]), num(action["y"]))
            "swipe" -> backend.swipe(
                num(action["x1"]), num(action["y1"]),
                num(action["x2"]), num(action["y2"]),
                num(action["duration_ms"], 300),
            )
            "human_delay" -> humanDelay(action)
            "gone_template" -> waitGoneTemplate(action, workflow)
            "stable" -> waitStable(action, workflow)
            else -> throw IllegalArgumentException("未知 action type: $type")
        }
    }

    suspend fun runStep(step: Map<String, Any?>, workflow: Map<String, Any?>) {
        val type = str(step["type"]).lowercase()
        when (type) {
            "delay" -> delay((num(step["seconds"], 0) * 1000).toLong())
            "tap" -> backend.tap(num(step["x"]), num(step["y"]))
            "swipe" -> backend.swipe(
                num(step["x1"]), num(step["y1"]),
                num(step["x2"]), num(step["y2"]),
                num(step["duration_ms"], 300),
            )
            "wait_template" -> runTemplate(step, workflow, click = false)
            "wait_click_template" -> runTemplate(step, workflow, click = true)
            "click_color", "color" -> runColor(step, workflow, click = true)
            "find_color" -> runColor(step, workflow, click = false)
            "wait_click_text", "click_text" -> runText(step, workflow, click = true)
            "find_text", "text" -> runText(step, workflow, click = step.get("click") != false)
            "recognize_text", "ocr" -> runRecognize(step, workflow)
            "yolo_click", "yolo" -> runYolo(step, workflow, click = true)
            "yolo_swipe" -> runYoloSwipe(step, workflow)
            "gone_template", "wait_gone_template" -> waitGoneTemplate(step, workflow)
            "stable", "wait_stable" -> waitStable(step, workflow)
            else -> throw IllegalArgumentException("未知 step type: $type")
        }
    }

    private suspend fun runTemplate(action: Map<String, Any?>, workflow: Map<String, Any?>, click: Boolean) {
        val path = str(action["template"])
        val threshold = flt(action["threshold"], 0.9f)
        val timeout = flt(action["timeout"], 20f)
        val interval = (config.defaultIntervalMs).toLong()
        val roi = parseRoi(action["roi"]) ?: parseRoi(workflow["yolo_roi"])
        val deadline = System.currentTimeMillis() + (timeout * 1000).toLong()
        while (System.currentTimeMillis() < deadline) {
            val frame = captureCache.getOrCapture { backend.capture() }
            val m = vision.findTemplate(frame, path, threshold, roi)
            if (m != null) {
                onLog("找图命中 $path score=${m.score}")
                if (click) {
                    backend.tap(
                        m.centerX + num(action["tap_dx"], 0),
                        m.centerY + num(action["tap_dy"], 0),
                    )
                }
                return
            }
            delay(interval)
        }
        captureCache.invalidate()
        throw IllegalStateException("找图超时: $path")
    }

    private suspend fun runColor(action: Map<String, Any?>, workflow: Map<String, Any?>, click: Boolean) {
        val bgr = parseBgr(action["bgr"] ?: action["color"])
        val tol = num(action["tol"], 12)
        val timeout = flt(action["timeout"], 15f)
        val roi = parseRoi(action["roi"]) ?: parseRoi(workflow["yolo_roi"])
        val deadline = System.currentTimeMillis() + (timeout * 1000).toLong()
        while (System.currentTimeMillis() < deadline) {
            val frame = captureCache.getOrCapture { backend.capture() }
            val pt = vision.findColor(frame, bgr, tol, roi)
            if (pt != null) {
                onLog("找色命中 $pt")
                if (click) {
                    backend.tap(pt.first + num(action["tap_dx"], 0), pt.second + num(action["tap_dy"], 0))
                }
                return
            }
            delay(config.defaultIntervalMs.toLong())
        }
        captureCache.invalidate()
        throw IllegalStateException("找色超时: $bgr")
    }

    private suspend fun runText(action: Map<String, Any?>, workflow: Map<String, Any?>, click: Boolean) {
        val target = str(action["target"] ?: action["text"])
        val mode = str(action["match_mode"], "contains")
        val timeout = flt(action["timeout"], 20f)
        val minConf = flt(action["min_confidence"], 0.5f)
        val roi = parseRoi(action["roi"]) ?: parseRoi(workflow["yolo_roi"])
        val deadline = System.currentTimeMillis() + (timeout * 1000).toLong()
        while (System.currentTimeMillis() < deadline) {
            val frame = captureCache.getOrCapture { backend.capture() }
            val hits = vision.findText(frame, target, mode, roi, minConf)
            if (hits.isNotEmpty()) {
                val h = hits[num(action["index"], 0).coerceAtMost(hits.lastIndex)]
                onLog("识字命中 ${h.text}")
                if (click) {
                    backend.tap(h.centerX + num(action["tap_dx"], 0), h.centerY + num(action["tap_dy"], 0))
                }
                return
            }
            delay(config.defaultIntervalMs.toLong())
        }
        captureCache.invalidate()
        throw IllegalStateException("识字超时: $target")
    }

    private suspend fun runYolo(action: Map<String, Any?>, workflow: Map<String, Any?>, click: Boolean) {
        val model = str(action["model"] ?: action["model_path"] ?: workflow["yolo_model"] ?: config.defaultYoloModel ?: "")
        if (model.isBlank()) throw IllegalStateException("未指定 yolo 模型")
        val className = str(action["class_name"], "")
        val conf = flt(action["conf"], config.defaultYoloConf)
        val pick = str(action["pick"], "best_conf")
        val timeout = flt(action["timeout"], 20f)
        val roi = parseRoi(action["roi"]) ?: parseRoi(workflow["yolo_roi"])
        val frac = parseFrac(action["frac"])
        val deadline = System.currentTimeMillis() + (timeout * 1000).toLong()
        while (System.currentTimeMillis() < deadline) {
            val frame = backend.capture()
            val dets = vision.yoloDetect(frame, model, conf, className, roi)
            val det = vision.pickYolo(dets, pick, null)
            if (det != null) {
                onLog("YOLO 命中 ${det.className} conf=${det.confidence}")
                if (click) {
                    val pt = vision.yoloClickPoint(det, frac)
                    backend.tap(pt.first, pt.second)
                }
                return
            }
            delay(config.defaultIntervalMs.toLong())
        }
        throw IllegalStateException("YOLO 超时: class=$className")
    }

    private suspend fun runYoloSwipe(action: Map<String, Any?>, workflow: Map<String, Any?>) {
        val model = str(action["model"] ?: action["model_path"] ?: workflow["yolo_model"] ?: config.defaultYoloModel ?: "")
        if (model.isBlank()) throw IllegalStateException("未指定 yolo 模型")
        val className = str(action["class_name"], "")
        val conf = flt(action["conf"], config.defaultYoloConf)
        val pick = str(action["pick"], "best_conf")
        val timeout = flt(action["timeout"], 20f)
        val roi = parseRoi(action["roi"]) ?: parseRoi(workflow["yolo_roi"])
        val distance = num(action["distance"], 400)
        val direction = str(action["direction"], "up").lowercase()
        val deadline = System.currentTimeMillis() + (timeout * 1000).toLong()
        while (System.currentTimeMillis() < deadline) {
            val frame = backend.capture()
            val dets = vision.yoloDetect(frame, model, conf, className, roi)
            val det = vision.pickYolo(dets, pick, null)
            if (det != null) {
                val (cx, cy) = vision.yoloClickPoint(det, parseFrac(action["frac"]))
                val (x2, y2) = when (direction) {
                    "down" -> cx to (cy + distance)
                    "left" -> (cx - distance) to cy
                    "right" -> (cx + distance) to cy
                    else -> cx to (cy - distance)
                }
                onLog("YOLO 滑动 $direction 起点=($cx,$cy)")
                backend.swipe(cx, cy, x2, y2, num(action["duration_ms"], 350))
                return
            }
            delay(config.defaultIntervalMs.toLong())
        }
        throw IllegalStateException("YOLO 滑动超时: class=$className")
    }

    private suspend fun runRecognize(step: Map<String, Any?>, workflow: Map<String, Any?>) {
        val minConf = flt(step["min_confidence"], 0.5f)
        val roi = parseRoi(step["roi"]) ?: parseRoi(workflow["yolo_roi"])
        val frame = backend.capture()
        val hits = vision.recognizeAll(frame, roi, minConf)
        onLog("识字共 ${hits.size} 条")
        val limit = num(step["limit"], 20)
        hits.take(limit).forEach { h ->
            onLog("  [${h.confidence}] ${h.text} @ (${h.centerX},${h.centerY})")
        }
    }

    private suspend fun waitGoneTemplate(action: Map<String, Any?>, workflow: Map<String, Any?>) {
        val path = str(action["template"])
        val threshold = flt(action["threshold"], 0.92f)
        val timeout = flt(action["timeout"], 45f)
        val roi = parseRoi(action["roi"])
        val deadline = System.currentTimeMillis() + (timeout * 1000).toLong()
        while (System.currentTimeMillis() < deadline) {
            val frame = backend.capture()
            val m = vision.findTemplate(frame, path, threshold, roi)
            if (m == null) {
                onLog("模板已消失 $path")
                return
            }
            delay(config.defaultIntervalMs.toLong())
        }
        throw IllegalStateException("等待模板消失超时: $path")
    }

    private suspend fun waitStable(action: Map<String, Any?>, workflow: Map<String, Any?>) {
        val timeout = flt(action["timeout"], 12f)
        val maxDiff = flt(action["max_mean_diff"], 4f)
        val samples = num(action["stable_samples"], 2)
        val deadline = System.currentTimeMillis() + (timeout * 1000).toLong()
        var stable = 0
        var prev: ByteArray? = null
        while (System.currentTimeMillis() < deadline) {
            val frame = backend.capture()
            val cur = frame.bgr
            if (prev != null && meanDiff(prev, cur) <= maxDiff) {
                stable++
                if (stable >= samples) {
                    onLog("画面稳定")
                    return
                }
            } else {
                stable = 0
            }
            prev = if (frame.sharedBuffer) frame.bgr.copyOf() else frame.bgr
            delay(config.defaultIntervalMs.toLong())
        }
        throw IllegalStateException("等待画面稳定超时")
    }

    private suspend fun humanDelay(action: Map<String, Any?>) {
        val base = flt(action["base"], 0.5f)
        val spread = flt(action["spread"], 0.2f)
        val ms = ((base + Random.nextDouble(-spread.toDouble(), spread.toDouble())) * 1000).toLong()
        delay(ms.coerceAtLeast(0))
    }

    private fun meanDiff(a: ByteArray, b: ByteArray): Float {
        val n = minOf(a.size, b.size) / 3
        if (n == 0) return 0f
        var sum = 0f
        for (i in 0 until n) {
            val j = i * 3
            sum += kotlin.math.abs((a[j].toInt() and 0xFF) - (b[j].toInt() and 0xFF))
        }
        return sum / n
    }

    private fun parseFrac(value: Any?): Pair<Float, Float> {
        if (value is List<*> && value.size == 2) {
            return (value[0] as Number).toFloat() to (value[1] as Number).toFloat()
        }
        return 0.5f to 0.5f
    }

    private fun str(v: Any?, default: String = ""): String = v?.toString()?.trim() ?: default
    private fun num(v: Any?, default: Int = 0): Int = when (v) {
        is Number -> v.toInt()
        else -> default
    }
    private fun flt(v: Any?, default: Float = 0f): Float = when (v) {
        is Number -> v.toFloat()
        else -> default
    }
}
