package br.com.caracore.pdv.sms;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

/**
 * A bancada dos testes da ponte: uma caixa postal IMAP falsa e uma saida SMTP falsa,
 * cada uma numa porta da propria maquina, exatamente como o B4 do Gaspar usa um
 * celular falso. O que se confere aqui e a fala, comando por comando, e o que volta.
 *
 * Nada disso depende de servidor de e-mail nenhum nem de celular: da para rodar na
 * maquina de testes quantas vezes for preciso.
 */
final class Bancada {

    static final int TEMPO_MS = 5000;

    private Bancada() {
    }

    interface Atendimento {
        void atende(Socket cliente) throws Exception;
    }

    /** O base64 da maquina de testes; no celular e o do Android. */
    static final class B64DaMaquina implements B64 {
        @Override
        public String codificar(byte[] dados) {
            return java.util.Base64.getEncoder().encodeToString(dados);
        }

        @Override
        public byte[] decodificar(String texto) {
            return java.util.Base64.getDecoder().decode(texto);
        }
    }

    /**
     * Escuta numa porta livre e atende uma conversa por vez, em linha separada.
     * Serve de fabrica de soquetes para os dois clientes.
     */
    static final class Servidor implements ImapClient.Fabrica, SmtpClient.Fabrica {
        private final ServerSocket escuta;
        private final AtomicInteger encerradas = new AtomicInteger();
        private final AtomicReference<Exception> erro = new AtomicReference<>();

        Servidor(final Atendimento atendimento) throws IOException {
            escuta = new ServerSocket(0);
            escuta.setSoTimeout(TEMPO_MS);
            Thread linha = new Thread(() -> {
                while (!escuta.isClosed()) {
                    Socket cliente;
                    try {
                        cliente = escuta.accept();
                    } catch (java.net.SocketTimeoutException vaga) {
                        continue;
                    } catch (IOException caiu) {
                        if (escuta.isClosed()) {
                            // o teste fechou a escuta: fim de papo
                            break;
                        }
                        erro.compareAndSet(null, caiu);
                        continue;
                    }
                    try {
                        atendimento.atende(cliente);
                    } catch (Exception caiu) {
                        erro.compareAndSet(null, caiu);
                    } finally {
                        try {
                            cliente.close();
                        } catch (IOException ignorado) {
                            // ja estava
                        }
                    }
                    encerradas.incrementAndGet();
                }
            });
            linha.setDaemon(true);
            linha.start();
        }

        @Override
        public Socket abrir(String host, int porta) throws IOException {
            Socket socket = new Socket("127.0.0.1", escuta.getLocalPort());
            socket.setSoTimeout(TEMPO_MS);
            return socket;
        }

        /** Espera as conversas anunciadas terminarem e denuncia o que a banca errada falou. */
        void esperarConversas(int quantidade) throws Exception {
            long fim = System.currentTimeMillis() + TEMPO_MS;
            while (encerradas.get() < quantidade && System.currentTimeMillis() < fim) {
                Thread.sleep(10L);
            }
            assertEquals("a conversa com o servidor falso nao fechou", quantidade, encerradas.get());
            if (erro.get() != null) {
                throw new AssertionError("servidor falso: " + erro.get(), erro.get());
            }
            escuta.close();
        }
    }

    static void escrever(OutputStream saida, String texto) throws IOException {
        saida.write(texto.getBytes(StandardCharsets.US_ASCII));
        saida.flush();
    }

    /** Uma linha terminada em CRLF; null quando o outro lado fecha. */
    static String leLinha(InputStream entrada) throws IOException {
        ByteArrayOutputStream linha = new ByteArrayOutputStream();
        int b;
        while ((b = entrada.read()) >= 0) {
            if (b == '\n') {
                String texto = new String(linha.toByteArray(), StandardCharsets.US_ASCII);
                return texto.endsWith("\r") ? texto.substring(0, texto.length() - 1) : texto;
            }
            linha.write(b);
        }
        return linha.size() == 0 ? null : new String(linha.toByteArray(), StandardCharsets.US_ASCII);
    }

