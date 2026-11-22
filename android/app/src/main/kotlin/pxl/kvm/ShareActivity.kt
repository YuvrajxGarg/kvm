package pxl.kvm

import android.app.Activity
import android.app.AlertDialog
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.Toast

/** Share → Kvm: text goes to the computer's clipboard, photos and files to its Downloads/Kvm. */
class ShareActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val uris = uris(intent)
        val text = intent.getStringExtra(Intent.EXTRA_TEXT)
        val live = Hub.connectedIds()
        val desks = Store.desks().filter { it.id in live }
        if (desks.isEmpty()) {
            KvmService.start(this)
            Toast.makeText(this, if (Store.desks().isEmpty()) "Pair Kvm with a computer first." else "Your computer isn't connected. Open Kvm on it and try again.", Toast.LENGTH_LONG).show()
            finish()
            return
        }
        val go = { id: String ->
            if (uris.isNotEmpty()) {
                Hub.sendUris(id, uris)
                Toast.makeText(this, "Sending to ${desks.first { it.id == id }.name}…", Toast.LENGTH_SHORT).show()
            } else if (!text.isNullOrEmpty()) {
                Hub.sendClip(text)
                Toast.makeText(this, "On the computer's clipboard", Toast.LENGTH_SHORT).show()
            }
            finish()
        }
        if (desks.size == 1 || uris.isEmpty()) go(desks[0].id)
        else AlertDialog.Builder(this, android.R.style.Theme_Material_Dialog_Alert)
            .setTitle("Send to")
            .setItems(desks.map { it.name }.toTypedArray()) { _, i -> go(desks[i].id) }
            .setOnCancelListener { finish() }
            .show()
    }

    @Suppress("DEPRECATION")
    private fun uris(i: Intent): List<Uri> = when (i.action) {
        Intent.ACTION_SEND -> listOfNotNull(i.getParcelableExtra(Intent.EXTRA_STREAM) as? Uri)
        Intent.ACTION_SEND_MULTIPLE -> i.getParcelableArrayListExtra<Uri>(Intent.EXTRA_STREAM) ?: emptyList()
        else -> emptyList()
    }
}
