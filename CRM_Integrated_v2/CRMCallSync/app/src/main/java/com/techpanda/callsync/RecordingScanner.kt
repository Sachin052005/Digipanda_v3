package com.techpanda.callsync

import android.content.ContentUris
import android.content.Context
import android.net.Uri
import android.provider.CallLog
import android.provider.MediaStore
import kotlin.math.abs

data class Recording(
    val id: Long,
    val uri: Uri,
    val name: String,
    val size: Long,
    val dateAddedSec: Long,
    val durationMs: Long,
)

data class CallInfo(
    val number: String,
    val direction: String,   // "incoming" / "outgoing" / "unknown"
    val startMs: Long,
    val durationSec: Long,
)

object RecordingScanner {

    /**
     * Auto-detect fallback: used when the user has NOT picked a folder manually.
     * Matches any MediaStore RELATIVE_PATH containing common audio recording keywords.
     * Covers:
     *   Samsung: Recordings/Call/
     *   Xiaomi:  MIUI/sound_recorder/call_rec/
     *   Vivo/Oppo/Realme: Recordings/Call Recordings/ or PhoneRecord/
     *   Google Pixel: Recordings/Call recordings/
     *   OnePlus/Others: Recordings/, Record/, SoundRecorder/, Voice/
     */
    private val FOLDER_PATTERNS = listOf(
        "%call%", "%record%", "%sound_recorder%", "%voice%", "%phone%"
    )

