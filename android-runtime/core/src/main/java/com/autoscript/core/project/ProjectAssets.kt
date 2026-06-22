package com.autoscript.core.project

import android.content.Context
import org.json.JSONObject
import java.io.InputStream

data class ProjectConfig(
    val name: String,
    val packageId: String,
    val entry: String,
    val scriptLanguage: String,
    val versionCode: Int,
    val versionName: String,
    val defaultIntervalMs: Int,
    val defaultYoloConf: Float,
    val ocrMode: String,
    val defaultYoloModel: String?,
    val autoRun: Boolean = false,
    val screenshotMode: String = "media_projection",
    val inputMode: String = "auto",
) {
    fun usesLua(): Boolean = when (scriptLanguage.lowercase()) {
        "lua" -> true
        "yaml", "yml" -> false
        else -> entry.lowercase().endsWith(".lua")
    }
}

class ProjectAssets(private val context: Context) {

    private val root = "project"

    fun loadConfig(): ProjectConfig {
        val json = readText("project.json")
        val obj = JSONObject(json)
        val runtime = obj.optJSONObject("runtime")
        return ProjectConfig(
            name = obj.getString("name"),
            packageId = obj.getString("package_id"),
            entry = obj.optString("entry", "main.lua"),
            scriptLanguage = obj.optString("script_language", "auto"),
            versionCode = obj.optInt("version_code", 1),
            versionName = obj.optString("version_name", "1.0.0"),
            defaultIntervalMs = runtime?.optInt("default_interval_ms", 300) ?: 300,
            defaultYoloConf = runtime?.optDouble("default_yolo_conf", 0.35)?.toFloat() ?: 0.35f,
            ocrMode = runtime?.optString("ocr_mode", "lazy") ?: "lazy",
            defaultYoloModel = runtime?.optString("default_yolo_model")?.takeIf { it.isNotBlank() },
            autoRun = runtime?.optBoolean("auto_run", false) ?: false,
            screenshotMode = runtime?.optString("screenshot_mode", "media_projection") ?: "media_projection",
            inputMode = runtime?.optString("input_mode", "auto") ?: "auto",
        )
    }

    fun readEntryYaml(): String = readText(loadConfig().entry)

    fun readEntryScript(): String = readText(loadConfig().entry)

    fun readYaml(path: String): String = readText(path)

    fun readBytes(path: String): ByteArray =
        open(path).use { it.readBytes() }

    fun exists(path: String): Boolean = try {
        open(path).close()
        true
    } catch (_: Exception) {
        false
    }

    fun appContext(): Context = context.applicationContext

    fun list(relativeDir: String): List<String> {
        return context.assets.list("$root/$relativeDir")?.toList().orEmpty()
    }

    private fun readText(relative: String): String =
        open(relative).bufferedReader().use { it.readText() }

    private fun open(relative: String): InputStream {
        val path = "$root/${relative.trimStart('/')}"
        return context.assets.open(path)
    }
}
