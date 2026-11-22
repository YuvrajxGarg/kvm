package pxl.kvm

import android.app.NotificationManager
import android.app.PendingIntent
import android.content.ContentValues
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Environment
import android.provider.MediaStore
import android.app.DownloadManager
import pxl.kvm.core.Files
import java.io.OutputStream

/** Saves files from a computer to Downloads/Kvm, through MediaStore (no storage permission). */
class Saver(private val ctx: Context, private val from: String) : Files.Sink {
    private val open = HashMap<String, Uri>()

    override fun open(rel: String, size: Long): OutputStream {
        val dir = rel.substringBeforeLast('/', "")
        val name = rel.substringAfterLast('/')
        val values = ContentValues().apply {
            put(MediaStore.MediaColumns.DISPLAY_NAME, name)
            put(MediaStore.MediaColumns.RELATIVE_PATH, Environment.DIRECTORY_DOWNLOADS + "/Kvm" + if (dir.isEmpty()) "" else "/$dir")
            put(MediaStore.MediaColumns.IS_PENDING, 1)
        }
        val uri = ctx.contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
            ?: throw java.io.IOException("Can't write to Downloads")
        open[rel] = uri
        return ctx.contentResolver.openOutputStream(uri) ?: throw java.io.IOException("Can't write to Downloads")
    }

    override fun finish(rel: String, ok: Boolean) {
        val uri = open.remove(rel) ?: return
        if (ok) {
            ctx.contentResolver.update(uri, ContentValues().apply { put(MediaStore.MediaColumns.IS_PENDING, 0) }, null, null)
        } else {
            runCatching { ctx.contentResolver.delete(uri, null, null) }
        }
    }

    companion object {
        private var n = 100

        fun notifyReceived(ctx: Context, from: String, label: String, count: Int) {
            val open = PendingIntent.getActivity(ctx, 0, Intent(DownloadManager.ACTION_VIEW_DOWNLOADS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                PendingIntent.FLAG_IMMUTABLE)
            val nb = android.app.Notification.Builder(ctx, KvmApp.CH_FILES)
                .setSmallIcon(R.drawable.ic_kvm)
                .setContentTitle(if (count > 1) "$count files from $from" else "$label from $from")
                .setContentText("Saved in Downloads/Kvm")
                .setContentIntent(open)
                .setAutoCancel(true)
            runCatching { ctx.getSystemService(NotificationManager::class.java).notify(n++, nb.build()) }
        }
    }
}
