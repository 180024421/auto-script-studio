package com.autoscript.vision.yolo

import android.content.Context
import com.autoscript.core.model.Detection
import com.autoscript.core.model.Rect
import com.autoscript.core.model.ScreenFrame
import com.autoscript.core.project.PerfConfig
import com.autoscript.core.project.ProjectAssets

/**
 * NCNN 推理占位：已导出 .ncnn.param/.bin 时仍回退 ONNX，待 NDK 集成后切换。
 * 导出：python tools/export_yolo_ncnn.py --pt best.pt --out models/ui
 */
class NcnnYoloDetector(
    context: Context,
    assets: ProjectAssets,
    imgsz: Int,
    perf: PerfConfig,
) : YoloDetector {

    private val fallback = OnnxYoloDetector(context, assets, imgsz, perf)
    private var warned = false

    override fun detect(
        frame: ScreenFrame,
        modelPath: String,
        conf: Float,
        className: String,
        roi: Rect?,
        maxDet: Int,
        maxMaskDecode: Int,
    ): List<Detection> {
        if (!warned) {
            warned = true
            android.util.Log.w(
                "NcnnYolo",
                "yolo_backend=ncnn 但 NCNN 运行时尚未集成，已回退 ONNX。",
            )
        }
        return fallback.detect(frame, modelPath, conf, className, roi, maxDet, maxMaskDecode)
    }

    override fun release() = fallback.release()
}
