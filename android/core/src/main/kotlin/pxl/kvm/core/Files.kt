package pxl.kvm.core

import org.json.JSONArray
import org.json.JSONObject
import java.io.InputStream
import java.io.OutputStream
import java.security.MessageDigest

/**
 * Files between the phone and a computer, the same messages the computers use:
 *   files {tid, from, label, items:[{i, rel, size}]}, piece (blob) {tid, i}, file_done {tid, i, sha},
 *   files_done {tid}, files_cancel {tid}, files_refused {tid}
 */
object Files {
    const val PIECE = 512 * 1024

    class Item(val rel: String, val size: Long, val open: () -> InputStream)

    /** Sends on this thread. Returns false if the link dropped or it was cancelled. */
    fun send(link: Link, tid: String, from: String, items: List<Item>, progress: (Long) -> Unit = {},
             cancelled: () -> Boolean = { false }): Boolean {
        val label = items.map { it.rel.substringBefore('/') }.distinct().let { if (it.size == 1) it[0] else "${it.size} items" }
        val list = JSONArray()
        items.forEachIndexed { i, it -> list.put(JSONObject().put("i", i).put("rel", it.rel).put("size", it.size)) }
        if (!link.msg(JSONObject().put("t", "files").put("tid", tid).put("from", from).put("label", label).put("items", list))) return false
        var done = 0L
        val buf = ByteArray(PIECE)
        items.forEachIndexed { i, item ->
            val sha = MessageDigest.getInstance("SHA-256")
            item.open().use { inp ->
                while (true) {
                    if (cancelled()) {
                        link.msg(JSONObject().put("t", "files_cancel").put("tid", tid))
                        return false
                    }
                    val n = readUpTo(inp, buf)
                    if (n <= 0) break
                    sha.update(buf, 0, n)
                    if (!link.blob(JSONObject().put("t", "piece").put("tid", tid).put("i", i), buf, 0, n)) return false
                    done += n
                    progress(done)
                }
            }
            link.msg(JSONObject().put("t", "file_done").put("tid", tid).put("i", i).put("sha", sha.digest().hex()))
        }
        return link.msg(JSONObject().put("t", "files_done").put("tid", tid))
    }

    private fun readUpTo(inp: InputStream, buf: ByteArray): Int {
        var n = 0
        while (n < buf.size) {
            val k = inp.read(buf, n, buf.size - n)
            if (k < 0) break
            n += k
        }
        return n
    }

    /** Where received files go: the app saves them to Downloads/Kvm. */
    interface Sink {
        fun open(rel: String, size: Long): OutputStream
        /** ok=false: delete what was written. */
        fun finish(rel: String, ok: Boolean)
    }

    /** One transfer coming in. Feed it every files-related message from the link. */
    class Incoming(val tid: String, val from: String, val label: String, val total: Long,
                   private val rels: Map<Int, String>, private val sizes: Map<Int, Long>, private val sink: Sink) {
        var done = 0L
            private set
        var failed: String? = null
            private set
        var finished = false
            private set
        val count get() = rels.size
        private var cur = -1
        private var out: OutputStream? = null
        private var sha = MessageDigest.getInstance("SHA-256")
        val saved = mutableListOf<String>()

        fun piece(i: Int, data: ByteArray) {
            if (failed != null) return
            if (i != cur) {
                closeCurrent(false)
                cur = i
                sha = MessageDigest.getInstance("SHA-256")
                out = sink.open(rels[i] ?: "file", sizes[i] ?: 0)
            }
            out!!.write(data)
            sha.update(data)
            done += data.size
        }

        fun fileDone(i: Int, hex: String) {
            if (failed != null) return
            if (i != cur) { // an empty file
                closeCurrent(false)
                cur = i
                sha = MessageDigest.getInstance("SHA-256")
                out = sink.open(rels[i] ?: "file", 0)
            }
            val ok = sha.digest().hex() == hex
            out?.close()
            out = null
            sink.finish(rels[i] ?: "file", ok)
            if (ok) saved += rels[i] ?: "file" else failed = "A file arrived damaged. Send it again."
            cur = -1
        }

        fun allDone() { finished = true }

        fun fail(why: String) {
            if (failed == null) failed = why
            closeCurrent(false)
        }

        private fun closeCurrent(ok: Boolean) {
            val o = out ?: return
            try { o.close() } catch (_: Exception) {}
            out = null
            if (cur >= 0) sink.finish(rels[cur] ?: "file", ok)
        }

        companion object {
            fun from(m: JSONObject, sink: Sink): Incoming {
                val items = m.optJSONArray("items") ?: JSONArray()
                val rels = HashMap<Int, String>()
                val sizes = HashMap<Int, Long>()
                for (k in 0 until items.length()) {
                    val it = items.getJSONObject(k)
                    rels[it.getInt("i")] = safeRel(it.optString("rel", "file"))
                    sizes[it.getInt("i")] = it.optLong("size", 0)
                }
                return Incoming(m.getString("tid"), m.optString("from", "Computer"), m.optString("label", "Files"),
                    sizes.values.sum(), rels, sizes, sink)
            }

            /** No absolute paths or "..": a computer can only write inside the Kvm folder. */
            fun safeRel(rel: String): String =
                rel.replace('\\', '/').split('/').filter { it.isNotEmpty() && it != "." && it != ".." }
                    .joinToString("/").ifEmpty { "file" }
        }
    }
}
