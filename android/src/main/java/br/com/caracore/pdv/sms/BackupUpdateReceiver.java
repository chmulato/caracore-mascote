package br.com.caracore.pdv.sms;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/**
 * Recebe do PDV, por broadcast via adb, o resultado do backup do banco.
 * Só aceita o aviso com o token mostrado no cartão de backup do app.
 * Extras: "token", "timestamp" (YYYY_MM_DD_HH_MM_SS), "status" (OK/ERRO).
 */
public class BackupUpdateReceiver extends BroadcastReceiver {

    public static final String ACTION_BACKUP_UPDATE = "br.com.caracore.pdv.sms.BACKUP_UPDATE";
    public static final String EXTRA_TOKEN = "token";
    public static final String EXTRA_TIMESTAMP = "timestamp";
    public static final String EXTRA_STATUS = "status";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || !ACTION_BACKUP_UPDATE.equals(intent.getAction())) {
            return;
        }
        SmsPreferences prefs = new SmsPreferences(context);
        if (!BackupToken.confere(intent.getStringExtra(EXTRA_TOKEN), prefs.getBackupToken())) {
            PdvSmsLogger.i("BackupUpdateReceiver", "Aviso de backup recusado: token ausente ou invalido.");
            return;
        }
        String timestamp = intent.getStringExtra(EXTRA_TIMESTAMP);
        String status = intent.getStringExtra(EXTRA_STATUS);
        prefs.setLastBackupTimestamp(timestamp);
        prefs.setLastBackupStatus(status != null && !status.isEmpty() ? status : "OK");
        PdvSmsLogger.i("BackupUpdateReceiver", "Backup recebido: " + timestamp + " status=" + status);
    }
}
