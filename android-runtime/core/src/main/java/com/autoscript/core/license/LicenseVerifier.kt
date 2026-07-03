package com.autoscript.core.license

import android.content.Context
import android.provider.Settings
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.nio.charset.StandardCharsets

object LicenseStore {
    private const val PREFS = "auto_script_license"

    fun getCode(context: Context): String? =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString("card_code", null)
            ?.takeIf { it.isNotBlank() }

    fun saveCode(context: Context, code: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString("card_code", code.trim())
            .apply()
    }

    fun clear(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().clear().apply()
    }
}

class LicenseVerifier(
    private val context: Context,
    private val config: LicenseConfig,
    private val packageId: String,
) {
    fun deviceId(): String {
        val androidId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID)
        return androidId ?: "unknown"
    }

    fun isLicensed(): Boolean {
        if (!config.enabled) return true
        val code = LicenseStore.getCode(context) ?: return false
        return verifyRemote(code)
    }

    fun verifyAndBind(code: String): Boolean {
        if (!config.enabled) {
            LicenseStore.saveCode(context, code)
            return true
        }
        if (!verifyRemote(code)) return false
        LicenseStore.saveCode(context, code)
        return true
    }

    private fun verifyRemote(code: String): Boolean {
        val base = config.apiBase.trim().trimEnd('/')
        if (base.isEmpty()) return config.skipOnOffline
        val app = config.appName.ifBlank { packageId }
        val mac = deviceId()
        val qs = listOf(
            "mac" to mac,
            "pwd" to code,
            "app" to app,
        ).joinToString("&") { (k, v) ->
            "$k=${URLEncoder.encode(v, StandardCharsets.UTF_8.name())}"
        }
        val url = URL("$base/jiaoben/sercurity?$qs")
        return try {
            val conn = (url.openConnection() as HttpURLConnection).apply {
                connectTimeout = 12_000
                readTimeout = 12_000
                requestMethod = "GET"
            }
            val body = conn.inputStream.bufferedReader().use(BufferedReader::readText).trim()
            conn.disconnect()
            body.equals("true", ignoreCase = true)
        } catch (_: Exception) {
            config.skipOnOffline
        }
    }
}
