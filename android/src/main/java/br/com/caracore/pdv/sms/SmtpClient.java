package br.com.caracore.pdv.sms;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

/**
 * Manda o comprovante do SMS pela saida SMTP, sobre TLS (porta 465) ou com
 * STARTTLS (porta 587), entrando com a Senha de App. As etapas sao as mesmas
 * que o Gaspar no computador registra, para os dois lados contarem a mesma historia:
 * conexao, login, recusa e entrega.
 */
public final class SmtpClient {

    public static final String ETAPA_CONEXAO = "conexao";
    public static final String ETAPA_LOGIN = "login";
    /** O servidor disse nao com codigo: ele garante que o pedido nao entrou. */
    public static final String ETAPA_RECUSA = "recusa";
    /** O corpo saiu e a resposta nao voltou: pode ter entrado, duvida nao reenvio. */
    public static final String ETAPA_ENTREGA = "entrega";

    /** Como abrir o soquete. Em producao e TLS; no teste e o servidor local. */
    public interface Fabrica {
        Socket abrir(String host, int porta) throws IOException;
    }

    /** A conversa caiu, e em que ponto ela caiu. */
    public static final class Queda extends IOException {
        private static final long serialVersionUID = 1L;
        private final String etapa;

        Queda(String etapa, String motivo) {
            super(motivo);
            this.etapa = etapa;
        }

        public String etapa() {
            return etapa;
        }
    }

    private final B64 base64;
    private Socket soquete;
    private InputStream entrada;
    private OutputStream saida;

    public SmtpClient(B64 base64) {
        this.base64 = base64;
    }

    /**
     * O recado de texto puro que a ponte escreve: cabecalhos ASCII e o envelope
     * cifrado no corpo, um em cada linha, do jeito que o computador le.
     */
    public static String montar(String de, String para, String assunto, String messageId, String corpo) {
        return "From: " + de + "\r\n"
                + "To: " + para + "\r\n"
                + "Subject: " + assunto + "\r\n"
                + "Message-ID: <" + messageId + ">\r\n"
                + "MIME-Version: 1.0\r\n"
                + "Content-Type: text/plain; charset=utf-8\r\n"
                + "Content-Transfer-Encoding: 7bit\r\n"
                + "\r\n"
                + corpo + "\r\n";
    }

    public void conectar(Fabrica fabrica, String host, int porta, boolean starttls, String nomeLocal)
            throws IOException {
        try {
            soquete = fabrica.abrir(host, porta);
            soquete.setSoTimeout(30000);
            entrada = soquete.getInputStream();
            saida = soquete.getOutputStream();
        } catch (IOException caiu) {
            throw new Queda(ETAPA_CONEXAO, "nao deu para falar com o servidor de saida: " + resumo(caiu));
        }
        espera(220, ETAPA_CONEXAO);
        cumprimenta(nomeLocal, ETAPA_CONEXAO);
        if (starttls) {
            try {
                comando("STARTTLS", 220, ETAPA_CONEXAO);
                Socket puro = soquete;
                soquete = ((javax.net.ssl.SSLSocketFactory) javax.net.ssl.SSLSocketFactory.getDefault())
                        .createSocket(puro, host, porta, true);
                soquete.setSoTimeout(30000);
                entrada = soquete.getInputStream();
                saida = soquete.getOutputStream();
            } catch (IOException caiu) {
                throw new Queda(ETAPA_CONEXAO, "o STARTTLS nao subiu: " + resumo(caiu));
            }
            cumprimenta(nomeLocal, ETAPA_CONEXAO);
        }
    }

    public void entrar(String usuario, String senha) throws IOException {
        try {
            comando("AUTH LOGIN", 334, ETAPA_LOGIN);
            linha(base64.codificar(usuario.getBytes(StandardCharsets.UTF_8)), 334, ETAPA_LOGIN);
            linha(base64.codificar(senha.getBytes(StandardCharsets.UTF_8)), 235, ETAPA_LOGIN);
        } catch (Queda recusou) {
            throw recusou;
        } catch (IOException caiu) {
            throw new Queda(ETAPA_LOGIN, "o servidor de saida recusou a credencial: " + resumo(caiu));
        }
    }

