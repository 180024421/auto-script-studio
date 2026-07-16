package com.autoscript.script.lua

import java.io.File
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Android 进程内存读取 / 按值搜索（需 root 或可读目标 `/proc/pid/mem`）。
 * 供 ce-base 指针链与面板「会话锁定」使用。
 */
object MemoryReader {
    data class Region(val start: Long, val end: Long, val path: String)

    data class SessionSlot(
        val key: String,
        val type: String,
        var candidates: MutableList<Long> = mutableListOf(),
        var locked: Long? = null,
    )

    private var targetPid: Int = android.os.Process.myPid()
    private var pointerSize: Int = 8
    private val moduleCache = mutableMapOf<String, Long>()
    private val sessions = linkedMapOf<String, SessionSlot>()

    /** 单次搜索最多保留候选数，防止 OOM / 过慢。 */
    var maxCandidates: Int = 800

    /** 单段 maps 区域最大扫描字节（超出则跳过）。 */
    var maxRegionBytes: Long = 48L * 1024 * 1024

    fun setTargetPid(pid: Int) {
        targetPid = pid
        moduleCache.clear()
    }

    fun getTargetPid(): Int = targetPid

    fun setPointerSize(size: Int) {
        pointerSize = if (size == 4) 4 else 8
    }

    fun clearSession(key: String? = null) {
        if (key.isNullOrBlank()) {
            sessions.clear()
        } else {
            sessions.remove(key.trim())
        }
    }

    fun sessionKeys(): List<String> = sessions.keys.toList()

    fun getLockedAddress(key: String): Long? = sessions[key.trim()]?.locked

    fun candidateCount(key: String): Int = sessions[key.trim()]?.candidates?.size ?: 0

    fun findPidByPackage(packageName: String): Int {
        val pkg = packageName.trim()
        if (pkg.isEmpty()) throw IllegalArgumentException("package empty")
        val proc = File("/proc")
        proc.listFiles()?.forEach { dir ->
            val pid = dir.name.toIntOrNull() ?: return@forEach
            val cmdline = File(dir, "cmdline")
            if (!cmdline.canRead()) return@forEach
            val text = runCatching {
                cmdline.readBytes().toString(Charsets.UTF_8).substringBefore('\u0000').trim()
            }.getOrNull() ?: return@forEach
            if (text == pkg || text.endsWith("/$pkg") || text.contains(pkg)) {
                return pid
            }
        }
        throw IllegalStateException("pid not found for package: $pkg")
    }

    fun listModules(refresh: Boolean = false): Map<String, Long> {
        if (!refresh && moduleCache.isNotEmpty()) {
            return moduleCache.toMap()
        }
        moduleCache.clear()
        val maps = File("/proc/$targetPid/maps")
        if (!maps.canRead()) return emptyMap()
        maps.forEachLine { line ->
            val parts = line.trim().split(Regex("\\s+"), limit = 6)
            if (parts.size < 6) return@forEachLine
            val range = parts[0].split("-")
            if (range.size != 2) return@forEachLine
            val start = range[0].toLongOrNull(16) ?: return@forEachLine
            val path = parts.getOrElse(5) { "" }
            val name = path.substringAfterLast('/')
            if (name.isNotBlank() && !moduleCache.containsKey(name)) {
                moduleCache[name] = start
            }
        }
        return moduleCache.toMap()
    }

    fun getModuleBase(moduleName: String): Long {
        val cached = moduleCache[moduleName]
        if (cached != null) return cached
        val modules = listModules(refresh = true)
        modules[moduleName]?.let { return it }
        val key = moduleName.substringAfterLast('/')
        modules[key]?.let { return it }
        val fuzzy = modules.entries.firstOrNull { (k, _) ->
            k.contains(moduleName, ignoreCase = true) || moduleName.contains(k, ignoreCase = true)
        }
        return fuzzy?.value ?: throw IllegalStateException("module not found: $moduleName")
    }

    fun readBytes(address: Long, size: Int): ByteArray {
        val mem = File("/proc/$targetPid/mem")
        RandomAccessFile(mem, "r").use { raf ->
            raf.seek(address)
            val buf = ByteArray(size)
            val read = raf.read(buf)
            if (read < size) throw IllegalStateException("short read @ 0x${address.toString(16)}")
            return buf
        }
    }

