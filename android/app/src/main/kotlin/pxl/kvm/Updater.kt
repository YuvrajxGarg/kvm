package pxl.kvm

import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import kotlinx.coroutines.flow.MutableStateFlow
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

/**
 * The same updates as the desktop apps: the latest GitHub release of YuvrajxGarg/kvm, whose
 * Kvm-Android.apk installs over this one (same signing key).
 */
object Updater {
    private const val API = "https://api.github.com/repos/YuvrajxGarg/kvm/releases/latest"
    private const val ASSET = "Kvm-Android.apk"

    /** phase: idle, checking, uptodate, available, downloading, installing, failed */
    data class State(val phase: String = "idle", val latest: String? = null, val url: String? = null,
                     val progress: Float = 0f, val error: String? = null)

    val state = MutableStateFlow(State())

    fun newer(a: String, b: String): Boolean {
        val x = a.trimStart('v').split('.').map { it.toIntOrNull() ?: 0 }
        val y = b.trimStart('v').split('.').map { it.toIntOrNull() ?: 0 }
        for (i in 0 until maxOf(x.size, y.size)) {
            val d = x.getOrElse(i) { 0 } - y.getOrElse(i) { 0 }
            if (d != 0) return d > 0
        }
        return false
    }

    fun check(auto: Boolean = false) {
        if (auto && System.currentTimeMillis() - Store.lastUpdateCheck < 6 * 3600_000L) return
        if (state.value.phase in setOf("checking", "downloading", "installing")) return
        state.value = State("checking")
        thread(isDaemon = true) {
            try {
                val c = URL(API).openConnection() as HttpURLConnection
                c.setRequestProperty("Accept", "application/vnd.github+json")
                c.setRequestProperty("User-Agent", "Kvm-Android")
                c.connectTimeout = 10_000; c.readTimeout = 15_000
                val r = JSONObject(c.inputStream.bufferedReader().readText())
                Store.lastUpdateCheck = System.currentTimeMillis()
                val tag = r.getString("tag_name")
                val assets = r.getJSONArray("assets")
                val url = (0 until assets.length()).map { assets.getJSONObject(it) }
                    .firstOrNull { it.getString("name") == ASSET }?.getString("browser_download_url")
                state.value = if (url != null && newer(tag, BuildConfig.VERSION_NAME)) State("available", tag.trimStart('v'), url)
                              else State("uptodate")
            } catch (e: Exception) {
                state.value = State("failed", error = "Couldn't check for updates (${e.message})")
            }
        }
    }

    fun install(ctx: Context) {
        val s = state.value
        val url = s.url ?: return
        state.value = s.copy(phase = "downloading", progress = 0f)
        thread(isDaemon = true) {
            try {
                val pi = ctx.packageManager.packageInstaller
                val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL)
                val id = pi.createSession(params)
                pi.openSession(id).use { session ->
                    val c = URL(url).openConnection() as HttpURLConnection
                    c.instanceFollowRedirects = true
                    c.setRequestProperty("User-Agent", "Kvm-Android")
                    val total = c.contentLengthLong.coerceAtLeast(1)
                    session.openWrite("kvm.apk", 0, c.contentLengthLong).use { out ->
                        c.inputStream.use { inp ->
                            val buf = ByteArray(256 * 1024)
                            var done = 0L
                            while (true) {
                                val n = inp.read(buf)
                                if (n < 0) break
                                out.write(buf, 0, n)
                                done += n
                                state.value = state.value.copy(progress = done.toFloat() / total)
                            }
                        }
                        session.fsync(out)
                    }
                    state.value = state.value.copy(phase = "installing")
                    val cb = PendingIntent.getBroadcast(ctx, 3, Intent(ctx, Result::class.java),
                        PendingIntent.FLAG_MUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
                    session.commit(cb.intentSender)
                }
            } catch (e: Exception) {
                state.value = State("failed", error = "Update failed: ${e.message}")
            }
        }
    }

    /** Android asks the person to confirm, then reports how it went. */
    class Result : BroadcastReceiver() {
        override fun onReceive(c: Context, i: Intent) {
            when (i.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
                PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                    @Suppress("DEPRECATION")
                    (i.getParcelableExtra<Intent>(Intent.EXTRA_INTENT))?.let {
                        c.startActivity(it.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                    }
                }
                PackageInstaller.STATUS_SUCCESS -> state.value = State("uptodate")
                else -> state.value = State("failed", error = i.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE) ?: "Update didn't install")
            }
        }
    }
}
