package br.com.caracore.pdv.sms;

import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.telephony.SmsManager;

import java.util.ArrayList;

/**
 * O radio do celular. Cada parte da mensagem sai com os dois comprovantes armados:
 * o do envio (SMS_SENT) e o da entrega (SMS_DELIVERED), ambos com o identificador
 * do pedido para o Gaspar saber de volta o que aconteceu.
 */
public final class PhoneRadio implements SmsDispatch.Radio {

    private final Context context;

    public PhoneRadio(Context context) {
        this.context = context.getApplicationContext();
    }

    @Override
    public void enviar(String numero, String texto, String jobId) {
        SmsManager sms = SmsManager.getDefault();
        ArrayList<String> partes = sms.divideMessage(texto);
        ArrayList<PendingIntent> enviados = new ArrayList<>();
        ArrayList<PendingIntent> entregues = new ArrayList<>();
        for (int i = 0; i < partes.size(); i++) {
            enviados.add(statusPending(SmsStatusReceiver.ACTION_SENT, jobId, i, true));
            entregues.add(statusPending(SmsStatusReceiver.ACTION_DELIVERED, jobId, i, false));
        }
        if (partes.size() == 1) {
            sms.sendTextMessage(numero, null, partes.get(0), enviados.get(0), entregues.get(0));
        } else {
            sms.sendMultipartTextMessage(numero, null, partes, enviados, entregues);
        }
    }

    private PendingIntent statusPending(String action, String id, int parte, boolean envio) {
        Intent intent = new Intent(context, SmsStatusReceiver.class);
        intent.setAction(action);
        intent.putExtra(SmsStatusReceiver.EXTRA_ID, id);
        int pedido = (id.hashCode() * 31 + parte) * 2 + (envio ? 0 : 1);
        return PendingIntent.getBroadcast(
                context,
                pedido,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }
}
