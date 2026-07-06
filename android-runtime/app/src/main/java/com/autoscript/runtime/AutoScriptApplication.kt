package com.autoscript.runtime

import android.app.Application
import com.autoscript.core.update.UpdateServer

class AutoScriptApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        UpdateServer.init(BuildConfig.JIAOBEN_API_BASE, BuildConfig.APPLICATION_ID)
    }
}
