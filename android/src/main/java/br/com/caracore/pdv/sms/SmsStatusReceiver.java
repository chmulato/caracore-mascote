package br.com.caracore.pdv.sms;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.telephony.SmsManager;

/**
 * Recebe o resultado do rádio (SMS_SENT) e o comprovante da operadora
 * (SMS_DELIVERED) e repassa ao Gaspar pelo endpoint de recibo.
 */
public class SmsStatusReceiver extends BroadcastReceiver {

    public static final String ACTION_SENT = "br.com.caracore.pdv.sms.SMS_SENT";
    public static final String ACTION_DELIVERED = "br.com.caracore.pdv.sms.SMS_DELIVERED";
    public static final String EXTRA_ID = "id";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null) {
            return;
        }
        String action = intent.getAction();
        boolean isSent = ACTION_SENT.equals(action);
        boolean isDelivered = ACTION_DELIVERED.equals(action);
        if (!isSent && !isDelivered) {
            return;
        }
        String id = intent.getStringExtra(EXTRA_ID);
        if (id == null || id.isEmpty()) {
            return;
        }

        final String status;
        final String detail;
        if (isSent) {
            if (getResultCode() == Activity.RESULT_OK) {
                status = "sent";
                detail = "aceito pela operadora";
            } else {
                status = "failed";
                detail = describe(getResultCode());
            }
        } else if (getResultCode() == Activity.RESULT_OK) {
            status = "delivered";
            detail = "entregue ao cliente";
        } else {
            status = "sent";
            detail = "operadora nao confirmou a entrega";
        }

        final PendingResult pending = goAsync();
        final Context app = context.getApplicationContext();
        new Thread(() -> {
            try {
                SmsReceiptSender.send(app, id, status, detail);
            } finally {
                pending.finish();
            }
        }).start();
    }

    private static String describe(int code) {
        switch (code) {
            case SmsManager.RESULT_ERROR_RADIO_OFF:
                return "radio desligado";
            case SmsManager.RESULT_ERROR_NO_SERVICE:
                return "sem servico de celular";
            case SmsManager.RESULT_ERROR_NULL_PDU:
                return "mensagem invalida";
            case SmsManager.RESULT_ERROR_GENERIC_FAILURE:
            default:
                return "falha da operadora (credito, chip ou rede)";
        }
    }
}
