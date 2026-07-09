package com.autoscript.vision.yolo

import android.content.Context
import com.autoscript.core.project.PerfConfig
import com.autoscript.core.project.ProjectAssets

object YoloDetectorFactory {
    fun create(
        context: Context,
        assets: ProjectAssets,
        imgsz: Int,
        perf: PerfConfig,
    ): YoloDetector = when (perf.yoloBackend.lowercase()) {
        "ncnn" -> NcnnYoloDetector(context, assets, imgsz, perf)
        else -> OnnxYoloDetector(context, assets, imgsz, perf)
    }
}
