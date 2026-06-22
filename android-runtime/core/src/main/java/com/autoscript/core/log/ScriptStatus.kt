package com.autoscript.core.log

import android.content.Context
import java.io.File

object ScriptStatus {
    private const val FILE = "script_status.txt"

    fun write(context: Context, message: String) {
        runCatching {
            val dir = context.getExternalFilesDir(null) ?: context.filesDir
            File(dir, FILE).writeText(message)
        }
        ScriptLog.i(message)
    }

    fun pathHint(context: Context): String {
        val dir = context.getExternalFilesDir(null) ?: context.filesDir
        return File(dir, FILE).absolutePath
    }
}
