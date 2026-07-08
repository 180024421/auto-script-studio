package com.autoscript.core.overlay

import org.json.JSONArray
import org.json.JSONObject

data class PanelConfig(
    val title: String = "脚本助手",
    val widthDp: Int = 220,
    /** fixed=Android dp；auto=设计稿像素宽度并按屏宽等比缩放 */
    val widthMode: String = "fixed",
    /** wrap=内容高度；full=撑满屏高；auto=按 design_height 等比缩放 */
    val heightMode: String = "wrap",
    /** auto 高度模式下设计稿像素高度 */
    val heightDp: Int = 1280,
    /** form/host=主页面表单+悬浮窗仅启停；minimal=无主页表单、悬浮窗仅启停 */
    val displayMode: String = "host",
    /** 无操作多少毫秒后自动收起到悬浮球；0=关闭 */
    val autoCollapseIdleMs: Int = 0,
    val opacity: Float = 0.96f,
    val position: String = "right_center",
    val startX: Int = 20,
    val startY: Int = 200,
    val columns: Int = 2,
    val ballSizeDp: Int = 48,
    val showLog: Boolean = true,
    /** minimal 悬浮窗日志区展开高度（dp） */
    val logHeightDp: Int = 88,
    val draggable: Boolean = true,
    val collapsible: Boolean = true,
    val theme: String = "light",
    val allowDesign: Boolean = true,
    val startConfirmCollapse: Boolean = true,
    val layoutMode: String = "grid",
    val designWidth: Int = 720,
    val designHeight: Int = 1280,
    val activeScreen: Int = 0,
    /** APK 启动时是否自动显示浮动面板（仍须悬浮窗权限） */
    val showOnLaunch: Boolean = false,
)

data class ScreenConfig(
    val title: String,
    val widgets: List<WidgetConfig> = emptyList(),
)

data class TabConfig(
    val title: String,
    val widgets: List<WidgetConfig> = emptyList(),
)

data class WidgetConfig(
    val id: String,
    val type: String,
    val label: String = "",
    val text: String = "",
    val color: String = "#2563EB",
    val width: Int = 1,
    val action: String = "",
    val placeholder: String = "",
    val default: String = "",
    val defaultStart: String = "",
    val defaultEnd: String = "",
    val options: List<String> = emptyList(),
    val tabs: List<TabConfig> = emptyList(),
    val x: Int = 0,
    val y: Int = 0,
    val x1: Int = 0,
    val y1: Int = 0,
    val x2: Int = 0,
    val y2: Int = 0,
    val durationMs: Int = 300,
    val lua: String = "",
    val required: Boolean = false,
    val min: Double? = null,
    val max: Double? = null,
    val step: Int = 1,
    val rows: Int = 3,
    val textStyle: String = "normal",
    val align: String = "left",
    val layoutX: Int = 24,
    val layoutY: Int = 120,
    val layoutW: Int = 672,
    val layoutH: Int = 56,
) {
    fun effectiveAction(): String = when {
        type == "button" -> action.ifBlank { "lua" }
        type in ACTION_TYPES -> type
        else -> ""
    }

    fun isActionControl(): Boolean = effectiveAction().isNotEmpty()

    fun isInteractiveInput(): Boolean = type in INPUT_TYPES

    companion object {
        val ACTION_TYPES = setOf(
            "button", "start_script", "stop_script", "tap", "swipe", "long_press",
            "lua", "snippet", "collapse", "hide", "open_app",
        )
        val INPUT_TYPES = setOf(
            "input", "select", "radio", "multiselect", "tabs",
            "switch", "time_range", "slider", "stepper", "textarea",
        )
        val FORM_VALUE_TYPES = setOf(
            "input", "select", "radio", "multiselect",
            "switch", "time_range", "slider", "stepper", "textarea",
        )
    }
}

typealias ButtonConfig = WidgetConfig

