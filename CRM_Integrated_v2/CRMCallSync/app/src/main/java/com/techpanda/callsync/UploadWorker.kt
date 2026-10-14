package com.techpanda.callsync

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import java.util.concurrent.TimeUnit

/**
 * Backup only: if the phone ever kills SyncService, this still syncs every 15 minutes.
 * The 30-second checking is done by SyncService.
 */
class UploadWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {

    override suspend fun doWork(): Result = when (SyncEngine.syncOnce(applicationContext)) {
        SyncEngine.Outcome.OK, SyncEngine.Outcome.BUSY -> Result.success()
        SyncEngine.Outcome.RETRY -> Result.retry()
        SyncEngine.Outcome.LOGGED_OUT, SyncEngine.Outcome.NO_PERMISSION -> Result.failure()
    }

    companion object {
        fun schedulePeriodic(context: Context) {
            val req = PeriodicWorkRequestBuilder<UploadWorker>(15, TimeUnit.MINUTES)
                .setConstraints(
                    Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()
                )
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                "call-sync-periodic", ExistingPeriodicWorkPolicy.KEEP, req
            )
        }

        fun cancelAll(context: Context) {
            WorkManager.getInstance(context).cancelAllWork()
        }
    }
}
