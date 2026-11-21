package br.com.caracore.pdv.sms;

import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

/**
 * O caminho por onde cada pedido entrou, para que o comprovante volte pelo mesmo.
 *
 * O radio do celular avisa a entrega minutos depois de o pedido chegar, e o aviso
 * chega sem dizer de onde veio: so o identificador. Sem esta trilha, um pedido que
 * entrou pela ponte de e-mail voltaria pelo Wi-Fi (que naquele momento nao existe,
 * porque a loja esta na rua) e o comprovante se perderia.
 *
 * O que nao tem trilha e o comportamento de sempre: o pareamento unico pelo Wi-Fi.
 */
public final class TrilhaDoPedido {

    public static final String CANAL_WIFI = "wifi";
    public static final String CANAL_EMAIL = "email";

    /** Pedidos acompanhados: os mais velhos caem, como na guarda da ponte. */
    static final int LIMITE = 300;

    private static final String CHAVE = "gaspar.pedido.trilha";

    /** Para onde e como devolver o estado de um pedido. */
    public static final class Registro {
        public final String jobId;
        public final String origem;
        public final String canal;
        public final String para;
        /** O endereco a responder: a caixa de quem escreveu, vazia no Wi-Fi. */
        public final String destino;

        Registro(String jobId, String origem, String canal, String para, String destino) {
            this.jobId = jobId;
            this.origem = origem;
            this.canal = canal;
            this.para = para;
            this.destino = destino;
        }

        public boolean porEmail() {
            return CANAL_EMAIL.equals(canal);
        }
    }

    private final ChaveValor store;
    private final List<Registro> trilhas = new ArrayList<>();

    public TrilhaDoPedido(ChaveValor store) {
        this.store = store;
        recarregar();
    }

    /** Registra o caminho do pedido. Chamar de novo com o mesmo identifica atualiza. */
    public void registrar(String jobId, String origem, String canal, String para, String destino) {
        String id = GuardaDeLinhas.limpar(jobId);
        if (id.isEmpty() || canal == null) {
            return;
        }
        recarregar();
        remover(id);
        trilhas.add(new Registro(id, GuardaDeLinhas.limpar(origem), canal,
                GuardaDeLinhas.limpar(para), GuardaDeLinhas.limpar(destino)));
        GuardaDeLinhas.aparar(trilhas, LIMITE);
        guardar();
    }

    /** Null quando o pedido nao passou por aqui: vale o caminho de sempre. */
    public Registro de(String jobId) {
        recarregar();
        String id = GuardaDeLinhas.limpar(jobId);
        for (Registro registro : trilhas) {
            if (registro.jobId.equals(id)) {
                return registro;
            }
        }
        return null;
    }

    /** Quantos caminhos a barra lembra. */
    public int tamanho() {
        recarregar();
        return trilhas.size();
    }

    // ------------------------------------------------------------------ miudezas

    private void recarregar() {
        trilhas.clear();
        for (String linha : GuardaDeLinhas.ler(store.texto(CHAVE))) {
            Registro registro = paraLinha(linha);
            if (registro != null) {
                trilhas.add(registro);
            }
        }
        GuardaDeLinhas.aparar(trilhas, LIMITE);
    }

    private void guardar() {
        List<String> linhas = new ArrayList<>();
        for (Registro registro : trilhas) {
            linhas.add(linhaDe(registro));
        }
        store.gravarTexto(CHAVE, GuardaDeLinhas.escrever(linhas));
    }

    private void remover(String jobId) {
        for (int i = trilhas.size() - 1; i >= 0; i--) {
            if (trilhas.get(i).jobId.equals(jobId)) {
                trilhas.remove(i);
            }
        }
    }

    private String linhaDe(Registro r) {
        JSONObject corpo = new JSONObject();
        try {
            corpo.put("i", r.jobId);
            corpo.put("o", r.origem);
            corpo.put("c", r.canal);
            corpo.put("n", r.para);
            corpo.put("d", r.destino);
        } catch (org.json.JSONException nuncaAcontece) {
            return "{}";
        }
        return corpo.toString();
    }

    /** Null quando a linha nao e uma trilha: fica de fora sem travar a volta. */
    private Registro paraLinha(String linha) {
        try {
            JSONObject corpo = new JSONObject(linha);
            String id = corpo.optString("i", "");
            String canal = corpo.optString("c", "");
            if (id.isEmpty() || canal.isEmpty()) {
                return null;
            }
            return new Registro(id, corpo.optString("o", ""), canal,
                    corpo.optString("n", ""), corpo.optString("d", ""));
        } catch (Exception naoAbriu) {
            return null;
        }
    }
}
