package br.com.caracore.pdv.sms;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import java.io.IOException;

/**
 * A tela da ponte de e-mail, na linguagem de quem cuida da loja.
 *
 * O lojista ve tres coisas: se o celular esta escutando, o que falta para comecar a
 * escutar e se a caixa abre de verdade. Os enderecos dos servidores ficam atras de
 * "mais opcoes": quem contrata o e-mail costuma saber os dois de cor, e quem nao
 * sabe recebe-os do suporte junto com a senha.
 *
 * O botao de teste so entra e sai: abre a caixa, confirma a senha, fecha. Ele nao le
 * recado nenhum, nao manda pedido ao radio e nao escreve nada na saida, para que
 * conferir a configuracao nunca dispare uma mensagem de verdade.
 */
public class EmailActivity extends Activity {

    private static final int TEMPO_TESTE_MS = 15_000;

    private EmailPreferencias ajustes;
    private Switch switchAtiva;
    private TextView textSenha;
    private TextView textEstado;
    private TextView textFila;
    private TextView textTeste;
    private Button btnTestar;

    private EditText editUsuario;
    private EditText editSenha;
    private EditText editEntrada;
    private EditText editEntradaPorta;
    private EditText editSaida;
    private EditText editSaidaPorta;
    private EditText editCaixa;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_email);

        ajustes = new EmailPreferencias(this);
        switchAtiva = findViewById(R.id.switchEmailAtiva);
        textSenha = findViewById(R.id.textEmailSenha);
        textEstado = findViewById(R.id.textEmailEstado);
        textFila = findViewById(R.id.textEmailFila);
        textTeste = findViewById(R.id.textEmailTeste);
        btnTestar = findViewById(R.id.btnEmailTestar);
        editUsuario = findViewById(R.id.editEmailUsuario);
        editSenha = findViewById(R.id.editEmailSenha);
        editEntrada = findViewById(R.id.editEmailEntrada);
        editEntradaPorta = findViewById(R.id.editEmailEntradaPorta);
        editSaida = findViewById(R.id.editEmailSaida);
        editSaidaPorta = findViewById(R.id.editEmailSaidaPorta);
        editCaixa = findViewById(R.id.editEmailCaixa);

        preencher();
        atualizarEstado();

        if (switchAtiva != null) {
            switchAtiva.setChecked(ajustes.estaAtiva());
            switchAtiva.setOnCheckedChangeListener((view, marcada) -> ligar(marcada));
        }
        Button btnAvancado = findViewById(R.id.btnEmailAvancado);
        View avancado = findViewById(R.id.emailAvancado);
        if (btnAvancado != null && avancado != null) {
            btnAvancado.setOnClickListener(v -> avancado.setVisibility(
                    avancado.getVisibility() == View.VISIBLE ? View.GONE : View.VISIBLE));
        }
        Button btnSalvar = findViewById(R.id.btnEmailSalvar);
        if (btnSalvar != null) {
            btnSalvar.setOnClickListener(v -> salvar());
        }
        if (btnTestar != null) {
            btnTestar.setOnClickListener(v -> testar());
        }
        Button btnVoltar = findViewById(R.id.btnEmailVoltar);
        if (btnVoltar != null) {
            btnVoltar.setOnClickListener(v -> finish());
        }
    }

    /** O que ja esta guardado volta para a tela, menos a senha: essa so se troca. */
    private void preencher() {
        EmailBridge.Configuracao cfg = ajustes.configuracao();
        if (editUsuario != null) {
            editUsuario.setText(cfg.usuario);
        }
        if (editEntrada != null) {
            editEntrada.setText(cfg.hostDaCaixa);
        }
        if (editEntradaPorta != null) {
            editEntradaPorta.setText(String.valueOf(cfg.portaDaCaixa));
        }
        if (editSaida != null) {
            editSaida.setText(cfg.hostDaSaida);
        }
        if (editSaidaPorta != null) {
            editSaidaPorta.setText(String.valueOf(cfg.portaDaSaida));
        }
        if (editCaixa != null) {
            editCaixa.setText(cfg.caixa);
        }
    }

    private void salvar() {
        String usuario = texto(editUsuario);
        String entrada = texto(editEntrada);
        String saida = texto(editSaida);
        if (usuario.isEmpty() || entrada.isEmpty() || saida.isEmpty()) {
            Toast.makeText(this, R.string.email_faltam_dados, Toast.LENGTH_LONG).show();
            return;
        }
        String senha = texto(editSenha);
        if (!senha.isEmpty() && !EmailKeystore.guardarSenhaDeApp(this, senha)) {
            Toast.makeText(this, R.string.email_senha_nenhuma, Toast.LENGTH_LONG).show();
            return;
        }
        if (!senha.isEmpty() && editSenha != null) {
            editSenha.setText("");
        }
        ajustes.salvarAjustes(entrada, porta(editEntradaPorta, 993), saida, porta(editSaidaPorta, 465),
                false, usuario, texto(editCaixa), null);
        atualizarEstado();
        Toast.makeText(this, R.string.email_salvo, Toast.LENGTH_LONG).show();
        PdvSmsLogger.i("EmailActivity", "Ajustes da ponte guardados.");
    }

    private void ligar(boolean marcada) {
        if (marcada && !ajustes.estaConfigurada()) {
            if (switchAtiva != null) {
                switchAtiva.setChecked(false);
            }
            Toast.makeText(this, EmailKeystore.temSenhaDeApp(this)
                            ? R.string.email_faltam_dados : R.string.email_sem_senha,
                    Toast.LENGTH_LONG).show();
            return;
        }
        ajustes.setAtiva(marcada);
        if (marcada) {
            startService(new Intent(this, EmailPonteServico.class));
        } else {
            stopService(new Intent(this, EmailPonteServico.class));
        }
        atualizarEstado();
    }

    private void atualizarEstado() {
        if (textSenha != null) {
            textSenha.setText(EmailKeystore.temSenhaDeApp(this)
                    ? R.string.email_senha_guardada : R.string.email_senha_nenhuma);
        }
        boolean ativa = ajustes.estaAtiva();
        if (textEstado != null) {
            int recurso = !ativa ? R.string.email_estado_off
                    : ajustes.estaConfigurada() ? R.string.email_estado_on : R.string.email_estado_incompleto;
            textEstado.setText(recurso);
            textEstado.setTextColor(getResources().getColor(
                    ativa && ajustes.estaConfigurada() ? R.color.status_on : R.color.status_off, getTheme()));
        }
        if (textFila != null) {
            int naFila = new EmailMemoria(new PreferenciasChaveValor(this)).comprovantesNaFila();
            textFila.setText(naFila == 0 ? getString(R.string.email_fila_vazia)
                    : getString(R.string.email_fila, naFila));
        }
    }

    /** Entra na caixa e fala com a saida sem mandar nada: prova que a configuracao abre. */
    private void testar() {
        final EmailBridge.Configuracao cfg = ajustes.configuracao();
        if (cfg.hostDaCaixa.isEmpty() || cfg.usuario.isEmpty() || !EmailKeystore.temSenhaDeApp(this)) {
            mostrarTeste(getString(R.string.email_teste_entrada_sem));
            return;
        }
        btnTestar.setEnabled(false);
        mostrarTeste(getString(R.string.email_testando));
        new Thread(() -> {
            String senha = EmailKeystore.senhaDeApp(this);
            TlsDaPonte fabricas = new TlsDaPonte();
            try {
                ImapClient caixa = new ImapClient(fabricas.caixa(), cfg.hostDaCaixa,
                        cfg.portaDaCaixa, TEMPO_TESTE_MS);
                try {
                    caixa.login(cfg.usuario, senha);
                    caixa.selecionar(cfg.caixa);
                } finally {
                    caixa.sair();
                }
            } catch (IOException caiu) {
                devolverTeste(getString(R.string.email_teste_falha_entrada,
                        cfg.hostDaCaixa, cfg.portaDaCaixa));
                return;
            }
            try {
                SmtpClient saida = new SmtpClient(new B64DoAparelho());
                try {
                    saida.conectar(fabricas.saida(), cfg.hostDaSaida, cfg.portaDaSaida,
                            cfg.starttls, cfg.nomeDoAparelho);
                    saida.entrar(cfg.usuario, senha);
                } finally {
                    saida.sair();
                }
            } catch (IOException caiu) {
                devolverTeste(getString(R.string.email_teste_falha_saida,
                        cfg.hostDaSaida, cfg.portaDaSaida));
                return;
            }
            devolverTeste(getString(R.string.email_teste_ok));
        }).start();
    }

    private void devolverTeste(String mensagem) {
        runOnUiThread(() -> {
            if (btnTestar != null) {
                btnTestar.setEnabled(true);
            }
            mostrarTeste(mensagem);
        });
    }

    private void mostrarTeste(String mensagem) {
        if (textTeste == null) {
            return;
        }
        textTeste.setText(mensagem);
        textTeste.setVisibility(View.VISIBLE);
    }

    private static String texto(EditText campo) {
        return campo == null || campo.getText() == null ? "" : campo.getText().toString().trim();
    }

    private static int porta(EditText campo, int padrao) {
        try {
            int valor = Integer.parseInt(texto(campo));
            return valor > 0 && valor < 65536 ? valor : padrao;
        } catch (RuntimeException invalido) {
            return padrao;
        }
    }
}
