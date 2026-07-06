package com.autoscript.core.update

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.provider.Settings
import android.os.Build
import com.autoscript.core.log.ScriptLog
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

object UpdateNetwork {
    fun isOnWifi(context: Context): Boolean {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
            ?: return true
        val network = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(network) ?: return false
        return caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) ||
            caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)
    }

    fun canCheckNow(context: Context): Boolean {
        if (UpdatePreferences.isWifiOnly(context) && !isOnWifi(context)) return false
        if (UpdatePreferences.isInSilentHours(context)) return false
        return true
    }
}

object UpdateReporter {
    fun reportScriptVersion(context: Context, scriptVersionCode: Int, scriptVersionName: String) {
        if (!UpdateServer.isConfigured()) return
        Thread {
            runCatching {
                val base = UpdateServer.apiBase()
                val prefix = if (base.endsWith("/api", ignoreCase = true)) base else "$base/api"
                val url = URL("$prefix/script/update/report")
                val conn = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    connectTimeout = 8000
                    readTimeout = 8000
                    doOutput = true
                    setRequestProperty("Content-Type", "application/json; charset=utf-8")
                }
                val deviceId = Settings.Secure.getString(context.contentResolver, Settings.Secure.ANDROID_ID) ?: ""
                val pInfo = context.packageManager.getPackageInfo(context.packageName, 0)
                @Suppress("DEPRECATION")
                val apkVer = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                    pInfo.longVersionCode.toInt()
                } else {
                    pInfo.versionCode
                }
                val body = JSONObject().apply {
                    put("app", UpdateServer.appPackage())
                    put("script_version_code", scriptVersionCode)
                    put("script_version_name", scriptVersionName)
                    put("apk_version_code", apkVer)
                    put("device_id", deviceId)
                }
                conn.outputStream.use { it.write(body.toString().toByteArray(Charsets.UTF_8)) }
                conn.inputStream.use { it.readBytes() }
                conn.disconnect()
            }.onFailure { ScriptLog.i("版本上报失败: ${it.message}") }
        }.start()
    }
}
