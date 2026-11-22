package pxl.kvm.core

import org.json.JSONObject
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.io.DataInputStream
import java.io.DataOutputStream
import java.net.ServerSocket
import java.security.MessageDigest
import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import kotlin.concurrent.thread

class CoreTest {
    private val v = JSONObject(javaClass.getResource("/vectors.json")!!.readText())

    @Test fun matchesPython() {
        val secret = v.getString("secret").unhex()
        assertEquals(v.getString("phone_proof"), Crypto.qrProof(secret, "phone", v.getString("phone_id")).hex())
        assertEquals(v.getString("desk_proof"), Crypto.qrProof(secret, "desktop", v.getString("desk_id")).hex())
        val key = Crypto.qrPairKey(secret)
        assertEquals(v.getString("pair_key"), key.hex())
        val (d2l, l2d) = Crypto.sessionKeys(key, v.getString("dialer_nonce").unhex(), v.getString("listener_nonce").unhex())
        assertEquals(v.getString("d2l"), d2l.hex())
        assertEquals(v.getString("l2d"), l2d.hex())
        val s = Crypto.Sealer(d2l)
        s.seal("first".toByteArray())
        val sealed = s.seal(v.getString("plain").unhex())
        assertEquals(v.getString("sealed_2"), sealed.hex())
        val o = Crypto.Opener(d2l)
        o.open(Crypto.Sealer(d2l).seal("first".toByteArray()))
        assertArrayEquals(v.getString("plain").unhex(), o.open(sealed))
    }

    @Test fun parsesTheQrCode() {
        val q = QrOffer.parse("kvm://pair?v=1&id=abc123&n=Yuvraj%E2%80%99s+MacBook&h=192.168.1.4%2C10.0.0.2&p=47610&s=AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8")
        assertNotNull(q)
        assertEquals("abc123", q!!.id)
        assertEquals("Yuvraj’s MacBook", q.name)
        assertEquals(listOf("192.168.1.4", "10.0.0.2"), q.hosts)
        assertArrayEquals(ByteArray(32) { it.toByte() }, q.secret)
        assertEquals(null, QrOffer.parse("https://example.com"))
    }

    /** A tiny computer: answers the QR pairing and the hello the way kvm/agent.py does. */
    @Test fun pairsDialsAndSendsFiles() {
        val secret = Crypto.randomBytes(32)
        val server = ServerSocket(0)
        val deskId = "desk0001"
        val got = LinkedBlockingQueue<Pair<JSONObject, ByteArray?>>()
        thread(isDaemon = true) {
            // 1. pairing
            server.accept().use { s ->
                val inp = DataInputStream(s.getInputStream()); val out = DataOutputStream(s.getOutputStream())
                val h = JSONObject(String(Link.readFrame(inp)))
                assertEquals("pair_qr", h.getString("purpose"))
                assertArrayEquals(Crypto.qrProof(secret, "phone", h.getString("id")), Link.unb64(h.getString("proof")))
                Link.writeFrame(out, JSONObject().put("t", "paired").put("id", deskId).put("name", "Mac")
                    .put("proof", Link.b64(Crypto.qrProof(secret, "desktop", deskId))).toString().toByteArray())
            }
            // 2. the main link
            val s = server.accept()
            val inp = DataInputStream(s.getInputStream()); val out = DataOutputStream(s.getOutputStream())
            val h = JSONObject(String(Link.readFrame(inp)))
            val nonce = Crypto.randomBytes(16)
            Link.writeFrame(out, JSONObject().put("t", "hello").put("id", deskId).put("nonce", Link.b64(nonce)).toString().toByteArray())
            val (d2l, l2d) = Crypto.sessionKeys(Crypto.qrPairKey(secret), Link.unb64(h.getString("nonce")), nonce)
            Link(s, l2d, d2l, h.getString("id"), "main").start({ _, m, d -> got.put(m to d) }, {})
        }
        val me = Me("phone001", "Pixel", "1.0.0")
        val desk = Link.pair(me, QrOffer(deskId, "Mac", listOf("127.0.0.1"), server.localPort, secret))
        assertEquals("Mac", desk.name)
        val link = Link.dial(me, desk, "127.0.0.1", "main")
        link.start({ _, _, _ -> }, {})
        assertTrue(link.msg(JSONObject().put("t", "notif").put("key", "k").put("title", "Hi")))
        assertEquals("Hi", got.poll(5, TimeUnit.SECONDS)!!.first.getString("title"))

        val data = Crypto.randomBytes(1_300_000)
        assertTrue(Files.send(link, "t1", "Pixel", listOf(Files.Item("DCIM/a.jpg", data.size.toLong()) { ByteArrayInputStream(data) })))
        val msgs = generateSequence { got.poll(5, TimeUnit.SECONDS) }.takeWhile { it.first.getString("t") != "files_done" }.toList()
        assertEquals("files", msgs[0].first.getString("t"))
        val buf = ByteArrayOutputStream()
        msgs.filter { it.first.getString("t") == "piece" }.forEach { buf.write(it.second!!) }
        assertArrayEquals(data, buf.toByteArray())
        val sha = MessageDigest.getInstance("SHA-256").digest(data).hex()
        assertEquals(sha, msgs.last().first.getString("sha"))
        link.close()
    }

    @Test fun receivesFilesSafely() {
        val written = HashMap<String, ByteArrayOutputStream>()
        val kept = mutableListOf<String>()
        val sink = object : Files.Sink {
            override fun open(rel: String, size: Long) = ByteArrayOutputStream().also { written[rel] = it }
            override fun finish(rel: String, ok: Boolean) { if (ok) kept += rel }
        }
        val m = JSONObject("""{"t":"files","tid":"x","from":"Mac","label":"a","items":[{"i":0,"rel":"../../etc/a.txt","size":3},{"i":1,"rel":"b","size":0}]}""")
        val inc = Files.Incoming.from(m, sink)
        inc.piece(0, "abc".toByteArray())
        inc.fileDone(0, MessageDigest.getInstance("SHA-256").digest("abc".toByteArray()).hex())
        inc.fileDone(1, MessageDigest.getInstance("SHA-256").digest(ByteArray(0)).hex())
        assertEquals(listOf("etc/a.txt", "b"), kept)
        assertEquals("abc", written["etc/a.txt"].toString())
    }
}
