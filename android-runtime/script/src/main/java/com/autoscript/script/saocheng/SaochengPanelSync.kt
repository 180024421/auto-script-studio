package com.autoscript.script.saocheng

import android.content.Context
import com.autoscript.core.overlay.OverlayWidgetStore

/** 将浮动面板 / 主界面表单值同步到扫城配置（SharedPreferences）。 */
object SaochengPanelSync {
    fun syncToStore(context: Context) {
        val store = SaochengConfigStore(context)
        val cityId = OverlayWidgetStore.get("city_id").trim().toIntOrNull()
        val player = OverlayWidgetStore.get("player_name").trim()
        val limit = OverlayWidgetStore.get("hourly_limit").trim().toIntOrNull()?.coerceAtLeast(1) ?: 3
        val selected = OverlayWidgetStore.get("heroes")
            .split(',', '，', ';')
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .toSet()
        val heroes = FlowConstants.DEFAULT_HERO_NAMES.map { name ->
            HeroConfig(name, limit, name in selected)
        }
        store.saveConfig(
            SaochengConfig(
                cities = if (cityId != null) listOf(cityId) else emptyList(),
                heroes = heroes,
                playerName = player,
            ),
        )
    }
}
