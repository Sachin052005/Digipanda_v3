package com.techpanda.callsync

import android.content.Context

class Prefs(context: Context) {
    companion object {
        const val DEFAULT_SERVER_URL = "https://digipandacrm.in/"
    }

    private val sp = context.getSharedPreferences("callsync", Context.MODE_PRIVATE)

    var serverUrl: String
        get() = DEFAULT_SERVER_URL.trimEnd('/')
        set(v) = sp.edit().putString("server_url", v.trimEnd('/')).apply()

    var token: String?
        get() = sp.getString("token", null)
        set(v) = sp.edit().putString("token", v).apply()

    var username: String
        get() = sp.getString("username", "") ?: ""
        set(v) = sp.edit().putString("username", v).apply()

    /** DATE_ADDED (seconds) of the last recording uploaded. Only newer files are synced. */
    var lastSyncedAddedSec: Long
        get() = sp.getLong("last_synced_added", 0L)
        set(v) = sp.edit().putLong("last_synced_added", v).apply()

    /**
     * MediaStore _ID of the last recording uploaded. Together with lastSyncedAddedSec it marks the
     * exact position reached, so the newest file is not uploaded again on every 30-second pass.
     */
    var lastSyncedId: Long
        get() = sp.getLong("last_synced_id", 0L)
        set(v) = sp.edit().putLong("last_synced_id", v).apply()

    fun markUploaded(addedSec: Long, id: Long) {
        sp.edit().putLong("last_synced_added", addedSec).putLong("last_synced_id", id).apply()
    }

    var lastStatus: String
        get() = sp.getString("last_status", "Not synced yet") ?: ""
        set(v) = sp.edit().putString("last_status", v).apply()

    var lastUploadStatus: String
        get() = sp.getString("last_upload_status", "") ?: ""
        set(v) = sp.edit().putString("last_upload_status", v).apply()

    /**
     * Google Ads number on this phone:
     *   ""    = off (this phone does not receive Google Ads calls)
     *   "all" = every incoming call on this phone is a Google call (dedicated phone / single SIM)
     *   else  = PHONE_ACCOUNT_ID of the Google SIM on a dual-SIM phone
     */
    var googleSim: String
        get() = sp.getString("google_sim", "") ?: ""
        set(v) = sp.edit().putString("google_sim", v).apply()

    var googleSimLabel: String
        get() = sp.getString("google_sim_label", "") ?: ""
        set(v) = sp.edit().putString("google_sim_label", v).apply()

    /** Call-log DATE (ms) of the last call sent to the CRM. Only newer calls are sent. */
    var callLogSinceMs: Long
        get() = sp.getLong("call_log_since_ms", 0L)
        set(v) = sp.edit().putLong("call_log_since_ms", v).apply()

    var lastCallStatus: String
        get() = sp.getString("last_call_status", "") ?: ""
        set(v) = sp.edit().putString("last_call_status", v).apply()

    val googleCallsOn: Boolean get() = googleSim.isNotEmpty()

    /**
     * The SAF tree URI string of the folder the user picked via the folder picker.
     * Empty = not set, fall back to the default %call% MediaStore pattern.
     */
    var recordingFolderUri: String
        get() = sp.getString("recording_folder_uri", "") ?: ""
        set(v) = sp.edit().putString("recording_folder_uri", v).apply()

    /** Human-readable folder path shown in the UI button label. */
    var recordingFolderName: String
        get() = sp.getString("recording_folder_name", "") ?: ""
        set(v) = sp.edit().putString("recording_folder_name", v).apply()

    /** Active remote outgoing call ID currently being handled */
    var activeOutgoingCallId: Long
        get() = sp.getLong("active_outgoing_call_id", 0L)
        set(v) = sp.edit().putLong("active_outgoing_call_id", v).apply()

    /** Phone number of the active outgoing call */
    var activeOutgoingNumber: String
        get() = sp.getString("active_outgoing_number", "") ?: ""
        set(v) = sp.edit().putString("active_outgoing_number", v).apply()

    /** Timestamp in ms when the active outgoing call was dialed */
    var activeOutgoingTimeMs: Long
        get() = sp.getLong("active_outgoing_time_ms", 0L)
        set(v) = sp.edit().putLong("active_outgoing_time_ms", v).apply()

    fun clearActiveOutgoingCall() {
        sp.edit()
            .remove("active_outgoing_call_id")
            .remove("active_outgoing_number")
            .remove("active_outgoing_time_ms")
            .apply()
    }

    fun logout() {
        sp.edit().remove("token").apply()
    }
}
