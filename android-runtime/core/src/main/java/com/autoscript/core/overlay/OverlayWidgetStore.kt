package com.autoscript.core.overlay

object OverlayWidgetStore {

    private val values = linkedMapOf<String, String>()
    private val changeListeners = mutableListOf<(String, String) -> Unit>()
    private var persistHook: ((String, String) -> Unit)? = null

    fun setPersistHook(hook: ((String, String) -> Unit)?) {
        persistHook = hook
    }

    fun reset(defaults: Map<String, String>) {
        values.clear()
        values.putAll(defaults)
    }

    fun get(id: String): String = values[id].orEmpty()

    fun set(id: String, value: String) {
        val old = values[id]
        values[id] = value
        if (old != value) {
            persistHook?.invoke(id, value)
            changeListeners.toList().forEach { it(id, value) }
        }
    }

    fun all(): Map<String, String> = values.toMap()

    fun addChangeListener(listener: (String, String) -> Unit) {
        if (!changeListeners.contains(listener)) changeListeners.add(listener)
    }

    fun removeChangeListener(listener: (String, String) -> Unit) {
        changeListeners.remove(listener)
    }

    fun clearChangeListeners() {
        changeListeners.clear()
    }

    fun isValue(id: String, expected: String): Boolean =
        get(id).trim().equals(expected.trim(), ignoreCase = true)

    fun isOn(id: String): Boolean {
        val v = get(id).trim().lowercase()
        return v in setOf("true", "1", "yes", "on")
    }

    fun hasOption(id: String, option: String): Boolean {
        val needle = option.trim()
        if (needle.isEmpty()) return false
        return get(id).split(',').any { it.trim().equals(needle, ignoreCase = true) }
    }

    fun timeRange(id: String): Pair<String, String> {
        val raw = get(id)
        if (raw.contains("-")) {
            val parts = raw.split("-", limit = 2)
            return parts[0].trim() to parts.getOrElse(1) { "" }.trim()
        }
        return "" to ""
    }

    fun seedFromLayout(layout: LayoutConfig, savedValues: Map<String, String> = emptyMap()) {
        val defaults = linkedMapOf<String, String>()
        for (w in layout.flattenWidgets()) {
            if (w.id.isBlank()) continue
            when (w.type) {
                in WidgetConfig.FORM_VALUE_TYPES -> {
                    defaults[w.id] = when (w.type) {
                        "switch" -> {
                            val raw = w.default.ifBlank { "false" }
                            if (raw.equals("true", true) || raw == "1") "true" else "false"
                        }
                        "time_range" -> w.default.ifBlank {
                            "${w.defaultStart.ifBlank { "09:00" }}-${w.defaultEnd.ifBlank { "18:00" }}"
                        }
                        else -> w.default
                    }
                }
            }
        }
        reset(defaults)
        savedValues.forEach { (id, value) ->
            if (defaults.containsKey(id) && value.isNotBlank()) {
                values[id] = value
            }
        }
    }

    @Deprecated("Use seedFromLayout", ReplaceWith("seedFromLayout(layout)"))
    fun seedFromWidgets(widgets: List<WidgetConfig>) {
        seedFromLayout(LayoutConfig(widgets = widgets))
    }
}
