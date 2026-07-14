package com.autoscript.core.project

import android.content.Context
import android.content.pm.PackageManager
import android.net.wifi.WifiManager
import androidx.core.content.ContextCompat
import java.util.Calendar

/**
 * 下班离开公司 WiFi 提醒偏好。
 * 最早触发时刻之后，从公司 SSID 断开一次即提醒（同一天只触发一次）。
 */
object WifiLeavePreferences {
    private const val PREFS = "auto_script_wifi_leave_prefs"
    private const val KEY_ENABLED = "enabled"
    private const val KEY_SSID = "ssid"
    private const val KEY_EARLIEST = "earliest_time"
    private const val KEY_LAST_TRIGGER_DAY = "last_trigger_day"

    const val DEFAULT_SSID = "HSYYYL-N28"
    const val DEFAULT_EARLIEST = "17:30"

    fun isEnabled(context: Context): Boolean =
        prefs(context).getBoolean(KEY_ENABLED, false)

    fun setEnabled(context: Context, enabled: Boolean) {
        prefs(context).edit().putBoolean(KEY_ENABLED, enabled).apply()
    }

    fun ssid(context: Context): String =
        prefs(context).getString(KEY_SSID, null)?.takeIf { it.isNotBlank() } ?: DEFAULT_SSID

    fun setSsid(context: Context, ssid: String) {
        prefs(context).edit().putString(KEY_SSID, ssid.trim()).apply()
    }

    fun earliestTime(context: Context): String =
        prefs(context).getString(KEY_EARLIEST, null)?.takeIf { it.isNotBlank() } ?: DEFAULT_EARLIEST

    fun setEarliestTime(context: Context, time: String) {
        prefs(context).edit().putString(KEY_EARLIEST, time.trim()).apply()
    }

    fun markTriggeredToday(context: Context) {
        prefs(context).edit().putInt(KEY_LAST_TRIGGER_DAY, dayKey()).apply()
    }

    fun alreadyTriggeredToday(context: Context): Boolean =
        prefs(context).getInt(KEY_LAST_TRIGGER_DAY, -1) == dayKey()

    fun isAfterEarliest(context: Context, nowMillis: Long = System.currentTimeMillis()): Boolean {
        val parts = earliestTime(context).split(":")
        val hour = parts.getOrNull(0)?.toIntOrNull() ?: 17
        val minute = parts.getOrNull(1)?.toIntOrNull() ?: 30
        val cal = Calendar.getInstance().apply { timeInMillis = nowMillis }
        val nowMins = cal.get(Calendar.HOUR_OF_DAY) * 60 + cal.get(Calendar.MINUTE)
        return nowMins >= hour * 60 + minute
    }

    /** 读取当前已连接 WiFi SSID（需定位权限；读不到返回 null）。 */
    fun currentConnectedSsid(context: Context): String? {
        val fine = ContextCompat.checkSelfPermission(
            context,
            android.Manifest.permission.ACCESS_FINE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED
        val coarse = ContextCompat.checkSelfPermission(
            context,
            android.Manifest.permission.ACCESS_COARSE_LOCATION,
        ) == PackageManager.PERMISSION_GRANTED
        if (!fine && !coarse) return null
        @Suppress("DEPRECATION")
        val wifi = context.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
            ?: return null
        @Suppress("DEPRECATION")
        val raw = wifi.connectionInfo?.ssid ?: return null
        val ssid = raw.trim().removeSurrounding("\"")
        if (ssid.isEmpty() || ssid.equals("<unknown ssid>", ignoreCase = true) ||
            ssid.equals("0x", ignoreCase = true)
        ) {
            return null
        }
        return ssid
    }

    private fun dayKey(): Int {
        val cal = Calendar.getInstance()
        return cal.get(Calendar.YEAR) * 1000 + cal.get(Calendar.DAY_OF_YEAR)
    }

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}