    static String repeat(String pedaco, int vezes) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < vezes; i++) {
            sb.append(pedaco);
        }
        return sb.toString();
    }

    /** O recado cru como a caixa postal o devolve: cabecalhos ASCII e o corpo em uma linha. */
    static byte[] recado(String de, String assunto, String mensagemId, String corpo) {
        return ("Return-Path: <" + de + ">\r\n"
                + "From: Gaspar do computador <" + de + ">\r\n"
                + "To: celular@loja.local\r\n"
                + "Subject: " + assunto + "\r\n"
                + "Message-ID: <" + mensagemId + ">\r\n"
                + "Content-Type: text/plain; charset=\"utf-8\"\r\n"
                + "Content-Transfer-Encoding: 7bit\r\n"
                + "\r\n"
                + corpo + "\r\n").getBytes(StandardCharsets.US_ASCII);
    }

    /** A caixa postal falsa: devolve os recados pelo UID e nunca tira ninguem da caixa de nao lidos. */
    static final class CaixaFalsa {
        final List<String> falas = Collections.synchronizedList(new ArrayList<String>());
        private final Map<Integer, byte[]> guardados = new LinkedHashMap<>();
        private Servidor servidor;

        CaixaFalsa adicionar(int uid, byte[] bruto) {
            guardados.put(uid, bruto);
            return this;
        }

        CaixaFalsa atender() throws IOException {
            servidor = new Servidor(this::conversar);
            return this;
        }

        ImapClient.Fabrica fabrica() {
            return servidor;
        }

        void esperar(int conversas) throws Exception {
            servidor.esperarConversas(conversas);
        }

        private void conversar(Socket cliente) throws IOException {
            OutputStream saida = cliente.getOutputStream();
            InputStream entrada = cliente.getInputStream();
            escrever(saida, "* OK Fake IMAP4rev1 pronto\r\n");
            String linha;
            while ((linha = leLinha(entrada)) != null) {
                falas.add(linha);
                String tag = linha.substring(0, linha.indexOf(' '));
                if (linha.contains(" LOGIN ")) {
                    escrever(saida, tag + " OK LOGIN completed\r\n");
                } else if (linha.contains(" SELECT ")) {
                    escrever(saida, "* " + guardados.size() + " EXISTS\r\n" + tag + " OK [READ-WRITE] SELECT ok\r\n");
                } else if (linha.contains("UID SEARCH")) {
                    escrever(saida, "* SEARCH " + unidos(listarMaiorQue(linha)) + "\r\n" + tag + " OK SEARCH done\r\n");
                } else {
                    int uid = uidDoFetch(linha);
                    if (uid > 0) {
                        byte[] bruto = guardados.get(uid);
                        if (bruto != null) {
                            escrever(saida, "* " + uid + " FETCH (UID " + uid + " BODY[] {" + bruto.length + "}\r\n");
                            saida.write(bruto);
                            escrever(saida, ")\r\n");
                        }
                        escrever(saida, tag + " OK FETCH done\r\n");
                    } else if (linha.contains(" LOGOUT")) {
                        escrever(saida, "* BYE logging out\r\n" + tag + " OK LOGOUT done\r\n");
                        return;
                    }
                }
            }
        }

        private List<Integer> listarMaiorQue(String linha) {
            List<Integer> encontrados = new ArrayList<>();
            for (Integer uid : guardados.keySet()) {
                if (uid >= desde(linha)) {
                    encontrados.add(uid);
                }
            }
            return encontrados;
        }

        /** O "UID SEARCH UID n:*" pede tudo a partir de n: e assim que a ponte anda na caixa. */
        private static int desde(String linha) {
            int inicio = linha.indexOf("UID SEARCH UID ");
            if (inicio < 0) {
                return 1;
            }
            String resto = linha.substring(inicio + "UID SEARCH UID ".length());
            int doisPontos = resto.indexOf(':');
            try {
                return Integer.parseInt(resto.substring(0, doisPontos < 0 ? resto.length() : doisPontos));
            } catch (NumberFormatException invalido) {
                return 1;
            }
        }

        private static int uidDoFetch(String linha) {
            int inicio = linha.indexOf("UID FETCH ");
            if (inicio < 0) {
                return -1;
            }
            String resto = linha.substring(inicio + "UID FETCH ".length()).trim();
            int espaco = resto.indexOf(' ');
            try {
                return Integer.parseInt(espaco < 0 ? resto : resto.substring(0, espaco));
            } catch (NumberFormatException invalido) {
                return -1;
            }
        }

        private static String unidos(List<Integer> uids) {
            StringBuilder sb = new StringBuilder();
            for (Integer uid : uids) {
                if (sb.length() > 0) {
                    sb.append(' ');
                }
                sb.append(uid);
            }
            return sb.toString();
        }
    }

    /** A saida SMTP falsa: conversa ate o fim, guarda os corpos e responde o que o teste mandar. */
    static final class SaidaFalsa {
        final List<String> falas = Collections.synchronizedList(new ArrayList<String>());
        final List<String> corpos = Collections.synchronizedList(new ArrayList<String>());
        /** Resposta ao RCPT TO; comecando com 5 significa recusa. */
        String respostaDoDestinatario = "250 2.1.5 Ok";
        /** true = o corpo entra e a resposta nunca volta: a duvida que o computador precisa desfazer. */
        boolean derrubaAposOData;
        private Servidor servidor;

        SaidaFalsa atender() throws IOException {
            servidor = new Servidor(this::conversar);
            return this;
        }

        SmtpClient.Fabrica fabrica() {
            return servidor;
        }

        void esperar(int conversas) throws Exception {
            servidor.esperarConversas(conversas);
        }

        /** O ultimo corpo que saiu pelo DATA, com as quebras de linha da conversa. */
        String ultimoCorpo() {
            assertTrue("a saida nao recebeu recado nenhum", !corpos.isEmpty());
            return corpos.get(corpos.size() - 1);
        }

        private void conversar(Socket cliente) throws IOException {
            OutputStream saida = cliente.getOutputStream();
            InputStream entrada = cliente.getInputStream();
            escrever(saida, "220 fake ESMTP\r\n");
            boolean dentroDoData = false;
            int faltaNoAuth = 0;
            ByteArrayOutputStream corpo = new ByteArrayOutputStream();
            String linha;
            while ((linha = leLinha(entrada)) != null) {
                if (dentroDoData) {
                    if (".".equals(linha)) {
                        dentroDoData = false;
                        corpos.add(new String(corpo.toByteArray(), StandardCharsets.US_ASCII));
                        if (derrubaAposOData) {
                            return;
                        }
                        escrever(saida, "250 2.0.0 Ok: queued\r\n");
                    } else {
                        corpo.write(linha.getBytes(StandardCharsets.US_ASCII));
                        corpo.write('\n');
                    }
                    continue;
                }
                falas.add(linha);
                if (linha.startsWith("EHLO")) {
                    escrever(saida, "250-fake\r\n250 AUTH=LOGIN\r\n");
                } else if (linha.startsWith("AUTH LOGIN")) {
                    faltaNoAuth = 2;
                    escrever(saida, "334 U2Vy\r\n");
                } else if (linha.startsWith("MAIL FROM")) {
                    escrever(saida, "250 2.1.0 Ok\r\n");
                } else if (linha.startsWith("RCPT TO")) {
                    escrever(saida, respostaDoDestinatario + "\r\n");
                    if (respostaDoDestinatario.startsWith("5")) {
                        return;
                    }
                } else if (linha.startsWith("DATA")) {
                    dentroDoData = true;
                    escrever(saida, "354 End data with <CR><LF>.<CR><LF>\r\n");
                } else if (linha.startsWith("QUIT")) {
                    escrever(saida, "221 Bye\r\n");
                    return;
                } else if (faltaNoAuth > 0) {
                    faltaNoAuth--;
                    escrever(saida, faltaNoAuth == 1 ? "334 U2VuaGE=\r\n" : "235 2.7.0 Accepted\r\n");
                }
            }
        }
    }
}
