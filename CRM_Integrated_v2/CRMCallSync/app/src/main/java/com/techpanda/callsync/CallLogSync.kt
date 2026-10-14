package com.techpanda.callsync

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.provider.CallLog
import android.telecom.TelecomManager
import androidx.core.content.ContextCompat
import org.json.JSONObject

/**
 * Google Ads call leads: reads new incoming / missed / rejected calls on the Google number
 * from the phone's call log and sends them to the CRM (/api/calls/ingest/).
 *
 * Runs inside SyncEngine BEFORE the recording upload, so the lead already exists when the
 * recording of that call arrives. Uses the same login token as the recording upload.
 * Safe to run every 30 seconds: only calls newer than the last accepted one are sent,
 * and the server also ignores duplicates.
 */
object CallLogSync {

    data class Sim(val accountId: String, val label: String)

    private const val BATCH_SIZE = 100
    private val WANTED_TYPES = setOf(
        CallLog.Calls.INCOMING_TYPE,
        CallLog.Calls.MISSED_TYPE,
        CallLog.Calls.REJECTED_TYPE,
    )

    fun hasPermission(ctx: Context) =
        ContextCompat.checkSelfPermission(ctx, Manifest.permission.READ_CALL_LOG) ==
            PackageManager.PERMISSION_GRANTED

    /**
     * Returns the number of calls the server saved, 0 if Google calls are off / nothing new.
     * Throws UnauthorizedException (login expired), SecurityException (permission removed)
     * or another Exception (no internet) - SyncEngine handles each.
     */
    fun sync(ctx: Context, prefs: Prefs, token: String): Int {
        if (!prefs.googleCallsOn) return 0
        if (!hasPermission(ctx)) throw SecurityException("READ_CALL_LOG not granted")

        val calls = readNewCalls(ctx, prefs.callLogSinceMs, prefs.googleSim)
        var saved = 0
        for (chunk in calls.chunked(BATCH_SIZE)) {
            saved += Api.ingestCalls(prefs.serverUrl, token, chunk)
            // Move the cursor only after the server accepted this chunk.
            prefs.callLogSinceMs = chunk.maxOf { it.getLong("timestamp_ms") }
        }
        return saved
    }

    private fun readNewCalls(ctx: Context, sinceMs: Long, googleSim: String): List<JSONObject> {
        val projection = arrayOf(
            CallLog.Calls.NUMBER,
            CallLog.Calls.TYPE,
            CallLog.Calls.DATE,
            CallLog.Calls.DURATION,
            CallLog.Calls.PHONE_ACCOUNT_ID,
            CallLog.Calls.CACHED_NAME,
        )
        val out = mutableListOf<JSONObject>()
        ctx.contentResolver.query(
            CallLog.Calls.CONTENT_URI, projection,
            "${CallLog.Calls.DATE} > ?", arrayOf(sinceMs.toString()),
            "${CallLog.Calls.DATE} ASC",
        )?.use { c ->
            val iNumber = c.getColumnIndexOrThrow(CallLog.Calls.NUMBER)
            val iType = c.getColumnIndexOrThrow(CallLog.Calls.TYPE)
            val iDate = c.getColumnIndexOrThrow(CallLog.Calls.DATE)
            val iDur = c.getColumnIndexOrThrow(CallLog.Calls.DURATION)
            val iAcc = c.getColumnIndexOrThrow(CallLog.Calls.PHONE_ACCOUNT_ID)
            val iName = c.getColumnIndexOrThrow(CallLog.Calls.CACHED_NAME)

            while (c.moveToNext()) {
                val type = c.getInt(iType)
                if (type !in WANTED_TYPES) continue
                val number = c.getString(iNumber)?.trim().orEmpty()
                if (number.isEmpty()) continue // private / hidden number
                val accountId = c.getString(iAcc)
                if (googleSim != "all" && accountId != googleSim) continue

                out += JSONObject()
                    .put("number", number)
                    .put("call_type", when (type) {
                        CallLog.Calls.MISSED_TYPE -> "missed"
                        CallLog.Calls.REJECTED_TYPE -> "rejected"
                        else -> "incoming"
                    })
                    .put("timestamp_ms", c.getLong(iDate))
                    .put("duration_sec", c.getLong(iDur))
                    .put("sim_account_id", accountId ?: JSONObject.NULL)
                    .put("contact_name", c.getString(iName) ?: JSONObject.NULL)
            }
        }
        return out
    }

    /**
     * SIMs for the "Google Ads number" picker. Uses the phone's SIM list (names like
     * "Jio" / "Airtel"); falls back to SIM ids seen in the recent call log.
     */
    fun listSims(ctx: Context): List<Sim> {
        val sims = linkedMapOf<String, String>()
        try {
            val telecom = ctx.getSystemService(TelecomManager::class.java)
            telecom?.callCapablePhoneAccounts?.forEachIndexed { i, handle ->
                val label = telecom.getPhoneAccount(handle)?.label?.toString()
                sims[handle.id] = "SIM ${i + 1}" + (label?.takeIf { it.isNotBlank() }?.let { " – $it" } ?: "")
            }
        } catch (e: SecurityException) {
            // READ_PHONE_STATE not granted yet - fall back to call log
        }
        if (hasPermission(ctx)) {
            try {
                ctx.contentResolver.query(
                    CallLog.Calls.CONTENT_URI,
                    arrayOf(CallLog.Calls.PHONE_ACCOUNT_ID, CallLog.Calls.NUMBER),
                    null, null, "${CallLog.Calls.DATE} DESC",
                )?.use { c ->
                    var rows = 0
                    while (c.moveToNext() && rows++ < 200) {
                        val id = c.getString(0) ?: continue
                        if (id !in sims) sims[id] = "SIM id $id (last call: ${c.getString(1) ?: "?"})"
                    }
                }
            } catch (e: Exception) {
                // Call log unreadable - the TelecomManager list is enough
            }
        }
        return sims.map { Sim(it.key, it.value) }
    }
}
