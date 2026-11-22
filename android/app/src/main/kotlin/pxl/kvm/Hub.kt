package pxl.kvm

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.net.Uri
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.BatteryManager
import android.os.Handler
import android.os.Looper
import android.provider.OpenableColumns
import android.widget.Toast
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import org.json.JSONObject
import pxl.kvm.core.Crypto
import pxl.kvm.core.Desk
import pxl.kvm.core.Files
import pxl.kvm.core.Link
import pxl.kvm.core.Unpaired
import pxl.kvm.core.hex
import java.util.concurrent.ConcurrentHashMap
import kotlin.concurrent.thread

/** One computer as the screen shows it. */
data class DeskState(val id: String, val name: String, val platform: String, val connected: Boolean, val host: String?)

/** A transfer as the screen shows it. */
data class Transfer(val id: String, val desk: String, val label: String, val outgoing: Boolean, val total: Long,
                    val done: Long, val phase: String, val error: String? = null,
                    val started: Long = System.currentTimeMillis())

data class UiState(val desks: List<DeskState> = emptyList(), val transfers: List<Transfer> = emptyList())

/**
 * Keeps a link to every paired computer while the service runs, and is what the screen, the
 * notification listener and the share sheet talk to.
 */
object Hub {
    private lateinit var ctx: Context
    private val main = Handler(Looper.getMainLooper())
    private val conns = ConcurrentHashMap<String, Conn>()
    private val found = ConcurrentHashMap<String, Pair<String, Int>>()     // desk id -> address seen on the network
    private val transfers = ConcurrentHashMap<String, Transfer>()
    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state
    @Volatile private var running = false
    private var nsd: NsdManager.DiscoveryListener? = null
    private var mcast: WifiManager.MulticastLock? = null

    fun init(c: Context) { ctx = c.applicationContext }

    fun start() {
        if (running) return
        running = true
        for (d in Store.desks()) conns.getOrPut(d.id) { Conn(d.id).also { it.start() } }
        discover()
        publish()
    }

    fun stop() {
        running = false
        conns.values.forEach { it.stop() }
        conns.clear()
        nsd?.let { runCatching { ctx.getSystemService(NsdManager::class.java).stopServiceDiscovery(it) } }
        nsd = null
        runCatching { mcast?.release() }
        publish()
    }

    fun added(d: Desk) {
        Store.put(d)
        conns.remove(d.id)?.stop()
        if (running) conns[d.id] = Conn(d.id).also { it.start() }
        publish()
    }

    fun forget(id: String) {
        conns.remove(id)?.let { c ->
            c.main?.msg(JSONObject().put("t", "unpair"))
            c.stop()
        }
        Store.remove(id)
        publish()
    }

    fun reconnectNow() { conns.values.forEach { it.wake() } }

    // ---- to the computers ---------------------------------------------------------------
    private fun everyone(m: JSONObject) { conns.values.forEach { it.main?.msg(m) } }

    fun notif(key: String, app: String, title: String, text: String, ts: Long, alert: Boolean) {
        if (!Store.mirrorNotifs) return
        everyone(JSONObject().put("t", "notif").put("key", key).put("app", app).put("title", title).put("text", text)
            .put("ts", ts / 1000.0).put("alert", alert))
    }

    fun notifGone(key: String) = everyone(JSONObject().put("t", "notif_gone").put("key", key))

    fun sendClip(text: String): Boolean {
        val live = conns.values.filter { it.main != null }
        live.forEach { it.main?.msg(JSONObject().put("t", "clip").put("kind", "text").put("data", text)) }
        return live.isNotEmpty()
    }

    fun ring(id: String) = conns[id]?.main?.msg(JSONObject().put("t", "action").put("a", "ring")) ?: false

