package com.autoscript.script

interface ScriptRuntime {
    suspend fun run()
    fun release()
}
