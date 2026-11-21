package br.com.caracore.pdv.sms;

/**
 * Os porteiros que todo pedido de SMS atravessa, seja ele vindo do Wi-Fi da loja
 * ou da ponte de e-mail. Um pedido so chega ao radio depois de passar por todos,
 * e na mesma ordem, para que os dois canais signifiquem a mesma coisa.
 *
 * Nao toca em classe do Android: quem guarda o estado e quem fala com o radio
 * chega por interface, o que permite conferir a ordem aqui mesmo, sem celular.
 */
public final class SmsDispatch {

    public static final int TEXTO_MAXIMO = 480;
    public static final int NUMERO_MINIMO = 10;
    public static final int NUMERO_MAXIMO = 15;

    public static final String STATUS_ACEITO = "aceito";
    public static final String STATUS_REPETIDO = "repetido";

    public static final String ERRO_SEM_IDENTIFICADOR = "pedido sem identificador";
    public static final String ERRO_APP_INATIVO = "app inativo";
    public static final String ERRO_INCOMPLETO = "pedido incompleto";
    public static final String ERRO_NUMERO = "numero invalido";
    public static final String ERRO_TEXTO = "mensagem acima de 480 caracteres";
    public static final String ERRO_REPETIDO = "pedido repetido";
    public static final String ERRO_SEM_PERMISSAO = "permissao de SMS negada";
    public static final String ERRO_COTA = "limite diario do celular atingido";
    public static final String ERRO_RADIO = "falha ao processar o pedido";

    /** O que o celular sabe sobre si mesmo no momento do pedido. */
    public interface Estado {
        boolean ativo();

        boolean jaConhecido(String jobId);

        long ultimaSequencia();

        boolean consumirCota();

        boolean podeEnviarSms();

        void registrar(String jobId, long sequencia);
    }

    /** O radio do celular, ja com os comprovantes de entrega armados. */
    public interface Radio {
        void enviar(String numero, String texto, String jobId) throws Exception;
    }

    /** O veredito do gate: aceito, repetido ou o motivo da recusa. */
    public static final class Ack {
        private final boolean ok;
        private final String status;
        private final String erro;

        private Ack(boolean ok, String status, String erro) {
            this.ok = ok;
            this.status = status;
            this.erro = erro;
        }

        public boolean ok() {
            return ok;
        }

        public String status() {
            return status;
        }

        public String erro() {
            return erro;
        }

        public boolean repetido() {
            return STATUS_REPETIDO.equals(status);
        }
    }

    private SmsDispatch() {
    }

    public static Ack enviar(Estado estado, Radio radio, String jobId, long sequencia, String numero, String texto) {
        String identificador = jobId == null ? "" : jobId.trim();
        if (identificador.isEmpty()) {
            return recusa(ERRO_SEM_IDENTIFICADOR);
        }
        if (estado == null || radio == null) {
            return recusa(ERRO_RADIO);
        }
        if (!estado.ativo()) {
            return recusa(ERRO_APP_INATIVO);
        }
        if (numero == null || numero.trim().isEmpty() || texto == null) {
            return recusa(ERRO_INCOMPLETO);
        }
        String destino = numero.trim().replaceAll("[^+0-9]", "");
        if (destino.length() < NUMERO_MINIMO || destino.length() > NUMERO_MAXIMO) {
            return recusa(ERRO_NUMERO);
        }
        if (texto.length() > TEXTO_MAXIMO) {
            return recusa(ERRO_TEXTO);
        }
        if (estado.jaConhecido(identificador)) {
            return new Ack(true, STATUS_REPETIDO, null);
        }
        if (sequencia > 0 && sequencia <= estado.ultimaSequencia()) {
            return recusa(ERRO_REPETIDO);
        }
        if (!estado.podeEnviarSms()) {
            return recusa(ERRO_SEM_PERMISSAO);
        }
        if (!estado.consumirCota()) {
            return recusa(ERRO_COTA);
        }
        try {
            radio.enviar(destino, texto, identificador);
        } catch (Exception falha) {
            return recusa(ERRO_RADIO);
        }
        estado.registrar(identificador, sequencia);
        return new Ack(true, STATUS_ACEITO, null);
    }

    private static Ack recusa(String motivo) {
        return new Ack(false, null, motivo);
    }
}
