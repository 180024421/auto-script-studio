package com.autoscript.core.overlay

/**
 * 不可变布局编辑操作。
 *
 * 路径约定（v3 screens + 旧 tabs 兼容）：
 * - 容器 `containerPath`：
 *   - `[]` = 根 widgets（网格）或 chrome（free）
 *   - `[screenIdx]` = 某界面 widgets（free，screenIdx >= 0）
 *   - `[-1]` = chrome widgets（free）
 *   - `[tabsIdx, tabIdx]` = 旧标签页内 widgets
 * - 控件 `widgetPath`：
 *   - 根 `[i]`；界面 `[screenIdx, childIdx]`；chrome `[-1, childIdx]`
 *   - 旧 tabs `[tabsIdx, tabIdx, childIdx]`
 */
object LayoutEditorOps {

    private const val CHROME_SCREEN = -1

    fun reorderInContainer(
        layout: LayoutConfig,
        containerPath: List<Int>,
        from: Int,
        to: Int,
    ): LayoutConfig {
        if (from == to) return layout
        val widgets = getContainerWidgets(layout, containerPath).toMutableList()
        if (from !in widgets.indices || to !in widgets.indices) return layout
        val item = widgets.removeAt(from)
        widgets.add(to, item)
        return setContainerWidgets(layout, containerPath, widgets)
    }

    fun setWidgetWidth(
        layout: LayoutConfig,
        widgetPath: List<Int>,
        width: Int,
    ): LayoutConfig {
        val span = width.coerceIn(1, 3)
        return updateWidgetAt(layout, widgetPath) { it.copy(width = span) }
    }

    fun setPanelWidthDp(layout: LayoutConfig, dp: Int): LayoutConfig =
        layout.copy(panel = layout.panel.copy(widthDp = dp.coerceIn(120, 480)))

    private fun getContainerWidgets(layout: LayoutConfig, containerPath: List<Int>): List<WidgetConfig> =
        when (containerPath.size) {
            0 -> if (layout.isFreeMode()) layout.chromeWidgets() else layout.widgets
            1 -> {
                val idx = containerPath[0]
                when {
                    idx == CHROME_SCREEN -> layout.chromeWidgets()
                    idx >= 0 -> layout.screenWidgets(idx)
                    else -> emptyList()
                }
            }
            2 -> {
                val tabsIdx = containerPath[0]
                val tabIdx = containerPath[1]
                layout.widgets.getOrNull(tabsIdx)?.tabs?.getOrNull(tabIdx)?.widgets.orEmpty()
            }
            else -> emptyList()
        }

    private fun setContainerWidgets(
        layout: LayoutConfig,
        containerPath: List<Int>,
        widgets: List<WidgetConfig>,
    ): LayoutConfig {
        return when (containerPath.size) {
            0 -> layout.copy(widgets = widgets)
            1 -> {
                val idx = containerPath[0]
                when {
                    idx == CHROME_SCREEN -> layout.copy(widgets = widgets)
                    idx >= 0 && layout.screens.isNotEmpty() -> {
                        val screens = layout.screens.toMutableList()
                        val sc = screens.getOrNull(idx) ?: return layout
                        screens[idx] = sc.copy(widgets = widgets)
                        layout.copy(screens = screens)
                    }
                    idx >= 0 -> {
                        val screens = layout.resolvedScreens().toMutableList()
                        if (idx !in screens.indices) return layout
                        screens[idx] = screens[idx].copy(widgets = widgets)
                        layout.copy(screens = screens)
                    }
                    else -> layout
                }
            }
            2 -> {
                val tabsIdx = containerPath[0]
                val tabIdx = containerPath[1]
                val root = layout.widgets.toMutableList()
                val tabsWidget = root.getOrNull(tabsIdx) ?: return layout
                val tabs = tabsWidget.tabs.toMutableList()
                val tab = tabs.getOrNull(tabIdx) ?: return layout
                tabs[tabIdx] = tab.copy(widgets = widgets)
                root[tabsIdx] = tabsWidget.copy(tabs = tabs)
                layout.copy(widgets = root)
            }
            else -> layout
        }
    }

    private fun updateWidgetAt(
        layout: LayoutConfig,
        widgetPath: List<Int>,
        transform: (WidgetConfig) -> WidgetConfig,
    ): LayoutConfig {
        return when (widgetPath.size) {
            1 -> {
                val idx = widgetPath[0]
                val root = layout.widgets.toMutableList()
                val w = root.getOrNull(idx) ?: return layout
                root[idx] = transform(w)
                layout.copy(widgets = root)
            }
            2 -> {
                val screenIdx = widgetPath[0]
                val childIdx = widgetPath[1]
                if (screenIdx == CHROME_SCREEN) {
                    val root = layout.widgets.toMutableList()
                    val w = root.getOrNull(childIdx) ?: return layout
                    root[childIdx] = transform(w)
                    return layout.copy(widgets = root)
                }
                val screens = layout.resolvedScreens().toMutableList()
                val sc = screens.getOrNull(screenIdx) ?: return layout
                val children = sc.widgets.toMutableList()
                val w = children.getOrNull(childIdx) ?: return layout
                children[childIdx] = transform(w)
                screens[screenIdx] = sc.copy(widgets = children)
                return layout.copy(screens = screens)
            }
            3 -> {
                val tabsIdx = widgetPath[0]
                val tabIdx = widgetPath[1]
                val childIdx = widgetPath[2]
                val root = layout.widgets.toMutableList()
                val tabsWidget = root.getOrNull(tabsIdx) ?: return layout
                val tabs = tabsWidget.tabs.toMutableList()
                val tab = tabs.getOrNull(tabIdx) ?: return layout
                val children = tab.widgets.toMutableList()
                val w = children.getOrNull(childIdx) ?: return layout
                children[childIdx] = transform(w)
                tabs[tabIdx] = tab.copy(widgets = children)
                root[tabsIdx] = tabsWidget.copy(tabs = tabs)
                layout.copy(widgets = root)
            }
            else -> layout
        }
    }
}
