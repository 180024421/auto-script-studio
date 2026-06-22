package com.autoscript.core.root

import android.util.Log
import java.io.BufferedReader
import java.io.ByteArrayOutputStream
import java.io.InputStreamReader
import java.util.concurrent.TimeUnit

/**
 * 通过 su 执行 shell（需设备已 root）。
 */
object RootShell {
    private const val TAG = "AutoScriptRoot"
    private var cachedAvailable: Boolean? = null

    fun isAvailable(): Boolean {
        cachedAvailable?.let { return it }
        val ok = try {
            val p = Runtime.getRuntime().exec(arrayOf("su", "-c", "id"))
            val out = p.inputStream.bufferedReader().readText()
            p.waitFor(3, TimeUnit.SECONDS)
            p.exitValue() == 0 && out.contains("uid=0")
        } catch (e: Exception) {
            Log.w(TAG, "root check failed", e)
            false
        }
        cachedAvailable = ok
        Log.i(TAG, "root available=$ok")
        return ok
    }

    fun exec(command: String, timeoutSec: Long = 10): Boolean {
        if (!isAvailable()) return false
        return try {
            val p = Runtime.getRuntime().exec(arrayOf("su", "-c", command))
            val finished = p.waitFor(timeoutSec, TimeUnit.SECONDS)
            if (!finished) {
                p.destroyForcibly()
                return false
            }
            p.exitValue() == 0
        } catch (e: Exception) {
            Log.e(TAG, "exec failed: $command", e)
            false
        }
    }

    fun execOutput(command: String, timeoutSec: Long = 15): ByteArray? {
        if (!isAvailable()) return null
        return try {
            val p = Runtime.getRuntime().exec(arrayOf("su", "-c", command))
            val out = ByteArrayOutputStream()
            p.inputStream.use { it.copyTo(out) }
            val err = p.errorStream.use { it.readBytes() }
            if (!p.waitFor(timeoutSec, TimeUnit.SECONDS)) {
                p.destroyForcibly()
                return null
            }
            if (p.exitValue() != 0) {
                Log.w(TAG, "execOutput exit=${p.exitValue()} err=${err.decodeToString().take(200)}")
                return null
            }
            out.toByteArray()
        } catch (e: Exception) {
            Log.e(TAG, "execOutput failed: $command", e)
            null
        }
    }

    fun execText(command: String, timeoutSec: Long = 10): String? {
        if (!isAvailable()) return null
        return try {
            val p = Runtime.getRuntime().exec(arrayOf("su", "-c", command))
            val text = p.inputStream.bufferedReader().use(BufferedReader::readText)
            if (!p.waitFor(timeoutSec, TimeUnit.SECONDS)) {
                p.destroyForcibly()
                return null
            }
            if (p.exitValue() != 0) null else text
        } catch (e: Exception) {
            null
        }
    }

    fun resetCache() {
        cachedAvailable = null
    }
}
