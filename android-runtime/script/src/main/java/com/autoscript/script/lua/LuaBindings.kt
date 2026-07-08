package com.autoscript.script.lua

import com.autoscript.core.model.Detection
import com.autoscript.core.overlay.OverlayWidgetStore
import kotlinx.coroutines.runBlocking
import org.luaj.vm2.Globals
import org.luaj.vm2.LuaInteger
import org.luaj.vm2.LuaString
import org.luaj.vm2.LuaTable
import org.luaj.vm2.LuaValue
import org.luaj.vm2.Varargs
import org.luaj.vm2.lib.OneArgFunction
import org.luaj.vm2.lib.TwoArgFunction
import org.luaj.vm2.lib.VarArgFunction

object LuaBindings {
    private var watchListener: ((String, String) -> Unit)? = null

    fun install(globals: LuaValue, bridge: AutoScriptBridge, onLog: (String) -> Unit) {
        val g = globals as Globals
        PanelWatchRegistry.clear()
        watchListener?.let { OverlayWidgetStore.removeChangeListener(it) }
        watchListener = { id, value -> PanelWatchRegistry.notify(g, id, value) }
        OverlayWidgetStore.addChangeListener(watchListener!!)
        val bot = LuaTable()
        bot.set("delay", DelayFn(bridge))
        bot.set("tap", TapFn(bridge))
        bot.set("swipe", SwipeFn(bridge))
        bot.set("longPress", LongPressFn(bridge))
        bot.set("findImage", FindImageFn(bridge))
        bot.set("findColor", FindColorFn(bridge))
        bot.set("findText", FindTextFn(bridge))
        bot.set("findNode", FindNodeFn(bridge))
        bot.set("recognizeText", RecognizeTextFn(bridge))
        bot.set("yoloDetect", YoloDetectFn(bridge))
        bot.set("findYolo", FindYoloFn(bridge))
        bot.set("yoloSwipe", YoloSwipeFn(bridge))
        bot.set("read_chain", ReadChainFn())
        bot.set("load_bases", LoadBasesFn())
        bot.set("set_memory_pid", SetMemoryPidFn())
        bot.set("set_pointer_size", SetPointerSizeFn())
        bot.set("log", object : OneArgFunction() {
            override fun call(msg: LuaValue): LuaValue {
                onLog(msg.tojstring())
                return NIL
            }
        })
        globals.set("bot", bot)
        val mem = LuaTable()
        mem.set("read_chain", bot.get("read_chain"))
        mem.set("load_bases", bot.get("load_bases"))
        mem.set("list_modules", object : OneArgFunction() {
            override fun call(refresh: LuaValue): LuaValue {
                val mods = MemoryReader.listModules(refresh.toboolean())
                val t = LuaTable()
                mods.forEach { (k, v) -> t.set(k, LuaInteger.valueOf(v)) }
                return t
            }
        })
        globals.set("mem", mem)
        val panel = LuaTable()
        panel.set("get", object : OneArgFunction() {
            override fun call(id: LuaValue): LuaValue = LuaString.valueOf(OverlayWidgetStore.get(id.checkjstring()))
        })
        panel.set("set", object : TwoArgFunction() {
            override fun call(id: LuaValue, value: LuaValue): LuaValue {
                OverlayWidgetStore.set(id.checkjstring(), value.tojstring())
                return NIL
            }
        })
        panel.set("is", object : TwoArgFunction() {
            override fun call(id: LuaValue, expected: LuaValue): LuaValue =
                LuaValue.valueOf(OverlayWidgetStore.isValue(id.checkjstring(), expected.checkjstring()))
        })
        panel.set("has", object : TwoArgFunction() {
            override fun call(id: LuaValue, option: LuaValue): LuaValue =
                LuaValue.valueOf(OverlayWidgetStore.hasOption(id.checkjstring(), option.checkjstring()))
        })
        panel.set("values", object : OneArgFunction() {
            override fun call(_arg: LuaValue): LuaValue {
                val t = LuaTable()
                OverlayWidgetStore.all().forEach { (k, v) -> t.set(k, LuaString.valueOf(v)) }
                return t
            }
        })
        panel.set("watch", object : TwoArgFunction() {
            override fun call(id: LuaValue, fn: LuaValue): LuaValue {
                if (!fn.isfunction()) {
                    throw org.luaj.vm2.LuaError("panel.watch 第二个参数须为函数")
                }
                PanelWatchRegistry.register(id.checkjstring(), fn.checkfunction())
                return NIL
            }
        })
        panel.set("unwatch", object : VarArgFunction() {
            override fun invoke(args: Varargs): Varargs {
                val id = args.arg(1).checkjstring()
                val fn = if (args.narg() >= 2 && args.arg(2).isfunction()) args.arg(2).checkfunction() else null
                PanelWatchRegistry.unregister(id, fn)
                return NONE
            }
        })
        panel.set("isOn", object : OneArgFunction() {
            override fun call(id: LuaValue): LuaValue =
                LuaValue.valueOf(OverlayWidgetStore.isOn(id.checkjstring()))
        })
        panel.set("getTimeRange", object : OneArgFunction() {
            override fun call(id: LuaValue): LuaValue {
                val (start, end) = OverlayWidgetStore.timeRange(id.checkjstring())
                val t = LuaTable()
                t.set("start", start)
                t.set("end", end)
                return t
            }
        })
        panel.set("snapshot", object : OneArgFunction() {
            override fun call(_arg: LuaValue): LuaValue {
                val t = LuaTable()
                OverlayWidgetStore.all().forEach { (k, v) -> t.set(k, LuaString.valueOf(v)) }
                return t
            }
        })
        globals.set("panel", panel)
        val loaded = globals.get("package").checktable().get("loaded").checktable()
        loaded.set("autoscript", bot)
    }

