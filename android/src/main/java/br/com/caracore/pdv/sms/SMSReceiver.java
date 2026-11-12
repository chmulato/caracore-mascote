package br.com.caracore.pdv.sms;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.provider.Telephony;
import android.telephony.SmsMessage;

/**
 * BroadcastReceiver que recebe o SMS de licença da Cara Core.
 * Ao receber "CC-LICENSE:[CHAVE]", extrai a chave e salva de forma segura em SharedPreferences.
 * A regra de aceitação fica em {@link LicenseSms}: sem número oficial configurado, nada é aceito.
 */
public class SMSReceiver extends BroadcastReceiver {

    @Override
    public void onReceive(Context context, Intent intent) {
        if (!Telephony.Sms.Intents.SMS_RECEIVED_ACTION.equals(intent.getAction())) {
            return;
        }
        SmsMessage[] msgs = Telephony.Sms.Intents.getMessagesFromIntent(intent);
        if (msgs == null || msgs.length == 0) {
            return;
        }
        SmsPreferences prefs = new SmsPreferences(context);
        String numeroOficial = prefs.getNumeroOficialLicenca();

        for (SmsMessage msg : msgs) {
            LicenseSms.Resultado resultado =
                    LicenseSms.avaliar(msg.getDisplayOriginatingAddress(), msg.getMessageBody(), numeroOficial);
            if (resultado.isAceita()) {
                prefs.setChaveLicenca(resultado.getChave());
                PdvSmsLogger.i("SMSReceiver", "Chave de licença recebida e salva.");
                return;
            }
            if (resultado.getMotivo() != LicenseSms.Motivo.CHAVE_AUSENTE) {
                PdvSmsLogger.i("SMSReceiver", "SMS de licença ignorado: " + resultado.getMotivo() + ".");
            }
        }
    }
}
