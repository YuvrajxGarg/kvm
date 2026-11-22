package pxl.kvm

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import android.provider.Settings
import org.json.JSONArray
import pxl.kvm.core.Crypto
import pxl.kvm.core.Desk
import pxl.kvm.core.Me
import pxl.kvm.core.hex

class KvmApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Store.init(this)
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CH_LINK, "Connection", NotificationManager.IMPORTANCE_MIN).apply {
            description = "Shows while Kvm keeps the phone connected to your computers."
        })
        nm.createNotificationChannel(NotificationChannel(CH_FILES, "Files", NotificationManager.IMPORTANCE_DEFAULT))
        nm.createNotificationChannel(NotificationChannel(CH_RING, "Ring", NotificationManager.IMPORTANCE_HIGH).apply {
            setSound(null, null)
        })
        Hub.init(this)
        if (Store.desks().isNotEmpty()) KvmService.start(this)
    }

    companion object {
        const val CH_LINK = "link"
        const val CH_FILES = "files"
        const val CH_RING = "ring"
    }
}

/** What the phone keeps: its id, and the computers it's paired with (and their keys). */
object Store {
    private lateinit var ctx: Context
    private val prefs get() = ctx.getSharedPreferences("kvm", Context.MODE_PRIVATE)

    fun init(c: Context) { ctx = c.applicationContext }

    val me: Me
        get() {
            var id = prefs.getString("id", null)
            if (id == null) {
                id = Crypto.randomBytes(8).hex()
                prefs.edit().putString("id", id).apply()
            }
            val name = Settings.Global.getString(ctx.contentResolver, "device_name")
                ?: Settings.Secure.getString(ctx.contentResolver, "bluetooth_name") ?: Build.MODEL
            return Me(id, name, BuildConfig.VERSION_NAME)
        }

    @Synchronized
    fun desks(): List<Desk> {
        val a = JSONArray(prefs.getString("desks", "[]"))
        return (0 until a.length()).mapNotNull { runCatching { Desk.fromJson(a.getJSONObject(it)) }.getOrNull() }
    }

    @Synchronized
    fun put(d: Desk) {
        val list = desks().filter { it.id != d.id } + d
        prefs.edit().putString("desks", JSONArray(list.map { it.toJson() }).toString()).apply()
    }

    @Synchronized
    fun remove(id: String) {
        prefs.edit().putString("desks", JSONArray(desks().filter { it.id != id }.map { it.toJson() }).toString()).apply()
    }

    var mirrorNotifs: Boolean
        get() = prefs.getBoolean("mirror", true)
        set(v) = prefs.edit().putBoolean("mirror", v).apply()

    var lastUpdateCheck: Long
        get() = prefs.getLong("upd_at", 0)
        set(v) = prefs.edit().putLong("upd_at", v).apply()
}
