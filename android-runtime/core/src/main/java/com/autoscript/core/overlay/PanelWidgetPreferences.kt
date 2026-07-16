package com.autoscript.core.overlay

import android.content.Context

/** 面板表单值持久化（按工程 package_id 隔离），重启后自动恢复。 */
object PanelWidgetPreferences {

    private const val PREFS = "panel_widget_values"

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    private fun key(projectId: String, widgetId: String): String = "$projectId::$widgetId"

    fun get(context: Context, projectId: String, widgetId: String): String? {
        if (projectId.isBlank() || widgetId.isBlank()) return null
        return prefs(context).getString(key(projectId, widgetId), null)
    }

    fun set(context: Context, projectId: String, widgetId: String, value: String) {
        if (projectId.isBlank() || widgetId.isBlank()) return
        prefs(context).edit().putString(key(projectId, widgetId), value).apply()
    }

    fun loadAll(context: Context, projectId: String): Map<String, String> {
        if (projectId.isBlank()) return emptyMap()
        val prefix = "$projectId::"
        return prefs(context).all.mapNotNull { (k, v) ->
            if (!k.startsWith(prefix)) return@mapNotNull null
            val id = k.removePrefix(prefix)
            val text = v?.toString().orEmpty()
            if (id.isBlank() || text.isBlank()) null else id to text
        }.toMap()
    }

    fun attach(context: Context, projectId: String, layout: LayoutConfig) {
        val saved = loadAll(context, projectId)
        OverlayWidgetStore.setPersistHook { id, value ->
            set(context, projectId, id, value)
        }
        OverlayWidgetStore.seedFromLayout(layout, saved)
    }
}
