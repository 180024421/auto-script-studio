package com.autoscript.script.saocheng

import android.content.Context
import android.graphics.Bitmap
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.io.File
import java.nio.FloatBuffer
import kotlin.math.max
import kotlin.math.min

class YoloDetector(context: Context, modelAsset: String = "project/models/ui.onnx", labelsAsset: String = "project/models/ui.labels") {
    private val env = OrtEnvironment.getEnvironment()
    private var session: OrtSession? = null
    private val classNames: List<String>
    var loadError: String? = null
        private set

    val ready: Boolean get() = session != null

    init {
        classNames = context.assets.open(labelsAsset).bufferedReader().readLines()
            .map { it.trim() }.filter { it.isNotEmpty() }
        try {
            val modelFile = copyAssetToCache(context, modelAsset, "saocheng_ui.onnx")
            session = env.createSession(modelFile.absolutePath, OrtSession.SessionOptions())
        } catch (e: Exception) {
            loadError = e.message ?: e.javaClass.simpleName
        }
    }

    fun detect(bitmap: Bitmap, conf: Float = FlowConstants.YOLO_CONF): List<YoloDetection> {
        val sess = session ?: return emptyList()
        val w = bitmap.width
        val h = bitmap.height
        val size = FlowConstants.YOLO_INPUT_SIZE
        val scale = min(size.toFloat() / w, size.toFloat() / h)
        val nw = (w * scale).toInt()
        val nh = (h * scale).toInt()
        val padX = (size - nw) / 2
        val padY = (size - nh) / 2

        val input = FloatArray(3 * size * size) { 114f / 255f }
        val pixels = IntArray(w * h)
        bitmap.getPixels(pixels, 0, w, 0, 0, w, h)

        for (y in 0 until nh) {
            val sy = min((y / scale).toInt(), h - 1)
            for (x in 0 until nw) {
                val sx = min((x / scale).toInt(), w - 1)
                val c = pixels[sy * w + sx]
                val r = ((c shr 16) and 0xFF) / 255f
                val g = ((c shr 8) and 0xFF) / 255f
                val b = (c and 0xFF) / 255f
                val ox = padX + x
                val oy = padY + y
                val base = oy * size + ox
                input[base] = r
                input[size * size + base] = g
                input[2 * size * size + base] = b
            }
        }

        val shape = longArrayOf(1, 3, size.toLong(), size.toLong())
        val tensor = OnnxTensor.createTensor(env, FloatBuffer.wrap(input), shape)
        val outputs = sess.run(mapOf("images" to tensor))
        tensor.close()

        val out0 = outputs[0].value as Array<Array<FloatArray>>
        val pred = out0[0] // [78, 8400]
        val nc = classNames.size
        val numAnchors = pred[0].size
        val raw = ArrayList<YoloDetection>(32)

        for (i in 0 until numAnchors) {
            var bestCls = 0
            var bestScore = 0f
            for (c in 0 until nc) {
                val s = pred[4 + c][i]
                if (s > bestScore) {
                    bestScore = s
                    bestCls = c
                }
            }
            if (bestScore < conf) continue

            val cx = pred[0][i]
            val cy = pred[1][i]
            val bw = pred[2][i]
            val bh = pred[3][i]
            val x1 = ((cx - bw / 2f - padX) / scale).toInt().coerceIn(0, w - 1)
            val y1 = ((cy - bh / 2f - padY) / scale).toInt().coerceIn(0, h - 1)
            val x2 = ((cx + bw / 2f - padX) / scale).toInt().coerceIn(0, w - 1)
            val y2 = ((cy + bh / 2f - padY) / scale).toInt().coerceIn(0, h - 1)
            if (x2 <= x1 || y2 <= y1) continue

            val name = classNames.getOrElse(bestCls) { bestCls.toString() }
            raw.add(YoloDetection(bestCls, name, bestScore, x1, y1, x2, y2))
        }
        outputs.close()
        return nms(raw, FlowConstants.YOLO_IOU)
    }

    fun close() {
        session?.close()
        session = null
    }

    private fun nms(dets: List<YoloDetection>, iouTh: Float): List<YoloDetection> {
        val sorted = dets.sortedByDescending { it.confidence }.toMutableList()
        val kept = ArrayList<YoloDetection>()
        while (sorted.isNotEmpty()) {
            val best = sorted.removeAt(0)
            kept.add(best)
            sorted.removeAll { it.className == best.className && it.iouWith(best) > iouTh }
        }
        return kept
    }

    private fun copyAssetToCache(context: Context, assetPath: String, cacheName: String): File {
        val out = File(context.cacheDir, cacheName)
        val bytes = context.assets.open(assetPath).use { it.readBytes() }
        if (!out.exists() || out.length() != bytes.size.toLong()) {
            out.parentFile?.mkdirs()
            out.writeBytes(bytes)
        }
        return out
    }
}
