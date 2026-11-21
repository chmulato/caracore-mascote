package br.com.caracore.pdv.sms;

import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.util.regex.Pattern;

/**
 * O que circula pela ponte de e-mail: um JSON pequeno, cifrado com a chave do
 * pareamento e escrito em base64 dentro do corpo de um recado de texto.
 *
 * As regras sao as mesmas do Gaspar no computador (gaspar/messaging/transports/
 * smtp_email.py): sem espacos no corpo, versao 1 e tipo conhecido, ou nada entra.
 * Esta classe nao toca em API do Android, para dar para conferir as regras sem celular.
 */
public final class EmailEnvelope {

    public static final String ASSUNTO_PREFIXO = "GASPAR";
    public static final int VERSAO = 1;
    public static final String DOMINIO_MESSAGE_ID = "gaspar.local";

    public static final String TIPO_PEDIDO = "pedido";
    public static final String TIPO_COMPROVANTE = "comprovante";
    public static final String TIPO_RESPOSTA = "resposta";

    public static final String ESTADO_ENVIADO = "enviado";
    public static final String ESTADO_ENTREGUE = "entregue";
    public static final String ESTADO_FALHOU = "falhou";

    /** IV (12) + etiqueta GCM (16): menos que isso nao pode ser envelope. */
    private static final int BLOB_MINIMO = 28;

    private static final Pattern BASE64_COMPACTO = Pattern.compile("^[A-Za-z0-9+/]+={0,2}$");
    private static final Pattern TODA_LACUNA = Pattern.compile("(?U)\\s");

    /** O recado nao e da ponte. O motivo vai para o painel, nunca o conteudo. */
    public static final class Recusa extends Exception {
        private static final long serialVersionUID = 1L;

        Recusa(String motivo) {
            super(motivo);
        }
    }

    private EmailEnvelope() {
    }

    /**
     * O servidor de e-mail quebra o corpo em colunas e pode acrescentar quebras.
     * Junta tudo antes de decodificar, do mesmo jeito que o computador faz.
     */
    public static String corpoLimpo(String texto) throws Recusa {
        String compacto = texto == null ? "" : TODA_LACUNA.matcher(texto).replaceAll("");
        if (compacto.isEmpty()) {
            throw new Recusa("corpo de e-mail vazio");
        }
        if (!BASE64_COMPACTO.matcher(compacto).matches()) {
            throw new Recusa("corpo de e-mail nao e base64");
        }
        return compacto;
    }

    /** Abre o envelope cifrado. So passa o que foi escrito com esta chave e na versao certa. */
    public static JSONObject abrir(GatewayCrypto cifra, byte[] blob) throws Recusa {
        if (blob == null || blob.length < BLOB_MINIMO) {
            throw new Recusa("corpo de e-mail curto demais");
        }
        JSONObject dados;
        try {
            dados = new JSONObject(new String(cifra.decrypt(blob), StandardCharsets.UTF_8));
        } catch (Exception falha) {
            throw new Recusa("envelope nao abre com esta chave");
        }
        if (dados.optInt("v", 0) != VERSAO) {
            throw new Recusa("versao de envelope desconhecida");
        }
        String tipo = dados.optString("tipo", "");
        if (!TIPO_PEDIDO.equals(tipo) && !TIPO_COMPROVANTE.equals(tipo) && !TIPO_RESPOSTA.equals(tipo)) {
            throw new Recusa("tipo de envelope desconhecido");
        }
        return dados;
    }

    /** O comprovante que o celular devolve: o mesmo JSON que o Gaspar le no computador. */
    public static JSONObject comprovante(String referencia, String para, String estado,
                                         long quandoEmSegundos, String dispositivo) throws Recusa {
        JSONObject corpo = new JSONObject();
        try {
            corpo.put("v", VERSAO);
            corpo.put("tipo", TIPO_COMPROVANTE);
            corpo.put("referencia", referencia == null ? "" : referencia);
            corpo.put("para", para == null ? "" : para);
            corpo.put("estado", estado == null ? "" : estado);
            corpo.put("quando", (double) quandoEmSegundos);
            corpo.put("dispositivo", dispositivo == null ? "" : dispositivo);
        } catch (org.json.JSONException falha) {
            throw new Recusa("nao deu para montar o comprovante");
        }
        return corpo;
    }

    public static byte[] selar(GatewayCrypto cifra, JSONObject corpo) throws Recusa {
        if (cifra == null || corpo == null) {
            throw new Recusa("nada para selar");
        }
        try {
            return cifra.encrypt(corpo.toString().getBytes(StandardCharsets.UTF_8));
        } catch (Exception falha) {
            throw new Recusa("nao deu para cifrar o comprovante");
        }
    }

    public static String assunto(String origem, String referencia) {
        return ASSUNTO_PREFIXO + " " + origem + " " + referencia;
    }

    public static boolean ehDaPonte(String assunto) {
        return assunto != null && assunto.startsWith(ASSUNTO_PREFIXO);
    }

    /** A origem declarada no assunto: GASPAR PDV abc -> PDV. */
    public static String origemNoAssunto(String assunto) {
        if (!ehDaPonte(assunto)) {
            return "";
        }
        String pedaco = assunto.substring(ASSUNTO_PREFIXO.length()).trim();
        int espaco = pedaco.indexOf(' ');
        return espaco < 0 ? pedaco : pedaco.substring(0, espaco);
    }

    /** O que o radio conta vira o estado que a ponte conhece. O resto nao e comprovante. */
    public static String estadoDoRadio(String status) {
        if (SmsStatusReceiver.ESTADO_SENT.equals(status)) {
            return ESTADO_ENVIADO;
        }
        if (SmsStatusReceiver.ESTADO_DELIVERED.equals(status)) {
            return ESTADO_ENTREGUE;
        }
        if (SmsStatusReceiver.ESTADO_FAILED.equals(status)) {
            return ESTADO_FALHOU;
        }
        return null;
    }

    public static String texto(JSONObject dados, String campo) {
        if (dados == null || dados.isNull(campo)) {
            return "";
        }
        return dados.optString(campo, "");
    }
}
