package com.autoscript.vision.digit

import com.autoscript.core.project.ProjectAssets
import org.json.JSONObject

data class DigitManifest(
    val width: Int = 32,
    val height: Int = 32,
    val invert: Boolean = false,
    val binarize: String = "otsu",
    val grayscale: Boolean = true,
    val classes: List<String> = emptyList(),
) {
    companion object {
        fun load(assets: ProjectAssets, onnxPath: String, explicit: String? = null): DigitManifest {
            val candidates = buildList {
                if (!explicit.isNullOrBlank()) add(explicit.trim())
                val base = if (onnxPath.endsWith(".onnx")) onnxPath.removeSuffix(".onnx") else onnxPath
                add("$base.manifest.json")
                val dir = onnxPath.substringBeforeLast('/', missingDelimiterValue = "")
                if (dir.isNotEmpty()) {
                    add("$dir/manifest.json")
                    add("$dir/digits.manifest.json")
                } else {
                    add("manifest.json")
                    add("models/manifest.json")
                }
            }.distinct()
            for (path in candidates) {
                if (!assets.exists(path)) continue
                return runCatching {
                    parse(String(assets.readBytes(path), Charsets.UTF_8))
                }.getOrNull() ?: continue
            }
            return DigitManifest()
        }

        private fun parse(raw: String): DigitManifest {
            val obj = JSONObject(raw)
            val input = obj.optJSONObject("input")
            val prep = obj.optJSONObject("preprocess")
            val classesArr = obj.optJSONArray("classes")
            val classes = mutableListOf<String>()
            if (classesArr != null) {
                for (i in 0 until classesArr.length()) {
                    classes.add(classesArr.optString(i))
                }
            }
            return DigitManifest(
                width = input?.optInt("width", 32) ?: obj.optInt("input_width", 32),
                height = input?.optInt("height", 32) ?: obj.optInt("input_height", 32),
                invert = prep?.optBoolean("invert", false) ?: false,
                binarize = prep?.optString("binarize", "otsu") ?: "otsu",
                grayscale = prep?.optBoolean("grayscale", true) ?: true,
                classes = classes,
            )
        }
    }
}
