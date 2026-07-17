package com.autoscript.vision.digit

import android.content.Context
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import com.autoscript.core.model.Rect
import com.autoscript.core.model.ScreenFrame
import com.autoscript.core.project.ProjectAssets
import com.autoscript.vision.util.ModelResolver
import java.io.File
import java.nio.FloatBuffer
import kotlin.math.max
import kotlin.math.min

/**
 * 游戏 HUD 数字小分类器：投影切字 + ONNX 逐字推理。
 * 模型约定与 game-digit-trainer 导出包一致（灰度 NCHW /255）。
 */
class DigitRecognizer(
    private val context: Context,
    private val assets: ProjectAssets,
) {
    private val env: OrtEnvironment = OrtEnvironment.getEnvironment()
    private val sessions = mutableMapOf<String, OrtSession>()
    private val labelsCache = mutableMapOf<String, List<String>>()

    fun recognize(
        frame: ScreenFrame,
        modelPath: String,
        roi: Rect?,
        minConf: Float = 0.5f,
        maxGap: Int = 3,
        manifestPath: String? = null,
    ): DigitResult {
        val onnxPath = ModelResolver.resolveOnnx(assets, modelPath)
        val session = getSession(onnxPath)
        val manifest = DigitManifest.load(assets, onnxPath, manifestPath)
        val labels = loadLabels(onnxPath, manifest)
        val bounds = (roi ?: Rect(0, 0, frame.width, frame.height)).clamp(frame.width, frame.height)
        if (bounds.w <= 1 || bounds.h <= 1) {
            return DigitResult("", emptyList(), 0f)
        }
        val gray = extractGray(frame, bounds)
        val binary = preprocessBinary(gray, manifest)
        val crops = segmentProjection(binary, maxGap)
        if (crops.isEmpty()) {
            // 整块当单字
            val (lab, conf) = inferOne(session, labels, binary, manifest)
            val shown = if (conf >= minConf) lab else "?"
            return DigitResult(
                shown,
                listOf(DigitChar(lab, conf, bounds.x, bounds.y, bounds.w, bounds.h)),
                conf,
            )
        }
        val chars = mutableListOf<DigitChar>()
        val sb = StringBuilder()
        var confSum = 0f
        for (c in crops) {
            val patch = crop2d(binary, c.x, c.y, c.w, c.h)
            val (lab, conf) = inferOne(session, labels, patch, manifest)
            confSum += conf
            chars.add(DigitChar(lab, conf, bounds.x + c.x, bounds.y + c.y, c.w, c.h))
            sb.append(if (conf >= minConf) displayLabel(lab) else "?")
        }
        val mean = if (chars.isEmpty()) 0f else confSum / chars.size
        return DigitResult(sb.toString(), chars, mean)
    }

    fun release() {
        sessions.values.forEach { runCatching { it.close() } }
        sessions.clear()
        labelsCache.clear()
    }

    private fun inferOne(
        session: OrtSession,
        labels: List<String>,
        gray: Array<ByteArray>,
        manifest: DigitManifest,
    ): Pair<String, Float> {
        val w = manifest.width.coerceAtLeast(8)
        val h = manifest.height.coerceAtLeast(8)
        val tensorData = FloatArray(w * h)
        resizeNorm(gray, w, h, tensorData)
        val inputName = session.inputNames.iterator().next()
        val shape = longArrayOf(1, 1, h.toLong(), w.toLong())
        OnnxTensor.createTensor(env, FloatBuffer.wrap(tensorData), shape).use { tensor ->
            session.run(mapOf(inputName to tensor)).use { result ->
                val raw = result[0].value
                val logits = when (raw) {
                    is Array<*> -> {
                        @Suppress("UNCHECKED_CAST")
                        val row = (raw as Array<FloatArray>)[0]
                        row
                    }
                    is FloatArray -> raw
                    else -> throw IllegalStateException("未知 ONNX 输出类型: ${raw?.javaClass}")
                }
                var best = 0
                var bestV = logits[0]
                for (i in 1 until logits.size) {
                    if (logits[i] > bestV) {
                        bestV = logits[i]
                        best = i
                    }
                }
                // softmax conf approx via max after exp-normalize
                var sum = 0.0
                val exps = DoubleArray(logits.size)
                for (i in logits.indices) {
                    exps[i] = kotlin.math.exp((logits[i] - bestV).toDouble())
                    sum += exps[i]
                }
                val conf = (exps[best] / sum).toFloat()
                val lab = labels.getOrElse(best) { best.toString() }
                return lab to conf
            }
        }
    }

    private data class Crop(val x: Int, val y: Int, val w: Int, val h: Int)

    private fun segmentProjection(binary: Array<ByteArray>, maxGap: Int): List<Crop> {
        val h = binary.size
        if (h == 0) return emptyList()
        val w = binary[0].size
        val colSum = IntArray(w)
        for (y in 0 until h) {
            val row = binary[y]
            for (x in 0 until w) {
                if ((row[x].toInt() and 0xFF) > 0) colSum[x]++
            }
        }
        val gaps = mutableListOf<Pair<Int, Int>>()
        var inGap = false
        var start = 0
        for (i in 0 until w) {
            if (colSum[i] == 0) {
                if (!inGap) {
                    inGap = true
                    start = i
                }
            } else if (inGap) {
                gaps.add(start to i)
                inGap = false
            }
        }
        if (inGap) gaps.add(start to w)
        val cuts = mutableListOf(0)
        for ((a, b) in gaps) {
            if (b - a >= maxGap) {
                val mid = (a + b) / 2
                if (mid > cuts.last()) cuts.add(mid)
            }
        }
        cuts.add(w)
        val out = mutableListOf<Crop>()
        for (i in 0 until cuts.size - 1) {
            val x0 = cuts[i]
            val x1 = cuts[i + 1]
            if (x1 - x0 < 2) continue
            var y0 = h
            var y1 = 0
            var area = 0
            for (y in 0 until h) {
                for (x in x0 until x1) {
                    if ((binary[y][x].toInt() and 0xFF) > 0) {
                        area++
                        y0 = min(y0, y)
                        y1 = max(y1, y + 1)
                    }
                }
            }
            if (area < 8 || y1 <= y0) continue
            out.add(Crop(x0, y0, x1 - x0, y1 - y0))
        }
        return out
    }

    private fun extractGray(frame: ScreenFrame, roi: Rect): Array<ByteArray> {
        val out = Array(roi.h) { ByteArray(roi.w) }
        for (y in 0 until roi.h) {
            val sy = roi.y + y
            for (x in 0 until roi.w) {
                val sx = roi.x + x
                val i = (sy * frame.width + sx) * 3
                val b = frame.bgr[i].toInt() and 0xFF
                val g = frame.bgr[i + 1].toInt() and 0xFF
                val r = frame.bgr[i + 2].toInt() and 0xFF
                out[y][x] = ((b * 29 + g * 150 + r * 77) shr 8).toByte()
            }
        }
        return out
    }

    private fun preprocessBinary(gray: Array<ByteArray>, manifest: DigitManifest): Array<ByteArray> {
        val h = gray.size
        val w = gray[0].size
        var work = Array(h) { y -> gray[y].copyOf() }
        if (manifest.binarize == "otsu") {
            work = otsu(work)
        } else if (manifest.binarize == "adaptive") {
            work = adaptive(work)
        }
        if (manifest.invert) {
            for (y in 0 until h) {
                for (x in 0 until w) {
                    work[y][x] = (255 - (work[y][x].toInt() and 0xFF)).toByte()
                }
            }
        }
        // Prefer white digits on black
        if (manifest.binarize != "none") {
            var sum = 0L
            var n = 0
            for (y in 0 until h) {
                for (x in 0 until w) {
                    sum += work[y][x].toInt() and 0xFF
                    n++
                }
            }
            if (n > 0 && sum / n > 127) {
                for (y in 0 until h) {
                    for (x in 0 until w) {
                        work[y][x] = (255 - (work[y][x].toInt() and 0xFF)).toByte()
                    }
                }
            }
        }
        return work
    }

    private fun otsu(gray: Array<ByteArray>): Array<ByteArray> {
        val hist = IntArray(256)
        val h = gray.size
        val w = gray[0].size
        for (y in 0 until h) {
            for (x in 0 until w) {
                hist[gray[y][x].toInt() and 0xFF]++
            }
        }
        val total = h * w
        var sum = 0.0
        for (i in 0 until 256) sum += i * hist[i]
        var sumB = 0.0
        var wB = 0
        var maxVar = -1.0
        var threshold = 127
        for (t in 0 until 256) {
            wB += hist[t]
            if (wB == 0) continue
            val wF = total - wB
            if (wF == 0) break
            sumB += t * hist[t]
            val mB = sumB / wB
            val mF = (sum - sumB) / wF
            val diff = mB - mF
            val between = wB.toDouble() * wF * diff * diff
            if (between > maxVar) {
                maxVar = between
                threshold = t
            }
        }
        return Array(h) { y ->
            ByteArray(w) { x ->
                if ((gray[y][x].toInt() and 0xFF) > threshold) 255.toByte() else 0
            }
        }
    }

    private fun adaptive(gray: Array<ByteArray>): Array<ByteArray> {
        // 简化：用全局均值近似
        val h = gray.size
        val w = gray[0].size
        var sum = 0L
        for (y in 0 until h) for (x in 0 until w) sum += gray[y][x].toInt() and 0xFF
        val mean = (sum / (h * w)).toInt()
        return Array(h) { y ->
            ByteArray(w) { x ->
                if ((gray[y][x].toInt() and 0xFF) > mean - 5) 255.toByte() else 0
            }
        }
    }

    private fun crop2d(src: Array<ByteArray>, x: Int, y: Int, cw: Int, ch: Int): Array<ByteArray> {
        return Array(ch) { yy ->
            ByteArray(cw) { xx -> src[y + yy][x + xx] }
        }
    }

    private fun resizeNorm(src: Array<ByteArray>, dw: Int, dh: Int, out: FloatArray) {
        val sh = src.size
        val sw = src[0].size
        var i = 0
        for (y in 0 until dh) {
            val sy = (y * sh) / dh
            for (x in 0 until dw) {
                val sx = (x * sw) / dw
                out[i++] = (src[sy][sx].toInt() and 0xFF) / 255f
            }
        }
    }

    private fun getSession(assetPath: String): OrtSession =
        sessions.getOrPut(assetPath) {
            val file = copyAssetToCache(assetPath)
            val opts = OrtSession.SessionOptions()
            opts.setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
            opts.setIntraOpNumThreads(2)
            env.createSession(file.absolutePath, opts)
        }

    private fun copyAssetToCache(path: String): File {
        val out = File(context.cacheDir, "onnx_digit/${path.replace('/', '_')}")
        if (!out.exists() || out.length() == 0L) {
            out.parentFile?.mkdirs()
            out.writeBytes(assets.readBytes(path))
        }
        // also copy labels/manifest siblings if present
        return out
    }

    private fun loadLabels(onnxPath: String, manifest: DigitManifest): List<String> {
        labelsCache[onnxPath]?.let { return it }
        if (manifest.classes.isNotEmpty()) {
            labelsCache[onnxPath] = manifest.classes
            return manifest.classes
        }
        val lp = ModelResolver.labelsPathForModel(onnxPath)
        val labels = if (assets.exists(lp)) {
            String(assets.readBytes(lp), Charsets.UTF_8)
                .lines()
                .map { it.trim() }
                .filter { it.isNotEmpty() }
        } else {
            (0..9).map { it.toString() }
        }
        labelsCache[onnxPath] = labels
        return labels
    }

    private fun displayLabel(lab: String): String = when (lab) {
        "wan", "万" -> "万"
        "yi", "亿" -> "亿"
        "comma" -> ","
        "slash" -> "/"
        "percent" -> "%"
        "colon" -> ":"
        else -> lab
    }
}
