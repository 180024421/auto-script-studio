package com.autoscript.script.saocheng

data class YoloDetection(
    val classId: Int,
    val className: String,
    val confidence: Float,
    val x1: Int,
    val y1: Int,
    val x2: Int,
    val y2: Int,
) {
    val centerX: Int get() = (x1 + x2) / 2
    val centerY: Int get() = (y1 + y2) / 2
    val width: Int get() = (x2 - x1).coerceAtLeast(0)
    val height: Int get() = (y2 - y1).coerceAtLeast(0)

    fun containsPoint(x: Int, y: Int, margin: Int = 0): Boolean =
        x1 - margin <= x && x <= x2 + margin && y1 - margin <= y && y <= y2 + margin

    fun iouWith(other: YoloDetection): Float {
        val ix1 = maxOf(x1, other.x1)
        val iy1 = maxOf(y1, other.y1)
        val ix2 = minOf(x2, other.x2)
        val iy2 = minOf(y2, other.y2)
        val iw = (ix2 - ix1).coerceAtLeast(0)
        val ih = (iy2 - iy1).coerceAtLeast(0)
        val inter = iw * ih
        if (inter <= 0) return 0f
        val union = width * height + other.width * other.height - inter
        return if (union > 0) inter.toFloat() / union else 0f
    }
}

fun findBest(detections: List<YoloDetection>, className: String): YoloDetection? =
    detections.filter { it.className == className }.maxByOrNull { it.confidence }

fun findAll(detections: List<YoloDetection>, className: String): List<YoloDetection> =
    detections.filter { it.className == className }

fun hasClass(detections: List<YoloDetection>, className: String, minConf: Float = 0f): Boolean =
    detections.any { it.className == className && it.confidence >= minConf }
