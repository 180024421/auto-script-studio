package com.autoscript.core.overlay

object WidgetValidator {
    fun validate(cfg: WidgetConfig, value: String): String? {
        val trimmed = value.trim()
        if (cfg.required && trimmed.isEmpty()) {
            return "「${cfg.label.ifBlank { cfg.id }}」为必填项"
        }
        if (cfg.min != null || cfg.max != null) {
            if (trimmed.isEmpty()) return null
            val num = trimmed.toDoubleOrNull() ?: return "须为数字"
            cfg.min?.let { if (num < it) return "不能小于 $it" }
            cfg.max?.let { if (num > it) return "不能大于 $it" }
        }
        return null
    }
}
