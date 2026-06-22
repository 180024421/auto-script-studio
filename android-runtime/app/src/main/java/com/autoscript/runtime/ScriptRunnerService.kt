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
import com.autoscript.core.capture.CaptureSession
import com.autoscript.core.project.ProjectAssets
import com.autoscript.script.ScriptEngine
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
        startForeground(NOTIFICATION_ID, buildNotification("脚本运行中"))
        val backend = DeviceAutomationBackend(CaptureSession.get())
        val assets = ProjectAssets(this)
        val engine = ScriptEngine(assets, backend) { msg ->
            MainActivity.logSink?.invoke(msg)
        }
        job = scope.launch {
            try {
                engine.run("main")
            } catch (e: Exception) {
                MainActivity.logSink?.invoke("错误: ${e.message}")
            } finally {
                engine.release()
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
        }
    }

    private fun stopRunning() {
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