    fun battery() {
        val b = ctx.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED)) ?: return
        val level = b.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) * 100 / b.getIntExtra(BatteryManager.EXTRA_SCALE, 100).coerceAtLeast(1)
        val st = b.getIntExtra(BatteryManager.EXTRA_STATUS, -1)
        val charging = st == BatteryManager.BATTERY_STATUS_CHARGING || st == BatteryManager.BATTERY_STATUS_FULL
        everyone(JSONObject().put("t", "phone").put("battery", level).put("charging", charging).put("model", android.os.Build.MODEL))
    }

    fun connectedIds(): List<String> = conns.values.filter { it.main != null }.map { it.id }

    /** Sends photos or files (content:// uris) to a computer, on a thread of its own. */
    fun sendUris(id: String, uris: List<Uri>) {
        val c = conns[id]
        val link = c?.bulk ?: c?.main
        if (link == null) {
            toast("That computer isn't connected.")
            return
        }
        val items = uris.map { uri ->
            var name = uri.lastPathSegment ?: "file"
            var size = 0L
            ctx.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { cur ->
                if (cur.moveToFirst()) {
                    cur.getString(0)?.let { name = it }
                    if (!cur.isNull(1)) size = cur.getLong(1)
                }
            }
            Files.Item(Files.Incoming.safeRel(name), size) { ctx.contentResolver.openInputStream(uri)!! }
        }
        if (items.isEmpty()) return
        val tid = Crypto.randomBytes(6).hex()
        val label = if (items.size == 1) items[0].rel else "${items.size} items"
        transfers[tid] = Transfer(tid, c.name(), label, true, items.sumOf { it.size }, 0, "sending")
        publish()
        thread(name = "kvm-send", isDaemon = true) {
            val ok = try {
                Files.send(link, tid, Store.me.name, items, { done ->
                    transfers[tid]?.let { transfers[tid] = it.copy(done = done) }
                    publishSoon()
                }, { transfers[tid]?.phase == "cancelled" })
            } catch (e: Exception) {
                transfers[tid]?.let { transfers[tid] = it.copy(phase = "failed", error = e.message) }
                false
            }
            transfers[tid]?.let { t ->
                if (t.phase == "sending") transfers[tid] = t.copy(phase = if (ok) "sent" else "failed",
                    error = if (ok) null else (t.error ?: "The connection dropped."))
            }
            publish()
        }
    }

    fun cancel(tid: String) {
        transfers[tid]?.let { if (it.phase == "sending") transfers[tid] = it.copy(phase = "cancelled") }
        publish()
    }

    fun clearTransfers() {
        transfers.values.filter { it.phase != "sending" && it.phase != "receiving" }.forEach { transfers.remove(it.id) }
        publish()
    }

    // ---- from the computers -------------------------------------------------------------
    private fun onMessage(c: Conn, link: Link, m: JSONObject, data: ByteArray?) {
        when (m.optString("t")) {
            "clip" -> if (m.optString("kind") == "text") {
                val text = m.optString("data")
                main.post {
                    ctx.getSystemService(ClipboardManager::class.java)
                        .setPrimaryClip(ClipData.newPlainText("From ${c.name()}", text))
                }
            }
            "action" -> if (m.optString("a") == "ring") Ringer.ring(ctx, c.name())
            "notif_dismiss" -> NotifListener.dismiss(m.optString("key"))
            "unpair" -> {
                toast("${c.name()} unpaired from this phone.")
                conns.remove(c.id)?.stop()
                Store.remove(c.id)
                publish()
            }
            "files" -> {
                val inc = Files.Incoming.from(m, Saver(ctx, c.name()))
                c.incoming[inc.tid] = inc
                transfers[inc.tid] = Transfer(inc.tid, c.name(), inc.label, false, inc.total, 0, "receiving")
                publish()
            }
            "piece" -> c.incoming[m.optString("tid")]?.let { inc ->
                if (data != null) try { inc.piece(m.optInt("i"), data) } catch (e: Exception) {
                    inc.fail("Couldn't save: ${e.message}")
                    link.msg(JSONObject().put("t", "files_cancel").put("tid", inc.tid))
                }
                transfers[inc.tid]?.let { transfers[inc.tid] = it.copy(done = inc.done) }
                publishSoon()
            }
            "file_done" -> c.incoming[m.optString("tid")]?.fileDone(m.optInt("i"), m.optString("sha"))
            "files_done" -> c.incoming.remove(m.optString("tid"))?.let { inc ->
                inc.allDone()
                val failed = inc.failed
                transfers[inc.tid]?.let { transfers[inc.tid] = it.copy(done = inc.total, phase = if (failed == null) "received" else "failed", error = failed) }
                if (failed == null) Saver.notifyReceived(ctx, c.name(), inc.label, inc.count)
                publish()
            }
            "files_cancel" -> {
                val tid = m.optString("tid")
                c.incoming.remove(tid)?.fail("Cancelled on the computer.")
                transfers[tid]?.let { transfers[tid] = it.copy(phase = "cancelled", error = if (it.outgoing) null else "Cancelled on the computer.") }
                publish()
            }
            "files_refused" -> {
                val tid = m.optString("tid")
                transfers[tid]?.let { transfers[tid] = it.copy(phase = "failed", error = "${c.name()} isn't accepting files.") }
                publish()
            }
        }
    }

    // ---- one computer ---------------------------------------------------------------------
    private class Conn(val id: String) {
        @Volatile var main: Link? = null
        @Volatile var bulk: Link? = null
        @Volatile var host: String? = null
        @Volatile private var alive = true
        private val lock = Object()
        val incoming = ConcurrentHashMap<String, Files.Incoming>()

        fun name() = Store.desks().firstOrNull { it.id == id }?.name ?: "Computer"

        fun start() { thread(name = "kvm-conn", isDaemon = true) { loop() } }

        fun stop() {
            alive = false
            main?.close(); bulk?.close()
            wake()
        }

        fun wake() = synchronized(lock) { lock.notifyAll() }

        private fun nap(ms: Long) = synchronized(lock) { if (alive) lock.wait(ms) }

        private fun loop() {
            var backoff = 2_000L
            var lastPing = 0L
            while (alive && running) {
                val m = main
                if (m != null && !m.closed) {
                    val now = System.currentTimeMillis()
                    if (now - lastPing > 15_000) {
                        m.msg(JSONObject().put("t", "ping"))
                        lastPing = now
                    }
                    if (now - m.lastHeard > 45_000) m.close()
                    nap(5_000)
                    continue
                }
                val desk = Store.desks().firstOrNull { it.id == id } ?: return
                if (connect(desk)) {
                    backoff = 2_000L
                    lastPing = System.currentTimeMillis()
                } else {
                    nap(backoff)
                    backoff = (backoff * 2).coerceAtMost(30_000L)
                }
            }
        }

        private fun connect(desk: Desk): Boolean {
            val hosts = LinkedHashSet<String>()
            found[desk.id]?.let { hosts += it.first }
            hosts += desk.hosts
            for (h in hosts) {
                try {
                    val d = found[desk.id]?.takeIf { it.first == h }?.let { desk.copy(port = it.second) } ?: desk
                    val link = Link.dial(Store.me, d, h, "main")
                    main = link
                    host = h
                    link.start({ l, msg, data -> onMessage(this, l, msg, data) }) { closed(it) }
                    link.msg(JSONObject().put("t", "ready").put("version", BuildConfig.VERSION_NAME))
                    if (desk.hosts.firstOrNull() != h || d.port != desk.port)
                        Store.put(desk.copy(hosts = listOf(h) + desk.hosts.filter { it != h }.take(4), port = d.port))
                    battery()
                    NotifListener.resend()
                    try {
                        bulk = Link.dial(Store.me, d, h, "bulk").also { b ->
                            b.start({ l, msg, data -> onMessage(this, l, msg, data) }) { closed(it) }
                        }
                    } catch (_: Exception) {
                    }
                    publish()
                    return true
                } catch (e: Unpaired) {
                    toast("${desk.name} no longer knows this phone. Pair again.")
                    Store.remove(desk.id)
                    conns.remove(desk.id)
                    alive = false
                    publish()
                    return false
                } catch (_: Exception) {
                }
            }
            return false
        }

        private fun closed(l: Link) {
            if (l === main) {
                main = null
                bulk?.close()
                incoming.values.forEach { inc ->
                    inc.fail("The connection dropped.")
                    transfers[inc.tid]?.let { transfers[inc.tid] = it.copy(phase = "failed", error = "The connection dropped.") }
                }
                incoming.clear()
                wake()
            } else if (l === bulk) {
                bulk = null
            }
            publish()
        }
    }

    // ---- finding computers that moved to another address -----------------------------
    private fun discover() {
        val nm = ctx.getSystemService(NsdManager::class.java) ?: return
        runCatching {
            mcast = ctx.getSystemService(WifiManager::class.java).createMulticastLock("kvm").apply { setReferenceCounted(false); acquire() }
        }
        val l = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(serviceType: String) {}
            override fun onDiscoveryStopped(serviceType: String) {}
            override fun onStartDiscoveryFailed(serviceType: String, errorCode: Int) {}
            override fun onStopDiscoveryFailed(serviceType: String, errorCode: Int) {}
            override fun onServiceLost(info: NsdServiceInfo) {}
            override fun onServiceFound(info: NsdServiceInfo) {
                @Suppress("DEPRECATION")
                runCatching {
                    nm.resolveService(info, object : NsdManager.ResolveListener {
                        override fun onResolveFailed(i: NsdServiceInfo, errorCode: Int) {}
                        override fun onServiceResolved(i: NsdServiceInfo) {
                            val did = i.attributes["id"]?.toString(Charsets.UTF_8) ?: return
                            val host = i.host?.hostAddress ?: return
                            if (host.contains(':')) return
                            val was = found.put(did, host to i.port)
                            if (was?.first != host) conns[did]?.takeIf { it.main == null }?.wake()
                        }
                    })
                }
            }
        }
        runCatching { nm.discoverServices("_pxlkvm._tcp", NsdManager.PROTOCOL_DNS_SD, l) }.onSuccess { nsd = l }
    }

    // ---- the screen ---------------------------------------------------------------------
    @Volatile private var pending = false

    private fun publishSoon() {
        if (pending) return
        pending = true
        main.postDelayed({ pending = false; publish() }, 250)
    }

    fun publish() {
        val desks = Store.desks().map { d ->
            val c = conns[d.id]
            DeskState(d.id, d.name, d.platform, c?.main != null, c?.host)
        }
        _state.value = UiState(desks, transfers.values.sortedByDescending { it.started }.toList())
        KvmService.refresh(ctx, desks.count { it.connected }, desks.size)
    }

    fun toast(text: String) = main.post { Toast.makeText(ctx, text, Toast.LENGTH_LONG).show() }
}
