package br.com.caracore.pdv.sms;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.telephony.SmsManager;
import android.widget.Toast;

/**
 * Activity interna de envio, sem acionamento por outros aplicativos.
 * O caminho normal e o GatewayListenerService, que recebe o pedido cifrado do Gaspar.
 * Mantida apenas para compatibilidade interna; o manifesto a declara como nao exportada.
 */
public class SendSmsActivity extends Activity {

    private static final int REQUEST_SEND_SMS = 1;

    private SmsPreferences prefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        try {
            super.onCreate(savedInstanceState);
            prefs = new SmsPreferences(this);

            if (!prefs.isAtivo()) {
                throw new SmsDisabledException();
            }

            String number = getIntent().getStringExtra("number");
            String body = getIntent().getStringExtra("body");

            if (number == null || number.trim().isEmpty() || body == null) {
                throw new SmsValidationException(
                        "Extras number e body obrigatórios",
                        "Acionamento externo desativado");
            }

            number = number.trim().replaceAll("[^+0-9]", "");
            if (number.length() < 10 || number.length() > 15) {
                throw new SmsValidationException("Número inválido", "Número inválido");
            }
            if (body.length() > 480) {
                throw new SmsValidationException(
                        "Mensagem acima de 480 caracteres",
                        "Mensagem acima de 480 caracteres");
            }

            if (Build.VERSION.SDK_INT >= 23) {
                if (checkSelfPermission(Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED) {
                    requestPermissions(new String[]{Manifest.permission.SEND_SMS}, REQUEST_SEND_SMS);
                    return;
                }
            }

            enviar(number, body);
        } catch (PdvSmsException e) {
            ErrorReporter.show(this, "SendSms.onCreate", e);
            finish();
        } catch (Exception e) {
            ErrorReporter.show(this, "SendSms.onCreate", e);
            finish();
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        try {
            super.onRequestPermissionsResult(requestCode, permissions, grantResults);
            if (requestCode != REQUEST_SEND_SMS) {
                finish();
                return;
            }
            if (!prefs.isAtivo()) {
                throw new SmsDisabledException();
            }
            String number = getIntent().getStringExtra("number");
            String body = getIntent().getStringExtra("body");
            if (number != null) {
                number = number.trim().replaceAll("[^+0-9]", "");
            }
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED
                    && number != null && !number.isEmpty()) {
                enviar(number, body);
            } else {
                throw new SmsPermissionException();
            }
        } catch (PdvSmsException e) {
            ErrorReporter.show(this, "SendSms.onRequestPermissionsResult", e);
        } catch (Exception e) {
            ErrorReporter.show(this, "SendSms.onRequestPermissionsResult", e);
        } finally {
            finish();
        }
    }

    private void enviar(String number, String body) {
        try {
            if (!prefs.consumeSmsQuota()) {
                ErrorReporter.show(this, "SendSms.enviar",
                        new SmsValidationException("Limite diário do celular atingido",
                                "Aguarde o próximo dia para enviar mais SMS"));
                return;
            }
            SmsManager.getDefault().sendTextMessage(number, null, body, null, null);
            PdvSmsLogger.i("SendSms.enviar", "SMS enviado com sucesso");
            Toast.makeText(this, "SMS enviado", Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            ErrorReporter.show(this, "SendSms.enviar", new SmsSendException(e));
        } finally {
            finish();
        }
    }
}
