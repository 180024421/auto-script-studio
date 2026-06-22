package com.autoscript.script.lua

import com.autoscript.core.model.Rect
import org.luaj.vm2.LuaTable
import org.luaj.vm2.LuaValue

internal object LuaOpts {

    fun table(value: LuaValue?): Map<String, Any?> {
        if (value == null || value.isnil() || !value.istable()) return emptyMap()
        val t = value.checktable()
        val out = linkedMapOf<String, Any?>()
        var k = LuaValue.NIL
        while (true) {
            val next = t.next(k)
            if (next.arg1().isnil()) break
            k = next.arg1()
            out[k.tojstring()] = toJava(next.arg(2))
        }
        return out
    }

    fun str(map: Map<String, Any?>, key: String, default: String = ""): String =
        map[key]?.toString()?.trim().takeUnless { it.isNullOrEmpty() } ?: default

    fun int(map: Map<String, Any?>, key: String, default: Int = 0): Int = when (val v = map[key]) {
        is Number -> v.toInt()
        is String -> v.toIntOrNull() ?: default
        else -> default
    }

    fun float(map: Map<String, Any?>, key: String, default: Float = 0f): Float = when (val v = map[key]) {
        is Number -> v.toFloat()
        is String -> v.toFloatOrNull() ?: default
        else -> default
    }

    fun bool(map: Map<String, Any?>, key: String, default: Boolean = false): Boolean = when (val v = map[key]) {
        is Boolean -> v
        is Number -> v.toInt() != 0
        is String -> v.equals("true", true) || v == "1"
        else -> default
    }

    fun roi(map: Map<String, Any?>): Rect? {
        val v = map["roi"] ?: return null
        if (v is List<*> && v.size == 4) {
            return Rect(
                (v[0] as Number).toInt(),
                (v[1] as Number).toInt(),
                (v[2] as Number).toInt(),
                (v[3] as Number).toInt(),
            )
        }
        if (v is Map<*, *>) {
            return Rect(
                (v["x"] as Number).toInt(),
                (v["y"] as Number).toInt(),
                (v["w"] as Number).toInt(),
                (v["h"] as Number).toInt(),
            )
        }
        return null
    }

    fun frac(map: Map<String, Any?>): Pair<Float, Float> {
        val v = map["frac"]
        if (v is List<*> && v.size == 2) {
            return (v[0] as Number).toFloat() to (v[1] as Number).toFloat()
        }
        return 0.5f to 0.5f
    }

    private fun toJava(v: LuaValue): Any? = when {
        v.isnil() -> null
        v.isboolean() -> v.toboolean()
        v.isint() -> v.toint()
        v.islong() -> v.tolong()
        v.isnumber() -> v.todouble()
        v.isstring() -> v.tojstring()
        v.istable() -> tableToList(v.checktable())
        else -> v.tojstring()
    }

    private fun tableToList(t: LuaTable): Any {
        if (t.length() > 0) {
            return (1..t.length()).map { i ->
                toJava(t.get(i))
            }
        }
        return table(t)
    }
}
