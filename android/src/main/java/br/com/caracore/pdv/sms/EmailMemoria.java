package br.com.caracore.pdv.sms;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * O que a ponte aprendeu entre uma volta e outra, guardado em texto sobre
 * {@link ChaveValor}. Sao tres coisas: ate onde a caixa foi lida, quais recados
 * ja abriram e quais comprovantes ainda faltam sair.
 *
 * Os tetos e a ordem de descarte sao os mesmos do Gaspar no computador
 * (gaspar/messaging/transports/smtp_email.py): os mais velhos saem primeiro. Uma
 * linha que nao abre nao derruba a volta: o resto da fila segue, e a linha ruim sai
 * na proxima escrita.
 *
 * A guarda e escrita por mais de uma mao no celular: o servico que roda a ponte e o
 * receptor do radio, que anota o comprovante da entrega minutos depois. Por isso cada
 * leitura e cada mudanca voltam na guarda antes de mexer: sem isto o servico poderia
 * reescrever a fila do jeito que a viu e deitar fora o comprovante que acabou de
 * entrar.
 */
public final class EmailMemoria implements EmailBridge.Memoria {

    /** Carimbos de recado ja aberto: os mais velhos caem depois deste tanto. */
    static final int LIMITE_CARIMBOS = 400;
    /** Comprovantes a devolver pela saida. */
    static final int LIMITE_FILA = 200;

    private static final String CHAVE_UID = "gaspar.email.uid";
    private static final String CHAVE_CARIMBOS = "gaspar.email.carimbos";
    private static final String CHAVE_FILA = "gaspar.email.fila";

    private final ChaveValor store;
    private final List<String> carimbos = new ArrayList<>();
    private final List<EmailBridge.Comprovante> fila = new ArrayList<>();
    private int uidLido;
    /** true quando a guarda tinha linha que nao abriu: ela sai na proxima escrita. */
    private boolean linhaRuim;

    public EmailMemoria(ChaveValor store) {
        this.store = store;
        recarregar();
    }

    // ------------------------------------------------------------------ caixa

    @Override
    public int ultimoUid() {
        recarregar();
        return uidLido;
    }

    @Override
    public void marcarUid(int uid) {
        recarregar();
        if (uid > uidLido) {
            uidLido = uid;
            store.gravarTexto(CHAVE_UID, String.valueOf(uid));
        }
    }

    @Override
    public boolean jaLido(String mensagemId) {
        recarregar();
        return mensagemId != null && carimbos.contains(GuardaDeLinhas.limpar(mensagemId));
    }

    @Override
    public void marcarLido(String mensagemId) {
        recarregar();
        String carimbo = GuardaDeLinhas.limpar(mensagemId);
        if (carimbo.isEmpty() || carimbos.contains(carimbo)) {
            return;
        }
        carimbos.add(carimbo);
        GuardaDeLinhas.aparar(carimbos, LIMITE_CARIMBOS);
        store.gravarTexto(CHAVE_CARIMBOS, GuardaDeLinhas.escrever(carimbos));
    }

    // ------------------------------------------------------------------ fila

    @Override
    public void anotarComprovante(EmailBridge.Comprovante comprovante) {
        if (comprovante == null || comprovante.referencia.isEmpty()) {
            // sem referencia nao ha para quem devolver: a fila nao pode crescer a toa
            return;
        }
        recarregar();
        // o estado mais novo do mesmo pedido e o que vale: o anterior sai da fila
        removerDaFila(comprovante.referencia);
        fila.add(comprovante);
        GuardaDeLinhas.aparar(fila, LIMITE_FILA);
        store.gravarTexto(CHAVE_FILA, GuardaDeLinhas.escrever(linhasDaFila()));
    }

    @Override
    public List<EmailBridge.Comprovante> comprovantesPendentes() {
        recarregar();
        // copia defensiva: a ponte percorre a fila enquanto ela muda
        return new ArrayList<>(fila);
    }

    @Override
    public void esquecerComprovante(String referencia) {
        if (referencia == null || referencia.isEmpty()) {
            return;
        }
        recarregar();
        if (removerDaFila(referencia) || linhaRuim) {
            store.gravarTexto(CHAVE_FILA, GuardaDeLinhas.escrever(linhasDaFila()));
        }
    }

    // ------------------------------------------------------------------ painel

    /** Quantos comprovantes esperam saida. */
    public int comprovantesNaFila() {
        recarregar();
        return fila.size();
    }

    /** Quantos carimbos a ponte lembra. */
    public int carimbosGuardados() {
        recarregar();
        return carimbos.size();
    }

    // ------------------------------------------------------------------ miudezas

    private void recarregar() {
        uidLido = inteiro(store.texto(CHAVE_UID));
        carimbos.clear();
        carimbos.addAll(GuardaDeLinhas.ler(store.texto(CHAVE_CARIMBOS)));
        GuardaDeLinhas.aparar(carimbos, LIMITE_CARIMBOS);
        fila.clear();
        linhaRuim = false;
        for (String linha : GuardaDeLinhas.ler(store.texto(CHAVE_FILA))) {
            EmailBridge.Comprovante comprovante = linhaPara(linha);
            if (comprovante != null) {
                fila.add(comprovante);
            } else {
                linhaRuim = true;
            }
        }
        GuardaDeLinhas.aparar(fila, LIMITE_FILA);
    }

    private boolean removerDaFila(String referencia) {
        boolean mudou = false;
        for (int i = fila.size() - 1; i >= 0; i--) {
            if (fila.get(i).referencia.equals(referencia)) {
                fila.remove(i);
                mudou = true;
            }
        }
        return mudou;
    }

    private List<String> linhasDaFila() {
        List<String> linhas = new ArrayList<>();
        for (EmailBridge.Comprovante c : fila) {
            linhas.add(linhaDe(c));
        }
        return linhas;
    }

    private String linhaDe(EmailBridge.Comprovante c) {
        JSONObject corpo = new JSONObject();
        try {
            corpo.put("o", c.origem);
            corpo.put("r", c.referencia);
            corpo.put("p", c.para);
            corpo.put("e", c.estado);
            corpo.put("d", c.destino);
            corpo.put("q", c.quandoEmSegundos);
        } catch (org.json.JSONException nuncaAcontece) {
            return "{}";
        }
        return corpo.toString();
    }

    /** Null quando a linha nao e um comprovante: ela sai da guarda sem travar a volta. */
    private EmailBridge.Comprovante linhaPara(String linha) {
        try {
            JSONObject corpo = new JSONObject(linha);
            String referencia = corpo.optString("r", "");
            if (referencia.isEmpty()) {
                return null;
            }
            return new EmailBridge.Comprovante(corpo.optString("o", ""), referencia,
                    corpo.optString("p", ""), corpo.optString("e", ""),
                    corpo.optString("d", ""), (long) corpo.optDouble("q", 0d));
        } catch (Exception naoAbriu) {
            // no Android o JSONException e de execucao; na maquina de testes e verificado
            return null;
        }
    }

    private static int inteiro(String texto) {
        try {
            return Math.max(0, Integer.parseInt(texto.trim()));
        } catch (RuntimeException invalido) {
            return 0;
        }
    }
}
