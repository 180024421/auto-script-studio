package com.autoscript.script.saocheng

import android.content.Context
import org.json.JSONArray

data class CityInfo(val id: Int, val x: Int, val y: Int, val name: String)

object CityData {
    private var cities: Map<Int, CityInfo> = emptyMap()

    fun load(context: Context) {
        if (cities.isNotEmpty()) return
        val json = context.assets.open("project/cities.json").bufferedReader().readText()
        val arr = JSONArray(json)
        val map = LinkedHashMap<Int, CityInfo>(arr.length())
        for (i in 0 until arr.length()) {
            val o = arr.getJSONObject(i)
            val id = o.getInt("id")
            map[id] = CityInfo(
                id = id,
                x = o.getInt("x"),
                y = o.getInt("y"),
                name = o.optString("name", ""),
            )
        }
        cities = map
    }

    fun get(id: Int): CityInfo? = cities[id]

    /** 按城池名排序，供下拉选择 */
    fun allSortedByName(): List<CityInfo> =
        cities.values.sortedWith(compareBy({ it.name }, { it.id }))

    fun scaleCityScreenXY(cityId: Int, fullW: Int, fullH: Int): Pair<Int, Int> {
        val info = cities[cityId] ?: return 0 to 0
        return ScreenCoord.scalePoint(info.x.toFloat(), info.y.toFloat(), fullW, fullH)
    }
}