    /** Entrega o recado. Depois do DATA enviado, qualquer queda e duvida, nao recusa. */
    public void entregar(String de, String para, String recado) throws IOException {
        comando("MAIL FROM:<" + de + ">", 250, ETAPA_RECUSA);
        comando("RCPT TO:<" + para + ">", 250, ETAPA_RECUSA);
        boolean empurrou = false;
        try {
            comando("DATA", 354, ETAPA_ENTREGA);
            empurrou = true;
            saida.write(escapa(recado.getBytes(StandardCharsets.UTF_8)));
            saida.write("\r\n.\r\n".getBytes(StandardCharsets.UTF_8));
            saida.flush();
            espera(250, ETAPA_ENTREGA);
        } catch (Queda recusou) {
            throw recusou;
        } catch (IOException caiu) {
            throw new Queda(empurrou ? ETAPA_ENTREGA : ETAPA_RECUSA,
                    empurrou ? "a entrega do pedido nao deu para confirmar: " + resumo(caiu)
                            : "o servidor de saida recusou o pedido: " + resumo(caiu));
        }
    }

    public void sair() {
        if (soquete == null) {
            return;
        }
        try {
            comando("QUIT", 221, ETAPA_CONEXAO);
        } catch (IOException ignorado) {
            // o servidor pode ja ter caido
        } finally {
            try {
                soquete.close();
            } catch (IOException ignorado) {
                // ja estava fechado
            }
        }
    }

    // ------------------------------------------------------------------ fiacao

    private void cumprimenta(String nomeLocal, String etapa) throws IOException {
        String nome = nomeLocal == null ? "" : nomeLocal.replaceAll("[^A-Za-z0-9.-]", "");
        comando("EHLO " + (nome.isEmpty() ? "celular" : nome), 250, etapa);
    }

    private void comando(String texto, int esperado, String etapa) throws IOException {
        linha(texto, esperado, etapa);
    }

    private void linha(String texto, int esperado, String etapa) throws IOException {
        try {
            saida.write((texto + "\r\n").getBytes(StandardCharsets.UTF_8));
            saida.flush();
        } catch (IOException caiu) {
            throw new Queda(etapa, "o servidor de saida nao recebeu o comando: " + resumo(caiu));
        }
        espera(esperado, etapa);
    }

    /** Le a resposta inteira (aceita as linhas continuation com traco) e confere o codigo. */
    private void espera(int esperado, String etapa) throws IOException {
        int codigo = -1;
        StringBuilder texto = new StringBuilder();
        while (true) {
            String linha = leLinha();
            if (linha == null) {
                if (codigo == esperado) {
                    return;
                }
                throw new Queda(etapa, "o servidor de saida fechou a conversa: " + resumo(texto.toString()));
            }
            if (linha.length() < 4 || !Character.isDigit(linha.charAt(0))
                    || !Character.isDigit(linha.charAt(1)) || !Character.isDigit(linha.charAt(2))) {
                throw new Queda(etapa, "resposta inesperada do servidor de saida: " + resumo(linha));
            }
            codigo = Integer.parseInt(linha.substring(0, 3));
            texto.append(linha.substring(3)).append(' ');
            if (linha.charAt(3) == ' ') {
                break;
            }
        }
        if (codigo != esperado) {
            throw new Queda(etapa, "o servidor de saida respondeu " + codigo + ": " + resumo(texto.toString()));
        }
    }

    private String leLinha() throws IOException {
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

    /** O ponto sozinho no meio do corpo significa fim: a saida dobra o ponto duplicado. */
    private static byte[] escapa(byte[] recado) {
        ByteArrayOutputStream fora = new ByteArrayOutputStream();
        boolean inicioDeLinha = true;
        for (byte valor : recado) {
            if (inicioDeLinha && valor == '.') {
                fora.write('.');
            }
            inicioDeLinha = valor == '\n';
            fora.write(valor);
        }
        return fora.toByteArray();
    }

    private static String resumo(Throwable causa) {
        String motivo = causa == null ? null : causa.getMessage();
        return resumo(motivo == null || motivo.isEmpty()
                ? (causa == null ? "sem motivo" : causa.getClass().getSimpleName()) : motivo);
    }

    private static String resumo(String texto) {
        String limpa = texto.replace("\r", " ").replace("\n", " ");
        return limpa.length() <= 150 ? limpa : limpa.substring(0, 150);
    }
}
