package br.com.caracore.pdv.sms;

import org.junit.Test;

import java.io.IOException;
import java.io.OutputStream;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.List;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

/**
 * Os dois clientes da ponte conversam aqui com a bancada da maquina de testes,
 * exatamente como o B4 do Gaspar faz com o celular falso: o que se confere e a
 * fala, comando por comando, e o que volta, sem depender de servidor de e-mail.
 */
public class EmailClientsTest {

    private static final String CAIXA_DO_GASPAR = "gaspar@pdv.local";
    private static final String CELULAR_DA_LOJA = "celular@loja.local";

    private static byte[] recadoDoGaspar(String referencia, int enchimento) {
        return Bancada.recado(CAIXA_DO_GASPAR, "GASPAR PDV " + referencia,
                referencia + "@gaspar.local", "aG9sYQ==" + Bancada.repeat("AAAA", enchimento));
    }

    @Test
    public void leOsRecadosNovosSemTirarNinguemDaCaixaDeNaoLidos() throws Exception {
        byte[] quarto = recadoDoGaspar("pdv-0001", 400);
        byte[] quinto = recadoDoGaspar("pdv-0002", 3);
        Bancada.CaixaFalsa caixa = new Bancada.CaixaFalsa().adicionar(4, quarto).adicionar(5, quinto).atender();

        ImapClient cliente = new ImapClient(caixa.fabrica(), "imap.local", 993, Bancada.TEMPO_MS);
        try {
            cliente.login(CELULAR_DA_LOJA, "senha de app");
            cliente.selecionar("");
            assertEquals(Arrays.asList(4, 5), cliente.buscarUid(4));
            assertEquals(new String(quarto, StandardCharsets.US_ASCII),
                    new String(cliente.corpoDoUid(4), StandardCharsets.US_ASCII));
            assertEquals(new String(quinto, StandardCharsets.US_ASCII),
                    new String(cliente.corpoDoUid(5), StandardCharsets.US_ASCII));
            assertEquals("PDV", EmailEnvelope.origemNoAssunto(EmailRecado.ler(quarto).assunto()));
            assertEquals("<pdv-0001@gaspar.local>", EmailRecado.ler(quarto).mensagemId());
        } finally {
            cliente.sair();
        }
        caixa.esperar(1);

        List<String> falas = caixa.falas;
        assertTrue(falas.toString(), falas.get(0).endsWith("LOGIN \"" + CELULAR_DA_LOJA + "\" \"senha de app\""));
        assertTrue(falas.toString(), falas.get(1).endsWith("SELECT \"INBOX\""));
        assertTrue(falas.toString(), falas.get(2).endsWith("UID SEARCH UID 4:*"));
        // BODY.PEEK: ler a ponte nunca pode marcar o recado como visto para o Gaspar.
        assertTrue(falas.toString(), falas.get(3).endsWith("UID FETCH 4 (BODY.PEEK[])"));
        assertTrue(falas.toString(), falas.get(4).endsWith("UID FETCH 5 (BODY.PEEK[])"));
        for (String fala : falas) {
            assertFalse("nunca pode marcar como visto: " + fala, fala.contains("STORE"));
            assertFalse("nunca pode apagar: " + fala, fala.contains("EXPUNGE"));
        }
    }

    @Test
    public void recusaQuandoACaixaPostalDizNao() throws Exception {
        Bancada.Servidor servidor = new Bancada.Servidor(cliente -> {
            OutputStream saida = cliente.getOutputStream();
            Bancada.escrever(saida, "* OK Fake IMAP4rev1 pronto\r\n");
            String linha = Bancada.leLinha(cliente.getInputStream());
            Bancada.escrever(saida, linha.substring(0, linha.indexOf(' ')) + " NO [PRIVACYREQUIRED] LOGIN failed\r\n");
        });
        ImapClient cliente = new ImapClient(servidor, "imap.local", 993, Bancada.TEMPO_MS);
        try {
            cliente.login(CELULAR_DA_LOJA, "errada");
            fail("era para a caixa postal recusar o login");
        } catch (ImapClient.Recusa recusou) {
            assertTrue(recusou.getMessage(), recusou.getMessage().contains("recusou o login"));
        } finally {
            cliente.sair();
        }
        servidor.esperarConversas(1);
    }

