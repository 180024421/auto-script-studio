package com.autoscript.core.backend

import com.autoscript.core.model.ScreenFrame

interface AutomationBackend {
    suspend fun capture(): ScreenFrame
    suspend fun tap(x: Int, y: Int)
    suspend fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Int = 300)
    suspend fun longPress(x: Int, y: Int, durationMs: Int = 500)
    fun isReady(): Boolean
}
