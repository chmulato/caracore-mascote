package br.com.caracore.pdv.sms;

import android.app.AlertDialog;
import android.content.Intent;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.fragment.app.FragmentActivity;

import java.util.Locale;

/**
 * Tela onde o dono do celular aprova ou nega um desconto, cancelamento ou sangria
 * pedidos pelo computador. A decisão é registrada e devolvida ao PDV.
 */
public class ConfirmationActivity extends FragmentActivity {

    public static final String EXTRA_ID = "confirmacao_id";

    private final Handler handler = new Handler(Looper.getMainLooper());
    private ConfirmationRequest pedido;
    private boolean decidido;
    private TextView textPrazo;
    private TextView textResultado;
    private Button btnAprovar;
    private Button btnNegar;
    private Button btnFechar;

    private final Runnable relogio = new Runnable() {
        @Override
        public void run() {
            if (pedido == null || decidido) return;
            long restante = pedido.expiraEmMillis - System.currentTimeMillis();
            if (restante <= 0) {
                finalizar("expirado", "prazo");
                return;
            }
            long segundos = (restante + 999) / 1000;
            textPrazo.setText(getString(R.string.confirm_prazo,
                    String.format(Locale.US, "%d:%02d", segundos / 60, segundos % 60)));
            handler.postDelayed(this, 1000);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_confirmation);
        if (Build.VERSION.SDK_INT >= 27) {
            setShowWhenLocked(true);
            setTurnScreenOn(true);
        }

        textPrazo = findViewById(R.id.textConfirmPrazo);
        textResultado = findViewById(R.id.textConfirmResultado);
        btnAprovar = findViewById(R.id.btnConfirmAprovar);
        btnNegar = findViewById(R.id.btnConfirmNegar);
        btnFechar = findViewById(R.id.btnConfirmFechar);

        String id = getIntent().getStringExtra(EXTRA_ID);
        pedido = id == null ? null : ConfirmationStore.pendente(this, id);
        if (pedido == null) {
            Toast.makeText(this, R.string.confirm_pedido_inexistente, Toast.LENGTH_LONG).show();
            finish();
            return;
        }

        TextView textTipo = findViewById(R.id.textConfirmTipo);
        TextView textDetalhes = findViewById(R.id.textConfirmDetalhes);
        textTipo.setText("Confirmar " + pedido.tituloTipo());
        textDetalhes.setText(pedido.detalhes());

        TextView badgeTeste = findViewById(R.id.textConfirmTeste);
        if (badgeTeste != null && pedido.ehTeste()) {
            badgeTeste.setVisibility(View.VISIBLE);
        }

        btnAprovar.setOnClickListener(v -> aprovar());
        btnNegar.setOnClickListener(v -> perguntarNegar());
        btnFechar.setOnClickListener(v -> finish());

        if (pedido.expirado(System.currentTimeMillis())) {
            finalizar("expirado", "prazo");
        } else {
            relogio.run();
        }
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }

    private void aprovar() {
        DeviceAuth.Callback callback = new DeviceAuth.Callback() {
            @Override
            public void onSuccess(String metodo) {
                finalizar("aprovado", metodo);
            }

            @Override
            public void onCancelado() {
                Toast.makeText(ConfirmationActivity.this, R.string.wifi_autorizacao_cancelada, Toast.LENGTH_LONG).show();
            }
        };
        DeviceAuth.confirmar(this, getString(R.string.confirm_aprovar_titulo),
                getString(R.string.confirm_aprovar_sub), callback);
    }

    private void perguntarNegar() {
        new AlertDialog.Builder(this)
                .setTitle(R.string.confirm_negado_titulo)
                .setMessage(R.string.confirm_negado_msg)
                .setPositiveButton(R.string.confirm_negar, (d, w) -> finalizar("negado", "usuario"))
                .setNegativeButton(R.string.confirm_nao, null)
                .show();
    }

    private void finalizar(final String status, String metodo) {
        if (pedido == null || decidido) return;
        decidido = true;
        handler.removeCallbacksAndMessages(null);
        ConfirmationStore.decidir(this, pedido.id, status, metodo);
        ConfirmationNotifier.cancelar(this, pedido.id);
        bloquear();

        if (pedido.ehTeste()) {
            mostrarResultado(getString(R.string.confirm_teste_resultado));
            return;
        }
        if ("expirado".equals(status)) {
            mostrarResultado(getString(R.string.confirm_expirado));
        } else if ("aprovado".equals(status)) {
            mostrarResultado(getString(R.string.confirm_aprovado_ok) + "\n" + getString(R.string.confirm_enviando));
        } else {
            mostrarResultado(getString(R.string.confirm_negado_ok) + "\n" + getString(R.string.confirm_enviando));
        }
        new Thread(() -> {
            final boolean ok = ConfirmationResponder.enviar(ConfirmationActivity.this, pedido, status, metodo);
            runOnUiThread(() -> {
                if (ok) {
                    mostrarResultado(getString(R.string.confirm_enviado));
                } else {
                    mostrarResultado(getString(R.string.confirm_guardado));
                }
            });
        }).start();
    }

    private void bloquear() {
        btnAprovar.setEnabled(false);
        btnNegar.setEnabled(false);
        btnAprovar.setVisibility(View.GONE);
        btnNegar.setVisibility(View.GONE);
        textPrazo.setVisibility(View.GONE);
    }

    private void mostrarResultado(String texto) {
        textResultado.setText(texto);
        textResultado.setVisibility(View.VISIBLE);
        btnFechar.setVisibility(View.VISIBLE);
    }
}
