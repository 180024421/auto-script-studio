package com.autoscript.runtime

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Color
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.widget.FrameLayout
import android.widget.TextView
import kotlin.math.roundToInt

interface FreeOverlayDesignCallbacks {
    fun onSelect(widgetPath: List<Int>)
    fun onRectChange(widgetPath: List<Int>, x: Int, y: Int, w: Int, h: Int)
}

/**
 * 自由布局设计模式：拖动移动控件，右下角缩放。
 * 表单类控件默认无顶栏手柄（与 PC FreeDesignItem 一致）。
 */
@SuppressLint("ViewConstructor")
class FreeOverlayDesignFrame(
    context: Context,
    private val widgetPath: List<Int>,
    private val designW: Int,
    private val designH: Int,
    private val scaleX: Float,
    private val scaleY: Float,
    private val callbacks: FreeOverlayDesignCallbacks,
    private val dp: (Int) -> Int,
    content: View,
    private val showDragHandle: Boolean = true,
) : FrameLayout(context) {

    private val handleHeight = if (showDragHandle) dp(16) else 0
    private var selected = false

    init {
        addView(
            content,
            LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.MATCH_PARENT).apply {
                topMargin = handleHeight
            },
        )
        if (showDragHandle) {
            val handle = TextView(context).apply {
                text = "⋮⋮"
                gravity = Gravity.CENTER
                textSize = 9f
                setTextColor(Color.parseColor("#64748B"))
                setBackgroundColor(Color.parseColor("#E2E8F0"))
                layoutParams = LayoutParams(LayoutParams.MATCH_PARENT, handleHeight, Gravity.TOP)
            }
            addView(handle)
            attachDrag(handle)
        } else {
            attachDrag(content)
        }
        val grip = View(context).apply {
            setBackgroundColor(Color.parseColor("#93C5FD"))
            alpha = 0.7f
            layoutParams = LayoutParams(dp(12), dp(12), Gravity.END or Gravity.BOTTOM)
        }
        addView(grip)
        setBackgroundColor(Color.parseColor("#F8FAFC"))
        attachResize(grip)
        setOnClickListener { selectSelf() }
    }

    fun setDesignSelected(on: Boolean) {
        selected = on
        setBackgroundColor(if (on) Color.parseColor("#DBEAFE") else Color.parseColor("#F8FAFC"))
    }

    private fun selectSelf() {
        callbacks.onSelect(widgetPath)
    }

    private fun snapDesign(v: Int): Int {
        val g = SNAP_GRID
        return ((v.toDouble() / g).roundToInt() * g).coerceAtLeast(0)
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun attachDrag(handle: View) {
        var downRawX = 0f
        var downRawY = 0f
        var startX = 0
        var startY = 0
        handle.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    downRawX = event.rawX
                    downRawY = event.rawY
                    val lp = layoutParams as? MarginLayoutParams
                    startX = lp?.leftMargin ?: 0
                    startY = lp?.topMargin ?: 0
                    selectSelf()
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    val lp = layoutParams as? MarginLayoutParams ?: return@setOnTouchListener true
                    val dx = (event.rawX - downRawX).roundToInt()
                    val dy = (event.rawY - downRawY).roundToInt()
                    lp.leftMargin = (startX + dx).coerceAtLeast(0)
                    lp.topMargin = (startY + dy).coerceAtLeast(0)
                    layoutParams = lp
                    true
                }
                MotionEvent.ACTION_UP -> {
                    emitRect()
                    true
                }
                else -> false
            }
        }
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun attachResize(grip: View) {
        var startW = 0
        var startH = 0
        var downX = 0f
        var downY = 0f
        grip.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> {
                    val lp = layoutParams as? MarginLayoutParams ?: return@setOnTouchListener true
                    startW = lp.width
                    startH = lp.height
                    downX = event.rawX
                    downY = event.rawY
                    selectSelf()
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    val lp = layoutParams as? MarginLayoutParams ?: return@setOnTouchListener true
                    val dw = (event.rawX - downX).roundToInt()
                    val dh = (event.rawY - downY).roundToInt()
                    lp.width = (startW + dw).coerceAtLeast(dp(48))
                    lp.height = (startH + dh).coerceAtLeast(dp(28))
                    layoutParams = lp
                    true
                }
                MotionEvent.ACTION_UP -> {
                    emitRect()
                    true
                }
                else -> false
            }
        }
    }

    private fun emitRect() {
        val lp = layoutParams as? MarginLayoutParams ?: return
        val x = snapDesign((lp.leftMargin / scaleX).roundToInt().coerceIn(0, designW))
        val y = snapDesign((lp.topMargin / scaleY).roundToInt().coerceIn(0, designH))
        val w = snapDesign((lp.width / scaleX).roundToInt().coerceAtLeast(48))
        val h = snapDesign((lp.height / scaleY).roundToInt().coerceAtLeast(20))
        callbacks.onRectChange(widgetPath, x, y, w, h)
    }

    companion object {
        private const val SNAP_GRID = 8

        fun isFormLikeWidget(type: String): Boolean = type in FORM_LIKE_TYPES

        private val FORM_LIKE_TYPES = setOf(
            "input", "select", "radio", "multiselect", "switch",
            "time_range", "slider", "stepper", "textarea",
            "text", "label", "divider", "section",
        )
    }
}