    /** 协程 yield → 调用 bot.delay，便于 Lua 协程式写法。 */
    fun installCoroutineYield(globals: LuaValue, bridge: AutoScriptBridge) {
        val co = globals.get("coroutine")
        if (!co.istable()) return
        co.checktable().set("yield", object : VarArgFunction() {
            override fun invoke(args: Varargs): Varargs {
                val sec = if (args.narg() >= 1) args.arg(1).todouble() else 0.0
                runBlocking { bridge.delaySeconds(sec) }
                return NONE
            }
        })
    }

    private class DelayFn(private val bridge: AutoScriptBridge) : OneArgFunction() {
        override fun call(seconds: LuaValue): LuaValue {
            runBlocking { bridge.delaySeconds(seconds.todouble()) }
            return NIL
        }
    }

    private class TapFn(private val bridge: AutoScriptBridge) : TwoArgFunction() {
        override fun call(x: LuaValue, y: LuaValue): LuaValue {
            runBlocking { bridge.tap(x.toint(), y.toint()) }
            return NIL
        }
    }

    private class SwipeFn(private val bridge: AutoScriptBridge) : VarArgFunction() {
        override fun invoke(args: Varargs): Varargs {
            val x1 = args.arg(1).toint()
            val y1 = args.arg(2).toint()
            val x2 = args.arg(3).toint()
            val y2 = args.arg(4).toint()
            val dur = if (args.narg() >= 5) args.arg(5).toint() else 300
            runBlocking { bridge.swipe(x1, y1, x2, y2, dur) }
            return NONE
        }
    }

    private class LongPressFn(private val bridge: AutoScriptBridge) : VarArgFunction() {
        override fun invoke(args: Varargs): Varargs {
            val x = args.arg(1).toint()
            val y = args.arg(2).toint()
            val dur = if (args.narg() >= 3) args.arg(3).toint() else 500
            runBlocking { bridge.longPress(x, y, dur) }
            return NONE
        }
    }

    private class FindImageFn(private val bridge: AutoScriptBridge) : VarArgFunction() {
        override fun invoke(args: Varargs): Varargs {
            val path = args.arg(1).checkjstring()
            val opts = LuaOpts.table(if (args.narg() >= 2) args.arg(2) else null)
            val pt = runBlocking { bridge.findImage(path, opts) }
            return ptToVarargs(pt)
        }
    }

    private class FindColorFn(private val bridge: AutoScriptBridge) : VarArgFunction() {
        override fun invoke(args: Varargs): Varargs {
            val b = args.arg(1).toint()
            val g = args.arg(2).toint()
            val r = args.arg(3).toint()
            val opts = LuaOpts.table(if (args.narg() >= 4 && args.arg(4).istable()) args.arg(4) else null)
            val pt = runBlocking { bridge.findColor(b, g, r, opts) }
            return ptToVarargs(pt)
        }
    }

    private class FindTextFn(private val bridge: AutoScriptBridge) : VarArgFunction() {
        override fun invoke(args: Varargs): Varargs {
            val target = args.arg(1).checkjstring()
            val opts = LuaOpts.table(if (args.narg() >= 2) args.arg(2) else null)
            val pt = runBlocking { bridge.findText(target, opts) }
            return ptToVarargs(pt)
        }
    }

    private class FindNodeFn(private val bridge: AutoScriptBridge) : VarArgFunction() {
        override fun invoke(args: Varargs): Varargs {
            val opts = LuaOpts.table(if (args.narg() >= 1) args.arg(1) else null)
            val pt = runBlocking { bridge.findNode(opts) }
            return ptToVarargs(pt)
        }
    }

    private class RecognizeTextFn(private val bridge: AutoScriptBridge) : VarArgFunction() {
        override fun invoke(args: Varargs): Varargs {
            val opts = LuaOpts.table(if (args.narg() >= 1) args.arg(1) else null)
            val hits = runBlocking { bridge.recognizeText(opts) }
            return LuaValue.varargsOf(arrayOf<LuaValue>(toLuaList(hits)))
        }
    }

    private class YoloDetectFn(private val bridge: AutoScriptBridge) : VarArgFunction() {
        override fun invoke(args: Varargs): Varargs {
            val opts = LuaOpts.table(if (args.narg() >= 1) args.arg(1) else null)
            val dets = runBlocking { bridge.yoloDetect(opts) }
            return LuaValue.varargsOf(arrayOf<LuaValue>(detectionsToLua(dets)))
        }
    }

