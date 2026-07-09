package com.autoscript.script.lua

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.async
import kotlinx.coroutines.runBlocking

/**
 * Lua → Kotlin suspend 桥接：在脚本协程作用域内调度，避免嵌套阻塞线程池。
 */
object LuaBridgeRunner {
    @Volatile private var scope: CoroutineScope? = null

    fun bind(scriptScope: CoroutineScope) {
        scope = scriptScope
    }

    fun unbind() {
        scope = null
    }

    fun <T> await(block: suspend () -> T): T {
        val s = scope
        return if (s != null) {
            runBlocking { s.async { block() }.await() }
        } else {
            runBlocking { block() }
        }
    }
}
