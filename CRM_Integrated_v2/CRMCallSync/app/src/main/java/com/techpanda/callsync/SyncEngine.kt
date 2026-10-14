package com.techpanda.callsync

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.withContext
import java.text.DateFormat
import java.util.Date

/**
 * Sync engine:
 *  1. Remote call dispatch: checks /api/calls/pending-dial/ (ultra-lightweight HTTP check)
 *  2. Google Ads calls from the call log -> /api/calls/ingest/ (creates the leads)
 *  3. New call recordings -> /api/call-recordings/upload/ (attached to those leads)
 */
object SyncEngine {

    enum class Outcome { OK, RETRY, LOGGED_OUT, NO_PERMISSION, BUSY }

    // Guard heavy filesystem and upload passes so only one runs at a time
    private val mutex = Mutex()

    /**
     * Ultra-lightweight check for remote outgoing call triggered from CRM laptop.
     * Only does a quick ~50ms HTTP GET, zero disk or database access.
     * Returns true if a call was placed.
     */
    suspend fun checkPendingDial(context: Context): Boolean {
        return withContext(Dispatchers.IO) {
            val ctx = context.applicationContext
            val prefs = Prefs(ctx)
            val token = prefs.token ?: return@withContext false
            try {
                val pendingCall = Api.fetchPendingDial(prefs.serverUrl, token) ?: return@withContext false
                val phone = pendingCall.optString("phone_number")
                if (phone.isBlank()) return@withContext false

                val cleanPhone = phone.replace(" ", "").replace("-", "")
                val hasCallPhonePermission = androidx.core.content.ContextCompat.checkSelfPermission(
                    ctx, android.Manifest.permission.CALL_PHONE
                ) == android.content.pm.PackageManager.PERMISSION_GRANTED

                val cleanDigits = cleanPhone.filter { it.isDigit() || it == '+' }
                val telUri = android.net.Uri.fromParts("tel", cleanDigits, null)

                val callId = pendingCall.optLong("call_id", 0L)
                if (callId > 0) {
                    prefs.activeOutgoingCallId = callId
                    prefs.activeOutgoingNumber = cleanDigits
                    prefs.activeOutgoingTimeMs = System.currentTimeMillis()
                    // Report DIALING state immediately to CRM
                    Api.reportCallState(prefs.serverUrl, token, callId, "DIALING")
                }

                if (hasCallPhonePermission) {
                    // AUTO CALL: Immediately places the phone call on the mobile device
                    val callIntent = android.content.Intent(android.content.Intent.ACTION_CALL, telUri).apply {
                        flags = android.content.Intent.FLAG_ACTIVITY_NEW_TASK
                    }
                    ctx.startActivity(callIntent)
                } else {
                    // Fallback: Open dial pad if CALL_PHONE permission not yet granted
                    val dialIntent = android.content.Intent(android.content.Intent.ACTION_DIAL, telUri).apply {
                        flags = android.content.Intent.FLAG_ACTIVITY_NEW_TASK
                    }
                    ctx.startActivity(dialIntent)
                }
                true
            } catch (e: Exception) {
                false
            }
        }
    }

    /**
     * Heavy pass: syncs call logs and audio recordings from disk/MediaStore and uploads them.
     */
    suspend fun syncRecordingsAndLogs(context: Context): Outcome {
        if (!mutex.tryLock()) return Outcome.BUSY
        try {
            return withContext(Dispatchers.IO) { runRecordingsAndLogs(context.applicationContext) }
        } finally {
            mutex.unlock()
        }
    }

    /**
     * Full sync pass (manual sync button in MainActivity, WorkManager, etc.).
     */
    suspend fun syncOnce(context: Context): Outcome {
        checkPendingDial(context)
        return syncRecordingsAndLogs(context)
    }