    /**
     * Direct SAF folder scanner: queries the folder picked by the user via DocumentsContract.
     * Works directly on the filesystem independently of MediaStore indexing,
     * ensuring newly saved audio files are detected instantly.
     */
    fun findRecordingsInSafFolder(context: Context, treeUriStr: String, sinceAddedSec: Long): List<Recording> {
        val results = mutableListOf<Recording>()
        val audioExtensions = setOf("mp3", "m4a", "aac", "amr", "awb", "wav", "ogg", "opus", "3gp", "3gpp", "mp4", "flac")
        try {
            val treeUri = android.net.Uri.parse(treeUriStr)
            val docId = android.provider.DocumentsContract.getTreeDocumentId(treeUri)
            val childrenUri = android.provider.DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, docId)
            val projection = arrayOf(
                android.provider.DocumentsContract.Document.COLUMN_DOCUMENT_ID,
                android.provider.DocumentsContract.Document.COLUMN_DISPLAY_NAME,
                android.provider.DocumentsContract.Document.COLUMN_SIZE,
                android.provider.DocumentsContract.Document.COLUMN_LAST_MODIFIED,
                android.provider.DocumentsContract.Document.COLUMN_MIME_TYPE,
            )

            context.contentResolver.query(childrenUri, projection, null, null, null)?.use { cursor ->
                val idCol = cursor.getColumnIndexOrThrow(android.provider.DocumentsContract.Document.COLUMN_DOCUMENT_ID)
                val nameCol = cursor.getColumnIndexOrThrow(android.provider.DocumentsContract.Document.COLUMN_DISPLAY_NAME)
                val sizeCol = cursor.getColumnIndexOrThrow(android.provider.DocumentsContract.Document.COLUMN_SIZE)
                val modCol = cursor.getColumnIndexOrThrow(android.provider.DocumentsContract.Document.COLUMN_LAST_MODIFIED)
                val mimeCol = cursor.getColumnIndexOrThrow(android.provider.DocumentsContract.Document.COLUMN_MIME_TYPE)

                while (cursor.moveToNext()) {
                    val documentId = cursor.getString(idCol)
                    val name = cursor.getString(nameCol) ?: continue
                    val ext = name.substringAfterLast('.', "").lowercase()
                    val mime = cursor.getString(mimeCol) ?: ""
                    val isAudio = mime.startsWith("audio/") || ext in audioExtensions
                    if (!isAudio) continue

                    val size = cursor.getLong(sizeCol)
                    val modMs = cursor.getLong(modCol)
                    val modSec = if (modMs > 0) modMs / 1000 else System.currentTimeMillis() / 1000

                    if (modSec <= sinceAddedSec) continue

                    val fileUri = android.provider.DocumentsContract.buildDocumentUriUsingTree(treeUri, documentId)
                    val stableId = (documentId.hashCode().toLong() and 0x7FFFFFFF)
                    results.add(
                        Recording(
                            id = stableId,
                            uri = fileUri,
                            name = name,
                            size = size,
                            dateAddedSec = modSec,
                            durationMs = 0L,
                        )
                    )
                }
            }
        } catch (e: Exception) {
            // Silently fallback if SAF provider query fails
        }
        return results.sortedBy { it.dateAddedSec }
    }

    /**
     * Finds audio files in the given folder (user-picked) or, if null, falls back to
     * any folder whose name contains "call" (the original auto-detect behaviour).
     *
     * [folderRelativePath] is the RELATIVE_PATH value from MediaStore, e.g.
     * "Recordings/Call/" — derived from the SAF tree URI chosen by the user.
     */
    fun findNewRecordings(
        context: Context,
        sinceAddedSec: Long,
        sinceId: Long,
        folderRelativePath: String? = null,
    ): List<Recording> {
        val collection = MediaStore.Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL)
        val projection = arrayOf(
            MediaStore.Audio.Media._ID,
            MediaStore.Audio.Media.DISPLAY_NAME,
            MediaStore.Audio.Media.SIZE,
            MediaStore.Audio.Media.DATE_ADDED,
            MediaStore.Audio.Media.DURATION,
            MediaStore.Audio.Media.RELATIVE_PATH,
        )

        val added = MediaStore.Audio.Media.DATE_ADDED
        val idCol0 = MediaStore.Audio.Media._ID
        val relPath = MediaStore.Audio.Media.RELATIVE_PATH

        // Build the folder clause: exact match when the user picked a folder, wildcard otherwise.
        val folderClause: String
        val folderArgs: List<String>
        if (folderRelativePath != null) {
            // Exact folder + subfolders (LIKE 'Recordings/Call/%' covers any sub-folder too)
            folderClause = "($relPath = ? OR $relPath LIKE ?)"
            folderArgs = listOf(folderRelativePath, "$folderRelativePath%")
        } else {
            // Auto-detect: any folder whose path contains the word "call"
            folderClause = FOLDER_PATTERNS.joinToString(" OR ") { "$relPath LIKE ?" }
            folderArgs = FOLDER_PATTERNS
        }

        val selection = "($folderClause) AND ($added > ? OR ($added = ? AND $idCol0 > ?))"
        val args = (folderArgs + listOf(
            sinceAddedSec.toString(), sinceAddedSec.toString(), sinceId.toString()
        )).toTypedArray()

        val result = mutableListOf<Recording>()
        context.contentResolver.query(
            collection, projection, selection, args,
            "$added ASC, $idCol0 ASC"
        )?.use { c ->
            val idCol   = c.getColumnIndexOrThrow(MediaStore.Audio.Media._ID)
            val nameCol = c.getColumnIndexOrThrow(MediaStore.Audio.Media.DISPLAY_NAME)
            val sizeCol = c.getColumnIndexOrThrow(MediaStore.Audio.Media.SIZE)
            val addedCol= c.getColumnIndexOrThrow(MediaStore.Audio.Media.DATE_ADDED)
            val durCol  = c.getColumnIndexOrThrow(MediaStore.Audio.Media.DURATION)
            while (c.moveToNext()) {
                val id = c.getLong(idCol)
                result += Recording(
                    id           = id,
                    uri          = ContentUris.withAppendedId(collection, id),
                    name         = c.getString(nameCol) ?: "recording_$id",
                    size         = c.getLong(sizeCol),
                    dateAddedSec = c.getLong(addedCol),
                    durationMs   = c.getLong(durCol),
                )
            }
        }
        return result
    }


    /**
     * Matches a recording to the call-log entry it most likely belongs to.
     * Recorders save the file either when the call starts or when it ends,
     * so we pick the call whose start OR end time is closest to the file time.
     */
    fun matchCall(context: Context, rec: Recording): CallInfo? {
        val fileMs = rec.dateAddedSec * 1000
        val windowMs = rec.durationMs + 10 * 60 * 1000L // call length + 10 min slack
        val projection = arrayOf(
            CallLog.Calls.NUMBER, CallLog.Calls.TYPE, CallLog.Calls.DATE, CallLog.Calls.DURATION
        )
        val selection = "${CallLog.Calls.DATE} BETWEEN ? AND ?"
        val args = arrayOf((fileMs - windowMs).toString(), (fileMs + 2 * 60 * 1000L).toString())

        var best: CallInfo? = null
        var bestGap = Long.MAX_VALUE
        context.contentResolver.query(
            CallLog.Calls.CONTENT_URI, projection, selection, args, "${CallLog.Calls.DATE} DESC"
        )?.use { c ->
            while (c.moveToNext()) {
                val type = c.getInt(1)
                if (type == CallLog.Calls.MISSED_TYPE || type == CallLog.Calls.REJECTED_TYPE) continue
                val start = c.getLong(2)
                val durSec = c.getLong(3)
                val end = start + durSec * 1000
                val gap = minOf(abs(fileMs - start), abs(fileMs - end))
                if (gap < bestGap) {
                    bestGap = gap
                    best = CallInfo(
                        number = c.getString(0) ?: "",
                        direction = when (type) {
                            CallLog.Calls.INCOMING_TYPE -> "incoming"
                            CallLog.Calls.OUTGOING_TYPE -> "outgoing"
                            else -> "unknown"
                        },
                        startMs = start,
                        durationSec = durSec,
                    )
                }
            }
        }
        return best
    }

    /** Fallback: many recorders put the number in the file name, e.g. "Call_+919876543210_2026..." */
    fun numberFromFileName(name: String): String {
        val m = Regex("""\+?\d[\d\s-]{8,14}\d""").find(name) ?: return ""
        val digits = m.value.filter { it.isDigit() }
        // Ignore long date-time stamps like 20261009103045
        return if (digits.length in 10..13 && !digits.startsWith("20")) digits else ""
    }
}
