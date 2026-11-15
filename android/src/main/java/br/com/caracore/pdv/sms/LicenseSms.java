package br.com.caracore.pdv.sms;

import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Regra da chave de licença digitada ou colada na tela de configuração.
 * Aceita a chave sozinha ou o SMS inteiro ("CC-LICENSE: ..."), sem ler a caixa de mensagens.
 */
public final class LicenseSms {

    private static final Pattern PREFIXO_CHAVE =
            Pattern.compile("(?:CC-LICENSE|CARACORE-KEY):\\s*([^\\s]+)", Pattern.CASE_INSENSITIVE);
    private static final Pattern CHAVE_VALIDA =
            Pattern.compile("^CC-\\d{6}-[0-9a-fA-F]{8}$");

    private LicenseSms() {
    }

    /**
     * Devolve a chave no formato CC-YYYYMM-hex8, ou null quando o texto não traz uma chave válida.
     */
    public static String chaveDe(String texto) {
        if (texto == null) {
            return null;
        }
        String bruto = texto.trim();
        if (bruto.isEmpty()) {
            return null;
        }
        Matcher m = PREFIXO_CHAVE.matcher(bruto);
        String chave = m.find() ? m.group(1).trim() : primeiroToken(bruto);
        if (chave == null || chave.length() < 4) {
            return null;
        }
        String normalizada = "CC-" + chave.substring(3);
        return CHAVE_VALIDA.matcher(normalizada).matches() ? normalizada : null;
    }

    private static String primeiroToken(String texto) {
        int fim = texto.indexOf(' ');
        return fim < 0 ? texto : texto.substring(0, fim);
    }
}
