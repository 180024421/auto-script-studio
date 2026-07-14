package com.autoscript.runtime

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import com.autoscript.core.project.ProjectAssets

/** 开机后：可选自动启动脚本；同步启动 WiFi 离开监听。 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action != Intent.ACTION_BOOT_COMPLETED) return
        WifiLeaveMonitorService.sync(context)
        val cfg = runCatching { ProjectAssets(context).loadConfig() }.getOrNull() ?: return
        if (!cfg.boot.autoStart) return
        val svc = Intent(context, ScriptRunnerService::class.java).apply {
            action = ScriptRunnerService.ACTION_START
        }
        context.startForegroundService(svc)
    }
}
