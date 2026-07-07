package com.autoscript.script.lua

import java.io.File
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Android 进程内存读取（需 root 或读取本进程）。
 * 供 ce-base-extractor 导出的 bot.read_chain 使用。
 */
object MemoryReader {
    private var targetPid: Int = android.os.Process.myPid()
    private var pointerSize: Int = 8
    private val moduleCache = mutableMapOf<String, Long>()

    fun setTargetPid(pid: Int) {
        targetPid = pid
        moduleCache.clear()
    }

    fun setPointerSize(size: Int) {
        pointerSize = if (size == 4) 4 else 8
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
            val path = parts[5]
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
        return when (type.lowercase()) {
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
}
