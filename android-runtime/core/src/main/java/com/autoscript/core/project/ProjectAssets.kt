package com.autoscript.core.project

import android.content.Context
import com.autoscript.core.update.ProjectUpdateManager
import org.json.JSONObject
import java.io.File
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
    val license: LicenseConfig = LicenseConfig(),
    val update: UpdateConfig = UpdateConfig(),
    val schedule: ScheduleConfig = ScheduleConfig(),
    val boot: BootConfig = BootConfig(),
    val perf: PerfConfig = PerfConfig(),
) {
    fun usesLua(): Boolean = when (scriptLanguage.lowercase()) {
        "lua" -> true
        "yaml", "yml" -> false
        else -> entry.lowercase().endsWith(".lua")
    }
}

class ProjectAssets(private val context: Context) {

    private val root = "project"
    private var updateManager: ProjectUpdateManager? = null

    fun loadConfig(): ProjectConfig {
        val json = readText("project.json")
        val obj = JSONObject(json)
        val runtime = obj.optJSONObject("runtime")
        val licenseObj = obj.optJSONObject("license")
        val updateObj = obj.optJSONObject("update")
        val scheduleObj = obj.optJSONObject("schedule")
        val bootObj = obj.optJSONObject("boot")
        val perfObj = runtime?.optJSONObject("perf") ?: obj.optJSONObject("perf")
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
            license = LicenseConfig(
                enabled = licenseObj?.optBoolean("enabled", false) ?: false,
                apiBase = licenseObj?.optString("api_base", "") ?: "",
                appName = licenseObj?.optString("app_name", "") ?: "",
                skipOnOffline = licenseObj?.optBoolean("skip_on_offline", false) ?: false,
            ),
            update = UpdateConfig(
                enabled = updateObj?.optBoolean("enabled", false) ?: false,
                manifestUrl = updateObj?.optString("manifest_url", "") ?: "",
                checkOnStart = updateObj?.optBoolean("check_on_start", true) ?: true,
                allowLocalImport = updateObj?.optBoolean("allow_local_import", true) ?: true,
                channel = updateObj?.optString("channel", "default") ?: "default",
            ),
            schedule = ScheduleConfig(
                enabled = scheduleObj?.optBoolean("enabled", false) ?: false,
                dailyTime = scheduleObj?.optString("daily_time", "") ?: "",
            ),
            boot = BootConfig(
                autoStart = bootObj?.optBoolean("auto_start", false) ?: false,
            ),
            perf = PerfConfig(
                opencvMobile = perfObj?.optBoolean("opencv_mobile", false) ?: false,
                yoloNnapi = perfObj?.optBoolean("yolo_nnapi", true) ?: true,
                yoloImgsz = perfObj?.optInt("yolo_imgsz", 320) ?: 320,
                captureCacheTtlMs = perfObj?.optLong("capture_cache_ttl_ms", 80L) ?: 80L,
            ),
        )
    }

    fun checkForUpdates(): Boolean {
        val cfg = loadConfig()
        val mgr = ProjectUpdateManager(context, cfg.update, cfg.versionCode)
        updateManager = mgr
        if (!mgr.isActive()) return false
        return mgr.maybeUpdate()
    }

    fun peekAvailableUpdate(): org.json.JSONObject? {
        val cfg = loadConfig()
        val mgr = updateManager ?: ProjectUpdateManager(context, cfg.update, cfg.versionCode).also { updateManager = it }
        return mgr.peekAvailableUpdate()
    }

    fun applyAvailableUpdate(manifest: org.json.JSONObject): Boolean {
        val cfg = loadConfig()
        val mgr = updateManager ?: ProjectUpdateManager(context, cfg.update, cfg.versionCode).also { updateManager = it }
        return mgr.applyManifest(manifest)
    }

    fun importUpdateZip(zipFile: File): Boolean {
        val cfg = loadConfig()
        val mgr = ProjectUpdateManager(context, cfg.update, cfg.versionCode)
        updateManager = mgr
        return mgr.importLocalZip(zipFile)
    }

    fun clearUpdateOverlay(): Boolean {
        val cfg = loadConfig()
        val mgr = updateManager ?: ProjectUpdateManager(context, cfg.update, cfg.versionCode)
        updateManager = mgr
        return mgr.clearOverlay()
    }

    fun overlayVersionInfo(): Pair<Int, String> {
        val cfg = loadConfig()
        val mgr = updateManager ?: ProjectUpdateManager(context, cfg.update, cfg.versionCode)
        return mgr.effectiveVersionCode() to mgr.overlayVersionName()
    }

    fun readEntryYaml(): String = readText(loadConfig().entry)

    fun readEntryScript(): String = readText(loadConfig().entry)

    fun readYaml(path: String): String = readText(path)

    fun readBytes(path: String): ByteArray {
        overlayFile(path)?.let { return it.readBytes() }
        return open(path).use { it.readBytes() }
    }

    fun exists(path: String): Boolean {
        if (overlayFile(path) != null) return true
        return try {
            open(path).close()
            true
        } catch (_: Exception) {
            false
        }
    }

    fun appContext(): Context = context.applicationContext

    fun list(relativeDir: String): List<String> {
        return context.assets.list("$root/$relativeDir")?.toList().orEmpty()
    }

    private fun ensureUpdateManager(): ProjectUpdateManager {
        updateManager?.let { return it }
        val json = open("project.json").bufferedReader().use { it.readText() }
        val obj = JSONObject(json)
        val updateObj = obj.optJSONObject("update")
        val updateCfg = UpdateConfig(
            enabled = updateObj?.optBoolean("enabled", false) ?: false,
            manifestUrl = updateObj?.optString("manifest_url", "") ?: "",
            checkOnStart = updateObj?.optBoolean("check_on_start", true) ?: true,
            allowLocalImport = updateObj?.optBoolean("allow_local_import", true) ?: true,
            channel = updateObj?.optString("channel", "default") ?: "default",
        )
        val versionCode = obj.optInt("version_code", 1)
        return ProjectUpdateManager(context, updateCfg, versionCode).also { updateManager = it }
    }

    private fun overlayFile(relative: String): File? {
        val rel = relative.trimStart('/')
        return ensureUpdateManager().overlayFile(rel)
    }

    private fun readText(relative: String): String {
        overlayFile(relative)?.let { return it.readText() }
        return open(relative).bufferedReader().use { it.readText() }
    }

    private fun open(relative: String): InputStream {
        val path = "$root/${relative.trimStart('/')}"
        return context.assets.open(path)
    }
}
