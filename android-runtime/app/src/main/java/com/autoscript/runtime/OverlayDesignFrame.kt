package com.autoscript.runtime

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Color
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.widget.FrameLayout
import android.widget.TextView
import kotlin.math.abs

interface OverlayDesignCallbacks {
    fun onReorder(containerPath: List<Int>, from: Int, to: Int)
    fun onSpanChange(widgetPath: List<Int>, span: Int)
    fun onSelect(widgetPath: List<Int>)
}

/**
 * 设计模式下包裹控件的 FrameLayout：顶部拖拽条用于排序，右缘用于调整列宽。
 */
@SuppressLint("ViewConstructor")
class OverlayDesignFrame(
    context: Context,
    private val widgetPath: List<Int>,
    private val containerPath: List<Int>,
    private val indexInContainer: Int,
    private val containerSize: Int,
    private val currentSpan: Int,
    private val maxCols: Int,
    private val callbacks: OverlayDesignCallbacks,
    private val dp: (Int) -> Int,
    content: View,
) : FrameLayout(context) {

    private val handleHeight = dp(22)
    private val edgeWidth = dp(14)
    private var selected = false

    init {
        addView(content, LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT))

        val handle = TextView(context).apply {
            text = "⋮⋮"
            gravity = Gravity.CENTER
            textSize = 10f
            setTextColor(Color.parseColor("#64748B"))
            setBackgroundColor(Color.parseColor("#E2E8F0"))
            layoutParams = LayoutParams(LayoutParams.MATCH_PARENT, handleHeight, Gravity.TOP)
        }
        addView(handle)

        val rightEdge = View(context).apply {
            setBackgroundColor(Color.parseColor("#93C5FD"))
            alpha = 0.6f
            layoutParams = LayoutParams(edgeWidth, LayoutParams.MATCH_PARENT, Gravity.END)
        }
        addView(rightEdge)

        setPadding(dp(1), handleHeight, dp(1), dp(1))
        setBackgroundColor(Color.parseColor("#F8FAFC"))

        attachReorderHandle(handle)
        attachResizeEdge(rightEdge)
        setOnClickListener { selectSelf() }
    }

    fun setDesignSelected(on: Boolean) {
        selected = on
        setBackgroundColor(if (on) Color.parseColor("#DBEAFE") else Color.parseColor("#F8FAFC"))
    }

    private fun selectSelf() {
        callbacks.onSelect(widgetPath)
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun attachReorderHandle(handle: View) {
        var downY = 0f
        var moved = false
        handle.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    downY = event.rawY
                    moved = false
                    selectSelf()
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    val dy = event.rawY - downY
                    if (abs(dy) > dp(24)) {
                        moved = true
                        val target = if (dy < 0) {
                            (indexInContainer - 1).coerceAtLeast(0)
                        } else {
                            (indexInContainer + 1).coerceAtMost(containerSize - 1)
                        }
                        if (target != indexInContainer) {
                            callbacks.onReorder(containerPath, indexInContainer, target)
                        }
                        downY = event.rawY
                    }
                    true
                }
                MotionEvent.ACTION_UP -> {
                    if (!moved) selectSelf()
                    true
                }
                else -> false
            }
        }
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun attachResizeEdge(edge: View) {
        var startSpan = currentSpan
        var accumulated = 0f
        edge.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    startSpan = currentSpan
                    accumulated = 0f
                    selectSelf()
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    accumulated += event.x
                    val deltaCols = (accumulated / dp(40)).toInt()
                    val newSpan = (startSpan + deltaCols).coerceIn(1, maxCols)
                    if (newSpan != currentSpan) {
                        callbacks.onSpanChange(widgetPath, newSpan)
                    }
                    true
                }
                MotionEvent.ACTION_UP -> true
                else -> false
            }
        }
    }
}
