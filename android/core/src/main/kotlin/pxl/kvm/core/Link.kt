package pxl.kvm.core

import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.BufferedOutputStream
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.IOException
import java.net.InetSocketAddress
import java.net.Socket
import java.util.Base64
import kotlin.concurrent.thread

/**
 * One sealed connection to a paired computer (kvm/link.py). Every frame is a 4-byte big-endian
 * length and then the bytes: plain JSON for the hello, then sealed frames whose plaintext starts
 * with a type byte. A phone only sends JSON (0x10) and BLOB (0x11): u32 header length, JSON
 * header, raw bytes.
 */
class Link(
    private val socket: Socket,
    sendKey: ByteArray,
    recvKey: ByteArray,
    val peerId: String,
    val purpose: String,
) {
    private val sealer = Crypto.Sealer(sendKey)
    private val opener = Crypto.Opener(recvKey)
    private val out = DataOutputStream(BufferedOutputStream(socket.getOutputStream(), 64 * 1024))
    private val inp = DataInputStream(BufferedInputStream(socket.getInputStream(), 64 * 1024))
    private val lock = Any()
    @Volatile var closed = false
        private set
    @Volatile var lastHeard = System.currentTimeMillis()
        private set

    /** A message, with the raw bytes of a BLOB frame (null for JSON). */
    fun interface Handler { fun onMessage(link: Link, msg: JSONObject, data: ByteArray?) }

    fun start(handler: Handler, onClose: (Link) -> Unit) {
        thread(name = "kvm-link-$purpose", isDaemon = true) {
            try {
                while (!closed) {
                    val plain = opener.open(readFrame(inp))
                    lastHeard = System.currentTimeMillis()
                    if (plain.isEmpty()) continue
                    when (plain[0].toInt()) {
                        T_JSON -> handler.onMessage(this, JSONObject(String(plain, 1, plain.size - 1, Charsets.UTF_8)), null)
                        T_BLOB -> {
                            val n = u32(plain, 1)
                            val hdr = JSONObject(String(plain, 5, n, Charsets.UTF_8))
                            handler.onMessage(this, hdr, plain.copyOfRange(5 + n, plain.size))
                        }
                        else -> {} // pointer and keys: a phone doesn't take those
                    }
                }
            } catch (_: Exception) {
            }
            close()
            onClose(this)
        }
    }

    fun msg(obj: JSONObject): Boolean = send(byteArrayOf(T_JSON.toByte()) + obj.toString().toByteArray(Charsets.UTF_8))

    fun blob(header: JSONObject, data: ByteArray, off: Int = 0, len: Int = data.size): Boolean {
        val h = header.toString().toByteArray(Charsets.UTF_8)
        val b = ByteArray(5 + h.size + len)
        b[0] = T_BLOB.toByte()
        putU32(b, 1, h.size)
        h.copyInto(b, 5)
        System.arraycopy(data, off, b, 5 + h.size, len)
        return send(b)
    }

    private fun send(plain: ByteArray): Boolean {
        if (closed) return false
        return try {
            synchronized(lock) {
                writeFrame(out, sealer.seal(plain))
                out.flush()
            }
            true
        } catch (e: IOException) {
            close()
            false
        }
    }

    fun close() {
        if (closed) return
        closed = true
        try { socket.close() } catch (_: IOException) {}
    }

    companion object {
        const val T_JSON = 0x10
        const val T_BLOB = 0x11
        const val MAX_FRAME = 4 shl 20
        const val PORT = 47610

        fun u32(b: ByteArray, at: Int): Int =
            ((b[at].toInt() and 0xff) shl 24) or ((b[at + 1].toInt() and 0xff) shl 16) or
                ((b[at + 2].toInt() and 0xff) shl 8) or (b[at + 3].toInt() and 0xff)

        fun putU32(b: ByteArray, at: Int, v: Int) {
            b[at] = (v ushr 24).toByte(); b[at + 1] = (v ushr 16).toByte()
            b[at + 2] = (v ushr 8).toByte(); b[at + 3] = v.toByte()
        }

        fun readFrame(inp: DataInputStream): ByteArray {
            val n = inp.readInt()
            if (n < 0 || n > MAX_FRAME + 64) throw IOException("frame too large")
            return ByteArray(n).also { inp.readFully(it) }
        }

        fun writeFrame(out: DataOutputStream, data: ByteArray) {
            out.writeInt(data.size)
            out.write(data)
        }

        fun b64(b: ByteArray): String = Base64.getEncoder().encodeToString(b)
        fun unb64(s: String): ByteArray = Base64.getDecoder().decode(s)

        private fun connect(host: String, port: Int, timeoutMs: Int): Socket {
            val s = Socket()
            s.tcpNoDelay = true
            s.keepAlive = true
            s.connect(InetSocketAddress(host, port), timeoutMs)
            s.soTimeout = 10_000
            return s
        }

        private fun hello(me: Me, purpose: String) = JSONObject()
            .put("t", "hello").put("v", 1).put("purpose", purpose).put("id", me.id).put("name", me.name)
            .put("platform", "android").put("version", me.version)

        private fun writeJson(s: Socket, o: JSONObject) {
            val out = DataOutputStream(s.getOutputStream())
            writeFrame(out, o.toString().toByteArray(Charsets.UTF_8))
            out.flush()
        }

        private fun readJson(s: Socket): JSONObject =
            JSONObject(String(readFrame(DataInputStream(s.getInputStream())), Charsets.UTF_8))

        /** Opens a link to a paired computer. Throws Unpaired if it no longer knows this phone. */
        fun dial(me: Me, desk: Desk, host: String, purpose: String, timeoutMs: Int = 4000): Link {
            val s = connect(host, desk.port, timeoutMs)
            try {
                val nonce = Crypto.randomBytes(16)
                writeJson(s, hello(me, purpose).put("nonce", b64(nonce)))
                val m = readJson(s)
                if (m.optString("t") == "err" && m.optString("why") == "unpaired") throw Unpaired()
                if (m.optString("t") != "hello" || m.optString("id") != desk.id) throw IOException("not ${desk.name}")
                val (d2l, l2d) = Crypto.sessionKeys(desk.key, nonce, unb64(m.getString("nonce")))
                s.soTimeout = 0
                return Link(s, d2l, l2d, desk.id, purpose)
            } catch (e: Exception) {
                try { s.close() } catch (_: IOException) {}
                throw e
            }
        }

        /** Pairs with the computer whose QR code was scanned. Tries each of its addresses. */
        fun pair(me: Me, offer: QrOffer): Desk {
            var last: Exception = IOException("No address in the code")
            for (host in offer.hosts) {
                val s = try { connect(host, offer.port, 5000) } catch (e: Exception) { last = e; continue }
                try {
                    writeJson(s, hello(me, "pair_qr").put("proof", b64(Crypto.qrProof(offer.secret, "phone", me.id))))
                    val m = readJson(s)
                    if (m.optString("t") != "paired") throw PairRefused()
                    val id = m.getString("id")
                    if (id != offer.id || !Crypto.qrProof(offer.secret, "desktop", id).contentEquals(unb64(m.getString("proof"))))
                        throw IOException("That computer didn't prove it showed the code")
                    return Desk(id, m.optString("name", offer.name), m.optString("platform", ""),
                        listOf(host) + offer.hosts.filter { it != host }, m.optInt("port", offer.port), Crypto.qrPairKey(offer.secret))
                } catch (e: PairRefused) {
                    throw e
                } catch (e: Exception) {
                    last = e
                } finally {
                    try { s.close() } catch (_: IOException) {}
                }
            }
            throw last
        }
    }
}