    fun resolveChain(moduleName: String, moduleOffset: Long, offsets: LongArray): Long {
        var address = getModuleBase(moduleName) + moduleOffset
        if (offsets.isEmpty()) return address
        for (i in offsets.indices) {
            if (i < offsets.lastIndex) {
                address = readPointer(address + offsets[i])
                if (address == 0L) throw IllegalStateException("null pointer @ index $i")
            } else {
                address += offsets[i]
            }
        }
        return address
    }

    fun readPointer(address: Long): Long {
        val buf = readBytes(address, pointerSize)
        val bb = ByteBuffer.wrap(buf).order(ByteOrder.LITTLE_ENDIAN)
        return if (pointerSize == 8) bb.long else (bb.int.toLong() and 0xffffffffL)
    }

    fun readTyped(address: Long, type: String): Any {
        return when (normalizeType(type)) {
            "int32" -> ByteBuffer.wrap(readBytes(address, 4)).order(ByteOrder.LITTLE_ENDIAN).int
            "uint32" -> ByteBuffer.wrap(readBytes(address, 4)).order(ByteOrder.LITTLE_ENDIAN).int.toLong() and 0xffffffffL
            "int64" -> ByteBuffer.wrap(readBytes(address, 8)).order(ByteOrder.LITTLE_ENDIAN).long
            "uint64" -> ByteBuffer.wrap(readBytes(address, 8)).order(ByteOrder.LITTLE_ENDIAN).long
            "float" -> ByteBuffer.wrap(readBytes(address, 4)).order(ByteOrder.LITTLE_ENDIAN).float
            "double" -> ByteBuffer.wrap(readBytes(address, 8)).order(ByteOrder.LITTLE_ENDIAN).double
            else -> ByteBuffer.wrap(readBytes(address, 4)).order(ByteOrder.LITTLE_ENDIAN).int
        }
    }

    fun readChain(moduleName: String, moduleOffset: Long, offsets: LongArray, type: String): Any {
        val addr = resolveChain(moduleName, moduleOffset, offsets)
        return readTyped(addr, type)
    }

    fun encodeValue(value: Double, type: String): ByteArray {
        val t = normalizeType(type)
        val bb = ByteBuffer.allocate(valueSize(t)).order(ByteOrder.LITTLE_ENDIAN)
        when (t) {
            "int32" -> bb.putInt(value.toInt())
            "uint32" -> bb.putInt(value.toLong().toInt())
            "int64", "uint64" -> bb.putLong(value.toLong())
            "float" -> bb.putFloat(value.toFloat())
            "double" -> bb.putDouble(value)
            else -> bb.putInt(value.toInt())
        }
        return bb.array()
    }

    fun valueSize(type: String): Int =
        when (normalizeType(type)) {
            "int64", "uint64", "double" -> 8
            else -> 4
        }

    fun normalizeType(type: String): String {
        val t = type.trim().lowercase()
        return when (t) {
            "d", "dword", "int", "i32" -> "int32"
            "q", "qword", "i64", "long" -> "int64"
            "f", "float32" -> "float"
            "u32" -> "uint32"
            "u64" -> "uint64"
            else -> t.ifBlank { "int32" }
        }
    }

    /**
     * 按精确值搜索可写匿名/堆区域，结果写入会话候选（不立即锁定）。
     * @return 候选数量
     */
    fun searchValue(key: String, value: Double, type: String = "int32"): Int {
        val k = key.trim()
        if (k.isEmpty()) throw IllegalArgumentException("key empty")
        val typ = normalizeType(type)
        val pattern = encodeValue(value, typ)
        val step = valueSize(typ)
        val hits = mutableListOf<Long>()
        val regions = listSearchRegions()
        val mem = File("/proc/$targetPid/mem")
        if (!mem.canRead()) throw IllegalStateException("cannot read /proc/$targetPid/mem (need root?)")

        RandomAccessFile(mem, "r").use { raf ->
            val chunk = ByteArray(1024 * 1024)
            for (region in regions) {
                if (hits.size >= maxCandidates) break
                val size = region.end - region.start
                if (size <= 0 || size > maxRegionBytes) continue
                var addr = region.start
                while (addr + step <= region.end && hits.size < maxCandidates) {
                    val toRead = minOf(chunk.size.toLong(), region.end - addr).toInt()
                    if (toRead < step) break
                    try {
                        raf.seek(addr)
                        val n = raf.read(chunk, 0, toRead)
                        if (n < step) break
                        var i = 0
                        while (i + step <= n && hits.size < maxCandidates) {
                            if (matchesAt(chunk, i, pattern)) {
                                hits.add(addr + i)
                            }
                            i += step
                        }
                        // 前进一整块，后退 step-1 避免跨块边界漏检
                        val advance = (n - step + 1).coerceAtLeast(step)
                        addr += advance.toLong()
                    } catch (_: Exception) {
                        break
                    }
                }
            }
        }

        sessions[k] = SessionSlot(key = k, type = typ, candidates = hits, locked = null)
        return hits.size
    }

