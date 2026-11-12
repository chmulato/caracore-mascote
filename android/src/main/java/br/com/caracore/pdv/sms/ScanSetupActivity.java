package br.com.caracore.pdv.sms;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.widget.Toast;

import com.google.zxing.integration.android.IntentIntegrator;
import com.google.zxing.integration.android.IntentResult;

/**
 * Activity que escaneia o QR Code de setup Premium+ na tela do PDV,
 * aplica IP, chave AES e licença, executa auto-diagnóstico e reporta ao PC.
 */
public class ScanSetupActivity extends Activity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        IntentIntegrator integrator = new IntentIntegrator(this);
        integrator.setDesiredBarcodeFormats(IntentIntegrator.QR_CODE);
        integrator.setPrompt(getString(R.string.setup_scan_prompt));
        integrator.setBeepEnabled(true);
        integrator.initiateScan();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        IntentResult result = IntentIntegrator.parseActivityResult(requestCode, resultCode, data);
        if (result == null) {
            super.onActivityResult(requestCode, resultCode, data);
            return;
        }
        if (result.getContents() == null) {
            Toast.makeText(this, R.string.setup_scan_cancelled, Toast.LENGTH_SHORT).show();
            finish();
            return;
        }
        SetupPayload payload = SetupPayload.parse(result.getContents());
        if (payload == null) {
            Toast.makeText(this, R.string.setup_scan_invalid, Toast.LENGTH_LONG).show();
            finish();
            return;
        }
        applyAndReport(payload);
    }

    private void applyAndReport(SetupPayload payload) {
        SmsPreferences prefs = new SmsPreferences(this);
        prefs.setGatewaySharedSecret(payload.keyBase64);
        prefs.setPdvBaseUrl(payload.baseUrl());
        if (payload.licenseToken != null) {
            prefs.setChaveLicenca(payload.licenseToken);
        }

        boolean smsOk = SetupDiagnosticHelper.checkSmsPermissions(this);
        boolean batteryOk = SetupDiagnosticHelper.checkBatteryOptimizationIgnored(this);
        String publicKey = "";
        StringBuilder msg = new StringBuilder();
        try {
            publicKey = E2ECrypto.ensureKeyPair(this);
        } catch (Exception e) {
            msg.append("Chave de criptografia: este celular não conseguiu criar a chave. ");
        }
        if (!smsOk) msg.append("Permissões SMS: conceda no app. ");
        if (!batteryOk) msg.append("Bateria: desative otimização para este app. ");

        final String baseUrl = payload.baseUrl();
        final String token = payload.setupToken;
        final boolean sms = smsOk;
        final boolean battery = batteryOk;
        final String message = msg.toString().trim();
        final String phoneKey = publicKey;

        new Thread(() -> {
            final String err = SetupDiagnosticHelper.reportToPdv(baseUrl, token, sms, battery, message, phoneKey);
            runOnUiThread(() -> {
                startService(new Intent(ScanSetupActivity.this, GatewayListenerService.class));
                if (err == null) {
                    Toast.makeText(ScanSetupActivity.this, R.string.setup_success, Toast.LENGTH_LONG).show();
                } else {
                    Toast.makeText(ScanSetupActivity.this, getString(R.string.setup_report_error, err), Toast.LENGTH_LONG).show();
                }
                finish();
            });
        }).start();
    }
}
