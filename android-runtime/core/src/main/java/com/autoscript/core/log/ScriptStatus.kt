package com.autoscript.core.log

import android.content.Context
import org.json.JSONObject
import java.io.File
import java.util.concurrent.CopyOnWriteArraySet

object ScriptStatus {
    private const val FILE = "script_status.json"

    @Volatile
    private var memoryRunning: Boolean = false

    private val runningListeners = CopyOnWriteArraySet<(Boolean) -> Unit>()

    fun addRunningListener(listener: (Boolean) -> Unit) {
        runningListeners.add(listener)
        listener(memoryRunning)
    }

    fun removeRunningListener(listener: (Boolean) -> Unit) {
        runningListeners.remove(listener)
    }

    private fun notifyRunning(running: Boolean) {
        if (memoryRunning == running) return
        memoryRunning = running
        runningListeners.forEach { it(running) }
    }

    fun write(context: Context, status: String, phase: String = "", error: String = "") {
        notifyRunning(status == "running")
        val obj = JSONObject()
        obj.put("status", status)
        obj.put("phase", phase)
        obj.put("error", error)
        obj.put("timestamp", System.currentTimeMillis())
        val text = obj.toString()
        runCatching {
            val dir = context.getExternalFilesDir(null) ?: context.filesDir
            File(dir, FILE).writeText(text)
            // 兼容旧版 adb 冒烟脚本
            File(dir, "script_status.txt").writeText(status)
        }
        ScriptLog.i(status)
    }

    fun writeLegacy(context: Context, message: String) {
        val parts = message.split(":", limit = 2)
        val status = parts[0]
        val detail = if (parts.size > 1) parts[1] else ""
        write(context, status, phase = detail, error = if (status == "error") detail else "")
    }

    fun read(context: Context): String {
        val dir = context.getExternalFilesDir(null) ?: context.filesDir
        val file = File(dir, FILE)
        if (!file.exists()) return "idle"
        return runCatching {
            JSONObject(file.readText()).optString("status", "idle")
        }.getOrElse { "idle" }
    }

    fun isRunning(context: Context): Boolean =
        memoryRunning || read(context) == "running"

    fun pathHint(context: Context): String {
        val dir = context.getExternalFilesDir(null) ?: context.filesDir
        return File(dir, FILE).absolutePath
    }
}
