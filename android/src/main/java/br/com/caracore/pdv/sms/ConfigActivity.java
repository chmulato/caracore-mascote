package br.com.caracore.pdv.sms;

import android.Manifest;
import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
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
    private static final int REQ_NOTIFICACOES = 1002;

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
            if (checkSelfPermission(Manifest.permission.SEND_SMS) == PackageManager.PERMISSION_GRANTED) {
                solicitarPermissaoNotificacoes();
            }

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
            Button btnWifiManage = findViewById(R.id.btnWifiManage);
            if (btnWifiManage != null) {
                btnWifiManage.setOnClickListener(v -> startActivity(new Intent(ConfigActivity.this, WifiActivity.class)));
            }
            Switch switchConfirmacao = findViewById(R.id.switchConfirmacao);
            if (switchConfirmacao != null) {
                switchConfirmacao.setChecked(prefs.isConfirmacaoAtiva());
                switchConfirmacao.setOnCheckedChangeListener((buttonView, isChecked) -> {
                    prefs.setConfirmacaoAtiva(isChecked);
                    atualizarStatusConfirmacao();
                });
            }
            Button btnHistorico = findViewById(R.id.btnConfirmacaoHistorico);
            if (btnHistorico != null) {
                btnHistorico.setOnClickListener(v -> mostrarHistoricoConfirmacao());
            }
            Button btnTeste = findViewById(R.id.btnConfirmacaoTeste);
            if (btnTeste != null) {
                btnTeste.setOnClickListener(v -> abrirPedidoDeTeste());
            }
            atualizarStatusConfirmacao();
            Button btnBateria = findViewById(R.id.btnBateria);
            if (btnBateria != null) {
                btnBateria.setOnClickListener(v -> pedirBateriaLivre());
            }
            EditText editChaveLicenca = findViewById(R.id.editChaveLicenca);
            if (editChaveLicenca != null) {
                String chave = prefs.getChaveLicenca();
                if (chave != null) {
                    editChaveLicenca.setText(chave);
                }
            }
            Button btnSalvarChave = findViewById(R.id.btnSalvarChave);
            if (btnSalvarChave != null) {
                btnSalvarChave.setOnClickListener(v -> salvarChaveLicenca());
            }
            garantirBackupToken();
            Button btnCopiarToken = findViewById(R.id.btnCopiarToken);
            if (btnCopiarToken != null) {
                btnCopiarToken.setOnClickListener(v -> copiarBackupToken());
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
        atualizarStatusWifi();
        atualizarStatusConfirmacao();
        if (prefs.getGatewaySharedSecret() != null && !prefs.getGatewaySharedSecret().isEmpty()) {
            startService(new Intent(this, GatewayListenerService.class));
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == REQ_SMS) {
            if (grantResults != null && grantResults.length > 0) {
                for (int r : grantResults) {
                    if (r != PackageManager.PERMISSION_GRANTED) {
                        Toast.makeText(this, getString(R.string.config_sms_permission_negada), Toast.LENGTH_LONG).show();
                        break;
                    }
                }
            }
            // Uma caixa de permissão por vez: a de notificações só abre depois desta.
            solicitarPermissaoNotificacoes();
            return;
        }
        if (requestCode == REQ_NOTIFICACOES && grantResults != null && grantResults.length > 0
                && grantResults[0] != PackageManager.PERMISSION_GRANTED) {
            Toast.makeText(this, getString(R.string.config_notificacao_negada), Toast.LENGTH_LONG).show();
        }
    }

    private void solicitarPermissoesSms() {
        if (Build.VERSION.SDK_INT < 23) return;
        if (checkSelfPermission(Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.SEND_SMS}, REQ_SMS);
        }
    }

    private void solicitarPermissaoNotificacoes() {
        if (Build.VERSION.SDK_INT < 33) return;
        if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQ_NOTIFICACOES);
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
            startActivity(new Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS));
            Toast.makeText(this, R.string.config_bateria_pedido, Toast.LENGTH_LONG).show();
        } catch (Exception e) {
            Toast.makeText(this, R.string.config_bateria_sem_tela, Toast.LENGTH_LONG).show();
        }
    }

    private void salvarChaveLicenca() {
        EditText edit = findViewById(R.id.editChaveLicenca);
        if (edit == null) return;
        String chave = LicenseSms.chaveDe(edit.getText().toString());
        if (chave == null) {
            Toast.makeText(this, R.string.config_licenca_chave_invalida, Toast.LENGTH_LONG).show();
            return;
        }
        prefs.setChaveLicenca(chave);
        edit.setText(chave);
        atualizarStatusLicenca();
        Toast.makeText(this, R.string.config_licenca_chave_salva, Toast.LENGTH_LONG).show();
        PdvSmsLogger.i("Config.chaveLicenca", "Chave de licença salva.");
    }

    private void garantirBackupToken() {
        String token = prefs.getBackupToken();
        if (token == null || token.isEmpty()) {
            token = BackupToken.gerar();
            prefs.setBackupToken(token);
        }
        TextView textToken = findViewById(R.id.textBackupToken);
        if (textToken != null) {
            textToken.setText(getString(R.string.config_backup_token, token));
        }
    }

    private void copiarBackupToken() {
        String token = prefs.getBackupToken();
        if (token == null || token.isEmpty()) return;
        ClipboardManager clipboard = (ClipboardManager) getSystemService(CLIPBOARD_SERVICE);
        if (clipboard == null) return;
        clipboard.setPrimaryClip(ClipData.newPlainText("token-backup", token));
        Toast.makeText(this, R.string.config_backup_token_copiado, Toast.LENGTH_LONG).show();
    }

    private void verificarConexaoUsb() {
        int v = Settings.Global.getInt(getContentResolver(), "adb_enabled", 0);
        boolean adbAtiva = (v == 1);
        Toast.makeText(this, adbAtiva ? R.string.config_usb_ativa : R.string.config_usb_inativa, Toast.LENGTH_LONG).show();
    }

    private void atualizarStatusWifi() {
        TextView textWifiRede = findViewById(R.id.textWifiRede);
        if (textWifiRede == null) return;
        String ssid = WifiCredentialStore.ssid(this);
        if (ssid == null) {
            textWifiRede.setText(R.string.config_wifi_rede_nenhuma);
        } else {
            textWifiRede.setText(getString(R.string.config_wifi_rede_guardada, ssid));
        }
    }

    private void atualizarStatusConfirmacao() {
        TextView text = findViewById(R.id.textConfirmacaoStatus);
        if (text == null) return;
        boolean ativa = prefs.isConfirmacaoAtiva();
        text.setText(ativa ? R.string.config_confirmacao_status_on : R.string.config_confirmacao_status_off);
        text.setTextColor(getResources().getColor(ativa ? R.color.status_on : R.color.status_off, getTheme()));
    }

    private void mostrarHistoricoConfirmacao() {
        java.util.List<String> linhas = ConfirmationStore.historicoFormatado(this);
        String texto = linhas.isEmpty()
                ? getString(R.string.config_confirmacao_historico_vazio)
                : android.text.TextUtils.join("\n\n", linhas);
        new android.app.AlertDialog.Builder(this)
                .setTitle(R.string.config_confirmacao_historico_titulo)
                .setMessage(texto)
                .setPositiveButton(R.string.confirm_fechar, null)
                .show();
    }

    private void abrirPedidoDeTeste() {
        if (!prefs.isConfirmacaoAtiva()) {
            Toast.makeText(this, R.string.config_confirmacao_status_off, Toast.LENGTH_LONG).show();
            return;
        }
        long agora = System.currentTimeMillis();
        String id = "teste" + agora;
        ConfirmationRequest pedido = new ConfirmationRequest(id,
                ConfirmationRequest.TIPO_DESCONTO, "TESTE-0001", 1500L,
                "Pedido de teste gerado no próprio celular", agora + 120_000L, agora, "teste");
        ConfirmationStore.enfileirar(this, pedido);
        ConfirmationNotifier.notificar(this, pedido);
        Intent intent = new Intent(this, ConfirmationActivity.class);
        intent.putExtra(ConfirmationActivity.EXTRA_ID, id);
        startActivity(intent);
    }
}