data class LayoutConfig(
    val version: Int = 3,
    val enabled: Boolean = true,
    val panel: PanelConfig = PanelConfig(),
    val screens: List<ScreenConfig> = emptyList(),
    val widgets: List<WidgetConfig> = emptyList(),
) {
    val buttons: List<WidgetConfig> get() = widgets

    fun isFreeMode(): Boolean = panel.layoutMode == "free"

    /** 表单在主 Activity，悬浮窗为紧凑工具条（▶/■/日志/悬浮球）。 */
    fun isHostDisplay(): Boolean =
        panel.displayMode.equals("host", ignoreCase = true) ||
            panel.displayMode.equals("form", ignoreCase = true)

    fun normalizedForRuntime(): LayoutConfig {
        if (!isHostDisplay()) return this
        return copy(
            widgets = emptyList(),
            screens = resolvedScreens().map { sc ->
                sc.copy(widgets = sc.widgets.filter { !it.isActionControl() })
            },
        )
    }

    fun hasHostFormWidgets(): Boolean =
        resolvedScreens().any { sc -> sc.widgets.any { w -> w.type in WidgetConfig.FORM_VALUE_TYPES || w.type in setOf("text", "label", "divider") } }

    fun resolvedScreens(): List<ScreenConfig> =
        if (screens.isNotEmpty()) screens else legacyScreensFromWidgets(widgets)

    fun chromeWidgets(): List<WidgetConfig> =
        widgets.filter { it.isActionControl() && it.type != "stop_script" }

    fun screenWidgets(screenIdx: Int): List<WidgetConfig> {
        val sc = resolvedScreens()
        if (screenIdx < 0 || screenIdx >= sc.size) return emptyList()
        return sc[screenIdx].widgets
    }

    fun activeScreenIndex(): Int {
        val n = resolvedScreens().size
        if (n == 0) return 0
        return panel.activeScreen.coerceIn(0, n - 1)
    }

    fun needsFocusablePanel(): Boolean {
        if (flattenWidgets().any { it.isInteractiveInput() }) return true
        return false
    }

    fun flattenWidgets(): List<WidgetConfig> {
        val out = mutableListOf<WidgetConfig>()
        fun walk(list: List<WidgetConfig>) {
            for (w in list) {
                if (w.type == "tabs") {
                    w.tabs.forEach { tab -> walk(tab.widgets) }
                } else {
                    out.add(w)
                }
            }
        }
        resolvedScreens().forEach { sc -> walk(sc.widgets) }
        walk(chromeWidgets())
        if (screens.isEmpty() && widgets.isNotEmpty()) walk(widgets)
        return out
    }

    companion object {
        val DEFAULT = LayoutConfig(
            enabled = true,
            panel = PanelConfig(
                widthDp = 360,
                widthMode = "auto",
                layoutMode = "free",
                displayMode = "host",
            ),
            screens = listOf(
                ScreenConfig(
                    title = "标签页1",
                    widgets = listOf(
                        WidgetConfig("hint", "text", text = "请填写登陆账号信息", textStyle = "title", layoutH = 40),
                        WidgetConfig("account", "input", label = "账号", placeholder = "请输入账号", layoutY = 88, layoutH = 64),
                    ),
                ),
                ScreenConfig(
                    title = "界面1",
                    widgets = listOf(
                        WidgetConfig("mode", "select", label = "模式", width = 2, options = listOf("普通", "极速"), default = "普通", layoutH = 64),
                    ),
                ),
            ),
            widgets = emptyList(),
        )

        fun parse(json: String): LayoutConfig {
            if (json.isBlank()) return DEFAULT
            val root = JSONObject(json)
            val panel = parsePanel(root.optJSONObject("panel"))
            val hostLike = panel.displayMode.equals("host", ignoreCase = true) ||
                panel.displayMode.equals("form", ignoreCase = true)
            val screensArr = root.optJSONArray("screens")
            val widgetArr = when {
                root.has("widgets") -> root.optJSONArray("widgets")
                else -> root.optJSONArray("buttons")
            } ?: JSONArray()
            val rawWidgets = parseWidgetArray(widgetArr)
            val screens = if (screensArr != null && screensArr.length() > 0) {
                parseScreenArray(screensArr)
            } else {
                emptyList()
            }
            val chrome = when {
                screens.isEmpty() -> rawWidgets
                hostLike -> emptyList()
                else -> rawWidgets.filter { it.isActionControl() && it.type != "stop_script" }
                    .ifEmpty { defaultChrome() }
            }
            val resolvedScreens = screens.ifEmpty { legacyScreensFromWidgets(rawWidgets) }
            return LayoutConfig(
                version = root.optInt("version", if (screens.isNotEmpty()) 3 else 2),
                enabled = root.optBoolean("enabled", true),
                panel = panel,
                screens = resolvedScreens,
                widgets = if (screens.isNotEmpty()) chrome else emptyList(),
            ).let { cfg ->
                if (!hostLike && cfg.screens.isNotEmpty() && cfg.widgets.isEmpty()) {
                    cfg.copy(widgets = defaultChrome())
                } else {
                    cfg
                }
            }
        }

        private fun defaultChrome(): List<WidgetConfig> = listOf(
            WidgetConfig("start", "start_script", label = "开始", color = "#2563EB", layoutW = 672, layoutH = 52),
        )

        private fun legacyScreensFromWidgets(widgets: List<WidgetConfig>): List<ScreenConfig> {
            val screens = mutableListOf<ScreenConfig>()
            val loose = mutableListOf<WidgetConfig>()
            for (w in widgets) {
                when {
                    w.type == "tabs" -> w.tabs.forEach { tab ->
                        screens.add(ScreenConfig(tab.title, tab.widgets))
                    }
                    w.isActionControl() -> Unit
                    else -> loose.add(w)
                }
            }
            if (screens.isEmpty()) {
                return listOf(
                    ScreenConfig("界面1", loose.ifEmpty { widgets.filter { !it.isActionControl() } }),
                )
            }
            if (loose.isNotEmpty()) {
                val first = screens[0]
                screens[0] = first.copy(widgets = first.widgets + loose)
            }
            return screens
        }

        private fun parseScreenArray(arr: JSONArray): List<ScreenConfig> {
            val out = mutableListOf<ScreenConfig>()
            for (i in 0 until arr.length()) {
                val obj = arr.getJSONObject(i)
                out.add(
                    ScreenConfig(
                        title = obj.optString("title", "界面${i + 1}"),
                        widgets = parseWidgetArray(obj.optJSONArray("widgets") ?: JSONArray()),
                    ),
                )
            }
            return out
        }

        private fun parsePanel(panelObj: JSONObject?): PanelConfig = PanelConfig(
            title = panelObj?.optString("title", "脚本助手") ?: "脚本助手",
            widthDp = panelObj?.optInt("width_dp", 220) ?: 220,
            widthMode = panelObj?.optString("width_mode", "fixed") ?: "fixed",
            heightMode = panelObj?.optString("height_mode", "wrap") ?: "wrap",
            heightDp = panelObj?.optInt("height_dp", 1280) ?: 1280,
            displayMode = panelObj?.optString("display_mode", "host") ?: "host",
            autoCollapseIdleMs = panelObj?.optInt("auto_collapse_idle_ms", 0) ?: 0,
            opacity = panelObj?.optDouble("opacity", 0.96)?.toFloat() ?: 0.96f,
            position = panelObj?.optString("position", "right_center") ?: "right_center",
            startX = panelObj?.optInt("start_x", 20) ?: 20,
            startY = panelObj?.optInt("start_y", 200) ?: 20,
            columns = panelObj?.optInt("columns", 2) ?: 2,
            ballSizeDp = panelObj?.optInt("ball_size_dp", 48) ?: 48,
            showLog = panelObj?.optBoolean("show_log", true) ?: true,
            logHeightDp = panelObj?.optInt("log_height_dp", 88) ?: 88,
            draggable = panelObj?.optBoolean("draggable", true) ?: true,
            collapsible = panelObj?.optBoolean("collapsible", true) ?: true,
            theme = panelObj?.optString("theme", "light") ?: "light",
            allowDesign = panelObj?.optBoolean("allow_design", true) ?: true,
            startConfirmCollapse = panelObj?.optBoolean("start_confirm_collapse", true) ?: true,
            layoutMode = panelObj?.optString("layout_mode", "grid") ?: "grid",
            designWidth = panelObj?.optInt("design_width", 720) ?: 720,
            designHeight = panelObj?.optInt("design_height", 1280) ?: 1280,
            activeScreen = panelObj?.optInt("active_screen", 0) ?: 0,
            showOnLaunch = panelObj?.optBoolean("show_on_launch", false) ?: false,
        )

        private fun parseWidgetArray(arr: JSONArray): List<WidgetConfig> {
            val out = mutableListOf<WidgetConfig>()
            for (i in 0 until arr.length()) {
                out.add(parseWidget(arr.getJSONObject(i), i))
            }
            return out
        }

        private fun parseWidget(obj: JSONObject, index: Int): WidgetConfig {
            val type = obj.optString("type", "tap")
            val id = obj.optString("id", "w_$index").ifBlank { "w_$index" }
            val tabs = mutableListOf<TabConfig>()
            val tabsArr = obj.optJSONArray("tabs")
            if (tabsArr != null) {
                for (t in 0 until tabsArr.length()) {
                    val tabObj = tabsArr.getJSONObject(t)
                    tabs.add(
                        TabConfig(
                            title = tabObj.optString("title", "页签"),
                            widgets = parseWidgetArray(tabObj.optJSONArray("widgets") ?: JSONArray()),
                        ),
                    )
                }
            }
            return WidgetConfig(
                id = id,
                type = type,
                label = obj.optString("label", obj.optString("text", "控件")),
                text = obj.optString("text", ""),
                color = obj.optString("color", "#2563EB"),
                width = obj.optInt("width", 1).coerceIn(1, 3),
                action = obj.optString("action", ""),
                placeholder = obj.optString("placeholder", ""),
                default = obj.optString("default", ""),
                defaultStart = obj.optString("default_start", ""),
                defaultEnd = obj.optString("default_end", ""),
                options = parseStringArray(obj.optJSONArray("options")),
                tabs = tabs,
                x = obj.optInt("x", 0),
                y = obj.optInt("y", 0),
                x1 = obj.optInt("x1", 0),
                y1 = obj.optInt("y1", 0),
                x2 = obj.optInt("x2", 0),
                y2 = obj.optInt("y2", 0),
                durationMs = obj.optInt("duration_ms", 300),
                lua = obj.optString("lua", ""),
                required = obj.optBoolean("required", false),
                min = if (obj.has("min")) obj.optDouble("min") else null,
                max = if (obj.has("max")) obj.optDouble("max") else null,
                step = obj.optInt("step", 1).coerceAtLeast(1),
                rows = obj.optInt("rows", 3).coerceAtLeast(2),
                textStyle = obj.optString("text_style", "normal"),
                align = obj.optString("align", "left"),
                layoutX = obj.optInt("layout_x", 24),
                layoutY = obj.optInt("layout_y", 120 + index * 72),
                layoutW = obj.optInt("layout_w", 672),
                layoutH = obj.optInt("layout_h", 56),
            )
        }

        private fun parseStringArray(arr: JSONArray?): List<String> {
            if (arr == null) return emptyList()
            return (0 until arr.length()).mapNotNull { i ->
                arr.optString(i, "").takeIf { it.isNotBlank() }
            }
        }
    }
}
