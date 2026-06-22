package com.autoscript.vision.util

import com.autoscript.core.project.ProjectAssets

object ModelResolver {

    fun resolveOnnx(assets: ProjectAssets, path: String): String {
        val p = path.trim().trimEnd('/')
        val candidates = listOf(
            p,
            "$p.onnx",
            if (p.endsWith(".onnx")) p else "$p.onnx",
        ).distinct()
        for (c in candidates) {
            if (assets.exists(c)) return c
        }
        throw IllegalStateException("ONNX 模型不存在: $path（已尝试 ${candidates.joinToString()}）")
    }

    fun labelsPathForModel(onnxPath: String): String {
        return when {
            onnxPath.endsWith(".onnx") -> onnxPath.removeSuffix(".onnx") + ".labels"
            else -> "$onnxPath.labels"
        }
    }
}
