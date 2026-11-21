package br.com.caracore.pdv.sms;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.Build;

import java.io.IOException;

/**
 * Os ajustes da ponte de e-mail: para onde o celular olha e com que nome ele assina.
 * Nada de segredo aqui: a senha de app e a chave de pareamento de cada origem ficam
 * no {@link EmailKeystore}, cifradas por uma chave que nao sai do aparelho.
 */
public final class EmailPreferencias implements EmailBridge.Credenciais {

    private static final String PREFS = "gaspar_email_cfg";
    private static final String KEY_ATIVA = "ponte_ativa";
    private static final String KEY_HOST_CAIXA = "host_caixa";
    private static final String KEY_PORTA_CAIXA = "porta_caixa";
    private static final String KEY_HOST_SAIDA = "host_saida";
    private static final String KEY_PORTA_SAIDA = "porta_saida";
    private static final String KEY_STARTTLS = "saida_starttls";
    private static final String KEY_USUARIO = "usuario";
    private static final String KEY_CAIXA = "caixa";
    private static final String KEY_REMETENTE = "remetente";

    private final Context context;
    private final SharedPreferences prefs;

    public EmailPreferencias(Context context) {
        this.context = context.getApplicationContext();
        this.prefs = this.context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    /** A ponte comeca desligada: o lojista liga depois de configurar, do jeito da casa. */
    public boolean estaAtiva() {
        return prefs.getBoolean(KEY_ATIVA, false);
    }

    public void setAtiva(boolean ativa) {
        prefs.edit().putBoolean(KEY_ATIVA, ativa).apply();
    }

    /** true quando ha para onde ir e com o que entrar: sem isto a ponte nao se levanta. */
    public boolean estaConfigurada() {
        return !vazio(prefs.getString(KEY_HOST_CAIXA, null))
                && !vazio(prefs.getString(KEY_HOST_SAIDA, null))
                && !vazio(prefs.getString(KEY_USUARIO, null))
                && EmailKeystore.temSenhaDeApp(context);
    }

    public void salvarAjustes(String hostCaixa, int portaCaixa, String hostSaida, int portaSaida,
                              boolean starttls, String usuario, String caixa, String remetente) {
        String quem = limpo(usuario);
        String assinante = limpo(remetente);
        prefs.edit()
                .putString(KEY_HOST_CAIXA, limpo(hostCaixa))
                .putInt(KEY_PORTA_CAIXA, portaCaixa > 0 ? portaCaixa : 993)
                .putString(KEY_HOST_SAIDA, limpo(hostSaida))
                .putInt(KEY_PORTA_SAIDA, portaSaida > 0 ? portaSaida : 465)
                .putBoolean(KEY_STARTTLS, starttls)
                .putString(KEY_USUARIO, limpo(usuario))
                .putString(KEY_CAIXA, limpo(caixa))
                .putString(KEY_REMETENTE, assinante == null ? quem : assinante)
                .apply();
    }

    /** O que a ponte usa para abrir as duas conversas. */
    public EmailBridge.Configuracao configuracao() {
        EmailBridge.Configuracao ajustes = new EmailBridge.Configuracao();
        ajustes.hostDaCaixa = texto(KEY_HOST_CAIXA, "");
        ajustes.portaDaCaixa = prefs.getInt(KEY_PORTA_CAIXA, 993);
        ajustes.hostDaSaida = texto(KEY_HOST_SAIDA, "");
        ajustes.portaDaSaida = prefs.getInt(KEY_PORTA_SAIDA, 465);
        ajustes.starttls = prefs.getBoolean(KEY_STARTTLS, false);
        ajustes.usuario = texto(KEY_USUARIO, "");
        ajustes.caixa = texto(KEY_CAIXA, "");
        ajustes.remetente = texto(KEY_REMETENTE, ajustes.usuario);
        ajustes.nomeDoAparelho = nomeDoAparelho();
        return ajustes;
    }

    /** O que o painel mostra: o endereco, nunca a senha. */
    public String enderecoDaCaixa() {
        return texto(KEY_HOST_CAIXA, "");
    }

    public String enderecoDaSaida() {
        return texto(KEY_HOST_SAIDA, "");
    }

    public String usuario() {
        return texto(KEY_USUARIO, "");
    }

    public String caixa() {
        return texto(KEY_CAIXA, "");
    }

    // ------------------------------------------------------------------ credenciais

    @Override
    public String senhaDeApp() throws IOException {
        String senha = EmailKeystore.senhaDeApp(context);
        if (senha == null || senha.isEmpty()) {
            throw new IOException("a ponte de e-mail ainda nao tem senha de app neste celular");
        }
        return senha;
    }

    @Override
    public String chaveDaPonte(String origem) {
        // a mesma chave que abre o canal Wi-Fi daquela loja: parear uma vez vale para as duas portas
        return new SmsPreferences(context).getGatewaySecretFor(origem);
    }

    // ------------------------------------------------------------------ miudezas

    /** O nome que o celular assina no comprovante: o lojista reconhece o aparelho dele. */
    private static String nomeDoAparelho() {
        String modelo = GuardaDeLinhas.limpar(Build.MODEL);
        return modelo.isEmpty() ? "celular" : modelo;
    }

    private String texto(String chave, String padrao) {
        String valor = prefs.getString(chave, null);
        return valor == null || valor.trim().isEmpty() ? padrao : valor;
    }

    private static boolean vazio(String texto) {
        return texto == null || texto.trim().isEmpty();
    }

    private static String limpo(String texto) {
        String limpo = texto == null ? null : texto.trim();
        return limpo == null || limpo.isEmpty() ? null : limpo;
    }
}
