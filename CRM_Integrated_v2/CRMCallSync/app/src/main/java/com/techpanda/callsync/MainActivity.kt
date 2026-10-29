package com.techpanda.callsync

import android.Manifest
import android.animation.AnimatorSet
import android.animation.ObjectAnimator
import android.animation.ValueAnimator
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.text.InputType
import android.view.HapticFeedbackConstants
import android.view.View
import android.view.ViewGroup
import android.view.animation.AccelerateDecelerateInterpolator
import android.view.animation.DecelerateInterpolator
import android.view.animation.OvershootInterpolator
import android.widget.Button
import android.widget.EditText
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : AppCompatActivity() {

    private lateinit var prefs: Prefs
    private var radarAnimator: AnimatorSet? = null

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
            contentResolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION
            )
            prefs.recordingFolderUri = uri.toString()
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

    private fun permissionsToAsk(): Array<String> =
        if (Build.VERSION.SDK_INT >= 33) requiredPermissions + Manifest.permission.POST_NOTIFICATIONS
        else requiredPermissions

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        prefs = Prefs(this)

        val usernameInput = findViewById<EditText>(R.id.username)
        val passwordInput = findViewById<EditText>(R.id.password)
        val userContainer = findViewById<LinearLayout>(R.id.usernameContainer)
        val passContainer = findViewById<LinearLayout>(R.id.passwordContainer)
        val passwordToggle = findViewById<ImageView>(R.id.passwordToggle)

        usernameInput.setText(prefs.username)

        // Floating focus micro-animations on input containers
        usernameInput.setOnFocusChangeListener { _, hasFocus ->
            if (hasFocus) {
                userContainer?.setBackgroundResource(R.drawable.bg_input_focused)
                userContainer?.animate()?.scaleX(1.01f)?.scaleY(1.01f)?.setDuration(160)?.start()
            } else {
                userContainer?.setBackgroundResource(R.drawable.bg_input)
                userContainer?.animate()?.scaleX(1.0f)?.scaleY(1.0f)?.setDuration(160)?.start()
            }
        }

        passwordInput.setOnFocusChangeListener { _, hasFocus ->
            if (hasFocus) {
                passContainer?.setBackgroundResource(R.drawable.bg_input_focused)
                passContainer?.animate()?.scaleX(1.01f)?.scaleY(1.01f)?.setDuration(160)?.start()
            } else {
                passContainer?.setBackgroundResource(R.drawable.bg_input)
                passContainer?.animate()?.scaleX(1.0f)?.scaleY(1.0f)?.setDuration(160)?.start()
            }
        }

        // Interactive Password Reveal Toggle with Spring Bounce
        var isPasswordVisible = false
        passwordToggle?.setOnClickListener {
            animatePress(it)
            isPasswordVisible = !isPasswordVisible
            val selection = passwordInput.selectionEnd
            if (isPasswordVisible) {
                passwordInput.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
                passwordToggle.setImageResource(R.drawable.ic_eye_off)
            } else {
                passwordInput.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD
                passwordToggle.setImageResource(R.drawable.ic_eye_toggle)
            }
            passwordInput.setSelection(selection)
            passwordToggle.animate().scaleX(1.25f).scaleY(1.25f).rotation(15f).setDuration(110).withEndAction {
                passwordToggle.animate().scaleX(1.0f).scaleY(1.0f).rotation(0f).setDuration(110).start()
            }.start()
        }

        findViewById<SwipeRefreshLayout>(R.id.swipeRefresh)?.let { swipe ->
            swipe.setColorSchemeColors(
                ContextCompat.getColor(this, R.color.accent_blue),
                ContextCompat.getColor(this, R.color.accent_emerald),
                ContextCompat.getColor(this, R.color.accent_cyan)
            )
            swipe.setOnRefreshListener {
                lifecycleScope.launch {
                    SyncEngine.syncOnce(this@MainActivity)
                    refresh()
                    swipe.isRefreshing = false
                }
            }
        }

        findViewById<Button>(R.id.loginButton).setOnClickListener {
            animatePress(it)
            login()
        }
        findViewById<Button>(R.id.permissionButton).setOnClickListener {
            animatePress(it)
            permissionLauncher.launch(permissionsToAsk())
        }
        findViewById<Button>(R.id.batteryButton).setOnClickListener {
            animatePress(it)
            handleBatteryOptimizationRequest()
        }
        findViewById<Button>(R.id.manufacturerSettingsButton).setOnClickListener {
            animatePress(it)
            showManufacturerReliabilityDialog()
        }

        val syncBtn = findViewById<Button>(R.id.syncButton)
        var isSyncing = false
        syncBtn.setOnClickListener {
            if (isSyncing) return@setOnClickListener
            isSyncing = true
            animatePress(it)
            syncBtn.text = "Syncing Telemetry..."
            Toast.makeText(this, "Connecting to CRM telemetry pipe...", Toast.LENGTH_SHORT).show()
            lifecycleScope.launch {
                try {
                    SyncEngine.syncOnce(this@MainActivity)
                } finally {
                    isSyncing = false
                    syncBtn.text = "Sync Now"
                    refresh()
                    playSyncSuccessAnimation(syncBtn)
                }
            }
        }
        syncBtn.setOnLongClickListener {
            it.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
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
            animatePress(it)
            folderPickerLauncher.launch(null)
        }
        findViewById<Button>(R.id.recordingFolderButton).setOnLongClickListener {
            it.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
            prefs.recordingFolderUri = ""
            prefs.recordingFolderName = ""
            Toast.makeText(this, "Folder reset to auto-detect", Toast.LENGTH_SHORT).show()
            refresh()
            true
        }
        findViewById<Button>(R.id.overlayPermissionButton).setOnClickListener {
            animatePress(it)
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
        findViewById<Button>(R.id.googleCallsButton).setOnClickListener {
            animatePress(it)
            chooseGoogleSim()
        }
        findViewById<Button>(R.id.logoutButton).setOnClickListener {
            animatePress(it)
            prefs.logout()
            SyncService.stop(this)
            UploadWorker.cancelAll(this)
            stopRadarAnimation()
            refresh()
            playLoginEntranceAnimation()
        }

        // Trigger smooth app open animation
        playAppOpenAnimation()
    }

    private fun playAppOpenAnimation() {
        val header = findViewById<View>(R.id.mainHeader)
        header?.alpha = 0f
        header?.translationY = -35f
        header?.animate()
            ?.alpha(1f)
            ?.translationY(0f)
            ?.setDuration(350)
            ?.setInterpolator(DecelerateInterpolator())
            ?.start()

        if (prefs.token == null) {
            playLoginEntranceAnimation()
        } else {
            playDashboardEntranceAnimation()
        }
    }

    private fun playLoginEntranceAnimation() {
        val loginCard = findViewById<View>(R.id.loginSection) ?: return
        val userBox = findViewById<View>(R.id.usernameContainer)
        val passBox = findViewById<View>(R.id.passwordContainer)
        val btn = findViewById<View>(R.id.loginButton)

        loginCard.alpha = 0f
        loginCard.scaleX = 0.94f
        loginCard.scaleY = 0.94f
        loginCard.translationY = 40f
        loginCard.animate()
            .alpha(1f)
            .scaleX(1f)
            .scaleY(1f)
            .translationY(0f)
            .setDuration(380)
            .setInterpolator(OvershootInterpolator(1.05f))
            .start()

        userBox?.alpha = 0f
        userBox?.translationX = -25f
        userBox?.animate()
            ?.alpha(1f)
            ?.translationX(0f)
            ?.setStartDelay(100)
            ?.setDuration(280)
            ?.setInterpolator(DecelerateInterpolator())
            ?.start()

        passBox?.alpha = 0f
        passBox?.translationX = -25f
        passBox?.animate()
            ?.alpha(1f)
            ?.translationX(0f)
            ?.setStartDelay(180)
            ?.setDuration(280)
            ?.setInterpolator(DecelerateInterpolator())
            ?.start()

        btn?.alpha = 0f
        btn?.translationY = 25f
        btn?.animate()
            ?.alpha(1f)
            ?.translationY(0f)
            ?.setStartDelay(260)
            ?.setDuration(300)
            ?.setInterpolator(DecelerateInterpolator())
            ?.start()
    }

    private fun playDashboardEntranceAnimation() {
        val cardStatus = findViewById<View>(R.id.cardStatus)
        val cardTelephony = findViewById<View>(R.id.cardTelephony)
        val cardReliability = findViewById<View>(R.id.cardReliability)
        val logoutBtn = findViewById<View>(R.id.logoutButton)

        cardStatus?.alpha = 0f
        cardStatus?.translationY = 45f
        cardStatus?.animate()
            ?.alpha(1f)
            ?.translationY(0f)
            ?.setStartDelay(60)
            ?.setDuration(320)
            ?.setInterpolator(DecelerateInterpolator())
            ?.start()

        cardTelephony?.alpha = 0f
        cardTelephony?.translationY = 45f
        cardTelephony?.animate()
            ?.alpha(1f)
            ?.translationY(0f)
            ?.setStartDelay(140)
            ?.setDuration(320)
            ?.setInterpolator(DecelerateInterpolator())
            ?.start()

        cardReliability?.alpha = 0f
        cardReliability?.translationY = 45f
        cardReliability?.animate()
            ?.alpha(1f)
            ?.translationY(0f)
            ?.setStartDelay(220)
            ?.setDuration(320)
            ?.setInterpolator(DecelerateInterpolator())
            ?.start()

        logoutBtn?.alpha = 0f
        logoutBtn?.translationY = 30f
        logoutBtn?.animate()
            ?.alpha(1f)
            ?.translationY(0f)
            ?.setStartDelay(300)
            ?.setDuration(280)
            ?.setInterpolator(DecelerateInterpolator())
            ?.start()

        playRadarPowerOnPing()
    }

    private fun playRadarPowerOnPing() {
        val ring1 = findViewById<View>(R.id.radarRing1) ?: return
        val ring2 = findViewById<View>(R.id.radarRing2) ?: return
        val core = findViewById<View>(R.id.radarCore) ?: return

        core.scaleX = 0.5f
        core.scaleY = 0.5f
        core.animate().scaleX(1.15f).scaleY(1.15f).setDuration(220).withEndAction {
            core.animate().scaleX(1.0f).scaleY(1.0f).setDuration(120).start()
            try {
                core.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
            } catch (ignored: Exception) {}
            startRadarAnimation()
        }.start()

        ring1.scaleX = 0.5f
        ring1.scaleY = 0.5f
        ring1.alpha = 0.9f
        ring1.animate().scaleX(2.0f).scaleY(2.0f).alpha(0f).setDuration(450).setInterpolator(DecelerateInterpolator()).start()

        ring2.scaleX = 0.5f
        ring2.scaleY = 0.5f
        ring2.alpha = 0.8f
        ring2.animate().scaleX(2.5f).scaleY(2.5f).alpha(0f).setStartDelay(100).setDuration(550).setInterpolator(DecelerateInterpolator()).start()
    }

    private fun animatePress(v: View) {
        try {
            v.performHapticFeedback(HapticFeedbackConstants.CONTEXT_CLICK)
        } catch (ignored: Exception) {}
        v.animate().scaleX(0.95f).scaleY(0.95f).setDuration(80).withEndAction {
            v.animate().scaleX(1.0f).scaleY(1.0f).setDuration(160).setInterpolator(OvershootInterpolator(1.2f)).start()
        }.start()
    }

    private fun playSyncSuccessAnimation(v: View) {
        try {
            v.performHapticFeedback(HapticFeedbackConstants.CONFIRM)
        } catch (ignored: Exception) {}
        v.animate().scaleX(1.04f).scaleY(1.04f).setDuration(120).withEndAction {
            v.animate().scaleX(1.0f).scaleY(1.0f).setDuration(180).setInterpolator(OvershootInterpolator(1.3f)).start()
        }.start()
    }

    private fun shakeView(v: View) {
        try {
            v.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
        } catch (ignored: Exception) {}
        ObjectAnimator.ofFloat(v, "translationX", 0f, -22f, 22f, -16f, 16f, -8f, 8f, 0f).apply {
            duration = 450L
            start()
        }
    }

    private fun startRadarAnimation() {
        if (radarAnimator != null && radarAnimator?.isStarted == true) return
        val ring1 = findViewById<View>(R.id.radarRing1) ?: return
        val ring2 = findViewById<View>(R.id.radarRing2) ?: return

        val anim1ScaleX = ObjectAnimator.ofFloat(ring1, "scaleX", 0.6f, 1.8f).apply {
            repeatCount = ValueAnimator.INFINITE
            duration = 2000L
            interpolator = AccelerateDecelerateInterpolator()
        }
        val anim1ScaleY = ObjectAnimator.ofFloat(ring1, "scaleY", 0.6f, 1.8f).apply {
            repeatCount = ValueAnimator.INFINITE
            duration = 2000L
            interpolator = AccelerateDecelerateInterpolator()
        }
        val anim1Alpha = ObjectAnimator.ofFloat(ring1, "alpha", 0.7f, 0f).apply {
            repeatCount = ValueAnimator.INFINITE
            duration = 2000L
            interpolator = AccelerateDecelerateInterpolator()
        }

        val anim2ScaleX = ObjectAnimator.ofFloat(ring2, "scaleX", 0.6f, 2.2f).apply {
            repeatCount = ValueAnimator.INFINITE
            duration = 2000L
            startDelay = 650L
            interpolator = AccelerateDecelerateInterpolator()
        }
        val anim2ScaleY = ObjectAnimator.ofFloat(ring2, "scaleY", 0.6f, 2.2f).apply {
            repeatCount = ValueAnimator.INFINITE
            duration = 2000L
            startDelay = 650L
            interpolator = AccelerateDecelerateInterpolator()
        }
        val anim2Alpha = ObjectAnimator.ofFloat(ring2, "alpha", 0.7f, 0f).apply {
            repeatCount = ValueAnimator.INFINITE
            duration = 2000L
            startDelay = 650L
            interpolator = AccelerateDecelerateInterpolator()
        }

        radarAnimator = AnimatorSet().apply {
            playTogether(anim1ScaleX, anim1ScaleY, anim1Alpha, anim2ScaleX, anim2ScaleY, anim2Alpha)
            start()
        }
    }

    private fun stopRadarAnimation() {
        radarAnimator?.cancel()
        radarAnimator = null
        findViewById<View>(R.id.radarRing1)?.alpha = 0f
        findViewById<View>(R.id.radarRing2)?.alpha = 0f
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
            Toast.makeText(this, "Already Unrestricted! Opening battery settings...", Toast.LENGTH_SHORT).show()
            try {
                startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS))
            } catch (e: Exception) {
                startActivity(Intent(Settings.ACTION_SETTINGS))
            }
            return
        }

        try {
            val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                data = android.net.Uri.parse("package:$packageName")
            }
            startActivity(intent)
        } catch (e: Exception) {
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
        if (prefs.token != null && hasPermissions()) {
            SyncService.start(this)
            startRadarAnimation()
        }
        refresh()
    }

    override fun onPause() {
        super.onPause()
        stopRadarAnimation()
    }

    private fun hasPermissions() = requiredPermissions.all {
        ContextCompat.checkSelfPermission(this, it) == PackageManager.PERMISSION_GRANTED
    }

    private fun login() {
        val server = prefs.serverUrl
        val user = findViewById<EditText>(R.id.username).text.toString().trim()
        val pass = findViewById<EditText>(R.id.password).text.toString()
        if (user.isEmpty() || pass.isEmpty()) {
            findViewById<LinearLayout>(R.id.loginSection)?.let { shakeView(it) }
            Toast.makeText(this, "Fill username and password", Toast.LENGTH_SHORT).show()
            return
        }
        lifecycleScope.launch {
            try {
                val token = withContext(Dispatchers.IO) { Api.login(server, user, pass) }
                val sameUser = prefs.username == user && prefs.serverUrl == server && prefs.lastSyncedAddedSec > 0
                prefs.serverUrl = server
                prefs.username = user
                prefs.token = token
                if (!sameUser) {
                    val lookbackSec = (System.currentTimeMillis() / 1000) - (4L * 3600)
                    prefs.markUploaded(lookbackSec, 0L)
                    prefs.callLogSinceMs = System.currentTimeMillis() - 24L * 60 * 60 * 1000
                }
                prefs.lastCallStatus = ""
                findViewById<EditText>(R.id.password).setText("")
                UploadWorker.schedulePeriodic(this@MainActivity)
                if (hasPermissions()) SyncService.start(this@MainActivity)
                else permissionLauncher.launch(permissionsToAsk())
                startRadarAnimation()
                Toast.makeText(this@MainActivity, "Logged in successfully", Toast.LENGTH_SHORT).show()
                refresh()
                playDashboardEntranceAnimation()
            } catch (e: Exception) {
                findViewById<LinearLayout>(R.id.loginSection)?.let { shakeView(it) }
                Toast.makeText(this@MainActivity, e.message, Toast.LENGTH_LONG).show()
            }
        }
    }

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
        val mainContainer = findViewById<ViewGroup>(R.id.mainContainer)
        if (mainContainer != null) {
            android.transition.TransitionManager.beginDelayedTransition(
                mainContainer,
                android.transition.AutoTransition().apply { duration = 200L }
            )
        }

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
                batteryStatusView.setTextColor(ContextCompat.getColor(this, R.color.accent_emerald))
            } else {
                batteryStatusView.text = "Battery Optimization: Optimized (May restrict sync when screen is off) ⚠️"
                batteryStatusView.setTextColor(ContextCompat.getColor(this, R.color.accent_amber))
            }
        }
        val batteryBtn = findViewById<Button>(R.id.batteryButton)
        if (batteryBtn != null) {
            batteryBtn.text = if (isIgnoringBattery) "Battery Optimization: Unrestricted (Tap to check)" else "Disable Battery Optimization (Set Unrestricted)"
        }

        val activeUserTitle = findViewById<TextView>(R.id.activeUserTitle)
        if (activeUserTitle != null && loggedIn) {
            activeUserTitle.text = prefs.username
        }

        val userAvatar = findViewById<TextView>(R.id.userAvatarText)
        if (userAvatar != null && loggedIn) {
            userAvatar.text = (prefs.username.firstOrNull() ?: 'T').uppercaseChar().toString()
        }

        val workspaceSub = findViewById<TextView>(R.id.workspaceSubtext)
        if (workspaceSub != null) {
            workspaceSub.text = if (loggedIn) "CRM Pipe: Active • Telemetry Linked" else "Device Unlinked"
        }

        findViewById<TextView>(R.id.tileCallsStatus)?.text = if (prefs.googleCallsOn) googleSimText() else "All Monitored"
        findViewById<TextView>(R.id.tileAudioStatus)?.text = if (prefs.recordingFolderName.isNotBlank()) "Folder Active" else "Auto-Detect"

        val tileEngine = findViewById<TextView>(R.id.tileEngineStatus)
        if (tileEngine != null) {
            if (isIgnoringBattery) {
                tileEngine.text = "Unrestricted ✓"
                tileEngine.setTextColor(ContextCompat.getColor(this, R.color.accent_emerald))
            } else {
                tileEngine.text = "Optimized ⚠️"
                tileEngine.setTextColor(ContextCompat.getColor(this, R.color.accent_amber))
            }
        }

        val liveBadge = findViewById<TextView>(R.id.liveStateBadge)
        val radarCore = findViewById<View>(R.id.radarCore)
        if (liveBadge != null && radarCore != null) {
            if (!loggedIn) {
                liveBadge.text = "● OFFLINE"
                liveBadge.setBackgroundResource(R.drawable.bg_badge_amber)
                liveBadge.setTextColor(ContextCompat.getColor(this, R.color.accent_amber))
                radarCore.setBackgroundResource(R.drawable.bg_badge_amber)
                stopRadarAnimation()
            } else if (!hasPermissions() || !isIgnoringBattery) {
                liveBadge.text = "● ATTENTION NEEDED"
                liveBadge.setBackgroundResource(R.drawable.bg_badge_amber)
                liveBadge.setTextColor(ContextCompat.getColor(this, R.color.accent_amber))
                radarCore.setBackgroundResource(R.drawable.bg_badge_amber)
                startRadarAnimation()
            } else {
                liveBadge.text = "● ACTIVE & SYNCING"
                liveBadge.setBackgroundResource(R.drawable.bg_badge_emerald)
                liveBadge.setTextColor(ContextCompat.getColor(this, R.color.accent_emerald))
                radarCore.setBackgroundResource(R.drawable.ic_radar_core)
                startRadarAnimation()
            }
        }

        findViewById<TextView>(R.id.statusText).text = buildString {
            append(if (loggedIn) "Logged in as ${prefs.username}\n" else "")
            append(if (hasPermissions()) "Permissions: OK\n" else "Permissions: MISSING - tap the warning button above\n")
            append("Battery state: ${if (isIgnoringBattery) "Unrestricted" else "Optimized / Restricted"}\n")
            append(prefs.lastStatus)
            if (loggedIn && prefs.googleCallsOn && prefs.lastCallStatus.isNotEmpty()) append("\n${prefs.lastCallStatus}")
        }
    }
}
