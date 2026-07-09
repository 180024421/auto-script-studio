package com.autoscript.vision.yolo

import android.content.Context
import com.autoscript.core.model.Detection
import com.autoscript.core.model.Rect
import com.autoscript.core.model.ScreenFrame
import com.autoscript.core.project.PerfConfig
import com.autoscript.core.project.ProjectAssets
import com.autoscript.vision.util.ModelResolver
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import java.io.File
import java.nio.FloatBuffer
import kotlin.math.exp
import kotlin.math.max
import kotlin.math.min

/**
 * YOLOv8/v11 ONNX 推理（detect + seg），ONNX Runtime（可选 NNAPI，失败自动回退 CPU）。
 * seg 极速：仅对前 [maxMaskDecode] 个 NMS 结果解码掩码质心（bbox 内采样，无全图 logits）。
 */
class OnnxYoloDetector(
    private val context: Context,
    private val assets: ProjectAssets,
    private val imgsz: Int = 320,
    private val perf: PerfConfig = PerfConfig(),
) : YoloDetector {

    private val useNnapi = perf.yoloNnapi
    private val env: OrtEnvironment = OrtEnvironment.getEnvironment()
    private val sessions = mutableMapOf<String, OrtSession>()
    private val labelsCache = mutableMapOf<String, List<String>>()
    private val nnapiDisabled = mutableSetOf<String>()
    private val preprocessBuffer = FloatArray(3 * imgsz * imgsz)

    override fun detect(
        frame: ScreenFrame,
        modelPath: String,
        conf: Float,
        className: String,
        roi: Rect?,
        maxDet: Int,
        maxMaskDecode: Int,
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

        return try {
            val inputName = session.inputNames.iterator().next()
            preprocess(frame, x0, y0, rw, rh)
            val inputShape = longArrayOf(1, 3, imgsz.toLong(), imgsz.toLong())
            OnnxTensor.createTensor(env, FloatBuffer.wrap(preprocessBuffer), inputShape).use { tensor ->
                session.run(mapOf(inputName to tensor)).use { result ->
                    val detRaw = result[0].value
                    val protoRaw = if (result.size() > 1) result[1].value else null
                    val rows = to2dFloatArray(detRaw)
                    val proto = parseProtoMask(protoRaw)
                    val isSeg = proto != null
                    val nm = proto?.nm ?: 0
                    postprocess(
                        rows,
                        conf,
                        className,
                        labels,
                        x0,
                        y0,
                        rw,
                        rh,
                        maxDet,
                        isSeg,
                        nm,
                        proto,
                        maxMaskDecode.coerceAtLeast(0),
                    )
                }
            }
        } catch (e: Exception) {
            if (useNnapi && onnxPath !in nnapiDisabled) {
                nnapiDisabled.add(onnxPath)
                sessions.remove(onnxPath)?.let { runCatching { it.close() } }
                android.util.Log.w("OnnxYolo", "NNAPI 推理失败，回退 CPU: ${e.message}")
                return detect(frame, modelPath, conf, className, roi, maxDet, maxMaskDecode)
            }
            throw e
        }
    }

    override fun release() {
        sessions.values.forEach { runCatching { it.close() } }
        sessions.clear()
    }

    private fun getSession(assetPath: String): OrtSession =
        sessions.getOrPut(assetPath) {
            val file = copyAssetToCache(assetPath)
            val opts = OrtSession.SessionOptions()
            opts.setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
            opts.setIntraOpNumThreads(4)
            if (useNnapi && assetPath !in nnapiDisabled) {
                runCatching { opts.addNnapi() }
            }
            env.createSession(file.absolutePath, opts)
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

    private fun preprocess(frame: ScreenFrame, x0: Int, y0: Int, rw: Int, rh: Int) {
        val plane = imgsz * imgsz
        for (dy in 0 until imgsz) {
            val sy = y0 + (dy * rh / imgsz)
            for (dx in 0 until imgsz) {
                val sx = x0 + (dx * rw / imgsz)
                val base = dy * imgsz + dx
                if (sx >= frame.width || sy >= frame.height) {
                    preprocessBuffer[base] = 0f
                    preprocessBuffer[plane + base] = 0f
                    preprocessBuffer[2 * plane + base] = 0f
                    continue
                }
                val j = (sy * frame.width + sx) * 3
                preprocessBuffer[base] = (frame.bgr[j + 2].toInt() and 0xFF) / 255f
                preprocessBuffer[plane + base] = (frame.bgr[j + 1].toInt() and 0xFF) / 255f
                preprocessBuffer[2 * plane + base] = (frame.bgr[j].toInt() and 0xFF) / 255f
            }
        }
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

    private data class ProtoMask(val nm: Int, val mh: Int, val mw: Int, val data: FloatArray)

    private data class RawDet(
        val className: String,
        val confidence: Float,
        val rect: Rect,
        val cxImg: Float,
        val cyImg: Float,
        val wImg: Float,
        val hImg: Float,
        val maskCoeffs: FloatArray?,
    )

    @Suppress("UNCHECKED_CAST")
    private fun parseProtoMask(raw: Any?): ProtoMask? {
        if (raw == null) return null
        val batch = when (raw) {
            is Array<*> -> if (raw.isNotEmpty() && raw[0] is Array<*>) raw[0] as Array<*> else return null
            else -> return null
        }
        if (batch.isEmpty() || batch[0] !is Array<*>) return null
        val nm = batch.size
        val plane0 = batch[0] as Array<*>
        if (plane0.isEmpty() || plane0[0] !is FloatArray) return null
        val mh = plane0.size
        val mw = (plane0[0] as FloatArray).size
        val data = FloatArray(nm * mh * mw)
        for (k in 0 until nm) {
            val plane = batch[k] as Array<FloatArray>
            for (y in 0 until mh) {
                System.arraycopy(plane[y], 0, data, k * mh * mw + y * mw, mw)
            }
        }
        return ProtoMask(nm, mh, mw, data)
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
        isSeg: Boolean,
        nm: Int,
        proto: ProtoMask?,
        maxMaskDecode: Int,
    ): List<Detection> {
        if (matrix.isEmpty()) return emptyList()
        val features = matrix.size
        val anchors = matrix[0].size
        if (features < 5) return emptyList()
        val numClasses = when {
            isSeg && labels.isNotEmpty() -> labels.size
            isSeg -> maxOf(1, features - 4 - nm)
            else -> features - 4
        }
        if (numClasses <= 0) return emptyList()

        val scaleX = roiW.toFloat() / imgsz
        val scaleY = roiH.toFloat() / imgsz
        val raw = mutableListOf<RawDet>()

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

            val cxImg = matrix[0][i]
            val cyImg = matrix[1][i]
            val wImg = matrix[2][i]
            val hImg = matrix[3][i]
            val cx = cxImg * scaleX + offsetX
            val cy = cyImg * scaleY + offsetY
            val w = wImg * scaleX
            val h = hImg * scaleY
            val x = (cx - w / 2f).toInt()
            val y = (cy - h / 2f).toInt()
            val coeffs = if (isSeg) {
                FloatArray(nm) { k -> matrix[4 + numClasses + k][i] }
            } else {
                null
            }
            raw.add(
                RawDet(
                    className = name,
                    confidence = bestScore,
                    rect = Rect(x, y, w.toInt().coerceAtLeast(1), h.toInt().coerceAtLeast(1)),
                    cxImg = cxImg,
                    cyImg = cyImg,
                    wImg = wImg,
                    hImg = hImg,
                    maskCoeffs = coeffs,
                ),
            )
        }
        return nms(raw, 0.45f)
            .take(maxDet)
            .mapIndexed { index, det ->
                toDetection(
                    det,
                    proto,
                    offsetX,
                    offsetY,
                    roiW,
                    roiH,
                    decodeMask = index < maxMaskDecode,
                )
            }
    }

    private fun toDetection(
        raw: RawDet,
        proto: ProtoMask?,
        offsetX: Int,
        offsetY: Int,
        roiW: Int,
        roiH: Int,
        decodeMask: Boolean,
    ): Detection {
        if (!decodeMask || raw.maskCoeffs == null || proto == null) {
            return Detection(raw.className, raw.confidence, raw.rect)
        }
        val centroid = decodeMaskCentroid(
            raw.maskCoeffs,
            proto,
            raw.cxImg,
            raw.cyImg,
            raw.wImg,
            raw.hImg,
            offsetX,
            offsetY,
            roiW,
            roiH,
        ) ?: return Detection(raw.className, raw.confidence, raw.rect)
        return Detection(
            className = raw.className,
            confidence = raw.confidence,
            rect = raw.rect,
            hasMask = true,
            maskCenterX = centroid.first,
            maskCenterY = centroid.second,
            maskArea = centroid.third,
        )
    }

    /** 仅在检测框对应 proto 区域采样，避免分配全图 logits。 */
    private fun decodeMaskCentroid(
        coeffs: FloatArray,
        proto: ProtoMask,
        cxImg: Float,
        cyImg: Float,
        wImg: Float,
        hImg: Float,
        offsetX: Int,
        offsetY: Int,
        roiW: Int,
        roiH: Int,
        thresh: Float = 0.5f,
    ): Triple<Int, Int, Int>? {
        val mh = proto.mh
        val mw = proto.mw
        val planeStride = mh * mw

        val bx1 = (cxImg - wImg / 2f).toInt().coerceIn(0, imgsz - 1)
        val by1 = (cyImg - hImg / 2f).toInt().coerceIn(0, imgsz - 1)
        val bx2 = (cxImg + wImg / 2f).toInt().coerceIn(0, imgsz - 1)
        val by2 = (cyImg + hImg / 2f).toInt().coerceIn(0, imgsz - 1)
        if (bx2 < bx1 || by2 < by1) return null

        var sumX = 0L
        var sumY = 0L
        var count = 0
        val step = if (perf.yoloSegFast) 2 else 1
        for (py in by1..by2 step step) {
            val sy = (py * mh / imgsz).coerceIn(0, mh - 1)
            val rowBase = sy * mw
            for (px in bx1..bx2 step step) {
                val sx = (px * mw / imgsz).coerceIn(0, mw - 1)
                val idx = rowBase + sx
                var logit = 0f
                for (k in 0 until proto.nm) {
                    logit += coeffs[k] * proto.data[k * planeStride + idx]
                }
                if (sigmoid(logit) < thresh) continue
                sumX += offsetX + (px * roiW / imgsz)
                sumY += offsetY + (py * roiH / imgsz)
                count++
            }
        }
        if (count == 0) return null
        return Triple((sumX / count).toInt(), (sumY / count).toInt(), count * step * step)
    }

    private fun sigmoid(x: Float): Float = 1f / (1f + exp(-x))

    private fun nms(dets: List<RawDet>, iouThresh: Float): List<RawDet> {
        val sorted = dets.sortedByDescending { it.confidence }.toMutableList()
        val kept = mutableListOf<RawDet>()
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
