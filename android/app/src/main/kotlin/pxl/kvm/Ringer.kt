package pxl.kvm

import android.app.Notification
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.media.Ringtone
import android.os.Handler
import android.os.Looper

/** "Ring" from a computer: loud, even on silent, for 30 seconds or until stopped. */
object Ringer {
    private var tone: Ringtone? = null
    private val h = Handler(Looper.getMainLooper())
    private const val NOTE = 7

    fun ring(ctx: Context, from: String) = h.post {
        stop(ctx)
        val uri = RingtoneManager.getActualDefaultRingtoneUri(ctx, RingtoneManager.TYPE_RINGTONE)
            ?: RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
        tone = RingtoneManager.getRingtone(ctx, uri)?.apply {
            audioAttributes = AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM)
                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build()
            isLooping = true
            play()
        }
        val stop = PendingIntent.getService(ctx, 1, Intent(ctx, KvmService::class.java).setAction(KvmService.STOP_RING),
            PendingIntent.FLAG_IMMUTABLE)
        val open = PendingIntent.getActivity(ctx, 2, Intent(ctx, MainActivity::class.java).setAction(KvmService.STOP_RING),
            PendingIntent.FLAG_IMMUTABLE)
        val n = Notification.Builder(ctx, KvmApp.CH_RING)
            .setSmallIcon(R.drawable.ic_kvm)
            .setContentTitle("$from is ringing this phone")
            .setContentText("Tap to stop")
            .setContentIntent(open)
            .setDeleteIntent(stop)
            .setFullScreenIntent(open, true)
            .addAction(Notification.Action.Builder(null, "Stop", stop).build())
            .setCategory(Notification.CATEGORY_ALARM)
            .build()
        runCatching { ctx.getSystemService(NotificationManager::class.java).notify(NOTE, n) }
        h.postDelayed({ stop(ctx) }, 30_000)
    }

    fun stop(ctx: Context) {
        h.removeCallbacksAndMessages(null)
        tone?.stop()
        tone = null
        runCatching { ctx.getSystemService(NotificationManager::class.java).cancel(NOTE) }
    }
}
