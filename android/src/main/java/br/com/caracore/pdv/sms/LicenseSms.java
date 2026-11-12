package br.com.caracore.pdv.sms;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Regra de aceitação do SMS de licença.
 *
 * <p>
 * A chave só é aceita quando o número oficial está configurado e o remetente
 * confere com ele. Sem número configurado a mensagem é ignorada — antes a regra
 * aceitava qualquer remetente, e como nada no app preenchia esse número, todo
 * SMS com o prefixo gravava uma licença.
 * </p>
 */
public final class LicenseSms {

    public enum Motivo {
        ACEITA,
        NUMERO_NAO_CONFIGURADO,
        REMETENTE_DIVERGENTE,
        CHAVE_AUSENTE,
        CHAVE_INVALIDA
    }

    public static final class Resultado {
        private final Motivo motivo;
        private final String chave;

        Resultado(Motivo motivo, String chave) {
            this.motivo = motivo;
            this.chave = chave;
        }

        public Motivo getMotivo() {
            return motivo;
        }

        public String getChave() {
            return chave;
        }

        public boolean isAceita() {
            return motivo == Motivo.ACEITA;
        }
    }

    private static final Pattern PREFIXO_CHAVE =
            Pattern.compile("(?:CC-LICENSE|CARACORE-KEY):\\s*([^\\s]+)", Pattern.CASE_INSENSITIVE);
    private static final Pattern CHAVE_VALIDA =
            Pattern.compile("^CC-\\d{6}-[0-9a-fA-F]{8}$");

    public static final int DIGITOS_MINIMOS = 10;
    public static final int DIGITOS_MAXIMOS = 13;

    private LicenseSms() {
    }

    public static Resultado avaliar(String remetente, String corpo, String numeroOficial) {
        String chave = extrairChave(corpo);
        if (chave == null) {
            return new Resultado(Motivo.CHAVE_AUSENTE, null);
        }
        if (!CHAVE_VALIDA.matcher(chave).matches()) {
            return new Resultado(Motivo.CHAVE_INVALIDA, null);
        }
        String oficial = somenteDigitos(numeroOficial);
        if (!numeroValido(oficial)) {
            return new Resultado(Motivo.NUMERO_NAO_CONFIGURADO, null);
        }
        String origem = somenteDigitos(remetente);
        if (!remetenteConfere(origem, oficial)) {
            return new Resultado(Motivo.REMETENTE_DIVERGENTE, null);
        }
        return new Resultado(Motivo.ACEITA, chave);
    }

    public static boolean numeroValido(String numero) {
        String digitos = somenteDigitos(numero);
        return digitos.length() >= DIGITOS_MINIMOS && digitos.length() <= DIGITOS_MAXIMOS;
    }

    static boolean remetenteConfere(String origem, String oficial) {
        if (origem.isEmpty() || oficial.isEmpty()) {
            return false;
        }
        return origem.endsWith(oficial) || oficial.endsWith(origem);
    }

    static String somenteDigitos(String valor) {
        return valor == null ? "" : valor.replaceAll("\\D", "");
    }

    static String extrairChave(String corpo) {
        if (corpo == null) {
            return null;
        }
        Matcher m = PREFIXO_CHAVE.matcher(corpo);
        if (!m.find()) {
            return null;
        }
        String chave = m.group(1).trim();
        return chave.isEmpty() ? null : chave;
    }
}
