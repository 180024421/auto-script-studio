package com.autoscript.script.saocheng

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.util.Calendar

data class HeroConfig(
    val name: String,
    val hourlyLimit: Int = 3,
    val enabled: Boolean = false,
)

data class SaochengConfig(
    val cities: List<Int> = emptyList(),
    val heroes: List<HeroConfig> = FlowConstants.DEFAULT_HERO_NAMES.map { HeroConfig(it, 3, false) },
    val playerName: String = "",
)

data class SaochengState(
    var cityIndex: Int = 0,
    val heroPushes: MutableMap<String, MutableList<Long>> = mutableMapOf(),
    var waitingNextHour: Boolean = false,
    var waitStartedHour: Int = -1,
)

class SaochengConfigStore(private val context: Context) {
    private val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun loadConfig(): SaochengConfig {
        val citiesStr = prefs.getString(KEY_CITIES, "") ?: ""
        val cities = citiesStr.split(",", "，", " ", ";")
            .mapNotNull { it.trim().toIntOrNull() }

        val heroes = FlowConstants.DEFAULT_HERO_NAMES.map { name ->
            HeroConfig(
                name = name,
                hourlyLimit = prefs.getInt("${KEY_HERO_LIMIT}_$name", 3).coerceAtLeast(1),
                enabled = prefs.getBoolean("${KEY_HERO_ENABLED}_$name", false),
            )
        }
        return SaochengConfig(
            cities = cities,
            heroes = heroes,
            playerName = prefs.getString(KEY_PLAYER_NAME, "") ?: "",
        )
    }

    fun saveConfig(cfg: SaochengConfig) {
        prefs.edit()
            .putString(KEY_CITIES, cfg.cities.joinToString(","))
            .putString(KEY_PLAYER_NAME, cfg.playerName)
            .apply()
        cfg.heroes.forEach { h ->
            prefs.edit()
                .putBoolean("${KEY_HERO_ENABLED}_${h.name}", h.enabled)
                .putInt("${KEY_HERO_LIMIT}_${h.name}", h.hourlyLimit)
                .apply()
        }
    }

    fun loadState(): SaochengState {
        val json = prefs.getString(KEY_STATE, null) ?: return SaochengState()
        return try {
            val o = JSONObject(json)
            val pushes = mutableMapOf<String, MutableList<Long>>()
            val hp = o.optJSONObject("hero_pushes")
            if (hp != null) {
                hp.keys().forEach { key ->
                    val arr = hp.optJSONArray(key) ?: JSONArray()
                    val list = mutableListOf<Long>()
                    for (i in 0 until arr.length()) list.add(arr.getLong(i))
                    pushes[key] = list
                }
            }
            SaochengState(
                cityIndex = o.optInt("city_index", 0),
                heroPushes = pushes,
                waitingNextHour = o.optBoolean("waiting_next_hour", false),
                waitStartedHour = o.optInt("wait_started_hour", -1),
            )
        } catch (_: Exception) {
            SaochengState()
        }
    }

    fun saveState(st: SaochengState) {
        val hp = JSONObject()
        st.heroPushes.forEach { (k, v) ->
            hp.put(k, JSONArray(v))
        }
        val o = JSONObject()
            .put("city_index", st.cityIndex)
            .put("hero_pushes", hp)
            .put("waiting_next_hour", st.waitingNextHour)
            .put("wait_started_hour", st.waitStartedHour)
        prefs.edit().putString(KEY_STATE, o.toString()).apply()
    }

    fun heroPushCount(st: SaochengState, heroName: String): Int {
        val now = System.currentTimeMillis()
        val list = st.heroPushes[heroName].orEmpty().filter { now - it < 3600_000L }
        st.heroPushes[heroName] = list.toMutableList()
        return list.size
    }

    fun heroCanPush(cfg: SaochengConfig, st: SaochengState, heroName: String): Boolean {
        val h = cfg.heroes.find { it.name == heroName && it.enabled } ?: return false
        return heroPushCount(st, heroName) < h.hourlyLimit.coerceAtLeast(1)
    }

    fun enabledHeroes(cfg: SaochengConfig, st: SaochengState): List<HeroConfig> =
        cfg.heroes.filter { it.enabled && heroCanPush(cfg, st, it.name) }

    fun recordHeroPush(st: SaochengState, heroName: String) {
        val list = st.heroPushes.getOrPut(heroName) { mutableListOf() }
        list.add(System.currentTimeMillis())
        val now = System.currentTimeMillis()
        st.heroPushes[heroName] = list.filter { now - it < 3600_000L }.toMutableList()
        saveState(st)
    }

    fun allEnabledHeroesAtLimit(cfg: SaochengConfig, st: SaochengState): Boolean {
        val enabled = cfg.heroes.filter { it.enabled }
        if (enabled.isEmpty()) return false
        return enabled.all { !heroCanPush(cfg, st, it.name) }
    }

    fun startWaitNextHour(st: SaochengState) {
        st.waitingNextHour = true
        st.waitStartedHour = Calendar.getInstance().get(Calendar.HOUR_OF_DAY)
        saveState(st)
    }

    fun isNextHourReached(st: SaochengState): Boolean {
        if (!st.waitingNextHour) return true
        if (st.waitStartedHour < 0) return true
        return Calendar.getInstance().get(Calendar.HOUR_OF_DAY) != st.waitStartedHour
    }

    fun clearWaitNextHour(st: SaochengState) {
        st.waitingNextHour = false
        st.waitStartedHour = -1
        saveState(st)
    }

    fun nextCityId(cfg: SaochengConfig, st: SaochengState): Int? {
        val cities = cfg.cities.filter { CityData.get(it) != null }
        if (cities.isEmpty()) return null
        return cities[st.cityIndex % cities.size]
    }

    fun advanceCity(st: SaochengState, cfg: SaochengConfig) {
        val cities = cfg.cities.filter { CityData.get(it) != null }
        if (cities.isNotEmpty()) {
            st.cityIndex = (st.cityIndex + 1) % cities.size
            saveState(st)
        }
    }

    companion object {
        private const val PREFS = "saocheng_local"
        private const val KEY_CITIES = "cities"
        private const val KEY_PLAYER_NAME = "player_name"
        private const val KEY_HERO_ENABLED = "hero_enabled"
        private const val KEY_HERO_LIMIT = "hero_limit"
        private const val KEY_STATE = "state_json"
    }
}