    /**
     * 在已有候选上过滤为 newValue；若剩 1 个则自动锁定；若多个则保留候选并锁定第一个（可再 refine）。
     * @return Pair(剩余候选数, 是否已锁定)
     */
    fun refineValue(key: String, newValue: Double): Pair<Int, Boolean> {
        val k = key.trim()
        val slot = sessions[k] ?: throw IllegalStateException("no search session for: $k")
        val pattern = encodeValue(newValue, slot.type)
        val kept = mutableListOf<Long>()
        for (addr in slot.candidates) {
            try {
                val buf = readBytes(addr, pattern.size)
                if (buf.contentEquals(pattern)) kept.add(addr)
            } catch (_: Exception) {
                // skip unreadable
            }
        }
        slot.candidates = kept
        when {
            kept.isEmpty() -> {
                slot.locked = null
                return 0 to false
            }
            kept.size == 1 -> {
                slot.locked = kept[0]
                return 1 to true
            }
            else -> {
                // 多候选：暂锁第一个，脚本可继续 refine
                slot.locked = kept[0]
                return kept.size to true
            }
        }
    }

    fun lockAddress(key: String, address: Long, type: String = "int32") {
        val k = key.trim()
        sessions[k] = SessionSlot(
            key = k,
            type = normalizeType(type),
            candidates = mutableListOf(address),
            locked = address,
        )
    }

    fun readCached(key: String, type: String? = null): Any {
        val slot = sessions[key.trim()] ?: throw IllegalStateException("no cached address for: $key")
        val addr = slot.locked ?: throw IllegalStateException("address not locked for: $key")
        return readTyped(addr, type ?: slot.type)
    }

    private fun matchesAt(buf: ByteArray, offset: Int, pattern: ByteArray): Boolean {
        if (offset + pattern.size > buf.size) return false
        for (i in pattern.indices) {
            if (buf[offset + i] != pattern[i]) return false
        }
        return true
    }

    private fun matchesMasked(buf: ByteArray, offset: Int, pattern: ByteArray, mask: ByteArray): Boolean {
        if (offset + pattern.size > buf.size) return false
        for (i in pattern.indices) {
            if (mask[i] != 0.toByte() && buf[offset + i] != pattern[i]) return false
        }
        return true
    }

    /** 解析 `48 8B ?? 00` 为 pattern + mask（mask 0=通配）。 */
    fun parseAob(patternText: String): Pair<ByteArray, ByteArray> {
        val tokens = patternText.replace(",", " ").trim().split(Regex("\\s+")).filter { it.isNotEmpty() }
        if (tokens.isEmpty()) throw IllegalArgumentException("aob pattern empty")
        val values = ByteArray(tokens.size)
        val mask = ByteArray(tokens.size)
        tokens.forEachIndexed { i, tok ->
            when (tok) {
                "?", "??" -> {
                    values[i] = 0
                    mask[i] = 0
                }
                else -> {
                    values[i] = tok.toInt(16).toByte()
                    mask[i] = 0xFF.toByte()
                }
            }
        }
        if (mask.all { it == 0.toByte() }) throw IllegalArgumentException("aob has no fixed bytes")
        return values to mask
    }