    private class FindYoloFn(private val bridge: AutoScriptBridge) : VarArgFunction() {
        override fun invoke(args: Varargs): Varargs {
            val opts = LuaOpts.table(if (args.narg() >= 1) args.arg(1) else null)
            val pt = runBlocking { bridge.findYolo(opts) }
            return ptToVarargs(pt)
        }
    }

    private class YoloSwipeFn(private val bridge: AutoScriptBridge) : VarArgFunction() {
        override fun invoke(args: Varargs): Varargs {
            val opts = LuaOpts.table(if (args.narg() >= 1) args.arg(1) else null)
            runBlocking { bridge.yoloSwipe(opts) }
            return NONE
        }
    }

    private class ReadChainFn : VarArgFunction() {
        override fun invoke(args: Varargs): Varargs {
            val module = args.arg(1).checkjstring()
            val baseOff = parseHexOrLong(args.arg(2))
            val offsetsTable = args.arg(3).checktable()
            val vtype = if (args.narg() >= 4) args.arg(4).checkjstring() else "int32"
            val offsets = LongArray(offsetsTable.length()) { i ->
                parseHexOrLong(offsetsTable.get(i + 1))
            }
            val value = MemoryReader.readChain(module, baseOff, offsets, vtype)
            return when (value) {
                is Int -> LuaInteger.valueOf(value)
                is Long -> LuaInteger.valueOf(value)
                is Float -> LuaValue.valueOf(value.toDouble())
                is Double -> LuaValue.valueOf(value)
                else -> LuaString.valueOf(value.toString())
            }
        }
    }

    private class LoadBasesFn : OneArgFunction() {
        override fun call(path: LuaValue): LuaValue {
            val file = java.io.File(path.checkjstring())
            if (!file.isFile) throw org.luaj.vm2.LuaError("bases file not found: ${file.path}")
            val json = org.json.JSONObject(file.readText())
            val chains = json.getJSONArray("chains")
            val out = LuaTable()
            for (i in 0 until chains.length()) {
                val c = chains.getJSONObject(i)
                val name = c.getString("name")
                val module = c.getString("module")
                val moduleOffset = c.getLong("module_offset")
                val offsetsArr = c.getJSONArray("offsets")
                val offsets = LongArray(offsetsArr.length()) { j -> offsetsArr.getLong(j) }
                val vtype = c.optString("type", "int32")
                out.set(name, object : VarArgFunction() {
                    override fun invoke(_args: Varargs): Varargs {
                        val value = MemoryReader.readChain(module, moduleOffset, offsets, vtype)
                        return when (value) {
                            is Int -> LuaInteger.valueOf(value)
                            is Long -> LuaInteger.valueOf(value)
                            is Float -> LuaValue.valueOf(value.toDouble())
                            is Double -> LuaValue.valueOf(value)
                            else -> LuaString.valueOf(value.toString())
                        }
                    }
                })
            }
            return out
        }
    }

    private class SetMemoryPidFn : OneArgFunction() {
        override fun call(pid: LuaValue): LuaValue {
            MemoryReader.setTargetPid(pid.toint())
            return NIL
        }
    }

    private class SetPointerSizeFn : OneArgFunction() {
        override fun call(size: LuaValue): LuaValue {
            MemoryReader.setPointerSize(size.toint())
            return NIL
        }
    }

    private fun parseHexOrLong(v: LuaValue): Long {
        if (v.isstring()) {
            val s = v.tojstring().trim()
            if (s.startsWith("0x", true)) return s.substring(2).toLong(16)
            return s.toLong()
        }
        return v.tolong()
    }

    private fun ptToVarargs(pt: Pair<Int, Int>?): Varargs =
        if (pt != null) {
            LuaValue.varargsOf(LuaInteger.valueOf(pt.first), LuaInteger.valueOf(pt.second))
        } else {
            LuaValue.NIL
        }

    private fun detectionsToLua(dets: List<Detection>): LuaTable {
        val arr = LuaTable()
        dets.forEachIndexed { i, d ->
            val t = LuaTable()
            t.set("class_name", d.className)
            t.set("confidence", d.confidence.toDouble())
            t.set("x", d.rect.x + d.rect.w / 2)
            t.set("y", d.rect.y + d.rect.h / 2)
            t.set("left", d.rect.x)
            t.set("top", d.rect.y)
            t.set("width", d.rect.w)
            t.set("height", d.rect.h)
            arr.set(i + 1, t)
        }
        return arr
    }

    private fun toLuaList(items: List<Map<String, Any>>): LuaTable {
        val arr = LuaTable()
        items.forEachIndexed { i, m ->
            val t = LuaTable()
            m.forEach { (k, v) ->
                t.set(k, when (v) {
                    is Int -> LuaInteger.valueOf(v)
                    is Float -> LuaValue.valueOf(v.toDouble())
                    is Double -> LuaValue.valueOf(v)
                    else -> LuaString.valueOf(v.toString())
                })
            }
            arr.set(i + 1, t)
        }
        return arr
    }
}
