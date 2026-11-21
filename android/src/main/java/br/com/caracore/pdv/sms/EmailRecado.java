package br.com.caracore.pdv.sms;

import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;

/**
 * O recado cru que a caixa postal devolve, separado em cabecalhos e corpo.
 * A ponte so escreve texto puro numa parte, entao nao ha MIME de verdade para
 * desmontar: o que importa e o assunto (a marca da ponte), o From (para onde
 * volta o comprovante), o Message-ID (a prova de que ja lemos) e o corpo cifrado.
 */
public final class EmailRecado {

    private static final Charset CABECALHO = StandardCharsets.ISO_8859_1;

    private final String assunto;
    private final String enderecoDe;
    private final String mensagemId;
    private final String corpo;

    private EmailRecado(String assunto, String enderecoDe, String mensagemId, String corpo) {
        this.assunto = assunto;
        this.enderecoDe = enderecoDe;
        this.mensagemId = mensagemId;
        this.corpo = corpo;
    }

    public static EmailRecado ler(byte[] bruto) {
        String texto = bruto == null ? "" : new String(bruto, CABECALHO);
        int corte = fimDosCabecalhos(texto);
        String cabecalhos = corte < 0 ? texto : texto.substring(0, corte);
        String corpo = corte < 0 ? "" : texto.substring(pulaQuebras(texto, corte));
        return new EmailRecado(cabecalho(cabecalhos, "subject"), endereco(cabecalho(cabecalhos, "from")),
                semPontas(cabecalho(cabecalhos, "message-id")), corpo);
    }

    public String assunto() {
        return assunto;
    }

    /** O endereco para onde o comprovante volta; vazio quando o recado nao tem From utilisavel. */
    public String enderecoDe() {
        return enderecoDe;
    }

    public String mensagemId() {
        return mensagemId;
    }

    public String corpo() {
        return corpo;
    }

    private static int fimDosCabecalhos(String texto) {
        int a = texto.indexOf("\r\n\r\n");
        int b = texto.indexOf("\n\n");
        if (a < 0) {
            return b;
        }
        return b < 0 ? a : Math.min(a, b);
    }

    private static int pulaQuebras(String texto, int inicio) {
        int i = inicio;
        while (i < texto.length() && (texto.charAt(i) == '\r' || texto.charAt(i) == '\n')) {
            i++;
        }
        return i;
    }

    /** Procura o cabecalho pelo nome, sem diferenciar maiuscula, juntando as linhas dobradas. */
    private static String cabecalho(String bloco, String nome) {
        StringBuilder valor = new StringBuilder();
        boolean achado = false;
        for (String linha : bloco.split("\r?\n")) {
            if (linha.isEmpty()) {
                continue;
            }
            if ((linha.startsWith(" ") || linha.startsWith("\t")) && achado) {
                valor.append(' ').append(linha.trim());
                continue;
            }
            int doisPontos = linha.indexOf(':');
            if (doisPontos <= 0) {
                continue;
            }
            achado = linha.substring(0, doisPontos).trim().equalsIgnoreCase(nome);
            if (achado) {
                valor.setLength(0);
                valor.append(linha.substring(doisPontos + 1).trim());
            }
        }
        return valor.toString();
    }

    /** "Nome da Loja" <loja@pdv.example> vira so o endereco, em minusculas. */
    private static String endereco(String de) {
        String bruto = semPontas(de);
        int abre = de == null ? -1 : de.lastIndexOf('<');
        int fecha = de == null ? -1 : de.lastIndexOf('>');
        if (abre >= 0 && fecha > abre) {
            bruto = de.substring(abre + 1, fecha);
        }
        bruto = bruto.trim();
        return bruto.replaceAll("[^A-Za-z0-9._%+-@]", "").toLowerCase(java.util.Locale.US);
    }

    private static String semPontas(String valor) {
        return valor == null ? "" : valor.trim();
    }
}
