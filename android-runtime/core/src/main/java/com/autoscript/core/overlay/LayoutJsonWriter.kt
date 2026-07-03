package com.autoscript.core.overlay

import org.json.JSONArray
import org.json.JSONObject

object LayoutJsonWriter {

    fun toJson(layout: LayoutConfig): String = toJsonObject(layout).toString(2)

    fun toJsonObject(layout: LayoutConfig): JSONObject = JSONObject().apply {
        put("version", layout.version)
        put("enabled", layout.enabled)
        put("panel", panelToJson(layout.panel))
        if (layout.screens.isNotEmpty()) {
            put("screens", screensToJson(layout.screens))
            put("widgets", widgetsToJson(layout.chromeWidgets()))
        } else {
            put("widgets", widgetsToJson(layout.widgets))
        }
    }

    private fun panelToJson(panel: PanelConfig): JSONObject = JSONObject().apply {
        put("title", panel.title)
        put("width_dp", panel.widthDp)
        put("width_mode", panel.widthMode)
        put("height_mode", panel.heightMode)
        put("height_dp", panel.heightDp)
        put("display_mode", panel.displayMode)
        put("auto_collapse_idle_ms", panel.autoCollapseIdleMs)
        put("opacity", panel.opacity.toDouble())
        put("position", panel.position)
        put("start_x", panel.startX)
        put("start_y", panel.startY)
        put("columns", panel.columns)
        put("ball_size_dp", panel.ballSizeDp)
        put("show_log", panel.showLog)
        put("log_height_dp", panel.logHeightDp)
        put("draggable", panel.draggable)
        put("collapsible", panel.collapsible)
        put("theme", panel.theme)
        put("allow_design", panel.allowDesign)
        put("start_confirm_collapse", panel.startConfirmCollapse)
        put("layout_mode", panel.layoutMode)
        put("design_width", panel.designWidth)
        put("design_height", panel.designHeight)
        put("active_screen", panel.activeScreen)
        put("show_on_launch", panel.showOnLaunch)
    }

    private fun screensToJson(screens: List<ScreenConfig>): JSONArray {
        val arr = JSONArray()
        screens.forEach { sc ->
            arr.put(
                JSONObject().apply {
                    put("title", sc.title)
                    put("widgets", widgetsToJson(sc.widgets))
                },
            )
        }
        return arr
    }

    private fun widgetsToJson(widgets: List<WidgetConfig>): JSONArray {
        val arr = JSONArray()
        widgets.forEach { arr.put(widgetToJson(it)) }
        return arr
    }

    private fun widgetToJson(w: WidgetConfig): JSONObject = JSONObject().apply {
        put("id", w.id)
        put("type", w.type)
        if (w.label.isNotBlank()) put("label", w.label)
        if (w.text.isNotBlank()) put("text", w.text)
        if (w.color != "#2563EB") put("color", w.color)
        if (w.width != 1) put("width", w.width)
        if (w.action.isNotBlank()) put("action", w.action)
        if (w.placeholder.isNotBlank()) put("placeholder", w.placeholder)
        if (w.default.isNotBlank()) put("default", w.default)
        if (w.defaultStart.isNotBlank()) put("default_start", w.defaultStart)
        if (w.defaultEnd.isNotBlank()) put("default_end", w.defaultEnd)
        if (w.options.isNotEmpty()) put("options", JSONArray(w.options))
        if (w.tabs.isNotEmpty()) {
            put("tabs", JSONArray().apply {
                w.tabs.forEach { tab ->
                    put(JSONObject().apply {
                        put("title", tab.title)
                        put("widgets", widgetsToJson(tab.widgets))
                    })
                }
            })
        }
        if (w.textStyle.isNotBlank() && w.textStyle != "normal") put("text_style", w.textStyle)
        if (w.align.isNotBlank() && w.align != "left") put("align", w.align)
        if (w.y != 0) put("y", w.y)
        if (w.x1 != 0) put("x1", w.x1)
        if (w.y1 != 0) put("y1", w.y1)
        if (w.x2 != 0) put("x2", w.x2)
        if (w.y2 != 0) put("y2", w.y2)
        if (w.durationMs != 300) put("duration_ms", w.durationMs)
        if (w.lua.isNotBlank()) put("lua", w.lua)
        if (w.required) put("required", true)
        w.min?.let { put("min", it) }
        w.max?.let { put("max", it) }
        if (w.step != 1) put("step", w.step)
        if (w.rows != 3) put("rows", w.rows)
        put("layout_x", w.layoutX)
        put("layout_y", w.layoutY)
        put("layout_w", w.layoutW)
        put("layout_h", w.layoutH)
    }
}
