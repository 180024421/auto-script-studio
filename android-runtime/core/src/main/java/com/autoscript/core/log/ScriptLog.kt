package com.autoscript.core.log

import android.util.Log

object ScriptLog {
    private const val TAG = "AutoScript"

    fun i(message: String) {
        Log.i(TAG, message)
    }

    fun e(message: String, throwable: Throwable? = null) {
        if (throwable != null) Log.e(TAG, message, throwable) else Log.e(TAG, message)
    }
}
