package com.autoscript.core.project

import android.content.Context

/**
 * 用户可改的每日定时偏好（覆盖 project.json schedule）。
 */
object SchedulePreferences {
    private const val PREFS = "auto_script_schedule_prefs"
    private const val KEY_ENABLED = "enabled"
    private const val KEY_DAILY_TIME = "daily_time"
    private const val KEY_HAS_OVERRIDE = "has_override"

    fun effectiveEnabled(context: Context, defaults: ScheduleConfig): Boolean {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return if (prefs.getBoolean(KEY_HAS_OVERRIDE, false)) {
            prefs.getBoolean(KEY_ENABLED, defaults.enabled)
        } else {
            defaults.enabled
        }
    }

    fun effectiveDailyTime(context: Context, defaults: ScheduleConfig): String {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return if (prefs.getBoolean(KEY_HAS_OVERRIDE, false)) {
            prefs.getString(KEY_DAILY_TIME, null)?.takeIf { it.isNotBlank() } ?: defaults.dailyTime
        } else {
            defaults.dailyTime
        }
    }

    fun save(context: Context, enabled: Boolean, dailyTime: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_HAS_OVERRIDE, true)
            .putBoolean(KEY_ENABLED, enabled)
            .putString(KEY_DAILY_TIME, dailyTime.trim())
            .apply()
    }
}
