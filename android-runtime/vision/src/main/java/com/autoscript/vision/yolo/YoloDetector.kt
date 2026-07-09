package com.autoscript.vision.yolo

import com.autoscript.core.model.Detection
import com.autoscript.core.model.Rect
import com.autoscript.core.model.ScreenFrame

/**
 * YOLO 推理接口。NCNN 集成前提供占位实现。
 * 集成路径：tools/export_yolo_ncnn.py → models/xxx.param + xxx.bin → NcnnYoloDetector
 */
interface YoloDetector {
    fun detect(
        frame: ScreenFrame,
        modelPath: String,
        conf: Float = 0.35f,
        className: String = "",
        roi: Rect? = null,
        maxDet: Int = 50,
        maxMaskDecode: Int = 50,
    ): List<Detection>

    fun release()
}

class StubYoloDetector : YoloDetector {
    override fun detect(
        frame: ScreenFrame,
        modelPath: String,
        conf: Float,
        className: String,
        roi: Rect?,
        maxDet: Int,
        maxMaskDecode: Int,
    ): List<Detection> = emptyList()

    override fun release() = Unit
}

object YoloPick {
    fun pick(detections: List<Detection>, policy: String, anchor: Pair<Int, Int>? = null): Detection? {
        if (detections.isEmpty()) return null
        return when (policy.lowercase()) {
            "largest" -> detections.maxByOrNull { it.rect.w * it.rect.h }
            "largest_mask" -> detections.filter { it.hasMask && it.maskArea > 0 }
                .maxByOrNull { it.maskArea }
                ?: detections.maxByOrNull { it.rect.w * it.rect.h }
            "nearest" -> {
                val ax = anchor?.first ?: 0
                val ay = anchor?.second ?: 0
                detections.minByOrNull {
                    val cx = it.rect.x + it.rect.w / 2
                    val cy = it.rect.y + it.rect.h / 2
                    val dx = cx - ax
                    val dy = cy - ay
                    dx * dx + dy * dy
                }
            }
            else -> detections.maxByOrNull { it.confidence }
        }
    }

    fun clickPoint(
        det: Detection,
        frac: Pair<Float, Float> = 0.5f to 0.5f,
        useMaskCenter: Boolean = false,
    ): Pair<Int, Int> {
        if (useMaskCenter && det.hasMask && det.maskCenterX != null && det.maskCenterY != null) {
            return det.maskCenterX to det.maskCenterY!!
        }
        val fx = frac.first.coerceIn(0f, 1f)
        val fy = frac.second.coerceIn(0f, 1f)
        val x = det.rect.x + (det.rect.w * fx).toInt()
        val y = det.rect.y + (det.rect.h * fy).toInt()
        return x to y
    }
}
