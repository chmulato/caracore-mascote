package br.com.caracore.pdv.sms;

import android.app.KeyguardManager;
import android.content.ClipData;
import android.content.ClipDescription;
import android.content.ClipboardManager;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.PersistableBundle;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;

import androidx.fragment.app.FragmentActivity;

import com.google.zxing.BarcodeFormat;
import com.google.zxing.qrcode.QRCodeWriter;

import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URL;

/**
 * Painel da rede da loja: guarda o nome e a senha, mostra, copia, gera QR
 * para outros aparelhos e testa se o computador do PDV responde.
 * Não altera o roteador da loja.
 */
public class WifiActivity extends FragmentActivity {

    private static final long TEMPO_SENHA_NA_TELA = 30_000L;
    private static final long TEMPO_SENHA_COPIADA = 60_000L;

    private final Handler handler = new Handler(Looper.getMainLooper());
    private Runnable acaoAutorizada;

    private TextView textWifiGuardada;
    private TextView textWifiAviso;
    private TextView textWifiTeste;
    private ImageView imgWifiQr;
    private TextView textWifiQrAjuda;
    private Button btnWifiTestar;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_wifi);

        EditText editSsid = findViewById(R.id.editWifiSsid);
        EditText editSenha = findViewById(R.id.editWifiSenha);
        textWifiGuardada = findViewById(R.id.textWifiGuardada);
        textWifiAviso = findViewById(R.id.textWifiAviso);
        textWifiTeste = findViewById(R.id.textWifiTeste);
        imgWifiQr = findViewById(R.id.imgWifiQr);
        textWifiQrAjuda = findViewById(R.id.textWifiQrAjuda);
        btnWifiTestar = findViewById(R.id.btnWifiTestar);

        String ssid = WifiCredentialStore.ssid(this);
        if (ssid != null && editSsid != null) {
            editSsid.setText(ssid);
        }

        Button btnSalvar = findViewById(R.id.btnWifiSalvar);
        if (btnSalvar != null) {
            btnSalvar.setOnClickListener(v -> {
                String novoSsid = editSsid != null ? editSsid.getText().toString().trim() : "";
                String novaSenha = editSenha != null ? editSenha.getText().toString() : "";
                if (novoSsid.isEmpty() || novaSenha.length() < 8 || novaSenha.length() > 63) {
                    Toast.makeText(this, R.string.wifi_invalido, Toast.LENGTH_LONG).show();
                    return;
                }
                if (WifiCredentialStore.guardar(this, novoSsid, novaSenha)) {
                    if (editSenha != null) editSenha.setText("");
                    atualizarSenhaGuardada();
                    Toast.makeText(this, R.string.wifi_salvo, Toast.LENGTH_LONG).show();
                }
            });
        }

        Button btnMostrar = findViewById(R.id.btnWifiMostrar);
        if (btnMostrar != null) {
            btnMostrar.setOnClickListener(v -> comAutorizacao(() -> revelarSenha()));
        }
        Button btnCopiar = findViewById(R.id.btnWifiCopiar);
        if (btnCopiar != null) {
            btnCopiar.setOnClickListener(v -> comAutorizacao(() -> copiarSenha()));
        }
        Button btnQr = findViewById(R.id.btnWifiQr);
        if (btnQr != null) {
            btnQr.setOnClickListener(v -> comAutorizacao(() -> mostrarQr()));
        }
        if (btnWifiTestar != null) {
            btnWifiTestar.setOnClickListener(v -> testarLigacao());
        }
        Button btnVoltar = findViewById(R.id.btnWifiVoltar);
        if (btnVoltar != null) {
            btnVoltar.setOnClickListener(v -> finish());
        }

        atualizarSenhaGuardada();
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }

    private void comAutorizacao(Runnable acao) {
        if (!WifiCredentialStore.temSenha(this)) {
            Toast.makeText(this, R.string.wifi_nenhuma_senha, Toast.LENGTH_LONG).show();
            return;
        }
        KeyguardManager km = (KeyguardManager) getSystemService(Context.KEYGUARD_SERVICE);
        if (km != null && !km.isDeviceSecure()) {
            Toast.makeText(this, R.string.wifi_sem_trava, Toast.LENGTH_LONG).show();
            return;
        }
        acaoAutorizada = acao;
        DeviceAuth.Callback callback = new DeviceAuth.Callback() {
            @Override
            public void onSuccess(String metodo) {
                executarAutorizada();
            }

            @Override
            public void onCancelado() {
                acaoAutorizada = null;
                Toast.makeText(WifiActivity.this, R.string.wifi_autorizacao_cancelada, Toast.LENGTH_LONG).show();
            }
        };
        DeviceAuth.confirmar(this, getString(R.string.wifi_auth_titulo), getString(R.string.wifi_auth_sub), callback);
    }

    private void executarAutorizada() {
        Runnable acao = acaoAutorizada;
        acaoAutorizada = null;
        if (acao != null) acao.run();
    }

    private void atualizarSenhaGuardada() {
        if (textWifiGuardada == null) return;
        textWifiGuardada.setText(WifiCredentialStore.temSenha(this)
                ? R.string.wifi_senha_mascarada : R.string.wifi_nenhuma_senha);
    }

    private void revelarSenha() {
        final String senha = WifiCredentialStore.senha(this, true);
        if (senha == null) return;
        textWifiGuardada.setText(senha);
        textWifiAviso.setText(R.string.wifi_revelada_aviso);
        textWifiAviso.setVisibility(View.VISIBLE);
        handler.removeCallbacksAndMessages(null);
        handler.postDelayed(() -> {
            atualizarSenhaGuardada();
            if (textWifiAviso != null) textWifiAviso.setVisibility(View.GONE);
        }, TEMPO_SENHA_NA_TELA);
    }

    private void copiarSenha() {
        final String senha = WifiCredentialStore.senha(this, true);
        if (senha == null) return;
        ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
        if (cm == null) return;
        ClipData clip = ClipData.newPlainText("Wi‑Fi da loja", senha);
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            PersistableBundle extras = new PersistableBundle();
            extras.putBoolean(ClipDescription.EXTRA_IS_SENSITIVE, true);
            clip.getDescription().setExtras(extras);
        }
        cm.setPrimaryClip(clip);
        Toast.makeText(this, R.string.wifi_copiado, Toast.LENGTH_LONG).show();
        handler.postDelayed(() -> {
            try {
                if (android.os.Build.VERSION.SDK_INT >= 28 && cm.hasPrimaryClip()) {
                    CharSequence atual = cm.getPrimaryClip() != null && cm.getPrimaryClip().getItemCount() > 0
                            ? cm.getPrimaryClip().getItemAt(0).getText() : null;
                    if (atual != null && senha.contentEquals(atual)) {
                        cm.clearPrimaryClip();
                    }
                }
            } catch (Exception ignored) {
            }
        }, TEMPO_SENHA_COPIADA);
    }

    private void mostrarQr() {
        String ssid = WifiCredentialStore.ssid(this);
        String senha = WifiCredentialStore.senha(this, true);
        if (ssid == null || senha == null) return;
        try {
            QRCodeWriter writer = new QRCodeWriter();
            int lado = 640;
            Bitmap bitmap = Bitmap.createBitmap(lado, lado, Bitmap.Config.ARGB_8888);
            com.google.zxing.common.BitMatrix matriz = writer.encode(
                    WifiQr.payload(ssid, senha), BarcodeFormat.QR_CODE, lado, lado);
            for (int x = 0; x < lado; x++) {
                for (int y = 0; y < lado; y++) {
                    bitmap.setPixel(x, y, matriz.get(x, y) ? Color.BLACK : Color.WHITE);
                }
            }
            imgWifiQr.setImageBitmap(bitmap);
            imgWifiQr.setVisibility(View.VISIBLE);
            textWifiQrAjuda.setVisibility(View.VISIBLE);
            Toast.makeText(this, getString(R.string.config_wifi_rede_guardada, ssid), Toast.LENGTH_SHORT).show();
            handler.postDelayed(() -> {
                if (imgWifiQr != null) imgWifiQr.setVisibility(View.GONE);
                if (textWifiQrAjuda != null) textWifiQrAjuda.setVisibility(View.GONE);
            }, TEMPO_SENHA_COPIADA);
        } catch (Exception e) {
            PdvSmsLogger.i("Wifi", "qr: " + e.getMessage());
            Toast.makeText(this, R.string.wifi_invalido, Toast.LENGTH_LONG).show();
        }
    }

    private void testarLigacao() {
        SmsPreferences prefs = new SmsPreferences(this);
        final String baseUrl = prefs.getPdvBaseUrl();
        if (baseUrl == null || baseUrl.isEmpty()) {
            mostrarTeste(getString(R.string.wifi_teste_sem_pareamento));
            return;
        }
        btnWifiTestar.setEnabled(false);
        mostrarTeste(getString(R.string.wifi_testando));
        new Thread(() -> {
            String host = null;
            int porta = 443;
            long inicio = System.currentTimeMillis();
            try {
                URL url = new URL(baseUrl.trim());
                host = url.getHost();
                if (url.getPort() > 0) {
                    porta = url.getPort();
                } else if ("http".equalsIgnoreCase(url.getProtocol())) {
                    porta = 80;
                }
            } catch (Exception e) {
                host = null;
            }
            boolean ok = false;
            long gasto = 0;
            if (host != null && !host.isEmpty()) {
                try (Socket socket = new Socket()) {
                    socket.connect(new InetSocketAddress(host, porta), 2500);
                    ok = true;
                } catch (Exception e) {
                    ok = false;
                }
                gasto = System.currentTimeMillis() - inicio;
            }
            final boolean respondeu = ok;
            final long ms = gasto;
            final String endereco = host == null ? baseUrl : host + ":" + porta;
            runOnUiThread(() -> {
                if (btnWifiTestar != null) btnWifiTestar.setEnabled(true);
                if (respondeu) {
                    mostrarTeste(getString(R.string.wifi_teste_ok, (int) ms, endereco));
                } else {
                    mostrarTeste(getString(R.string.wifi_teste_falhou, endereco));
                }
            });
        }).start();
    }

    private void mostrarTeste(String texto) {
        textWifiTeste.setText(texto);
        textWifiTeste.setVisibility(View.VISIBLE);
    }
}