class Unpaired : IOException("This computer no longer knows the phone. Pair again.")
class PairRefused : IOException("That code ran out or was already used. Show a new one on the computer.")

/** This phone. */
data class Me(val id: String, val name: String, val version: String)

/** A paired computer, as kept on the phone. */
data class Desk(val id: String, val name: String, val platform: String, val hosts: List<String>, val port: Int, val key: ByteArray) {
    fun toJson(): JSONObject = JSONObject().put("id", id).put("name", name).put("platform", platform)
        .put("hosts", org.json.JSONArray(hosts)).put("port", port).put("key", key.hex())

    companion object {
        fun fromJson(o: JSONObject): Desk {
            val hs = o.optJSONArray("hosts")
            return Desk(o.getString("id"), o.optString("name", "Computer"), o.optString("platform", ""),
                (0 until (hs?.length() ?: 0)).map { hs!!.getString(it) }, o.optInt("port", Link.PORT), o.getString("key").unhex())
        }
    }
}

/** What the computer's QR code holds: kvm://pair?v=1&id=&n=&h=a,b&p=&s=<base64url secret> */
data class QrOffer(val id: String, val name: String, val hosts: List<String>, val port: Int, val secret: ByteArray) {
    companion object {
        fun parse(uri: String): QrOffer? {
            if (!uri.startsWith("kvm://pair?")) return null
            val q = uri.substringAfter('?').split('&').mapNotNull {
                val i = it.indexOf('=')
                if (i < 0) null else decode(it.substring(0, i)) to decode(it.substring(i + 1))
            }.toMap()
            val id = q["id"] ?: return null
            val secret = try { Base64.getUrlDecoder().decode(q["s"] ?: return null) } catch (e: Exception) { return null }
            if (secret.size != 32) return null
            val hosts = (q["h"] ?: "").split(',').map { it.trim() }.filter { it.isNotEmpty() }
            return QrOffer(id, q["n"] ?: "Computer", hosts, q["p"]?.toIntOrNull() ?: Link.PORT, secret)
        }

        private fun decode(s: String) = java.net.URLDecoder.decode(s, "UTF-8")
    }
}
