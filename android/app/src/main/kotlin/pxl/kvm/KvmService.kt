package pxl.kvm

import android.app.Notification
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.ServiceInfo
import android.net.ConnectivityManager
import android.net.Network
import android.os.IBinder

/** Keeps the links to the computers open in the background. */
class KvmService : Service() {
    private var battery: BroadcastReceiver? = null
    private var net: ConnectivityManager.NetworkCallback? = null
    private var lastLevel = -1

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        running = true
        startForeground(NOTE, note(this, 0, Store.desks().size), ServiceInfo.FOREGROUND_SERVICE_TYPE_CONNECTED_DEVICE)
        Hub.start()
        battery = object : BroadcastReceiver() {
            override fun onReceive(c: Context, i: Intent) {
                val level = i.getIntExtra(android.os.BatteryManager.EXTRA_LEVEL, -1)
                if (i.action != Intent.ACTION_BATTERY_CHANGED || level != lastLevel) {
                    lastLevel = level
                    Hub.battery()
                }
            }
        }
        registerReceiver(battery, IntentFilter().apply {
            addAction(Intent.ACTION_BATTERY_CHANGED)
            addAction(Intent.ACTION_POWER_CONNECTED)
            addAction(Intent.ACTION_POWER_DISCONNECTED)
        })
        net = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) = Hub.reconnectNow()
        }
        runCatching { getSystemService(ConnectivityManager::class.java).registerDefaultNetworkCallback(net!!) }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            STOP_RING -> Ringer.stop(this)
            QUIT -> {
                Hub.stop()
                stopSelf()
                return START_NOT_STICKY
            }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        battery?.let { runCatching { unregisterReceiver(it) } }
        net?.let { runCatching { getSystemService(ConnectivityManager::class.java).unregisterNetworkCallback(it) } }
        Hub.stop()
        running = false
        super.onDestroy()
    }

    companion object {
        const val STOP_RING = "pxl.kvm.STOP_RING"
        const val QUIT = "pxl.kvm.QUIT"
        private const val NOTE = 1
        @Volatile var running = false

        fun start(ctx: Context) {
            runCatching { ctx.startForegroundService(Intent(ctx, KvmService::class.java)) }
        }

        private fun note(ctx: Context, connected: Int, total: Int): Notification {
            val open = PendingIntent.getActivity(ctx, 0, Intent(ctx, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
            return Notification.Builder(ctx, KvmApp.CH_LINK)
                .setSmallIcon(R.drawable.ic_kvm)
                .setContentTitle(if (connected > 0) "Connected to $connected computer${if (connected > 1) "s" else ""}"
                                 else if (total > 0) "Looking for your computer" else "Kvm")
                .setContentIntent(open)
                .setOngoing(true)
                .build()
        }

        fun refresh(ctx: Context, connected: Int, total: Int) {
            if (running) runCatching { ctx.getSystemService(NotificationManager::class.java).notify(NOTE, note(ctx, connected, total)) }
        }
    }
}

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(c: Context, i: Intent) {
        if (Store.desks().isNotEmpty()) KvmService.start(c)
    }
}