    /**
     * AOB 特征码扫描。
     * @param moduleHint 非空时优先扫路径/名包含该串的映射（如 libil2cpp.so）
     * @return 命中地址列表（特征码起点）
     */
    fun aobScan(
        patternText: String,
        moduleHint: String? = null,
        maxHits: Int = 16,
    ): List<Long> {
        val (pattern, mask) = parseAob(patternText)
        val plen = pattern.size
        val regions = listAobRegions(moduleHint)
        val hits = mutableListOf<Long>()
        val mem = File("/proc/$targetPid/mem")
        if (!mem.canRead()) throw IllegalStateException("cannot read /proc/$targetPid/mem (need root?)")

        RandomAccessFile(mem, "r").use { raf ->
            val chunk = ByteArray(1024 * 1024)
            for (region in regions) {
                if (hits.size >= maxHits) break
                val size = region.end - region.start
                if (size <= 0 || size > maxRegionBytes) continue
                var addr = region.start
                while (addr + plen <= region.end && hits.size < maxHits) {
                    val toRead = minOf(chunk.size.toLong(), region.end - addr).toInt()
                    if (toRead < plen) break
                    try {
                        raf.seek(addr)
                        val n = raf.read(chunk, 0, toRead)
                        if (n < plen) break
                        var i = 0
                        while (i + plen <= n && hits.size < maxHits) {
                            if (matchesMasked(chunk, i, pattern, mask)) {
                                hits.add(addr + i)
                            }
                            i++
                        }
                        val advance = (n - plen + 1).coerceAtLeast(1)
                        addr += advance.toLong()
                    } catch (_: Exception) {
                        break
                    }
                }
            }
        }
        return hits
    }

    /** AOB 扫描区域：有模块提示时扫匹配映射；否则扫可读映射（含 .so）。 */
    fun listAobRegions(moduleHint: String? = null): List<Region> {
        val maps = File("/proc/$targetPid/maps")
        if (!maps.canRead()) return emptyList()
        val needle = moduleHint?.trim()?.lowercase().orEmpty()
        val out = mutableListOf<Region>()
        maps.forEachLine { line ->
            val parts = line.trim().split(Regex("\\s+"), limit = 6)
            if (parts.size < 5) return@forEachLine
            val perms = parts[1]
            if (!perms.contains('r')) return@forEachLine
            val range = parts[0].split("-")
            if (range.size != 2) return@forEachLine
            val start = range[0].toLongOrNull(16) ?: return@forEachLine
            val end = range[1].toLongOrNull(16) ?: return@forEachLine
            val path = parts.getOrElse(5) { "" }
            if (needle.isNotEmpty()) {
                val name = path.substringAfterLast('/')
                if (!path.lowercase().contains(needle) && !name.lowercase().contains(needle)) {
                    return@forEachLine
                }
            } else {
                // 无提示：优先文件映射与堆，跳过超大纯匿名可另限
                if (path.isBlank() && end - start > maxRegionBytes) return@forEachLine
            }
            out.add(Region(start, end, path))
        }
        return out
    }

    fun listSearchRegions(): List<Region> {
        val maps = File("/proc/$targetPid/maps")
        if (!maps.canRead()) return emptyList()
        val out = mutableListOf<Region>()
        maps.forEachLine { line ->
            val parts = line.trim().split(Regex("\\s+"), limit = 6)
            if (parts.size < 5) return@forEachLine
            val perms = parts[1]
            if (!perms.startsWith("rw")) return@forEachLine
            val range = parts[0].split("-")
            if (range.size != 2) return@forEachLine
            val start = range[0].toLongOrNull(16) ?: return@forEachLine
            val end = range[1].toLongOrNull(16) ?: return@forEachLine
            val path = parts.getOrElse(5) { "" }
            if (!isSearchablePath(path)) return@forEachLine
            out.add(Region(start, end, path))
        }
        return out
    }

    private fun isSearchablePath(path: String): Boolean {
        if (path.isBlank()) return true
        if (path.startsWith("[anon") || path == "[heap]" || path == "[stack]") return true
        if (path.contains("dalvik") || path.contains("ashmem")) return true
        // 跳过 so/apk/字体等文件映射
        if (path.startsWith("/")) {
            if (path.endsWith(".so") || path.endsWith(".apk") || path.endsWith(".jar") ||
                path.endsWith(".odex") || path.endsWith(".vdex") || path.endsWith(".art")
            ) {
                return false
            }
            // 其它文件映射一般不是游戏数值堆
            return false
        }
        return true
    }
}
