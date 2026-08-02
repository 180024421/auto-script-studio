package com.autoscript.script.saocheng

import android.graphics.Bitmap
import android.graphics.Matrix

/**
 * 模型按 1280×720 横屏训练。竖屏/横屏多种方式推理，自动选识别到游戏 UI 最多的一种。
 */
object YoloScreenMapper {

    private val GAME_CLASSES = setOf(
        "主城", "地图", "世界", "血战", "换页", "扫城", "国战中", "单挑", "快进", "胜利",
        "血战-展开", "血战-关闭", "停止血战", "关闭", "叉", "确定", "召集", "撤退", "返回",
    )

    /** 最近一次推理说明，供日志/预览显示 */
    @Volatile
    var lastDebugInfo: String = ""

    fun detectOnScreen(
        yolo: YoloDetector,
        screen: Bitmap,
        conf: Float = FlowConstants.YOLO_CONF,
    ): List<YoloDetection> {
        val passes = mutableListOf<Pair<String, List<YoloDetection>>>()

        passes.add("原图" to yolo.detect(screen, conf))

        if (screen.height > screen.width) {
            passes.add("顺90°" to detectRotated(yolo, screen, 90f, conf))
            passes.add("逆90°" to detectRotated(yolo, screen, -90f, conf))
        } else if (screen.width > screen.height) {
            // 横屏但非 1280×720 时也尝试旋转（部分云手机方向相反）
            passes.add("顺90°" to detectRotated(yolo, screen, 90f, conf))
        }

        val best = selectBest(passes)
        lastDebugInfo = buildString {
            append("${screen.width}x${screen.height} 选用[${best.first}] ")
            append("共${best.second.size}个")
            best.second.sortedByDescending { it.confidence }.take(6).forEach { d ->
                append(" | ${d.className} ${"%.2f".format(d.confidence)}")
            }
            if (passes.size > 1) {
                append(" （")
                passes.forEach { (tag, dets) ->
                    append("$tag:${dets.size} ")
                }
                append("）")
            }
        }
        return best.second
    }

    private fun selectBest(passes: List<Pair<String, List<YoloDetection>>>): Pair<String, List<YoloDetection>> {
        fun gameScore(dets: List<YoloDetection>): Float {
            return dets.filter { it.className in GAME_CLASSES }
                .maxOfOrNull { it.confidence } ?: 0f
        }

        val withGame = passes.filter { (_, dets) -> gameScore(dets) > 0f }
        if (withGame.isNotEmpty()) {
            return withGame.maxByOrNull { (_, dets) -> gameScore(dets) }!!
        }
        return passes.maxByOrNull { (_, dets) -> dets.size } ?: ("原图" to emptyList())
    }

    private fun detectRotated(
        yolo: YoloDetector,
        screen: Bitmap,
        degrees: Float,
        conf: Float,
    ): List<YoloDetection> {
        val rotate = Matrix().apply { postRotate(degrees) }
        val rotated = Bitmap.createBitmap(screen, 0, 0, screen.width, screen.height, rotate, true)
        return try {
            val inverse = Matrix()
            if (!rotate.invert(inverse)) return emptyList()
            yolo.detect(rotated, conf).map { mapDetection(inverse, it, screen.width, screen.height) }
        } finally {
            if (rotated !== screen) rotated.recycle()
        }
    }

    private fun mapDetection(inv: Matrix, det: YoloDetection, maxW: Int, maxH: Int): YoloDetection {
        val pts = floatArrayOf(
            det.x1.toFloat(), det.y1.toFloat(),
            det.x2.toFloat(), det.y2.toFloat(),
        )
        inv.mapPoints(pts)
        val xs = floatArrayOf(pts[0], pts[2])
        val ys = floatArrayOf(pts[1], pts[3])
        return det.copy(
            x1 = xs.min().toInt().coerceIn(0, maxW - 1),
            y1 = ys.min().toInt().coerceIn(0, maxH - 1),
            x2 = xs.max().toInt().coerceIn(0, maxW - 1),
            y2 = ys.max().toInt().coerceIn(0, maxH - 1),
        )
    }
}
