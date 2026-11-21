package br.com.caracore.pdv.sms;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * Le a caixa postal da ponte por IMAP4rev1 sobre TLS, do jeito que o Gaspar no
 * computador le: entra pela porta 993, procura os UID depois do ultimo lido e
 * pega o conteudo inteiro de cada recado sem tirar ninguem da caixa de nao lidos.
 *
 * Nada de biblioteca de terceiros: sao quatro comandos e o cuidado de ler o
 * literal byte a byte, porque o corpo cifrado nao pode chegar cortado.
 */
public final class ImapClient {

    /** Como abrir o soquete. Em producao e TLS; no teste e o servidor local. */
    public interface Fabrica {
        Socket abrir(String host, int porta) throws IOException;
    }

    /** O servidor respondeu NO/BAD, ou a conversa acabou no meio. */
    public static final class Recusa extends IOException {
        private static final long serialVersionUID = 1L;

        Recusa(String motivo) {
            super(motivo);
        }
    }

    private static final class Resposta {
        final List<String> linhas;
        final byte[] corpo;

        Resposta(List<String> linhas, byte[] corpo) {
            this.linhas = linhas;
            this.corpo = corpo;
        }
    }

    private final Socket soquete;
    private final InputStream entrada;
    private final OutputStream saida;
    private int etiqueta = 0;

    public ImapClient(Fabrica fabrica, String host, int porta, int timeoutMs) throws IOException {
        soquete = fabrica.abrir(host, porta);
        soquete.setSoTimeout(timeoutMs);
        entrada = soquete.getInputStream();
        saida = soquete.getOutputStream();
        saudacao();
    }

    public void login(String usuario, String senha) throws IOException {
        espera(enviar("LOGIN " + aspa(usuario) + " " + aspa(senha)), "o login");
    }

    public void selecionar(String caixa) throws IOException {
        String nome = caixa == null || caixa.trim().isEmpty() ? "INBOX" : caixa.trim();
        espera(enviar("SELECT " + aspa(nome)), "a selecao da caixa");
    }

    /** Os UID dos recados a partir de um UID (inclusive). Vazio quando nao ha nada novo. */
    public List<Integer> buscarUid(int desde) throws IOException {
        Resposta resposta = espera(enviar("UID SEARCH UID " + Math.max(1, desde) + ":*"), "a busca por UID");
        List<Integer> encontrados = new ArrayList<>();
        for (String linha : resposta.linhas) {
            if (!linha.startsWith("* SEARCH")) {
                continue;
            }
            String corpo = linha.substring("* SEARCH".length()).trim();
            if (corpo.isEmpty()) {
                continue;
            }
            for (String pedaco : corpo.split("\\s+")) {
                try {
                    encontrados.add(Integer.parseInt(pedaco));
                } catch (NumberFormatException ignorado) {
                    // o que nao e numero nao e UID
                }
            }
        }
        return encontrados;
    }

    /** O recado inteiro (cabecalhos e corpo), sem tirar ninguem da caixa de nao lidos. */
    public byte[] corpoDoUid(int uid) throws IOException {
        Resposta resposta = espera(enviar("UID FETCH " + uid + " (BODY.PEEK[])"), "a leitura do recado");
        if (resposta.corpo == null) {
            throw new Recusa("a caixa postal nao devolveu o conteudo do recado " + uid);
        }
        return resposta.corpo;
    }

    public void sair() {
        try {
            enviar("LOGOUT");
            linha();
        } catch (IOException ignorado) {
            // o servidor pode cair aqui; nao ha o que fazer
        } finally {
            try {
                soquete.close();
            } catch (IOException ignorado) {
                // ja estava fechado
            }
        }
    }

    // ------------------------------------------------------------------ fiacao

    private void saudacao() throws IOException {
        String linha = linha();
        if (linha == null) {
            throw new Recusa("a caixa postal nao disse oi");
        }
        if (!linha.startsWith("* OK")) {
            throw new Recusa("a caixa postal abriu de um jeito inesperado: " + resumo(linha));
        }
    }

    private String enviar(String comando) throws IOException {
        String tag = "a" + (++etiqueta);
        saida.write((tag + " " + comando + "\r\n").getBytes(StandardCharsets.UTF_8));
        saida.flush();
        return tag;
    }

    private Resposta espera(String tag, String descricao) throws IOException {
        List<String> linhas = new ArrayList<>();
        byte[] corpo = null;
        while (true) {
            String linha = linha();
            if (linha == null) {
                throw new Recusa("a caixa postal cortou a conversa durante " + descricao);
            }
            byte[] literal = literalNaLinha(linha);
            if (literal != null) {
                corpo = literal;
                continue;
            }
            if (linha.startsWith(tag + " ")) {
                String tipo = linha.substring(tag.length() + 1).trim().split("\\s+")[0];
                if (!"OK".equalsIgnoreCase(tipo)) {
                    throw new Recusa("a caixa postal recusou " + descricao + " (" + tipo + "): " + resumo(linha));
                }
                return new Resposta(linhas, corpo);
            }
            linhas.add(linha);
        }
    }

    /** Uma linha terminada em LF, sem o CR. Null quando o servidor fecha a conexao. */
    private String linha() throws IOException {
        ByteArrayOutputStream acumulada = new ByteArrayOutputStream();
        int b;
        while ((b = entrada.read()) >= 0) {
            if (b == '\n') {
                String texto = new String(acumulada.toByteArray(), StandardCharsets.US_ASCII);
                return texto.endsWith("\r") ? texto.substring(0, texto.length() - 1) : texto;
            }
            acumulada.write(b);
        }
        return acumulada.size() == 0 ? null : new String(acumulada.toByteArray(), StandardCharsets.US_ASCII);
    }

    /** Os bytes do literal quando a linha termina em {N}; null quando nao termina. */
    private byte[] literalNaLinha(String linha) throws IOException {
        int abre = linha.lastIndexOf('{');
        if (abre < 0 || !linha.endsWith("}")) {
            return null;
        }
        int tamanho;
        try {
            tamanho = Integer.parseInt(linha.substring(abre + 1, linha.length() - 1));
        } catch (NumberFormatException invalido) {
            return null;
        }
        if (tamanho < 0) {
            return null;
        }
        return ler(tamanho);
    }

    /** Le exatamente os bytes do literal: o corpo cifrado nao aceita pedaco perdido. */
    private byte[] ler(int quantidade) throws IOException {
        byte[] bruto = new byte[quantidade];
        int lido = 0;
        while (lido < quantidade) {
            int n = entrada.read(bruto, lido, quantidade - lido);
            if (n < 0) {
                throw new Recusa("a caixa postal cortou o conteudo do recado");
            }
            lido += n;
        }
        return bruto;
    }

    private static String aspa(String valor) {
        return "\"" + (valor == null ? "" : valor).replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }

    private static String resumo(String texto) {
        return texto.length() <= 120 ? texto : texto.substring(0, 120);
    }
}
