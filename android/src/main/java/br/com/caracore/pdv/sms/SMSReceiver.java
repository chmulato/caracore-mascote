package br.com.caracore.pdv.sms;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.provider.Telephony;
import android.telephony.SmsMessage;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * BroadcastReceiver que filtra SMS do remetente oficial da Cara Core.
 * Ao receber "CC-LICENSE:[CHAVE]", extrai a chave e salva de forma segura em SharedPreferences.
 * Ignora SMS de outros remetentes quando o número oficial estiver definido.
 */
public class SMSReceiver extends BroadcastReceiver {

    /** Aceita CC-LICENSE: ou CARACORE-KEY: (compatível com o PDV) para extrair [CHAVE]. */
    private static final Pattern PREFIX_CHAVE = Pattern.compile("(?:CC-LICENSE|CARACORE-KEY):\\s*(.+)", Pattern.CASE_INSENSITIVE);

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
        String numeroOficialDigitos = numeroOficial != null && !numeroOficial.isEmpty()
                ? numeroOficial.replaceAll("\\D", "") : null;

        for (SmsMessage msg : msgs) {
            String sender = msg.getDisplayOriginatingAddress();
            if (sender == null) sender = "";
            String body = msg.getMessageBody();
            if (body == null) body = "";

            // Filtrar por número oficial (quando configurado)
            if (numeroOficialDigitos != null && !numeroOficialDigitos.isEmpty()) {
                String senderDigitos = sender.replaceAll("\\D", "");
                if (senderDigitos.isEmpty() || !(senderDigitos.endsWith(numeroOficialDigitos) || numeroOficialDigitos.endsWith(senderDigitos) || senderDigitos.equals(numeroOficialDigitos))) {
                    continue;
                }
            }

            String chave = extrairChave(body);
            if (chave != null && !chave.isEmpty()) {
                prefs.setChaveLicenca(chave);
                PdvSmsLogger.i("SMSReceiver", "Chave de licença recebida e salva.");
                break;
            }
        }
    }

    /**
     * Extrai [CHAVE] de "CC-LICENSE:[CHAVE]" ou "CARACORE-KEY: [CHAVE]".
     */
    private String extrairChave(String body) {
        if (body == null) return null;
        Matcher m = PREFIX_CHAVE.matcher(body.trim());
        if (!m.find()) return null;
        String s = m.group(1).trim();
        return s.isEmpty() ? null : s;
    }
}
