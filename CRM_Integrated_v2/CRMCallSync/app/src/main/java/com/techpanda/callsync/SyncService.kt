package com.techpanda.callsync

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.database.ContentObserver
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.provider.MediaStore
import android.telephony.PhoneStateListener
import android.telephony.TelephonyCallback
import android.telephony.TelephonyManager
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Battery-efficient, cool-running foreground sync service:
 *  1. Remote Call Dispatcher: ultra-lightweight HTTP check with adaptive sleep:
 *     - Screen ON: 4 seconds (snappy responsiveness when telecaller is working)
 *     - Screen OFF: 15 seconds (prevents modem/CPU heating in pocket/idle)
 *     - Battery Saver: 30 seconds
 *     - During Active Call: paused (no need to poll when already speaking)
 *  2. File & Call Log Sync:
 *     - Event-driven: MediaStore audio observer triggers ~2s after new audio file is saved
 *     - Call-ended: triggers immediately when phone hangs up
 *     - Periodic safety net: runs calmly every 60s (screen on) or 120s (screen off),
 *       completely eliminating continuous SAF and CallLog disk churning.
 */
class SyncService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var quickSyncJob: Job? = null
    private var afterCallJob: Job? = null
    private var callListener: Any? = null
    private var lastCallState = TelephonyManager.CALL_STATE_IDLE
    private var lastNotificationText: String? = null

    private val audioObserver = object : ContentObserver(Handler(Looper.getMainLooper())) {
        override fun onChange(selfChange: Boolean) {
            quickSyncJob?.cancel()
            quickSyncJob = scope.launch {
                delay(QUICK_SYNC_DELAY_MS)
                withWakeLock("callsync:newfile", 25_000L) { runRecordingsSync() }
            }
        }
    }

    override fun onCreate() {
        super.onCreate()
        startInForeground()
        contentResolver.registerContentObserver(
            MediaStore.Audio.Media.EXTERNAL_CONTENT_URI, true, audioObserver
        )
        listenForCallEnd()

        // 1. Adaptive remote dial polling loop
        scope.launch {
            while (isActive) {
                val delayMs = try {
                    val pm = getSystemService(PowerManager::class.java)
                    val isScreenOn = pm?.isInteractive ?: true
                    val isPowerSave = pm?.isPowerSaveMode ?: false
                    val isCallActive = lastCallState != TelephonyManager.CALL_STATE_IDLE

                    when {
                        isCallActive -> 10_000L
                        isPowerSave -> 30_000L
                        !isScreenOn -> 15_000L
                        else -> 4_000L
                    }
                } catch (e: Exception) {
                    10_000L
                }

                try {
                    SyncEngine.checkPendingDial(applicationContext)
                } catch (e: Exception) {
                    // Ignore non-blocking remote dial errors
                }
                delay(delayMs)
            }
        }

        // 2. Calm periodic safety sync loop (no more 2-second disk/SAF thrashing)
        scope.launch {
            delay(2_000L)
            runRecordingsSync()

            while (isActive) {
                val pm = getSystemService(PowerManager::class.java)
                val isScreenOn = pm?.isInteractive ?: true
                val syncDelay = if (isScreenOn) 60_000L else 120_000L
                delay(syncDelay)
                runRecordingsSync()
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        listenForCallEnd()
        return START_STICKY
    }

    override fun onDestroy() {
        contentResolver.unregisterContentObserver(audioObserver)
        stopListeningForCalls()
        scope.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    // ---------- sync ----------

    private suspend fun runRecordingsSync(): SyncEngine.Outcome {
        val outcome = SyncEngine.syncRecordingsAndLogs(applicationContext)
        if (outcome == SyncEngine.Outcome.LOGGED_OUT) {
            stopSelf()
        } else if (outcome != SyncEngine.Outcome.BUSY) {
            val status = Prefs(this).lastStatus
            if (status != lastNotificationText) {
                lastNotificationText = status
                updateNotification(status)
            }
        }
        return outcome
    }

    /** Called when a call ends: retry with quick backoff until the new recording is uploaded. */
    private fun syncAfterCall() {
        afterCallJob?.cancel()
        afterCallJob = scope.launch {
            val prefs = Prefs(this@SyncService)
            val before = prefs.lastSyncedAddedSec to prefs.lastSyncedId
            for (wait in AFTER_CALL_RETRY_DELAYS_MS) {
                delay(wait)
                val outcome = withWakeLock("callsync:aftercall", 20_000L) {
                    runRecordingsSync()
                }
                if (outcome == SyncEngine.Outcome.LOGGED_OUT) break
                if ((prefs.lastSyncedAddedSec to prefs.lastSyncedId) != before) break // uploaded
            }
        }
    }

    private suspend fun <T> withWakeLock(tag: String, timeoutMs: Long, block: suspend () -> T): T {
        val pm = getSystemService(PowerManager::class.java)
        val wl = pm?.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, tag)
        wl?.acquire(timeoutMs)
        return try {
            block()
        } finally {
            if (wl?.isHeld == true) wl.release()
        }
    }

    // ---------- call-end detection ----------

    private fun onCallState(state: Int) {
        if (state == TelephonyManager.CALL_STATE_IDLE && lastCallState != TelephonyManager.CALL_STATE_IDLE) {
            checkAndReportActiveCallEnded()
            syncAfterCall()
        }
        lastCallState = state
    }

    /**
     * When a call enters CALL_STATE_IDLE, check if there was an active outgoing call dialed from CRM.
     * Query CallLog to find its exact duration and final status (COMPLETED vs NO_ANSWER).
     */
    private fun checkAndReportActiveCallEnded() {
        val prefs = Prefs(this)
        val activeCallId = prefs.activeOutgoingCallId
        if (activeCallId <= 0) return

        val token = prefs.token ?: return
        val serverUrl = prefs.serverUrl
        val dialedTimeMs = prefs.activeOutgoingTimeMs

        scope.launch {
            // Delay to let Android finish writing the call log entry
            delay(1200L)
            var foundDuration = 0L
            var isAnswered = false

            if (ContextCompat.checkSelfPermission(this@SyncService, Manifest.permission.READ_CALL_LOG)
                == PackageManager.PERMISSION_GRANTED
            ) {
                try {
                    val projection = arrayOf(
                        android.provider.CallLog.Calls.NUMBER,
                        android.provider.CallLog.Calls.TYPE,
                        android.provider.CallLog.Calls.DATE,
                        android.provider.CallLog.Calls.DURATION
                    )
                    val sinceMs = if (dialedTimeMs > 0) dialedTimeMs - 30_000L else System.currentTimeMillis() - 180_000L
                    val selection = "${android.provider.CallLog.Calls.DATE} >= ? AND ${android.provider.CallLog.Calls.TYPE} = ?"
                    val args = arrayOf(sinceMs.toString(), android.provider.CallLog.Calls.OUTGOING_TYPE.toString())

                    contentResolver.query(
                        android.provider.CallLog.Calls.CONTENT_URI,
                        projection,
                        selection,
                        args,
                        "${android.provider.CallLog.Calls.DATE} DESC"
                    )?.use { cursor ->
                        if (cursor.moveToFirst()) {
                            val dur = cursor.getLong(3)
                            foundDuration = dur
                            if (dur > 0) {
                                isAnswered = true
                            }
                        }
                    }
                } catch (e: Exception) {
                    // Ignore call log read error
                }
            }

            val finalState = if (isAnswered) "COMPLETED" else "NO_ANSWER"
            try {
                Api.reportCallState(
                    serverUrl = serverUrl,
                    token = token,
                    callId = activeCallId,
                    state = finalState,
                    durationSeconds = foundDuration
                )
            } catch (e: Exception) {
                // Ignore reporting error
            } finally {
                prefs.clearActiveOutgoingCall()
            }
        }
    }

    private fun listenForCallEnd() {
        if (callListener != null) return
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_PHONE_STATE)
            != PackageManager.PERMISSION_GRANTED
        ) return

        val tm = getSystemService(TelephonyManager::class.java) ?: return
        try {
            if (Build.VERSION.SDK_INT >= 31) {
                val cb = object : TelephonyCallback(), TelephonyCallback.CallStateListener {
                    override fun onCallStateChanged(state: Int) = onCallState(state)
                }
                tm.registerTelephonyCallback(mainExecutor, cb)
                callListener = cb
            } else {
                @Suppress("DEPRECATION")
                val listener = object : PhoneStateListener() {
                    @Deprecated("Deprecated in Java")
                    override fun onCallStateChanged(state: Int, phoneNumber: String?) = onCallState(state)
                }
                @Suppress("DEPRECATION")
                tm.listen(listener, PhoneStateListener.LISTEN_CALL_STATE)
                callListener = listener
            }
        } catch (e: SecurityException) {
            callListener = null
        }
    }

    private fun stopListeningForCalls() {
        val tm = getSystemService(TelephonyManager::class.java) ?: return
        val l = callListener ?: return
        if (Build.VERSION.SDK_INT >= 31 && l is TelephonyCallback) {
            tm.unregisterTelephonyCallback(l)
        } else if (l is PhoneStateListener) {
            @Suppress("DEPRECATION")
            tm.listen(l, PhoneStateListener.LISTEN_NONE)
        }
        callListener = null
    }

    // ---------- notification ----------

    private fun buildNotification(text: String): Notification {
        val openApp = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_sys_upload_done)
            .setContentTitle("CRM call sync is on")
            .setContentText(text.lineSequence().firstOrNull() ?: text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(openApp)
            .build()
    }

    private fun updateNotification(text: String) {
        getSystemService(NotificationManager::class.java)?.notify(NOTIFICATION_ID, buildNotification(text))
    }

    private fun startInForeground() {
        getSystemService(NotificationManager::class.java)?.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "Call sync", NotificationManager.IMPORTANCE_LOW)
        )
        val notification = buildNotification("Waiting for calls")
        if (Build.VERSION.SDK_INT >= 34) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    companion object {
        private const val QUICK_SYNC_DELAY_MS = 2_000L
        /** After a call ends: retry at +1s, +2s, +4s, +8s, +15s. */
        private val AFTER_CALL_RETRY_DELAYS_MS = listOf(1_000L, 2_000L, 4_000L, 8_000L, 15_000L)
        private const val CHANNEL_ID = "call_sync"
        private const val NOTIFICATION_ID = 1

        fun start(context: Context) {
            ContextCompat.startForegroundService(context, Intent(context, SyncService::class.java))
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, SyncService::class.java))
        }
    }
}
