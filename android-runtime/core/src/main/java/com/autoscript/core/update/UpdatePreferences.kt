package com.autoscript.core.update

import android.content.Context

/**
 * APK 内置热更新用户偏好：可关闭检测、跳过版本、或自动安装。
 */
object UpdatePreferences {
    private const val PREFS = "auto_script_update_prefs"
    private const val KEY_CHECK_ENABLED = "check_enabled"
    private const val KEY_AUTO_INSTALL = "auto_install"
    private const val KEY_DECLINED_VERSION = "declined_version"

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
