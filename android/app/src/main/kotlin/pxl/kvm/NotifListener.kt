package pxl.kvm

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification

/** Passes the phone's notifications to paired computers (once the person allows it in Settings). */
class NotifListener : NotificationListenerService() {
    override fun onListenerConnected() {
        me = this
        resend()
    }

    override fun onListenerDisconnected() {
        if (me === this) me = null
    }

    override fun onNotificationPosted(sbn: StatusBarNotification) = send(sbn, alert = true)

    override fun onNotificationRemoved(sbn: StatusBarNotification) {
        if (wanted(sbn)) Hub.notifGone(sbn.key)
    }

    private fun wanted(sbn: StatusBarNotification): Boolean {
        val n = sbn.notification
        if (sbn.packageName == packageName) return false
        if (n.flags and Notification.FLAG_GROUP_SUMMARY != 0) return false
        // Ongoing ones (music, navigation, downloads) aren't news; calls are.
        if (sbn.isOngoing && n.category != Notification.CATEGORY_CALL) return false
        return true
    }

    private fun send(sbn: StatusBarNotification, alert: Boolean) {
        if (!wanted(sbn)) return
        val n = sbn.notification
        val x = n.extras
        val title = x.getCharSequence(Notification.EXTRA_TITLE)?.toString() ?: ""
        val text = (x.getCharSequence(Notification.EXTRA_BIG_TEXT) ?: x.getCharSequence(Notification.EXTRA_TEXT))?.toString() ?: ""
        if (title.isEmpty() && text.isEmpty()) return
        val app = runCatching {
            packageManager.getApplicationLabel(packageManager.getApplicationInfo(sbn.packageName, 0)).toString()
        }.getOrDefault(sbn.packageName)
        Hub.notif(sbn.key, app, title.take(200), text.take(1000), sbn.postTime, alert)
    }

    companion object {
        @Volatile private var me: NotifListener? = null

        /** What's on the phone now, for a computer that just connected (no alerts for these). */
        fun resend() {
            val l = me ?: return
            runCatching { l.activeNotifications?.forEach { l.send(it, alert = false) } }
        }

        fun dismiss(key: String) {
            runCatching { me?.cancelNotification(key) }
        }
    }
}
