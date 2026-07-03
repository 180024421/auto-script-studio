package com.autoscript.runtime

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.autoscript.core.backend.DeviceAutomationBackend
import com.autoscript.core.log.ScriptLog
import com.autoscript.core.log.ScriptStatus
import com.autoscript.core.script.ScriptCancelToken
import com.autoscript.core.license.LicenseVerifier
import com.autoscript.core.project.ProjectAssets
import com.autoscript.script.ScriptRuntime
import com.autoscript.script.ScriptRuntimeFactory
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

class ScriptRunnerService : Service() {

    private val scope = CoroutineScope(Dispatchers.Default)
    private var job: Job? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> startRunning()
            ACTION_STOP -> stopRunning()
        }
        return START_NOT_STICKY
    }

    private fun startRunning() {
        if (job?.isActive == true) return
        ScriptCancelToken.reset()
        startForeground(NOTIFICATION_ID, buildNotification("脚本运行中"))
        val assets = ProjectAssets(this)
        val config = assets.loadConfig()
        if (config.update.checkOnStart) {
            assets.checkForUpdates()
        }
        val verifier = LicenseVerifier(this, config.license, config.packageId)
        if (config.license.enabled && !verifier.isLicensed()) {
            ScriptLog.i("卡密未验证，脚本未启动")
            MainActivity.logSink?.invoke("请先输入有效卡密")
                ?: OverlayLog.notify("请先输入有效卡密")
            stopForeground(STOP_FOREGROUND_REMOVE)
            stopSelf()
            return
        }
        val backend = DeviceAutomationBackend(config)
        val runtime: ScriptRuntime = ScriptRuntimeFactory.create(assets, backend) { msg ->
            ScriptLog.i(msg)
            MainActivity.logSink?.invoke(msg) ?: OverlayLog.notify(msg)
        }
        job = scope.launch {
            try {
                ScriptStatus.write(this@ScriptRunnerService, "running", phase = "main")
                runtime.run()
                ScriptStatus.write(this@ScriptRunnerService, "done", phase = "main")
            } catch (e: Exception) {
                ScriptStatus.write(this@ScriptRunnerService, "error", phase = "main", error = e.message ?: "unknown")
                MainActivity.logSink?.invoke("错误: ${e.message}")
                    ?: OverlayLog.notify("错误: ${e.message}")
            } finally {
                runtime.release()
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
        }
    }

    private fun stopRunning() {
        ScriptCancelToken.cancel()
        job?.cancel()
        job = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    private fun buildNotification(text: String): Notification {
        val channelId = "auto_script_run"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val mgr = getSystemService(NotificationManager::class.java)
            mgr.createNotificationChannel(
                NotificationChannel(channelId, "脚本运行", NotificationManager.IMPORTANCE_LOW),
            )
        }
        return NotificationCompat.Builder(this, channelId)
            .setContentTitle(getString(R.string.app_name))
            .setContentText(text)
            .setSmallIcon(R.drawable.ic_launcher)
            .setOngoing(true)
            .build()
    }

    companion object {
        const val ACTION_START = "com.autoscript.runtime.START"
        const val ACTION_STOP = "com.autoscript.runtime.STOP"
        private const val NOTIFICATION_ID = 1001
    }
}