    @Test
    public void percebeQuandoACaixaCortaOLiteralNoMeio() throws Exception {
        byte[] quarto = recadoDoGaspar("pdv-0003", 40);
        Bancada.Servidor servidor = new Bancada.Servidor(cliente -> {
            OutputStream saida = cliente.getOutputStream();
            Bancada.escrever(saida, "* OK Fake IMAP4rev1 pronto\r\n");
            String linha = Bancada.leLinha(cliente.getInputStream());
            Bancada.escrever(saida, confirmacao(linha) + " OK LOGIN completed\r\n");
            linha = Bancada.leLinha(cliente.getInputStream());
            Bancada.escrever(saida, confirmacao(linha) + " OK SELECT ok\r\n");
            linha = Bancada.leLinha(cliente.getInputStream());
            Bancada.escrever(saida, confirmacao(linha) + " OK SEARCH done\r\n");
            // anuncia o tamanho inteiro e so manda metade: o cliente nao pode aceitar
            Bancada.leLinha(cliente.getInputStream());
            Bancada.escrever(saida, "* 4 FETCH (UID 4 BODY[] {" + quarto.length + "}\r\n");
            saida.write(quarto, 0, quarto.length / 2);
            saida.flush();
            cliente.close();
        });
        ImapClient cliente = new ImapClient(servidor, "imap.local", 993, Bancada.TEMPO_MS);
        try {
            cliente.login(CELULAR_DA_LOJA, "senha");
            cliente.selecionar("INBOX");
            cliente.buscarUid(1);
            cliente.corpoDoUid(4);
            fail("era para faltar conteudo do recado");
        } catch (ImapClient.Recusa cortou) {
            assertNotNull(cortou.getMessage());
            assertTrue(cortou.getMessage(), cortou.getMessage().contains("cortou o conteudo"));
        } finally {
            cliente.sair();
        }
        servidor.esperarConversas(1);
    }

    private static String confirmacao(String linha) {
        return linha.substring(0, linha.indexOf(' '));
    }

    @Test
    public void mandaOMesmoRecadoQueOGasparLeDoOutroLado() throws Exception {
        Bancada.SaidaFalsa saida = new Bancada.SaidaFalsa().atender();
        SmtpClient cliente = new SmtpClient(new Bancada.B64DaMaquina());
        String recado = SmtpClient.montar(CELULAR_DA_LOJA, CAIXA_DO_GASPAR,
                "GASPAR PDV pdv-0001", "recibo-1@gaspar.local", "aGVsbG8=");
        try {
            cliente.conectar(saida.fabrica(), "smtp.local", 465, false, "SM-G991B");
            cliente.entrar(CELULAR_DA_LOJA, "senha de app");
            cliente.entregar(CELULAR_DA_LOJA, CAIXA_DO_GASPAR, recado);
        } finally {
            cliente.sair();
        }
        saida.esperar(1);

        assertEquals("EHLO SM-G991B", saida.falas.get(0));
        assertEquals("AUTH LOGIN", saida.falas.get(1));
        Bancada.B64DaMaquina base64 = new Bancada.B64DaMaquina();
        assertEquals(CELULAR_DA_LOJA, new String(base64.decodificar(saida.falas.get(2)), StandardCharsets.UTF_8));
        assertEquals("senha de app", new String(base64.decodificar(saida.falas.get(3)), StandardCharsets.UTF_8));
        assertEquals("MAIL FROM:<" + CELULAR_DA_LOJA + ">", saida.falas.get(4));
        assertEquals("RCPT TO:<" + CAIXA_DO_GASPAR + ">", saida.falas.get(5));
        assertEquals("DATA", saida.falas.get(6));
        assertEquals(recado.replace("\r\n", "\n") + "\n", saida.ultimoCorpo());
        // o que saiu pelo DATA e o recado inteiro: o Gaspar le os cabecalhos e o corpo do mesmo lado
        EmailRecado lido = EmailRecado.ler(saida.ultimoCorpo().getBytes(StandardCharsets.US_ASCII));
        assertEquals("GASPAR PDV pdv-0001", lido.assunto());
        assertEquals(CELULAR_DA_LOJA, lido.enderecoDe());
        assertEquals("aGVsbG8=", EmailEnvelope.corpoLimpo(lido.corpo()));
        assertTrue(saida.falas.toString(), saida.falas.contains("QUIT"));
    }

