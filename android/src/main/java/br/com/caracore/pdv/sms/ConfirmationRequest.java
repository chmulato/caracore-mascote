package br.com.caracore.pdv.sms;

import java.util.Arrays;
import java.util.List;
import java.util.Locale;

/**
 * Pedido de confirmação enviado pelo computador para uma operação sensível do PDV.
 * Regras puras (sem Android) para poderem ser testadas sem aparelho.
 */
public final class ConfirmationRequest {

    public static final String TIPO_DESCONTO = "desconto";
    public static final String TIPO_CANCELAMENTO = "cancelamento";
    public static final String TIPO_SANGRIA = "sangria";
    private static final List<String> TIPOS = Arrays.asList(TIPO_DESCONTO, TIPO_CANCELAMENTO, TIPO_SANGRIA);

    public static final long VALOR_MAXIMO_CENTAVOS = 100_000_00L;
    public static final int PRAZO_MINIMO_SEGUNDOS = 30;
    public static final int PRAZO_MAXIMO_SEGUNDOS = 900;

    public final String id;
    public final String tipo;
    public final String referencia;
    public final long valorCentavos;
    public final String motivo;
    public final long expiraEmMillis;
    public final long recebidoEmMillis;
    public final String origem;

    public ConfirmationRequest(String id, String tipo, String referencia, long valorCentavos,
                               String motivo, long expiraEmMillis, long recebidoEmMillis, String origem) {
        this.id = id == null ? "" : id.trim();
        this.tipo = tipo == null ? "" : tipo.trim().toLowerCase(Locale.ROOT);
        this.referencia = referencia == null ? "" : referencia.trim();
        this.valorCentavos = valorCentavos;
        this.motivo = motivo == null ? "" : motivo.trim();
        this.expiraEmMillis = expiraEmMillis;
        this.recebidoEmMillis = recebidoEmMillis;
        this.origem = origem == null ? "" : origem.trim();
    }

    /** Devolve null quando o pedido é aceitável; caso contrário, o motivo recusado. */
    public String validar(long agoraMillis) {
        if (id.isEmpty() || id.length() > 64 || !id.matches("[A-Za-z0-9._-]+")) {
            return "identificador";
        }
        if (!TIPOS.contains(tipo)) {
            return "tipo";
        }
        if (referencia.isEmpty() || referencia.length() > 64) {
            return "referencia";
        }
        if (valorCentavos < 0 || valorCentavos > VALOR_MAXIMO_CENTAVOS) {
            return "valor";
        }
        if (motivo.length() > 200) {
            return "motivo";
        }
        long prazo = expiraEmMillis - agoraMillis;
        if (prazo < PRAZO_MINIMO_SEGUNDOS * 1000L || prazo > PRAZO_MAXIMO_SEGUNDOS * 1000L) {
            return "prazo";
        }
        return null;
    }

    public boolean expirado(long agoraMillis) {
        return agoraMillis >= expiraEmMillis;
    }

    public boolean ehTeste() {
        return "teste".equals(origem);
    }

    public String valorFormatado() {
        return "R$ " + String.format(new Locale("pt", "BR"), "%.2f", valorCentavos / 100.0);
    }

    public String tituloTipo() {
        switch (tipo) {
            case TIPO_DESCONTO:
                return "desconto";
            case TIPO_CANCELAMENTO:
                return "cancelamento";
            case TIPO_SANGRIA:
                return "sangria";
            default:
                return "operação";
        }
    }

    public String detalhes() {
        String motivoTexto = motivo.isEmpty() ? "sem motivo informado" : motivo;
        return "Venda/referência: " + referencia + "\n"
                + "Valor: " + valorFormatado() + "\n"
                + "Motivo: " + motivoTexto;
    }
}
