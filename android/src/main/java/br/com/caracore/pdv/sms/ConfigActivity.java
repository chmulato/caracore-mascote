package br.com.caracore.pdv.sms;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

/**
 * Painel administrativo CaraCore PDV - Envio SMS.
 * Ativa ou pausa o envio de SMS; exibe status da licença Premium e verifica conexão USB.
 * Componente do Enlace de Contingência (operação sem internet) do CaraCore-PDV.
 */
public class ConfigActivity extends Activity {

    private static final int REQ_SMS = 1001;

    private SmsPreferences prefs;
    private Switch switchAtivo;
    private TextView textStatus;
    private TextView textStatusLicenca;
    private TextView textStatusBackupCard;
    private TextView textDataHoraBackupCard;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        try {
            super.onCreate(savedInstanceState);
            setContentView(R.layout.activity_config);

            prefs = new SmsPreferences(this);
            textStatus = findViewById(R.id.textStatus);
            switchAtivo = findViewById(R.id.switchAtivo);
            textStatusLicenca = findViewById(R.id.textStatusLicenca);
            textStatusBackupCard = findViewById(R.id.textStatusBackupCard);
            textDataHoraBackupCard = findViewById(R.id.textDataHoraBackupCard);

            solicitarPermissoesSms();

            switchAtivo.setChecked(prefs.isAtivo());
            atualizarStatus();
            atualizarStatusLicenca();
            atualizarStatusBackup();

            switchAtivo.setOnCheckedChangeListener((buttonView, isChecked) -> {
                prefs.setAtivo(isChecked);
                atualizarStatus();
                PdvSmsLogger.i("Config.switchAtivo", "App ativo=" + isChecked);
                Toast.makeText(ConfigActivity.this,
                        isChecked ? R.string.config_app_ativo_toast_ativado : R.string.config_app_ativo_toast_desativado,
                        Toast.LENGTH_SHORT).show();
            });

            Button btnUsb = findViewById(R.id.btnVerificarUsb);
            if (btnUsb != null) {
                btnUsb.setOnClickListener(v -> verificarConexaoUsb());
            }
            EditText editGatewaySecret = findViewById(R.id.editGatewaySecret);
            if (editGatewaySecret != null && prefs.getGatewaySharedSecret() != null) {
                editGatewaySecret.setText(prefs.getGatewaySharedSecret());
            }
            Button btnGatewayStart = findViewById(R.id.btnGatewayStart);
            if (btnGatewayStart != null) {
                btnGatewayStart.setOnClickListener(v -> {
                    EditText edit = findViewById(R.id.editGatewaySecret);
                    String secret = edit != null ? edit.getText().toString().trim() : "";
                    prefs.setGatewaySharedSecret(secret.isEmpty() ? null : secret);
                    if (!secret.isEmpty()) {
                        startService(new Intent(ConfigActivity.this, GatewayListenerService.class));
                        Toast.makeText(ConfigActivity.this, "Gateway iniciado. PDV na mesma rede Wi‑Fi pode enviar comandos.", Toast.LENGTH_SHORT).show();
                    }
                });
            }
            Button btnSetupQr = findViewById(R.id.btnSetupQr);
            if (btnSetupQr != null) {
                btnSetupQr.setOnClickListener(v -> startActivity(new Intent(ConfigActivity.this, ScanSetupActivity.class)));
            }
            Button btnBateria = findViewById(R.id.btnBateria);
            if (btnBateria != null) {
                btnBateria.setOnClickListener(v -> pedirBateriaLivre());
            }
            EditText editNumeroOficial = findViewById(R.id.editNumeroOficial);
            if (editNumeroOficial != null) {
                String numeroOficial = prefs.getNumeroOficialLicenca();
                if (numeroOficial != null) {
                    editNumeroOficial.setText(numeroOficial);
                }
            }
            Button btnSalvarNumeroOficial = findViewById(R.id.btnSalvarNumeroOficial);
            if (btnSalvarNumeroOficial != null) {
                btnSalvarNumeroOficial.setOnClickListener(v -> salvarNumeroOficial());
            }

            TextView textVersao = findViewById(R.id.textVersao);
            try {
                String v = BuildConfig.VERSION_NAME != null ? BuildConfig.VERSION_NAME : "?";
                textVersao.setText(getString(R.string.config_versao, v));
            } catch (Exception e) {
                ErrorReporter.log("Config.versao", e);
                textVersao.setText(getString(R.string.config_versao, "1.0"));
            }
        } catch (Exception e) {
            ErrorReporter.show(this, "Config.onCreate", e);
            finish();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        atualizarStatusLicenca();
        if (prefs.getGatewaySharedSecret() != null && !prefs.getGatewaySharedSecret().isEmpty()) {
            startService(new Intent(this, GatewayListenerService.class));
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_SMS && grantResults != null && grantResults.length > 0) {
            for (int r : grantResults) {
                if (r != PackageManager.PERMISSION_GRANTED) {
                    Toast.makeText(this, getString(R.string.config_sms_permission_negada), Toast.LENGTH_LONG).show();
                    return;
                }
            }
        }
    }

