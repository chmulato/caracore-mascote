package br.com.caracore.pdv.sms;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * Recebe broadcast do PDV (via adb) quando um backup do banco é enviado para o celular.
 * Ação: {@link #ACTION_BACKUP_UPDATE}. Extras: "timestamp" (YYYY_MM_DD_HH_MM_SS), "status" (OK/ERRO).
 */
public class BackupUpdateReceiver extends BroadcastReceiver {

    public static final String ACTION_BACKUP_UPDATE = "br.com.caracore.pdv.sms.BACKUP_UPDATE";
    public static final String EXTRA_TIMESTAMP = "timestamp";
    public static final String EXTRA_STATUS = "status";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || !ACTION_BACKUP_UPDATE.equals(intent.getAction())) {
            return;
        }
        String timestamp = intent.getStringExtra(EXTRA_TIMESTAMP);
        String status = intent.getStringExtra(EXTRA_STATUS);
        SmsPreferences prefs = new SmsPreferences(context);
        prefs.setLastBackupTimestamp(timestamp);
        prefs.setLastBackupStatus(status != null && !status.isEmpty() ? status : "OK");
        PdvSmsLogger.i("BackupUpdateReceiver", "Backup recebido: " + timestamp + " status=" + status);
    }
}
