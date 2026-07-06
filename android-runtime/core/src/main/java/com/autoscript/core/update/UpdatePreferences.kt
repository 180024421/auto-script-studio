package com.autoscript.core.update

import android.content.Context
import java.util.Calendar

/**
 * APK 内置热更新用户偏好：可关闭检测、跳过版本、或自动安装。
 */
object UpdatePreferences {
    private const val PREFS = "auto_script_update_prefs"
    private const val KEY_CHECK_ENABLED = "check_enabled"
    private const val KEY_AUTO_INSTALL = "auto_install"
    private const val KEY_DECLINED_VERSION = "declined_version"
    private const val KEY_WIFI_ONLY = "wifi_only"
    private const val KEY_SILENT_START = "silent_start_hour"
    private const val KEY_SILENT_END = "silent_end_hour"
    private const val KEY_PENDING_BADGE = "pending_update_badge"

    fun isCheckEnabled(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_CHECK_ENABLED, true)

    fun setCheckEnabled(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_CHECK_ENABLED, enabled)
            .apply()
    }

    fun isAutoInstall(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_AUTO_INSTALL, false)

    fun setAutoInstall(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_AUTO_INSTALL, enabled)
            .apply()
    }

    fun isWifiOnly(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_WIFI_ONLY, false)

    fun setWifiOnly(context: Context, enabled: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_WIFI_ONLY, enabled)
            .apply()
    }

    fun silentHours(context: Context): Pair<Int, Int> {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return prefs.getInt(KEY_SILENT_START, -1) to prefs.getInt(KEY_SILENT_END, -1)
    }

    fun setSilentHours(context: Context, startHour: Int, endHour: Int) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putInt(KEY_SILENT_START, startHour)
            .putInt(KEY_SILENT_END, endHour)
            .apply()
    }

    fun isInSilentHours(context: Context): Boolean {
        val (start, end) = silentHours(context)
        if (start < 0 || end < 0 || start == end) return false
        val hour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        return if (start < end) {
            hour in start until end
        } else {
            hour >= start || hour < end
        }
    }

    fun hasPendingUpdateBadge(context: Context): Boolean =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getBoolean(KEY_PENDING_BADGE, false)

    fun setPendingUpdateBadge(context: Context, pending: Boolean) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_PENDING_BADGE, pending)
            .apply()
    }

    fun declinedVersion(context: Context): Int =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getInt(KEY_DECLINED_VERSION, 0)

    fun setDeclinedVersion(context: Context, versionCode: Int) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putInt(KEY_DECLINED_VERSION, versionCode)
            .apply()
    }

    fun clearDeclined(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .remove(KEY_DECLINED_VERSION)
            .apply()
    }
}