    private void solicitarPermissoesSms() {
        if (Build.VERSION.SDK_INT < 23) return;
        if (checkSelfPermission(Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED
                || checkSelfPermission(Manifest.permission.RECEIVE_SMS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{
                    Manifest.permission.SEND_SMS,
                    Manifest.permission.RECEIVE_SMS
            }, REQ_SMS);
        }
    }

    private void atualizarStatus() {
        if (textStatus != null) {
            textStatus.setText(prefs.isAtivo() ? R.string.config_status_ativo : R.string.config_status_inativo);
        }
    }

    private void atualizarStatusLicenca() {
        if (textStatusLicenca == null) return;
        boolean valida = prefs.isLicencaValida();
        textStatusLicenca.setText(valida ? R.string.config_licenca_ativa : R.string.config_licenca_inativa);
        textStatusLicenca.setTextColor(getResources().getColor(valida ? R.color.licenca_ativa : R.color.licenca_inativa, getTheme()));
    }

    private void atualizarStatusBackup() {
        if (textStatusBackupCard == null || textDataHoraBackupCard == null) return;
        String timestamp = prefs.getLastBackupTimestamp();
        String status = prefs.getLastBackupStatus();
        if (timestamp == null || timestamp.isEmpty()) {
            textStatusBackupCard.setText(R.string.config_backup_status_nenhum);
            textDataHoraBackupCard.setText(R.string.config_backup_data_hora_nd);
            return;
        }
        if ("OK".equalsIgnoreCase(status)) {
            textStatusBackupCard.setText(R.string.config_backup_status_ok);
        } else {
            textStatusBackupCard.setText(R.string.config_backup_status_erro);
        }
        textDataHoraBackupCard.setText(getString(R.string.config_backup_data_hora, timestamp));
    }

    private void pedirBateriaLivre() {
        if (Build.VERSION.SDK_INT < 23 || SetupDiagnosticHelper.checkBatteryOptimizationIgnored(this)) {
            Toast.makeText(this, R.string.config_bateria_ja, Toast.LENGTH_LONG).show();
            return;
        }
        try {
            Intent intent = new Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,
                    android.net.Uri.parse("package:" + getPackageName()));
            startActivity(intent);
            Toast.makeText(this, R.string.config_bateria_pedido, Toast.LENGTH_LONG).show();
        } catch (Exception e) {
            startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS));
        }
    }

    private void salvarNumeroOficial() {
        EditText edit = findViewById(R.id.editNumeroOficial);
        if (edit == null) return;
        String digitos = LicenseSms.somenteDigitos(edit.getText().toString());
        if (!LicenseSms.numeroValido(digitos)) {
            Toast.makeText(this, R.string.config_numero_oficial_invalido, Toast.LENGTH_LONG).show();
            return;
        }
        prefs.setNumeroOficialLicenca(digitos);
        edit.setText(digitos);
        Toast.makeText(this, R.string.config_numero_oficial_salvo, Toast.LENGTH_LONG).show();
        PdvSmsLogger.i("Config.numeroOficial", "Número oficial de licença salvo.");
    }

    private void verificarConexaoUsb() {
        int v = Settings.Global.getInt(getContentResolver(), "adb_enabled", 0);
        boolean adbAtiva = (v == 1);
        Toast.makeText(this, adbAtiva ? R.string.config_usb_ativa : R.string.config_usb_inativa, Toast.LENGTH_LONG).show();
    }
}