    private fun runRecordingsAndLogs(ctx: Context): Outcome {
        val prefs = Prefs(ctx)
        val token = prefs.token ?: return Outcome.LOGGED_OUT
        Api.appVersion = appVersion(ctx)
        Api.googleSim = prefs.googleSim
        val now = DateFormat.getTimeInstance().format(Date())

        // 1. Google Ads calls first, so the lead exists before its recording is uploaded.
        //    A failure here never blocks the recording upload below.
        if (prefs.googleCallsOn) {
            try {
                val saved = CallLogSync.sync(ctx, prefs, token)
                if (saved > 0) prefs.lastCallStatus = "Google calls: sent $saved at $now"
                else if (!prefs.lastCallStatus.startsWith("Google calls: sent"))
                    prefs.lastCallStatus = "Google calls: up to date ($now)"
            } catch (e: UnauthorizedException) {
                prefs.logout()
                prefs.lastStatus = "Login expired - please log in again"
                return Outcome.LOGGED_OUT
            } catch (e: SecurityException) {
                prefs.lastCallStatus = "Google calls: call log permission missing"
            } catch (e: Exception) {
                prefs.lastCallStatus = "Google calls: retrying (${e.message})"
            }
        }

        val recordings = try {
            val foundList = mutableListOf<Recording>()
            val seenNames = mutableSetOf<String>()

            // A. If a folder was picked manually, scan it directly via SAF first
            if (prefs.recordingFolderUri.isNotEmpty()) {
                val safRecs = RecordingScanner.findRecordingsInSafFolder(
                    ctx, prefs.recordingFolderUri, prefs.lastSyncedAddedSec
                )
                for (r in safRecs) {
                    if (seenNames.add(r.name)) {
                        foundList.add(r)
                    }
                }
            }

            // B. Also scan MediaStore (using custom relative path if picked, or auto-detect)
            val customPath: String? = prefs.recordingFolderUri
                .takeIf { it.isNotEmpty() }
                ?.let { uriStr ->
                    try {
                        val uri = android.net.Uri.parse(uriStr)
                        val lastSeg = uri.lastPathSegment ?: ""
                        val relative = lastSeg
                            .substringAfter(":")
                            .replace("%2F", "/")
                            .trimEnd('/') + "/"
                        relative.ifEmpty { null }
                    } catch (e: Exception) { null }
                }

            val msRecs = RecordingScanner.findNewRecordings(ctx, prefs.lastSyncedAddedSec, prefs.lastSyncedId, customPath)
            for (r in msRecs) {
                if (seenNames.add(r.name)) {
                    foundList.add(r)
                }
            }

            foundList.sortedWith(compareBy({ it.dateAddedSec }, { it.id }))
        } catch (e: SecurityException) {
            prefs.lastStatus = "Permission missing - open the app and allow access"
            return Outcome.NO_PERMISSION
        }

        var uploaded = 0
        for (rec in recordings) {
            val call = try {
                RecordingScanner.matchCall(ctx, rec)
            } catch (e: SecurityException) {
                null
            }
            try {
                Api.upload(
                    ctx.contentResolver, prefs.serverUrl, token, rec, call,
                    RecordingScanner.numberFromFileName(rec.name)
                )
                prefs.markUploaded(rec.dateAddedSec, rec.id)
                uploaded++
            } catch (e: UnauthorizedException) {
                prefs.logout()
                prefs.lastStatus = "Login expired - please log in again"
                return Outcome.LOGGED_OUT
            } catch (e: Exception) {
                // No internet / server down: stop here, next pass continues from this file.
                prefs.lastStatus = "Retrying: ${e.message}"
                return Outcome.RETRY
            }
        }

        prefs.lastStatus = if (uploaded > 0) {
            "Uploaded $uploaded recording(s) at $now".also { prefs.lastUploadStatus = it }
        } else {
            "Last checked $now" + (prefs.lastUploadStatus.takeIf { it.isNotEmpty() }?.let { "\n$it" } ?: "")
        }
        return Outcome.OK
    }

    private fun appVersion(ctx: Context): String = try {
        ctx.packageManager.getPackageInfo(ctx.packageName, 0).versionName ?: ""
    } catch (e: Exception) {
        ""
    }
}
