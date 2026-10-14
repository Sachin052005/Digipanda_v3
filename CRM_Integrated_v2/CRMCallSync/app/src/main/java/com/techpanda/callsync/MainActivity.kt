package com.techpanda.callsync

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : AppCompatActivity() {

    private lateinit var prefs: Prefs

    private val requiredPermissions: Array<String>
        get() = if (Build.VERSION.SDK_INT >= 33)
            arrayOf(
                Manifest.permission.READ_CALL_LOG,
                Manifest.permission.READ_PHONE_STATE,
                Manifest.permission.CALL_PHONE,
                Manifest.permission.READ_MEDIA_AUDIO,
            )
        else
            arrayOf(
                Manifest.permission.READ_CALL_LOG,
                Manifest.permission.READ_PHONE_STATE,
                Manifest.permission.CALL_PHONE,
                Manifest.permission.READ_EXTERNAL_STORAGE,
            )

    private val permissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
            if (prefs.token != null) SyncService.start(this)
            refresh()
        }

    /** Folder picker: user selects the exact folder where recordings are saved. */
    private val folderPickerLauncher =
        registerForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
            if (uri == null) return@registerForActivityResult
            // Persist permission across reboots so SyncEngine can keep reading the folder
            contentResolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION
            )
            prefs.recordingFolderUri = uri.toString()
            // Build a readable name: decode the last path segment, e.g. "primary:Recordings/Call"
            val name = try {
                uri.lastPathSegment
                    ?.substringAfter(":")
                    ?.replace("%2F", "/")
                    ?.trimEnd('/') ?: uri.toString()
            } catch (e: Exception) { uri.toString() }
            prefs.recordingFolderName = name
            Toast.makeText(this, "Recording folder set: $name", Toast.LENGTH_LONG).show()
            refresh()
        }

    /** Core permissions, plus notification permission on Android 13+ (needed to show the sync notification). */
    private fun permissionsToAsk(): Array<String> =
        if (Build.VERSION.SDK_INT >= 33) requiredPermissions + Manifest.permission.POST_NOTIFICATIONS
        else requiredPermissions

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        prefs = Prefs(this)

        findViewById<EditText>(R.id.serverUrl).setText(prefs.serverUrl)
        findViewById<EditText>(R.id.username).setText(prefs.username)

        findViewById<Button>(R.id.loginButton).setOnClickListener { login() }
        findViewById<Button>(R.id.permissionButton).setOnClickListener {
            permissionLauncher.launch(permissionsToAsk())
        }
        findViewById<Button>(R.id.batteryButton).setOnClickListener {
            handleBatteryOptimizationRequest()
        }
        findViewById<Button>(R.id.manufacturerSettingsButton).setOnClickListener {
            showManufacturerReliabilityDialog()
        }
        findViewById<Button>(R.id.syncButton).setOnClickListener {
            Toast.makeText(this, "Syncing...", Toast.LENGTH_SHORT).show()
            lifecycleScope.launch {
                SyncEngine.syncOnce(this@MainActivity)
                refresh()
            }
        }
        findViewById<Button>(R.id.syncButton).setOnLongClickListener {
            Toast.makeText(this, "Resetting sync cursor: scanning all recordings...", Toast.LENGTH_LONG).show()
            prefs.lastSyncedAddedSec = 0L
            prefs.lastSyncedId = 0L
            lifecycleScope.launch {
                SyncEngine.syncOnce(this@MainActivity)
                refresh()
            }
            true
        }
        findViewById<Button>(R.id.recordingFolderButton).setOnClickListener {
            folderPickerLauncher.launch(null)
        }
        findViewById<Button>(R.id.recordingFolderButton).setOnLongClickListener {
            prefs.recordingFolderUri = ""
            prefs.recordingFolderName = ""
            Toast.makeText(this, "Folder reset to auto-detect", Toast.LENGTH_SHORT).show()
            refresh()
            true
        }
        findViewById<Button>(R.id.overlayPermissionButton).setOnClickListener {
            if (Build.VERSION.SDK_INT >= 23 && !Settings.canDrawOverlays(this)) {
                val intent = Intent(
                    Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    android.net.Uri.parse("package:$packageName")
                )
                startActivity(intent)
            } else {
                Toast.makeText(this, "Background call permission already granted", Toast.LENGTH_SHORT).show()
            }
        }
        findViewById<Button>(R.id.googleCallsButton).setOnClickListener { chooseGoogleSim() }
        findViewById<Button>(R.id.logoutButton).setOnClickListener {
            prefs.logout()
            SyncService.stop(this)
            UploadWorker.cancelAll(this)
            refresh()
        }
    }

    private fun isIgnoringBatteryOptimizations(): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) return true
        val pm = getSystemService(android.os.PowerManager::class.java) ?: return true
        return pm.isIgnoringBatteryOptimizations(packageName)
    }

    private fun handleBatteryOptimizationRequest() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M) {
            Toast.makeText(this, "Battery optimization not restricted on this Android version", Toast.LENGTH_SHORT).show()
            return
        }
        if (isIgnoringBatteryOptimizations()) {
            // Already ignoring, take user to the full system settings screen where they can verify
            Toast.makeText(this, "Already Unrestricted! Opening battery settings...", Toast.LENGTH_SHORT).show()
            try {
                startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
            } catch (e: Exception) {
                startActivity(Intent(Settings.ACTION_SETTINGS))
            }
            return
        }

        // Direct request dialog compliant with enterprise background dialing & sync core use case
        try {
            val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                data = android.net.Uri.parse("package:$packageName")
            }
            startActivity(intent)
        } catch (e: Exception) {
            // Fallback to standard ignore optimization settings screen
            try {
                startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
            } catch (ex: Exception) {
                startActivity(Intent(Settings.ACTION_SETTINGS))
            }
        }
    }

    private fun showManufacturerReliabilityDialog() {
        val manufacturer = Build.MANUFACTURER.lowercase()
        val brand = Build.BRAND.lowercase()

        val guideMessage = when {
            manufacturer.contains("xiaomi") || brand.contains("redmi") || brand.contains("poco") ->
                "Xiaomi / MIUI / HyperOS Instructions:\n\n" +
                "1. Autostart: Go to Settings -> Apps -> Manage Apps -> CRM Call Sync -> Enable 'Autostart'.\n" +
                "2. Battery Saver: Under app settings, set Battery Saver to 'No restrictions'.\n" +
                "3. Lock App: In Recent Apps view, press & hold CRM Call Sync and tap the Lock icon so MIUI does not clear it."

            manufacturer.contains("samsung") ->
                "Samsung One UI Instructions:\n\n" +
                "1. Background usage limits: Go to Settings -> Battery and device care -> Battery -> Background usage limits.\n" +
                "2. Never sleeping apps: Add 'CRM Call Sync' to 'Never sleeping apps'.\n" +
                "3. Set Battery mode for this app to 'Unrestricted' in App Info."

            manufacturer.contains("oppo") || manufacturer.contains("realme") ->
                "Oppo / Realme / ColorOS Instructions:\n\n" +
                "1. Auto-launch: Settings -> App management -> CRM Call Sync -> Enable 'Allow auto-launch' & 'Allow background activity'.\n" +
                "2. Battery: Settings -> Battery -> CRM Call Sync -> Select 'Don't optimize'.\n" +
                "3. Lock in Recents: In recent tasks screen, tap dots / swipe down and choose 'Lock'."

            manufacturer.contains("vivo") || manufacturer.contains("iqoo") ->
                "Vivo / iQOO / Funtouch OS Instructions:\n\n" +
                "1. Autostart: Settings -> Battery -> High background power consumption -> Allow 'CRM Call Sync'.\n" +
                "2. Permissions: Settings -> Applications -> Autostart -> Enable for 'CRM Call Sync'.\n" +
                "3. Lock App: Lock CRM Call Sync in recent task view."

            manufacturer.contains("oneplus") ->
                "OnePlus / OxygenOS Instructions:\n\n" +
                "1. Battery Optimization: Settings -> Battery -> Battery optimization -> CRM Call Sync -> Choose 'Don't optimize'.\n" +
                "2. App Auto-launch: Enable background launch for CRM Call Sync."

            manufacturer.contains("huawei") || manufacturer.contains("honor") ->
                "Huawei / Honor Instructions:\n\n" +
                "1. App Launch: Settings -> Battery -> App Launch -> Turn off auto-manage for CRM Call Sync, and manually enable Auto-launch, Secondary launch, and Run in background."

            else ->
                "Manufacturer Background Activity:\n\n" +
                "1. Ensure 'CRM Call Sync' has Background execution allowed.\n" +
                "2. Set Battery usage to 'Unrestricted'.\n" +
                "3. If your device has an Auto-start or App Killer manager, whitelist CRM Call Sync.\n\n" +
                "Device: ${Build.MANUFACTURER} (${Build.MODEL})"
        }

        AlertDialog.Builder(this)
            .setTitle("Background Reliability Guide")
            .setMessage(guideMessage)
            .setPositiveButton("Open App Settings") { _, _ ->
                try {
                    val intent = Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                        data = android.net.Uri.parse("package:$packageName")
                    }
                    startActivity(intent)
                } catch (e: Exception) {
                    startActivity(Intent(Settings.ACTION_SETTINGS))
                }
            }
            .setNeutralButton("Battery Settings") { _, _ ->
                try {
                    startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
                } catch (e: Exception) {
                    startActivity(Intent(Settings.ACTION_SETTINGS))
                }
            }
            .setNegativeButton("Close", null)
            .show()
    }

    override fun onResume() {
        super.onResume()
        // Make sure the always-on sync is running whenever a logged-in user opens the app
        if (prefs.token != null && hasPermissions()) SyncService.start(this)
        refresh()
    }

    private fun hasPermissions() = requiredPermissions.all {
        ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED
    }

    private fun login() {
        val server = findViewById<EditText>(R.id.serverUrl).text.toString().trim().trimEnd('/')
        val user = findViewById<EditText>(R.id.username).text.toString().trim()
        val pass = findViewById<EditText>(R.id.password).text.toString()
        if (server.isEmpty() || user.isEmpty() || pass.isEmpty()) {
            Toast.makeText(this, "Fill server, username and password", Toast.LENGTH_SHORT).show()
            return
        }
        lifecycleScope.launch {
            try {
                val token = withContext(Dispatchers.IO) { Api.login(server, user, pass) }
                // Same person logging in again (e.g. after a password change): keep the sync
                // position so recordings / Google calls made while logged out are still sent.
                val sameUser = prefs.username == user && prefs.serverUrl == server && prefs.lastSyncedAddedSec > 0
                prefs.serverUrl = server
                prefs.username = user
                prefs.token = token
                if (!sameUser) {
                    // New login on this phone: look back 4 hours so recent calls/recordings made today are uploaded.
                    val lookbackSec = (System.currentTimeMillis() / 1000) - (4L * 3600)
                    prefs.markUploaded(lookbackSec, 0L)
                    // Google calls: pick up the last 24 hours so today's missed calls are not lost.
                    prefs.callLogSinceMs = System.currentTimeMillis() - 24L * 60 * 60 * 1000
                }
                prefs.lastCallStatus = ""
                findViewById<EditText>(R.id.password).setText("")
                UploadWorker.schedulePeriodic(this@MainActivity)
                if (hasPermissions()) SyncService.start(this@MainActivity)
                else permissionLauncher.launch(permissionsToAsk())
                Toast.makeText(this@MainActivity, "Logged in", Toast.LENGTH_SHORT).show()
            } catch (e: Exception) {
                Toast.makeText(this@MainActivity, e.message, Toast.LENGTH_LONG).show()
            }
            refresh()
        }
    }

    /**
     * "Google Ads number" picker. Telecaller phones that do not carry the Google number keep it Off,
     * otherwise every personal / lead call on that phone would become a Google lead.
     */
    private fun chooseGoogleSim() {
        val sims = CallLogSync.listSims(this)
        val labels = mutableListOf("Off – this phone does not get Google Ads calls",
            "All SIMs – this phone is only for the Google number")
        val values = mutableListOf("", "all")
        sims.forEach { labels += it.label; values += it.accountId }
        val checked = values.indexOf(prefs.googleSim).coerceAtLeast(0)

        AlertDialog.Builder(this)
            .setTitle("Which SIM has the Google Ads number?")
            .setSingleChoiceItems(labels.toTypedArray(), checked) { dialog, which ->
                val wasOff = !prefs.googleCallsOn
                prefs.googleSim = values[which]
                prefs.googleSimLabel = if (which >= 2) labels[which] else ""
                if (wasOff && prefs.googleCallsOn) {
                    // Turning it on: also send the last 24 hours of Google calls.
                    prefs.callLogSinceMs = System.currentTimeMillis() - 24L * 60 * 60 * 1000
                }
                prefs.lastCallStatus = ""
                dialog.dismiss()
                refresh()
                if (prefs.googleCallsOn) lifecycleScope.launch { SyncEngine.syncOnce(this@MainActivity); refresh() }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun googleSimText(): String = when {
        !prefs.googleCallsOn -> "Off"
        prefs.googleSim == "all" -> "All SIMs"
        else -> prefs.googleSimLabel.ifBlank { "SIM ${prefs.googleSim}" }
    }

    private fun refresh() {
        val loggedIn = prefs.token != null
        findViewById<LinearLayout>(R.id.loginSection).visibility = if (loggedIn) View.GONE else View.VISIBLE
        findViewById<LinearLayout>(R.id.statusSection).visibility = if (loggedIn) View.VISIBLE else View.GONE
        findViewById<Button>(R.id.permissionButton).visibility =
            if (hasPermissions()) View.GONE else View.VISIBLE
        findViewById<Button>(R.id.googleCallsButton).text = "Google Ads number: ${googleSimText()}"
        val folderLabel = if (prefs.recordingFolderName.isNotBlank()) {
            "Recording folder: ${prefs.recordingFolderName}"
        } else {
            "Recording folder: auto-detect (tap to select)"
        }
        findViewById<Button>(R.id.recordingFolderButton).text = folderLabel
        val hasOverlay = Build.VERSION.SDK_INT < 23 || Settings.canDrawOverlays(this)
        findViewById<Button>(R.id.overlayPermissionButton).text =
            if (hasOverlay) "Background auto-call: Allowed (OK)"
            else "Background auto-call: Tap to enable 'Appear on top'"

        val isIgnoringBattery = isIgnoringBatteryOptimizations()
        val batteryStatusView = findViewById<TextView>(R.id.batteryStateText)
        if (batteryStatusView != null) {
            if (isIgnoringBattery) {
                batteryStatusView.text = "Battery Optimization: Unrestricted (Exempted) ✓"
                batteryStatusView.setTextColor(android.graphics.Color.parseColor("#15803d"))
            } else {
                batteryStatusView.text = "Battery Optimization: Optimized (May be restricted when screen is off) ⚠️"
                batteryStatusView.setTextColor(android.graphics.Color.parseColor("#b45309"))
            }
        }
        val batteryBtn = findViewById<Button>(R.id.batteryButton)
        if (batteryBtn != null) {
            batteryBtn.text = if (isIgnoringBattery) "Battery Optimization: Unrestricted (Tap to check)" else "Disable Battery Optimization (Set Unrestricted)"
        }

        findViewById<TextView>(R.id.statusText).text = buildString {
            append(if (loggedIn) "Logged in as ${prefs.username}\n" else "")
            append(if (hasPermissions()) "Permissions: OK\n" else "Permissions: MISSING - tap the button below\n")
            append("Battery state: ${if (isIgnoringBattery) "Unrestricted" else "Optimized / Restricted"}\n")
            append(prefs.lastStatus)
            if (loggedIn && prefs.googleCallsOn && prefs.lastCallStatus.isNotEmpty()) append("\n${prefs.lastCallStatus}")
        }
    }
}
