package com.autoscript.core.update

import android.content.Context
import com.autoscript.core.log.ScriptLog
import com.autoscript.core.project.UpdateConfig
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.util.zip.ZipInputStream

/**
 * 从远程 manifest 拉取脚本 zip，解压到 files/project_overlay/，供 ProjectAssets 优先读取。
 *
 * manifest JSON 示例::
 *   { "version_code": 2, "zip_url": "https://example.com/project-v2.zip" }
 */
class ProjectUpdateManager(
    private val context: Context,
    private val config: UpdateConfig,
    private val currentVersionCode: Int,
) {
    private val overlayRoot: File
        get() = File(context.filesDir, "project_overlay")

    fun maybeUpdate(): Boolean {
        if (!config.enabled || config.manifestUrl.isBlank()) return false
        return try {
            val manifest = fetchManifest(config.manifestUrl.trim()) ?: return false
            val remoteVer = manifest.optInt("version_code", currentVersionCode)
            if (remoteVer <= currentVersionCode) return false
            val zipUrl = manifest.optString("zip_url", "")
            if (zipUrl.isBlank()) return false
            downloadAndExtract(zipUrl)
            ScriptLog.i("脚本热更新完成 → v$remoteVer")
            true
        } catch (e: Exception) {
            ScriptLog.i("脚本热更新失败: ${e.message}")
            false
        }
    }

    fun overlayFile(relative: String): File? {
        val f = File(overlayRoot, relative.trimStart('/'))
        return f.takeIf { it.isFile }
    }

    private fun fetchManifest(url: String): JSONObject? {
        val conn = (URL(url).openConnection() as HttpURLConnection).apply {
            connectTimeout = 15_000
            readTimeout = 15_000
        }
        val text = conn.inputStream.bufferedReader().use { it.readText() }
        conn.disconnect()
        return JSONObject(text)
    }

    private fun downloadAndExtract(zipUrl: String) {
        val tmp = File(context.cacheDir, "project_update.zip")
        val conn = (URL(zipUrl).openConnection() as HttpURLConnection).apply {
            connectTimeout = 30_000
            readTimeout = 120_000
        }
        conn.inputStream.use { input ->
            tmp.outputStream().use { output -> input.copyTo(output) }
        }
        conn.disconnect()
        if (overlayRoot.exists()) overlayRoot.deleteRecursively()
        overlayRoot.mkdirs()
        ZipInputStream(BufferedInputStream(tmp.inputStream())).use { zis ->
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
        tmp.delete()
    }
}
