package pxl.kvm

import android.Manifest
import android.content.ClipboardManager
import android.content.ComponentName
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.journeyapps.barcodescanner.ScanContract
import com.journeyapps.barcodescanner.ScanOptions
import pxl.kvm.core.Link
import pxl.kvm.core.QrOffer
import kotlin.concurrent.thread

private val Lime = Color(0xFFC8F560)
private val Bg = Color(0xFF0E0F11)
private val CardBg = Color(0xFF17181B)
private val Faint = Color(0xFF9A9CA3)

class MainActivity : ComponentActivity() {
    private var pairing by mutableStateOf<String?>(null)     // what pairing is doing, or null
    private var resumed by mutableIntStateOf(0)              // bumps on resume, so permission rows re-check
    private var sendTo: String? = null

    private val scan = registerForActivityResult(ScanContract()) { r -> r.contents?.let { pairWith(it) } }
    private val photos = registerForActivityResult(ActivityResultContracts.PickMultipleVisualMedia(50)) { uris ->
        sendTo?.let { if (uris.isNotEmpty()) Hub.sendUris(it, uris) }
    }
    private val files = registerForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        sendTo?.let { if (uris.isNotEmpty()) Hub.sendUris(it, uris) }
    }
    private val askPost = registerForActivityResult(ActivityResultContracts.RequestPermission()) { resumed++ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (intent?.action == KvmService.STOP_RING) Ringer.stop(this)
        if (Store.desks().isNotEmpty()) KvmService.start(this)
        Updater.check(auto = true)
        setContent {
            MaterialTheme(colorScheme = darkColorScheme(primary = Lime, onPrimary = Color.Black, background = Bg, surface = CardBg)) {
                Screen()
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        if (intent.action == KvmService.STOP_RING) Ringer.stop(this)
    }

    override fun onResume() {
        super.onResume()
        Ringer.stop(this)
        resumed++
        Hub.publish()
    }

    private fun startScan() {
        scan.launch(ScanOptions().setDesiredBarcodeFormats(ScanOptions.QR_CODE).setBeepEnabled(false)
            .setOrientationLocked(false).setPrompt("Scan the code in Kvm on your computer (Phones → Pair a phone)"))
    }

    private fun pairWith(text: String) {
        val offer = QrOffer.parse(text)
        if (offer == null) {
            Toast.makeText(this, "That isn't a Kvm pairing code.", Toast.LENGTH_LONG).show()
            return
        }
        pairing = "Pairing with ${offer.name}…"
        thread(isDaemon = true) {
            val msg = try {
                val desk = Link.pair(Store.me, offer)
                Hub.added(desk)
                KvmService.start(this)
                "Paired with ${desk.name}"
            } catch (e: Exception) {
                "Didn't pair: ${e.message ?: "couldn't reach the computer. Is the phone on the same Wi-Fi?"}"
            }
            runOnUiThread {
                pairing = null
                Toast.makeText(this, msg, Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun notifAccess(): Boolean {
        val flat = Settings.Secure.getString(contentResolver, "enabled_notification_listeners") ?: ""
        return flat.contains(ComponentName(this, NotifListener::class.java).flattenToString())
    }

    private fun batteryFree() = getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(packageName)

    private fun canPost() = Build.VERSION.SDK_INT < 33 ||
        checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

    @Composable
    private fun Screen() {
        val st by Hub.state.collectAsState()
        val upd by Updater.state.collectAsState()
        @Suppress("UNUSED_VARIABLE") val r = resumed
        Box(Modifier.fillMaxSize().background(Bg)) {
            Column(Modifier.safeDrawingPadding().verticalScroll(rememberScrollState()).padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("kvm", fontSize = 26.sp, fontWeight = FontWeight.Bold, color = Color.White)
                    Box(Modifier.padding(start = 6.dp, top = 4.dp).size(7.dp).clip(CircleShape).background(Lime))
                    Spacer(Modifier.weight(1f))
                    Text("v" + BuildConfig.VERSION_NAME, color = Faint, fontSize = 13.sp)
                }
                if (upd.phase in setOf("available", "downloading", "installing")) UpdateCard(upd)

                if (st.desks.isEmpty()) {
                    Section {
                        Text("Pair with a computer", fontWeight = FontWeight.SemiBold, fontSize = 18.sp, color = Color.White)
                        Text("On your Mac or PC, open Kvm and click Phones → Pair a phone. Then scan the code it shows. " +
                            "The phone and the computer need to be on the same Wi-Fi.", color = Faint)
                        Button(onClick = { startScan() }, enabled = pairing == null) { Text(pairing ?: "Scan the code") }
                    }
                }
                for (d in st.desks) DeskCard(d)

                val todo = listOf(
                    Triple(!canPost(), "Let Kvm show notifications", "For files that arrive and for Ring.") to {
                        if (Build.VERSION.SDK_INT >= 33) askPost.launch(Manifest.permission.POST_NOTIFICATIONS)
                    },
                    Triple(!notifAccess(), "See phone notifications on the computer", "Allow Kvm in Notification access.") to {
                        startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
                    },
                    Triple(st.desks.isNotEmpty() && !batteryFree(), "Stay connected in the background", "Android would otherwise cut the connection when the screen is off.") to {
                        startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName")))
                    },
                ).filter { it.first.first }
                if (todo.isNotEmpty()) Section {
                    Text("Finish setting up", fontWeight = FontWeight.SemiBold, color = Color.White)
                    for ((t, go) in todo) Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(t.second, color = Color.White)
                            Text(t.third, color = Faint, fontSize = 13.sp)
                        }
                        TextButton(onClick = go) { Text("Allow") }
                    }
                }

                if (st.transfers.isNotEmpty()) Section {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("Files", fontWeight = FontWeight.SemiBold, color = Color.White, modifier = Modifier.weight(1f))
                        TextButton(onClick = { Hub.clearTransfers() }) { Text("Clear") }
                    }
                    for (t in st.transfers.take(10)) TransferRow(t)
                }

                Section {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("Send notifications to computers", color = Color.White)
                            Text("Texts, calls and app alerts show up on your Mac or PC.", color = Faint, fontSize = 13.sp)
                        }
                        var on by remember { mutableStateOf(Store.mirrorNotifs) }
                        Switch(checked = on, onCheckedChange = { on = it; Store.mirrorNotifs = it })
                    }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(when (upd.phase) {
                            "checking" -> "Checking for updates…"
                            "uptodate" -> "Kvm is up to date"
                            "failed" -> upd.error ?: "Update check failed"
                            else -> "Updates come from kvm.pxlvzn.in"
                        }, color = Faint, fontSize = 13.sp, modifier = Modifier.weight(1f))
                        TextButton(onClick = { Updater.check() }) { Text("Check now") }
                    }
                    if (st.desks.isNotEmpty()) OutlinedButton(onClick = { startScan() }, enabled = pairing == null) {
                        Text(pairing ?: "Pair another computer")
                    }
                }
            }
        }
    }

    @Composable
    private fun Section(content: @Composable () -> Unit) {
        Card(colors = CardDefaults.cardColors(containerColor = CardBg), shape = RoundedCornerShape(18.dp), modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) { content() }
        }
    }

    @Composable
    private fun DeskCard(d: DeskState) = Section {
        var menu by remember { mutableStateOf(false) }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(9.dp).clip(CircleShape).background(if (d.connected) Lime else Color(0xFF55575D)))
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(d.name, fontWeight = FontWeight.SemiBold, fontSize = 17.sp, color = Color.White)
                Text(if (d.connected) "Connected" else "Not connected. Open Kvm on it, on the same Wi-Fi.", color = Faint, fontSize = 13.sp)
            }
            Box {
                TextButton(onClick = { menu = true }) { Text("•••") }
                DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                    DropdownMenuItem(text = { Text("Unpair") }, onClick = { menu = false; Hub.forget(d.id) })
                }
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = {
                sendTo = d.id
                photos.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageAndVideo))
            }, enabled = d.connected, modifier = Modifier.weight(1f)) { Text("Photos") }
            Button(onClick = { sendTo = d.id; files.launch(arrayOf("*/*")) }, enabled = d.connected, modifier = Modifier.weight(1f),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF26282C), contentColor = Color.White)) { Text("Files") }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = {
                val clip = getSystemService(ClipboardManager::class.java).primaryClip
                val text = clip?.takeIf { it.itemCount > 0 }?.getItemAt(0)?.coerceToText(this@MainActivity)?.toString()
                val msg = if (text.isNullOrEmpty()) "The clipboard is empty." else if (Hub.sendClip(text)) "On ${d.name}'s clipboard" else "Not connected."
                Toast.makeText(this@MainActivity, msg, Toast.LENGTH_SHORT).show()
            }, enabled = d.connected, modifier = Modifier.weight(1f)) { Text("Send clipboard") }
            OutlinedButton(onClick = { Hub.ring(d.id) }, enabled = d.connected, modifier = Modifier.weight(1f)) { Text("Ring") }
        }
    }

    @Composable
    private fun TransferRow(t: Transfer) {
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(t.label, color = Color.White, maxLines = 1)
                    val verb = when (t.phase) {
                        "sending" -> "Sending to ${t.desk}"; "receiving" -> "From ${t.desk}"
                        "sent" -> "Sent to ${t.desk}"; "received" -> "Saved in Downloads/Kvm"
                        "cancelled" -> "Cancelled"; else -> t.error ?: "Didn't finish"
                    }
                    Text(if (t.phase == "failed") (t.error ?: verb) else verb + " · " + human(t.total), color = Faint, fontSize = 13.sp)
                }
                if (t.phase == "sending" && t.outgoing) TextButton(onClick = { Hub.cancel(t.id) }) { Text("Cancel") }
            }
            if (t.phase == "sending" || t.phase == "receiving")
                LinearProgressIndicator(progress = { if (t.total > 0) t.done.toFloat() / t.total else 0f }, modifier = Modifier.fillMaxWidth())
        }
    }

    @Composable
    private fun UpdateCard(u: Updater.State) = Section {
        Text(when (u.phase) {
            "available" -> "Kvm ${u.latest} is available"
            "downloading" -> "Downloading Kvm ${u.latest}…"
            else -> "Installing…"
        }, color = Color.White, fontWeight = FontWeight.SemiBold)
        if (u.phase == "downloading") LinearProgressIndicator(progress = { u.progress }, modifier = Modifier.fillMaxWidth())
        if (u.phase == "available") Button(onClick = {
            if (!packageManager.canRequestPackageInstalls()) {
                Toast.makeText(this@MainActivity, "Allow Kvm to install updates, then tap Update again.", Toast.LENGTH_LONG).show()
                startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:$packageName")))
            } else Updater.install(this@MainActivity)
        }) { Text("Update") }
        Spacer(Modifier.height(2.dp))
    }
}

private fun human(n: Long): String {
    if (n <= 0) return "0 B"
    val u = listOf("B", "KB", "MB", "GB", "TB")
    var v = n.toDouble()
    var i = 0
    while (v >= 1000 && i < 4) { v /= 1000; i++ }
    return if (i == 0) "$n B" else "%.${if (v < 10) 1 else 0}f %s".format(v, u[i])
}
