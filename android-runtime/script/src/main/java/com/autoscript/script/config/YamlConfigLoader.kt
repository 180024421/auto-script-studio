package com.autoscript.script.config

import org.yaml.snakeyaml.Yaml

@Suppress("UNCHECKED_CAST")
class YamlConfigLoader {

    private val yaml = Yaml()

    fun load(text: String): MutableMap<String, Any?> =
        (yaml.load(text) as? MutableMap<String, Any?>) ?: mutableMapOf()

    fun mergeIncludes(base: MutableMap<String, Any?>, loader: (String) -> String) {
        val includes = base.remove("includes") as? List<*> ?: return
        var merged = mutableMapOf<String, Any?>()
        for (inc in includes) {
            val path = inc.toString()
            val child = load(loader(path))
            mergeIncludes(child, loader)
            merged = deepMerge(merged, child)
        }
        base.putAll(deepMerge(merged, base))
    }

    private fun deepMerge(a: Map<String, Any?>, b: Map<String, Any?>): MutableMap<String, Any?> {
        val out = a.toMutableMap()
        for ((k, v) in b) {
            val av = out[k]
            if (av is Map<*, *> && v is Map<*, *>) {
                @Suppress("UNCHECKED_CAST")
                out[k] = deepMerge(av as Map<String, Any?>, v as Map<String, Any?>)
            } else {
                out[k] = v
            }
        }
        return out
    }
}