    @Test
    public void recusaDoServidorNuncaConfundidaComEntrega() throws Exception {
        Bancada.SaidaFalsa saida = new Bancada.SaidaFalsa().atender();
        saida.respostaDoDestinatario = "550 5.7.1 Relay access denied";
        SmtpClient cliente = new SmtpClient(new Bancada.B64DaMaquina());
        try {
            cliente.conectar(saida.fabrica(), "smtp.local", 465, false, "celular");
            cliente.entrar(CELULAR_DA_LOJA, "senha de app");
            cliente.entregar(CELULAR_DA_LOJA, CAIXA_DO_GASPAR, "From: a\r\n\r\nz\r\n");
            fail("era para o servidor recusar o destinatario");
        } catch (SmtpClient.Queda recusou) {
            assertEquals(SmtpClient.ETAPA_RECUSA, recusou.etapa());
            assertTrue(recusou.getMessage(), recusou.getMessage().contains("550"));
        } finally {
            cliente.sair();
        }
        saida.esperar(1);
    }

    @Test
    public void quedaDepoisDeEmpurrarODadoEhDuvidaEaNaoRecusa() throws Exception {
        Bancada.SaidaFalsa saida = new Bancada.SaidaFalsa().atender();
        saida.derrubaAposOData = true;
        SmtpClient cliente = new SmtpClient(new Bancada.B64DaMaquina());
        try {
            cliente.conectar(saida.fabrica(), "smtp.local", 465, false, "celular");
            cliente.entrar(CELULAR_DA_LOJA, "senha");
            cliente.entregar(CELULAR_DA_LOJA, CAIXA_DO_GASPAR, "From: a\r\n\r\nb\r\n");
            fail("era para a entrega ter caido");
        } catch (SmtpClient.Queda caiu) {
            assertEquals(SmtpClient.ETAPA_ENTREGA, caiu.etapa());
        } finally {
            cliente.sair();
        }
        saida.esperar(1);
    }

    @Test
    public void ehloSemNomeValidoNaoQuebraAConversa() throws Exception {
        Bancada.SaidaFalsa saida = new Bancada.SaidaFalsa().atender();
        SmtpClient cliente = new SmtpClient(new Bancada.B64DaMaquina());
        try {
            // o nome do aparelho so leva o que o servidor de saida aceita: o resto cai
            cliente.conectar(saida.fabrica(), "smtp.local", 465, false, "celular da loja");
        } finally {
            cliente.sair();
        }
        saida.esperar(1);
        assertEquals("EHLO celulardaloja", saida.falas.get(0));
    }

    @Test(expected = IOException.class)
    public void caixaQueNaoDizOiNaoViraCliente() throws Exception {
        Bancada.Servidor servidor = new Bancada.Servidor(cliente -> {
            Bancada.escrever(cliente.getOutputStream(), "* PREAUTH alguem ja entrou\r\n");
        });
        new ImapClient(servidor, "imap.local", 993, Bancada.TEMPO_MS);
    }
}
