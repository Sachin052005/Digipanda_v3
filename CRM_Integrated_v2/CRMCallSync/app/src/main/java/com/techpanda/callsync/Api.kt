package com.techpanda.callsync

import android.content.ContentResolver
import android.net.Uri
import okhttp3.FormBody
import okhttp3.MediaType
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okio.BufferedSink
import okio.source
import org.json.JSONArray
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import java.util.concurrent.TimeUnit

class UnauthorizedException : Exception("Login expired")

object Api {
    /** Sent with every request so the CRM admin can see app version + Google SIM setting per phone. */
    var appVersion: String = ""
    var googleSim: String = ""

    private fun Request.Builder.meta(): Request.Builder =
        header("X-App-Version", ascii(appVersion)).header("X-Google-Sim", ascii(googleSim))

    /** OkHttp rejects non-ASCII header values. */
    private fun ascii(v: String) = v.filter { it in ' '..'~' }.take(100)

    private fun errorText(code: Int, body: String): String {
        val msg = try { JSONObject(body).optString("error") } catch (e: Exception) { "" }
        return msg.ifBlank { "HTTP $code" }
    }

    private val client = OkHttpClient.Builder()
        .connectTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(5, TimeUnit.MINUTES)
        .readTimeout(2, TimeUnit.MINUTES)
        .build()

    /** Returns the auth token, or throws with the server's message. */
    fun login(serverUrl: String, username: String, password: String): String {
        val body = FormBody.Builder()
            .add("username", username)
            .add("password", password)
            .build()
        val req = Request.Builder().url("$serverUrl/api/auth/token/").meta().post(body).build()
        client.newCall(req).execute().use { resp ->
            val text = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) throw Exception("Login failed: ${errorText(resp.code, text)}")
            return JSONObject(text).getString("token")
        }
    }

    fun upload(
        resolver: ContentResolver,
        serverUrl: String,
        token: String,
        rec: Recording,
        call: CallInfo?,
        fallbackNumber: String,
    ) {
        val mime = (resolver.getType(rec.uri) ?: "audio/mpeg").toMediaTypeOrNull()
        val iso = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)
            .apply { timeZone = TimeZone.getTimeZone("UTC") }

        val form = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("audio_file", rec.name, UriRequestBody(resolver, rec.uri, mime, rec.size))
            .addFormDataPart("device_file_id", rec.id.toString())
            .addFormDataPart("phone_number", call?.number?.ifBlank { null } ?: fallbackNumber)
            .addFormDataPart("direction", call?.direction ?: "unknown")
            .addFormDataPart("duration_seconds", (call?.durationSec ?: (rec.durationMs / 1000)).toString())
        call?.let { form.addFormDataPart("call_started_at", iso.format(Date(it.startMs))) }

        val req = Request.Builder()
            .url("$serverUrl/api/call-recordings/upload/")
            .header("Authorization", "Token $token")
            .meta()
            .post(form.build())
            .build()
        client.newCall(req).execute().use { resp ->
            // Only 401 means "log in again". A 403 can come from a proxy / firewall: retry later.
            if (resp.code == 401) throw UnauthorizedException()
            if (resp.code == 400) {
                // Bad file (e.g. unsupported type) - skip it rather than retry forever
                return
            }
            if (!resp.isSuccessful) throw Exception("Upload failed (${resp.code})")
        }
    }

    /**
     * Sends Google-number calls from the call log to /api/calls/ingest/.
     * Returns how many the server saved (new). Throws on network / server errors.
     */
    fun ingestCalls(serverUrl: String, token: String, calls: List<JSONObject>): Int {
        val body = JSONObject().put("calls", JSONArray(calls)).toString()
            .toRequestBody("application/json".toMediaType())
        val req = Request.Builder()
            .url("$serverUrl/api/calls/ingest/")
            .header("Authorization", "Token $token")
            .meta()
            .post(body)
            .build()
        client.newCall(req).execute().use { resp ->
            if (resp.code == 401) throw UnauthorizedException()
            val text = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) throw Exception("Call sync failed: ${errorText(resp.code, text)}")
            return try { JSONObject(text).optInt("created", 0) } catch (e: Exception) { 0 }
        }
    }

    /** Checks for pending outgoing calls queued from laptop CRM */
    fun fetchPendingDial(serverUrl: String, token: String): JSONObject? {
        val req = Request.Builder()
            .url("$serverUrl/api/calls/pending-dial/")
            .header("Authorization", "Token $token")
            .meta()
            .get()
            .build()
        client.newCall(req).execute().use { resp ->
            if (resp.code == 401) throw UnauthorizedException()
            if (!resp.isSuccessful) return null
            val text = resp.body?.string().orEmpty()
            val json = try { JSONObject(text) } catch (e: Exception) { null }
            return if (json?.optBoolean("has_call") == true) json else null
        }
    }

    /** Reports real-time call states (DIALING, IN_PROGRESS, COMPLETED, NO_ANSWER, etc.) to CRM */
    fun reportCallState(
        serverUrl: String,
        token: String,
        callId: Long,
        state: String,
        durationSeconds: Long = 0,
        timestampIso: String? = null
    ): Boolean {
        val payload = JSONObject().apply {
            put("call_id", callId)
            put("state", state)
            put("duration_seconds", durationSeconds)
            if (timestampIso != null) {
                put("timestamp", timestampIso)
            }
        }
        val body = payload.toString().toRequestBody("application/json".toMediaType())
        val req = Request.Builder()
            .url("$serverUrl/api/calls/report-state/")
            .header("Authorization", "Token $token")
            .meta()
            .post(body)
            .build()
        return try {
            client.newCall(req).execute().use { resp ->
                if (resp.code == 401) throw UnauthorizedException()
                resp.isSuccessful
            }
        } catch (e: UnauthorizedException) {
            throw e
        } catch (e: Exception) {
            false
        }
    }

    private class UriRequestBody(
        private val resolver: ContentResolver,
        private val uri: Uri,
        private val type: MediaType?,
        private val length: Long,
    ) : RequestBody() {
        override fun contentType() = type
        override fun contentLength() = if (length > 0) length else -1
        override fun writeTo(sink: BufferedSink) {
            resolver.openInputStream(uri)?.source()?.use { sink.writeAll(it) }
                ?: throw Exception("Cannot open $uri")
        }
    }
}
