package com.autoscript.core.root

object RootInput {

    fun tap(x: Int, y: Int): Boolean =
        RootShell.exec("input tap $x $y")

    fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Int): Boolean =
        RootShell.exec("input swipe $x1 $y1 $x2 $y2 $durationMs")

    fun longPress(x: Int, y: Int, durationMs: Int): Boolean =
        swipe(x, y, x, y, durationMs.coerceAtLeast(100))

    fun isAvailable(): Boolean = RootShell.isAvailable()
}
