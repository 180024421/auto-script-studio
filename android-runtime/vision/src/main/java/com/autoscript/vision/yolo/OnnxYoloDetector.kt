package com.autoscript.vision.yolo

import android.content.Context
import com.autoscript.core.model.Detection
import com.autoscript.core.model.Rect
import com.autoscript.core.model.ScreenFrame
import com.autoscript.core.project.ProjectAssets
import com.autoscript.vision.util.ModelResolver
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.io.File
import java.nio.FloatBuffer
import kotlin.math.max
import kotlin.math.min

/**
 * YOLOv8/v11 ONNX 推理（CPU）。
 * 模型由 tools/export_yolo_onnx.py 从 .pt 导出，放入工程 models/ 目录。
 */
class OnnxYoloDetector(
    private val context: Context,
    private val assets: ProjectAssets,
    private val imgsz: Int = 320,
) : YoloDetector {

    private val env: OrtEnvironment = OrtEnvironment.getEnvironment()
    private val sessions = mutableMapOf<String, OrtSession>()
    private val labelsCache = mutableMapOf<String, List<String>>()

    override fun detect(
        frame: ScreenFrame,
        modelPath: String,
        conf: Float,
        className: String,
        roi: Rect?,
        maxDet: Int,
    ): List<Detection> {
        val onnxPath = ModelResolver.resolveOnnx(assets, modelPath)
        val session = getSession(onnxPath)
        val labels = loadLabels(onnxPath)
        val bounds = roi?.clamp(frame.width, frame.height)
        val x0 = bounds?.x ?: 0
        val y0 = bounds?.y ?: 0
        val rw = bounds?.w ?: frame.width
        val rh = bounds?.h ?: frame.height
        if (rw <= 0 || rh <= 0) return emptyList()

        val inputName = session.inputNames.iterator().next()
        val inputData = preprocess(frame, x0, y0, rw, rh)
        val inputShape = longArrayOf(1, 3, imgsz.toLong(), imgsz.toLong())
        OnnxTensor.createTensor(env, FloatBuffer.wrap(inputData), inputShape).use { tensor ->
            session.run(mapOf(inputName to tensor)).use { result ->
                val raw = result[0].value
                val rows = to2dFloatArray(raw)
                return postprocess(rows, conf, className, labels, x0, y0, rw, rh, maxDet)
            }
        }
    }

    override fun release() {
        sessions.values.forEach { runCatching { it.close() } }
        sessions.clear()
    }

    private fun getSession(assetPath: String): OrtSession =
        sessions.getOrPut(assetPath) {
            val file = copyAssetToCache(assetPath)
            env.createSession(file.absolutePath, OrtSession.SessionOptions())
        }

    private fun copyAssetToCache(path: String): File {
        val out = File(context.cacheDir, "onnx/${path.replace('/', '_')}")
        if (!out.exists() || out.length() == 0L) {
            out.parentFile?.mkdirs()
            assets.readBytes(path).let { bytes ->
                out.writeBytes(bytes)
            }
        }
        return out
    }

    private fun loadLabels(onnxPath: String): List<String> {
        return labelsCache.getOrPut(onnxPath) {
            val labelPath = ModelResolver.labelsPathForModel(onnxPath)
            if (!assets.exists(labelPath)) return@getOrPut emptyList()
            assets.readBytes(labelPath).toString(Charsets.UTF_8)
                .lineSequence()
                .map { it.trim() }
                .filter { it.isNotEmpty() }
                .toList()
        }
    }

    private fun preprocess(frame: ScreenFrame, x0: Int, y0: Int, rw: Int, rh: Int): FloatArray {
        val out = FloatArray(3 * imgsz * imgsz)
        for (dy in 0 until imgsz) {
            val sy = y0 + (dy * rh / imgsz)
            for (dx in 0 until imgsz) {
                val sx = x0 + (dx * rw / imgsz)
                if (sx >= frame.width || sy >= frame.height) continue
                val j = (sy * frame.width + sx) * 3
                val b = (frame.bgr[j].toInt() and 0xFF) / 255f
                val g = (frame.bgr[j + 1].toInt() and 0xFF) / 255f
                val r = (frame.bgr[j + 2].toInt() and 0xFF) / 255f
                val base = dy * imgsz + dx
                out[base] = r
                out[imgsz * imgsz + base] = g
                out[2 * imgsz * imgsz + base] = b
            }
        }
        return out
    }

    @Suppress("UNCHECKED_CAST")
    private fun to2dFloatArray(raw: Any?): Array<FloatArray> {
        when (raw) {
            is Array<*> -> {
                if (raw.isEmpty()) return emptyArray()
                val first = raw[0]
                when (first) {
                    is Array<*> -> {
                        if (first.isNotEmpty() && first[0] is FloatArray) {
                            return first as Array<FloatArray>
                        }
                        if (first.isNotEmpty() && first[0] is Float) {
                            val rows = raw[0] as Array<FloatArray>
                            return transpose(rows)
                        }
                    }
                    is FloatArray -> return arrayOf(first)
                }
            }
        }
        throw IllegalStateException("无法解析 ONNX 输出: ${raw?.javaClass?.name}")
    }

    private fun transpose(rows: Array<FloatArray>): Array<FloatArray> {
        if (rows.isEmpty()) return emptyArray()
        val anchors = rows.size
        val features = rows[0].size
        return Array(features) { f ->
            FloatArray(anchors) { a -> rows[a][f] }
        }
    }

    private fun postprocess(
        matrix: Array<FloatArray>,
        conf: Float,
        className: String,
        labels: List<String>,
        offsetX: Int,
        offsetY: Int,
        roiW: Int,
        roiH: Int,
        maxDet: Int,
    ): List<Detection> {
        if (matrix.isEmpty()) return emptyList()
        val features = matrix.size
        val anchors = matrix[0].size
        if (features < 5) return emptyList()
        val numClasses = features - 4
        val scaleX = roiW.toFloat() / imgsz
        val scaleY = roiH.toFloat() / imgsz
        val raw = mutableListOf<Detection>()

        for (i in 0 until anchors) {
            var bestScore = 0f
            var bestClass = 0
            for (c in 0 until numClasses) {
                val s = matrix[4 + c][i]
                if (s > bestScore) {
                    bestScore = s
                    bestClass = c
                }
            }
            if (bestScore < conf) continue
            val name = labels.getOrElse(bestClass) { "class_$bestClass" }
            if (className.isNotBlank() && !name.contains(className, ignoreCase = true)) continue

            val cx = matrix[0][i] * scaleX + offsetX
            val cy = matrix[1][i] * scaleY + offsetY
            val w = matrix[2][i] * scaleX
            val h = matrix[3][i] * scaleY
            val x = (cx - w / 2f).toInt()
            val y = (cy - h / 2f).toInt()
            raw.add(
                Detection(
                    className = name,
                    confidence = bestScore,
                    rect = Rect(x, y, w.toInt().coerceAtLeast(1), h.toInt().coerceAtLeast(1)),
                ),
            )
        }
        return nms(raw, 0.45f).take(maxDet)
    }

    private fun nms(dets: List<Detection>, iouThresh: Float): List<Detection> {
        val sorted = dets.sortedByDescending { it.confidence }.toMutableList()
        val kept = mutableListOf<Detection>()
        while (sorted.isNotEmpty()) {
            val best = sorted.removeAt(0)
            kept.add(best)
            sorted.removeAll { iou(best.rect, it.rect) > iouThresh }
        }
        return kept
    }

    private fun iou(a: Rect, b: Rect): Float {
        val x1 = max(a.x, b.x)
        val y1 = max(a.y, b.y)
        val x2 = min(a.x + a.w, b.x + b.w)
        val y2 = min(a.y + a.h, b.y + b.h)
        val inter = max(0, x2 - x1) * max(0, y2 - y1)
        val union = a.w * a.h + b.w * b.h - inter
        return if (union <= 0) 0f else inter.toFloat() / union
    }
}
