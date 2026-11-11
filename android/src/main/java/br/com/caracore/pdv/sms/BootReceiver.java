package br.com.caracore.pdv.sms;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

import androidx.core.content.ContextCompat;

/** Religa o gateway Wi-Fi depois que o celular reinicia. */
public class BootReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || !Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            return;
        }
        SmsPreferences prefs = new SmsPreferences(context);
        String secret = prefs.getGatewaySharedSecret();
        if (secret == null || secret.isEmpty() || !prefs.isAtivo()) {
            return;
        }
        try {
            ContextCompat.startForegroundService(context, new Intent(context, GatewayListenerService.class));
            PdvSmsLogger.i("BootReceiver", "Gateway religado apos reiniciar o celular.");
        } catch (Exception e) {
            PdvSmsLogger.i("BootReceiver", "boot: " + e.getMessage());
        }
    }
}
