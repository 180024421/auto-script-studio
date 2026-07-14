package com.autoscript.runtime

import android.app.AlarmManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.autoscript.core.project.ProjectAssets
import com.autoscript.core.project.SchedulePreferences
import java.util.Calendar

/** 每日定时启动脚本（用户偏好优先，否则 project.json schedule.daily_time = HH:mm）。 */
class ScheduleReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action == ACTION_SCHEDULE) {
            val svc = Intent(context, ScriptRunnerService::class.java).apply {
                action = ScriptRunnerService.ACTION_START
            }
            context.startForegroundService(svc)
            scheduleNext(context)
            return
        }
        if (intent?.action == Intent.ACTION_BOOT_COMPLETED) {
            scheduleNext(context)
        }
    }

    companion object {
        const val ACTION_SCHEDULE = "com.autoscript.runtime.SCHEDULE_RUN"

        fun scheduleNext(context: Context) {
            val cfg = runCatching { ProjectAssets(context).loadConfig() }.getOrNull() ?: return
            val enabled = SchedulePreferences.effectiveEnabled(context, cfg.schedule)
            if (!enabled) {
                cancel(context)
                return
            }
            val dailyTime = SchedulePreferences.effectiveDailyTime(context, cfg.schedule)
            val parts = dailyTime.split(":")
            if (parts.size < 2) return
            val hour = parts[0].toIntOrNull() ?: return
            val minute = parts[1].toIntOrNull() ?: return
            val cal = Calendar.getInstance().apply {
                set(Calendar.HOUR_OF_DAY, hour)
                set(Calendar.MINUTE, minute)
                set(Calendar.SECOND, 0)
                set(Calendar.MILLISECOND, 0)
                if (timeInMillis <= System.currentTimeMillis()) {
                    add(Calendar.DAY_OF_YEAR, 1)
                }
            }
            val pi = PendingIntent.getBroadcast(
                context,
                0,
                Intent(context, ScheduleReceiver::class.java).setAction(ACTION_SCHEDULE),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
            val am = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, cal.timeInMillis, pi)
        }

        fun cancel(context: Context) {
            val pi = PendingIntent.getBroadcast(
                context,
                0,
                Intent(context, ScheduleReceiver::class.java).setAction(ACTION_SCHEDULE),
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
            val am = context.getSystemService(Context.ALARM_SERVICE) as AlarmManager
            am.cancel(pi)
        }
    }
}
