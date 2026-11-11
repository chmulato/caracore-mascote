package br.com.caracore.pdv.sms;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.telephony.SmsManager;
import android.widget.Toast;

/**
 * Activity que envia SMS quando acionada via ADB com os extras "number" e "body".
 * Respeita a configuração "App ativo" do painel. Se desativado, não envia.
 *
 * Exemplo:
 *   adb shell am start -n br.com.caracore.pdv.sms/.SendSmsActivity -e number "5541999999999" -e body "Mensagem"
 *
 * Na primeira execução o app solicita a permissão SEND_SMS. Após permitir, o envio é automático quando ativo.
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
                        "Uso: am start -n ... -e number NUM -e body \"MSG\"");
            }

            number = number.trim().replaceAll("[^+0-9]", "");
            if (number.isEmpty()) {
                throw new SmsValidationException("Número vazio após limpeza", "Número inválido");
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
            SmsManager.getDefault().sendTextMessage(number, null, body, null, null);
            PdvSmsLogger.i("SendSms.enviar", "SMS enviado com sucesso para " + number);
            Toast.makeText(this, "SMS enviado para " + number, Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            ErrorReporter.show(this, "SendSms.enviar", new SmsSendException(e));
        } finally {
            finish();
        }
    }
}
