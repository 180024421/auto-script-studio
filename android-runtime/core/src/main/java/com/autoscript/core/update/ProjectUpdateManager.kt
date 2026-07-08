package com.autoscript.core.update

import android.content.Context
import com.autoscript.core.log.ScriptLog
import com.autoscript.core.project.UpdateConfig
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.File
import java.io.FileInputStream
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest
import java.util.zip.ZipInputStream

/**
 * 从 jiaoben（run-jane-script）或兼容 manifest 拉取脚本 zip，解压到 files/project_overlay/。
 *
 * 打包 APK 时写入 [UpdateServer] 地址后，热更新检测为内置能力，不依赖 project.json 开关。
 */
class ProjectUpdateManager(
    private val context: Context,
    private val config: UpdateConfig,
    private val apkVersionCode: Int,
) {
    private val overlayRoot: File
        get() = File(context.filesDir, "project_overlay")

    private val prefs by lazy {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
    }

    fun effectiveVersionCode(): Int {
        val overlayVer = prefs.getInt(KEY_OVERLAY_VERSION, 0)
        return maxOf(apkVersionCode, overlayVer)
    }

    fun overlayVersionName(): String =
        prefs.getString(KEY_OVERLAY_VERSION_NAME, "") ?: ""

    fun manifestUrl(): String =
        UpdateServer.manifestUrl().ifBlank { config.manifestUrl.trim() }

    fun isActive(): Boolean = manifestUrl().isNotBlank()

    /** 拉取 manifest，若有比当前更高的 version_code 则返回，否则 null。 */
    fun peekAvailableUpdate(): JSONObject? {
        val url = manifestUrl()
        if (url.isBlank()) return null
        return try {
            val manifest = fetchManifest(url) ?: return null
            UpdateReporter.reportScriptVersion(
                context,
                effectiveVersionCode(),
                overlayVersionName(),
            )
            val remoteVer = manifest.optInt("version_code", 0)
            if (remoteVer <= 0 || remoteVer <= effectiveVersionCode()) return null
            val minApk = manifest.optInt("min_apk_version", 0)
            if (minApk > apkVersionCode) {
                ScriptLog.i("热更新需要 APK v$minApk+，当前 APK v$apkVersionCode")
                return null
            }
            if (manifest.optString("zip_url", "").isBlank()) return null
            manifest
        } catch (e: Exception) {
            ScriptLog.i("检查热更新失败: ${e.message}")
            null
        }
    }

    fun maybeUpdate(): Boolean {
        val manifest = peekAvailableUpdate() ?: return false
        return try {
            applyManifest(manifest, downloadZip = true)
        } catch (e: Exception) {
            ScriptLog.i("脚本热更新失败: ${e.message}")
            false
        }
    }

    fun applyManifest(manifest: JSONObject): Boolean =
        applyManifest(manifest, downloadZip = true)

    fun importLocalZip(zipFile: File): Boolean {
        return try {
            val manifest = JSONObject()
                .put("version_code", effectiveVersionCode() + 1)
                .put("version_name", "local")
                .put("zip_url", "")
            extractZip(zipFile, manifest.optString("sha256", ""))
            saveOverlayMeta(manifest)
            ScriptLog.i("本地脚本包已导入 → v${manifest.getInt("version_code")}")
            true
        } catch (e: Exception) {
            ScriptLog.i("本地导入失败: ${e.message}")
            false
        }
    }

    fun overlayFile(relative: String): File? {
        val f = File(overlayRoot, relative.trimStart('/'))
        return f.takeIf { it.isFile }
    }

    fun clearOverlay(): Boolean {
        if (!overlayRoot.exists()) return false
        overlayRoot.deleteRecursively()
        prefs.edit()
            .remove(KEY_OVERLAY_VERSION)
            .remove(KEY_OVERLAY_VERSION_NAME)
            .remove(KEY_OVERLAY_SHA)
            .apply()
        ScriptLog.i("已清除热更新覆盖层")
        return true
    }

    private fun applyManifest(manifest: JSONObject, downloadZip: Boolean): Boolean {
        val remoteVer = manifest.optInt("version_code", apkVersionCode)
        val minApk = manifest.optInt("min_apk_version", 0)
        if (minApk > apkVersionCode) {
            ScriptLog.i("热更新需要 APK v$minApk+，当前 APK v$apkVersionCode")
            return false
        }
        if (remoteVer <= effectiveVersionCode()) return false
        val zipUrl = manifest.optString("zip_url", "")
        val sha = manifest.optString("sha256", "")
        if (downloadZip) {
            if (zipUrl.isBlank()) return false
            val resolved = resolveZipUrl(manifestUrl(), zipUrl)
            val tmp = downloadZipFile(resolved)
            extractZip(tmp, sha)
            tmp.delete()
        }
        saveOverlayMeta(manifest)
        val changelog = manifest.optString("changelog", "")
        if (changelog.isNotBlank()) {
            ScriptLog.i("更新说明: $changelog")
        }
        ScriptLog.i("脚本热更新完成 → v$remoteVer")
        UpdatePreferences.clearDeclined(context)
        return true
    }

    private fun saveOverlayMeta(manifest: JSONObject) {
        val ver = manifest.optInt("version_code", effectiveVersionCode())
        prefs.edit()
            .putInt(KEY_OVERLAY_VERSION, ver)
            .putString(KEY_OVERLAY_VERSION_NAME, manifest.optString("version_name", ""))
            .putString(KEY_OVERLAY_SHA, manifest.optString("sha256", ""))
            .apply()
    }

    private fun resolveZipUrl(manifestUrl: String, zipUrl: String): String {
        if (zipUrl.startsWith("http://") || zipUrl.startsWith("https://")) return zipUrl
        val base = URL(manifestUrl)
        if (zipUrl.startsWith("/")) {
            return "${base.protocol}://${base.host}${if (base.port > 0 && base.port != base.defaultPort) ":${base.port}" else ""}$zipUrl"
        }
        val parent = manifestUrl.substringBeforeLast('/') + "/"
        return parent + zipUrl
    }

    private fun fetchManifest(url: String): JSONObject? {
        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 15_000
            readTimeout = 15_000
        }
        val code = conn.responseCode
        if (code !in 200..299) {
            conn.disconnect()
            return null
        }
        val text = conn.inputStream.bufferedReader().use { it.readText() }
        conn.disconnect()
        return JSONObject(text)
    }

    private fun downloadZipFile(zipUrl: String): File {
        val tmp = File(context.cacheDir, "project_update.zip")
        val conn = (URL(zipUrl).openConnection() as HttpURLConnection).apply {
            connectTimeout = 30_000
            readTimeout = 120_000
        }
        conn.inputStream.use { input ->
            tmp.outputStream().use { output -> input.copyTo(output) }
        }
        conn.disconnect()
        return tmp
    }

    private fun extractZip(zipFile: File, expectedSha: String) {
        if (expectedSha.isNotBlank()) {
            val actual = sha256File(zipFile)
            if (!actual.equals(expectedSha, ignoreCase = true)) {
                throw IllegalStateException("zip sha256 不匹配")
            }
        }
        if (overlayRoot.exists()) overlayRoot.deleteRecursively()
        overlayRoot.mkdirs()
        ZipInputStream(BufferedInputStream(FileInputStream(zipFile))).use { zis ->
            var entry = zis.nextEntry
            while (entry != null) {
                if (!entry.isDirectory) {
                    val out = File(overlayRoot, entry.name)
                    out.parentFile?.mkdirs()
                    out.outputStream().use { zis.copyTo(it) }
                }
                zis.closeEntry()
                entry = zis.nextEntry
            }
        }
        // 面板布局以 APK + 设计模式覆盖为准，热更新 zip 不覆盖 ui/layout.json
        File(overlayRoot, "ui/layout.json").delete()
    }

    private fun sha256File(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buf = ByteArray(8192)
            var n = input.read(buf)
            while (n > 0) {
                digest.update(buf, 0, n)
                n = input.read(buf)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    companion object {
        private const val PREFS = "project_update"
        private const val KEY_OVERLAY_VERSION = "overlay_version_code"
        private const val KEY_OVERLAY_VERSION_NAME = "overlay_version_name"
        private const val KEY_OVERLAY_SHA = "overlay_sha256"
    }
}
