package br.com.caracore.pdv.sms;

import org.json.JSONObject;
import org.junit.Test;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

/**
 * A ponte de e-mail do celular, conferida de ponta a ponta sem servidor nenhum:
 * o Gaspar escreve o pedido cifrado numa caixa falsa, o celular le, entrega ao
 * radio e devolve o comprovante pela saida falsa. O que se confere aqui e a
 * fisionomia da conversa inteira, inclusive o que nao pode acontecer: reler o
 * mesmo recado, abrir o que nao tem a nossa chave e misturar a fila do PDV com
 * a do Hub.
 */
public class EmailBridgeTest {

    /** As mesmas chaves de teste dos vetores da cifra: nada aqui e segredo de producao. */
    private static final String CHAVE_PDV = "csQIe53lPqgTl+lCJvdRNPUUlSPRQR6Vi5a/w6EjR0w=";
    private static final String CHAVE_HUB = "l9ByRVNsUTEjYFvTzS0PlmdWV84CSB8kcWqeXyy6U0yXN2mwy2Yb7Y74V9Mui26m";
    private static final String CAIXA_DO_GASPAR = "gaspar@pdv.local";
    private static final String CELULAR_DA_LOJA = "celular@loja.local";
    private static final String NUMERO = "+5541999998888";
    private static final String TEXTO = "sua conta esta vencida";

    private final Bancada.B64DaMaquina base64 = new Bancada.B64DaMaquina();

    // ------------------------------------------------------------------ bancada

    private static final class MemoriaFalsa implements EmailBridge.Memoria {
        int ultimoUid;
        final List<String> lidos = new ArrayList<>();
        final List<EmailBridge.Comprovante> fila = new ArrayList<>();

        @Override
        public int ultimoUid() {
            return ultimoUid;
        }

        @Override
        public void marcarUid(int uid) {
            ultimoUid = uid;
        }

        @Override
        public boolean jaLido(String mensagemId) {
            return lidos.contains(mensagemId);
        }

        @Override
        public void marcarLido(String mensagemId) {
            lidos.add(mensagemId);
        }

        @Override
        public void anotarComprovante(EmailBridge.Comprovante comprovante) {
            fila.add(comprovante);
        }

        @Override
        public List<EmailBridge.Comprovante> comprovantesPendentes() {
            return new ArrayList<>(fila);
        }

        @Override
        public void esquecerComprovante(String referencia) {
            for (int i = 0; i < fila.size(); i++) {
                if (fila.get(i).referencia.equals(referencia)) {
                    fila.remove(i);
                    return;
                }
            }
        }
    }

    private static final class DespachoFalso implements EmailBridge.Despacho {
        final List<String> chamadas = new ArrayList<>();
        String estado = EmailEnvelope.ESTADO_ENVIADO;

        @Override
        public String executar(String origem, String referencia, String para, String texto, String destino) {
            chamadas.add(origem + "|" + referencia + "|" + para + "|" + texto);
            return estado;
        }
    }

    private static final class CredenciaisFalsas implements EmailBridge.Credenciais {
        final Map<String, String> chaves = new HashMap<>();
        String senha = "senha de app";

        @Override
        public String senhaDeApp() {
            return senha;
        }

        @Override
        public String chaveDaPonte(String origem) {
            return chaves.get(origem);
        }
    }

    private EmailBridge ponte(Bancada.CaixaFalsa caixa, Bancada.SaidaFalsa saida,
                              EmailBridge.Memoria memoria, EmailBridge.Despacho despacho,
                              EmailBridge.Credenciais credenciais) {
        EmailBridge.Configuracao ajustes = new EmailBridge.Configuracao();
        ajustes.hostDaCaixa = "imap.local";
        ajustes.portaDaCaixa = 993;
        ajustes.hostDaSaida = "smtp.local";
        ajustes.portaDaSaida = 465;
        ajustes.usuario = CELULAR_DA_LOJA;
        ajustes.remetente = CELULAR_DA_LOJA;
        ajustes.nomeDoAparelho = "SM-G991B";
        ajustes.tempoLimiteMs = Bancada.TEMPO_MS;
        EmailBridge.Fabricas fabricas = new EmailBridge.Fabricas() {
            @Override
            public ImapClient.Fabrica caixa() {
                return caixa.fabrica();
            }

            @Override
            public SmtpClient.Fabrica saida() {
                return saida.fabrica();
            }
        };
        return new EmailBridge(fabricas, ajustes, credenciais, base64, despacho, memoria);
    }

    /** O pedido cifrado que o Gaspar escreve na caixa, do jeito que ele escreve de verdade. */
    private byte[] pedidoDaPonte(String origemDoAssunto, String origemNoEnvelope,
                                 String referencia, String chave) throws Exception {
        JSONObject corpo = new JSONObject();
        corpo.put("v", EmailEnvelope.VERSAO);
        corpo.put("tipo", EmailEnvelope.TIPO_PEDIDO);
        corpo.put("referencia", referencia);
        corpo.put("origem", origemNoEnvelope);
        corpo.put("id_externo", "nota-17");
        corpo.put("para", NUMERO);
        corpo.put("texto", TEXTO);
        corpo.put("quando", 1760000000.0);
        String envelope = base64.codificar(
                EmailEnvelope.selar(new GatewayCrypto(base64.decodificar(chave)), corpo));
        return Bancada.recado(CAIXA_DO_GASPAR, EmailEnvelope.assunto(origemDoAssunto, referencia),
                referencia + "@" + EmailEnvelope.DOMINIO_MESSAGE_ID, envelope);
    }

    private static CredenciaisFalsas soPdv() {
        CredenciaisFalsas credenciais = new CredenciaisFalsas();
        credenciais.chaves.put("PDV", CHAVE_PDV);
        return credenciais;
    }

    // ------------------------------------------------------------------- testes

    @Test
    public void leOPedidoDaCaixaDevolveOComprovantePelaSaida() throws Exception {
        Bancada.CaixaFalsa caixa = new Bancada.CaixaFalsa()
                .adicionar(4, pedidoDaPonte("PDV", "PDV", "pdv-0001", CHAVE_PDV))
                .atender();
        Bancada.SaidaFalsa saida = new Bancada.SaidaFalsa().atender();
        MemoriaFalsa memoria = new MemoriaFalsa();
        DespachoFalso despacho = new DespachoFalso();

        EmailBridge ponte = ponte(caixa, saida, memoria, despacho, soPdv());
        assertEquals(1, ponte.umaVolta());

        assertEquals("o radio recebeu o pedido errado",
                java.util.Collections.singletonList("PDV|pdv-0001|" + NUMERO + "|" + TEXTO), despacho.chamadas);
        assertEquals(4, memoria.ultimoUid);
        assertTrue(memoria.lidos.toString(), memoria.lidos.contains("<pdv-0001@gaspar.local>"));
        assertTrue("o comprovante saiu da fila", memoria.fila.isEmpty());

        // a saida foi aberta com a senha de app e respondeu ao endereco de quem escreveu
        assertEquals("EHLO SM-G991B", saida.falas.get(0));
        assertTrue(saida.falas.toString(), saida.falas.contains("MAIL FROM:<" + CELULAR_DA_LOJA + ">"));
        assertTrue(saida.falas.toString(), saida.falas.contains("RCPT TO:<" + CAIXA_DO_GASPAR + ">"));

        EmailRecado comprovante = EmailRecado.ler(saida.ultimoCorpo().getBytes(StandardCharsets.US_ASCII));
        assertEquals("GASPAR PDV pdv-0001", comprovante.assunto());
        JSONObject aberto = EmailEnvelope.abrir(new GatewayCrypto(base64.decodificar(CHAVE_PDV)),
                base64.decodificar(EmailEnvelope.corpoLimpo(comprovante.corpo())));
        assertEquals(EmailEnvelope.VERSAO, aberto.optInt("v"));
        assertEquals(EmailEnvelope.TIPO_COMPROVANTE, EmailEnvelope.texto(aberto, "tipo"));
        assertEquals("pdv-0001", EmailEnvelope.texto(aberto, "referencia"));
        assertEquals(NUMERO, EmailEnvelope.texto(aberto, "para"));
        assertEquals(EmailEnvelope.ESTADO_ENVIADO, EmailEnvelope.texto(aberto, "estado"));
        assertEquals("SM-G991B", EmailEnvelope.texto(aberto, "dispositivo"));
        assertTrue("o comprovante precisa dizer quando saiu", aberto.optDouble("quando", 0.0) > 0.0);
        assertEquals("", ponte.ultimoErro());

        caixa.esperar(1);
        saida.esperar(1);
    }

    @Test
    public void aSegundaVoltaProcuraDepoisDoUltimoUidLido() throws Exception {
        Bancada.CaixaFalsa caixa = new Bancada.CaixaFalsa()
                .adicionar(4, pedidoDaPonte("PDV", "PDV", "pdv-0001", CHAVE_PDV))
                .atender();
        Bancada.SaidaFalsa saida = new Bancada.SaidaFalsa().atender();
        MemoriaFalsa memoria = new MemoriaFalsa();
        DespachoFalso despacho = new DespachoFalso();
        EmailBridge ponte = ponte(caixa, saida, memoria, despacho, soPdv());

        assertEquals(1, ponte.umaVolta());
        assertEquals(0, ponte.umaVolta());

        assertEquals(1, despacho.chamadas.size());
        assertTrue(caixa.falas.toString(), caixa.falas.contains("a3 UID SEARCH UID 1:*"));
        assertTrue(caixa.falas.toString(), caixa.falas.contains("a3 UID SEARCH UID 5:*"));
        caixa.esperar(2);
        saida.esperar(1);
    }

    @Test
    public void origemSemPareamentoNaoChegaAoRadio() throws Exception {
        Bancada.CaixaFalsa caixa = new Bancada.CaixaFalsa()
                .adicionar(7, pedidoDaPonte("HUB", "HUB", "hub-0001", CHAVE_HUB))
                .atender();
        Bancada.SaidaFalsa saida = new Bancada.SaidaFalsa().atender();
        MemoriaFalsa memoria = new MemoriaFalsa();
        DespachoFalso despacho = new DespachoFalso();

        assertEquals(0, ponte(caixa, saida, memoria, despacho, soPdv()).lerCaixa());

        assertTrue("o Hub nao esta pareado neste celular", despacho.chamadas.isEmpty());
        assertEquals("o recado recusado nao pode voltar para ser lido de novo", 7, memoria.ultimoUid);
        caixa.esperar(1);
    }

    @Test
    public void envelopeComOrigemTrocadaNaoPassa() throws Exception {
        // escrito com a chave do PDV e anunciado como PDV, mas o envelope diz HUB
        Bancada.CaixaFalsa caixa = new Bancada.CaixaFalsa()
                .adicionar(4, pedidoDaPonte("PDV", "HUB", "pdv-0002", CHAVE_PDV))
                .atender();
        Bancada.SaidaFalsa saida = new Bancada.SaidaFalsa().atender();
        MemoriaFalsa memoria = new MemoriaFalsa();
        DespachoFalso despacho = new DespachoFalso();
        EmailBridge ponte = ponte(caixa, saida, memoria, despacho, soPdv());

        assertEquals(0, ponte.lerCaixa());

        assertTrue(despacho.chamadas.isEmpty());
        assertEquals(1, ponte.origensSemPareamento());
        assertTrue("a fila do PDV nao pode receber aviso de origem estranha", memoria.fila.isEmpty());
        caixa.esperar(1);
    }

    @Test
    public void marcaNossaQueNaoAbreContaComoFalsificacao() throws Exception {
        String corpoFalso = base64.codificar("nao somos nos".getBytes(StandardCharsets.UTF_8))
                + Bancada.repeat("AAAA", 20);
        Bancada.CaixaFalsa caixa = new Bancada.CaixaFalsa()
                .adicionar(4, Bancada.recado(CAIXA_DO_GASPAR, "GASPAR PDV pdv-0003",
                        "pdv-0003@gaspar.local", corpoFalso))
                .atender();
        Bancada.SaidaFalsa saida = new Bancada.SaidaFalsa().atender();
        MemoriaFalsa memoria = new MemoriaFalsa();
        DespachoFalso despacho = new DespachoFalso();
        EmailBridge ponte = ponte(caixa, saida, memoria, despacho, soPdv());

        assertEquals(0, ponte.lerCaixa());

        assertEquals(1, ponte.recadosDaPonte());
        assertEquals("a marca e nossa, o conteudo nao abriu: isso tem de aparecer no painel",
                1, ponte.corposSemAbertura());
        assertTrue(despacho.chamadas.isEmpty());
        assertEquals(4, memoria.ultimoUid);
        caixa.esperar(1);
    }

    @Test
    public void recadoDeForaDaPontePassaLongeDoRadio() throws Exception {
        Bancada.CaixaFalsa caixa = new Bancada.CaixaFalsa()
                .adicionar(4, Bancada.recado("promo@loja.local", "Oferta da semana",
                        "oferta-1@loja.local", "aGVsbG8="))
                .atender();
        Bancada.SaidaFalsa saida = new Bancada.SaidaFalsa().atender();
        MemoriaFalsa memoria = new MemoriaFalsa();
        DespachoFalso despacho = new DespachoFalso();
        EmailBridge ponte = ponte(caixa, saida, memoria, despacho, soPdv());

        assertEquals(0, ponte.lerCaixa());

        assertEquals(0, ponte.recadosDaPonte());
        assertEquals(0, ponte.corposSemAbertura());
        assertTrue(despacho.chamadas.isEmpty());
        caixa.esperar(1);
    }

    @Test
    public void mesmoCarimboDuasVezesSohUmPedido() throws Exception {
        byte[] pedido = pedidoDaPonte("PDV", "PDV", "pdv-0004", CHAVE_PDV);
        // a caixa devolve o mesmo recado sob dois UID diferentes: o carimbo e a prova de que ja lemos
        Bancada.CaixaFalsa caixa = new Bancada.CaixaFalsa()
                .adicionar(4, pedido)
                .adicionar(5, pedido)
                .atender();
        Bancada.SaidaFalsa saida = new Bancada.SaidaFalsa().atender();
        MemoriaFalsa memoria = new MemoriaFalsa();
        DespachoFalso despacho = new DespachoFalso();

        assertEquals(1, ponte(caixa, saida, memoria, despacho, soPdv()).lerCaixa());

        assertEquals(1, despacho.chamadas.size());
        assertEquals(5, memoria.ultimoUid);
        caixa.esperar(1);
    }

    @Test
    public void recusaDoServidorMantemOComprovanteNaFila() throws Exception {
        Bancada.CaixaFalsa caixa = new Bancada.CaixaFalsa().atender();
        Bancada.SaidaFalsa saida = new Bancada.SaidaFalsa().atender();
        saida.respostaDoDestinatario = "550 5.7.1 Relay access denied";
        MemoriaFalsa memoria = new MemoriaFalsa();
        memoria.fila.add(new EmailBridge.Comprovante("PDV", "pdv-0005", NUMERO,
                EmailEnvelope.ESTADO_ENTREGUE, CAIXA_DO_GASPAR, 1760000000L));
        EmailBridge ponte = ponte(caixa, saida, memoria, new DespachoFalso(), soPdv());

        assertEquals("nada foi entregue", 0, ponte.enviarPendentes());

        assertEquals(1, memoria.fila.size());
        assertEquals(1, ponte.recusasDoServidor());
        assertEquals(0, ponte.duvidas());
        assertTrue(ponte.ultimaRecusa(), ponte.ultimaRecusa().contains("550"));
        saida.esperar(1);
    }

    @Test
    public void quedaDepoisDoDataNaoReenviaONemContaComoEnviado() throws Exception {
        Bancada.CaixaFalsa caixa = new Bancada.CaixaFalsa().atender();
        Bancada.SaidaFalsa saida = new Bancada.SaidaFalsa().atender();
        saida.derrubaAposOData = true;
        MemoriaFalsa memoria = new MemoriaFalsa();
        memoria.fila.add(new EmailBridge.Comprovante("PDV", "pdv-0006", NUMERO,
                EmailEnvelope.ESTADO_FALHOU, CAIXA_DO_GASPAR, 1760000000L));
        EmailBridge ponte = ponte(caixa, saida, memoria, new DespachoFalso(), soPdv());

        assertEquals("o corpo saiu mas a resposta nao voltou: nao ha o que contar como enviado",
                0, ponte.enviarPendentes());

        assertTrue("reenviar seria avisar duas vezes", memoria.fila.isEmpty());
        assertEquals(1, ponte.duvidas());
        assertEquals(0, ponte.recusasDoServidor());
        saida.esperar(1);
    }

    @Test
    public void caixaPostalForaDoArNaoDerrubaServicoEhSoErroDaVolta() throws Exception {
        Bancada.CaixaFalsa caixa = new Bancada.CaixaFalsa().atender();
        Bancada.SaidaFalsa saida = new Bancada.SaidaFalsa().atender();
        EmailBridge ponte = ponte(caixa, saida, new MemoriaFalsa(), new DespachoFalso(),
                new EmailBridge.Credenciais() {
                    @Override
                    public String senhaDeApp() throws IOException {
                        throw new IOException("sem rede");
                    }

                    @Override
                    public String chaveDaPonte(String origem) {
                        return CHAVE_PDV;
                    }
                });

        try {
            ponte.lerCaixa();
            org.junit.Assert.fail("a caixa nao pode responder sem senha");
        } catch (IOException esperado) {
            assertEquals("sem rede", esperado.getMessage());
        }

        assertEquals("sem rede", ponte.ultimoErro());
        caixa.esperar(1);
    }

    @Test
    public void oReinicioDoServicoNaoRelenENaoEsqueceOFila() throws Exception {
        final Map<String, String> guarda = new HashMap<>();
        ChaveValor store = new ChaveValor() {
            @Override
            public String texto(String chave) {
                return guarda.get(chave);
            }

            @Override
            public void gravarTexto(String chave, String valor) {
                if (valor == null) {
                    guarda.remove(chave);
                } else {
                    guarda.put(chave, valor);
                }
            }
        };

        // primeira volta: dois pedidos entram, mas a saida recusa os dois comprovantes
        Bancada.CaixaFalsa caixa = new Bancada.CaixaFalsa()
                .adicionar(4, pedidoDaPonte("PDV", "PDV", "pdv-0001", CHAVE_PDV))
                .adicionar(5, pedidoDaPonte("PDV", "PDV", "pdv-0002", CHAVE_PDV))
                .atender();
        Bancada.SaidaFalsa recusada = new Bancada.SaidaFalsa().atender();
        recusada.respostaDoDestinatario = "550 5.7.1 caixa cheia";
        EmailMemoria memoria = new EmailMemoria(store);
        DespachoFalso despacho = new DespachoFalso();
        assertEquals(2, ponte(caixa, recusada, memoria, despacho, soPdv()).umaVolta());
        assertEquals("o que o servidor recusou fica na fila", 2, memoria.comprovantesNaFila());
        caixa.esperar(1);
        recusada.esperar(1);

        // o android mata o servico e comeca tudo de novo, com a mesma guarda
        EmailMemoria depois = new EmailMemoria(store);
        assertEquals(2, depois.comprovantesNaFila());
        Bancada.CaixaFalsa vazia = new Bancada.CaixaFalsa().atender();
        Bancada.SaidaFalsa saida = new Bancada.SaidaFalsa().atender();
        DespachoFalso outroDespacho = new DespachoFalso();
        EmailBridge ponte = ponte(vazia, saida, depois, outroDespacho, soPdv());

        assertEquals(0, ponte.lerCaixa());
        vazia.esperar(1);
        assertTrue("o recado ja aberto nao pode virar pedido duas vezes", outroDespacho.chamadas.isEmpty());
        assertTrue("o reinicio continua de onde parou na caixa",
                vazia.falas.contains("a3 UID SEARCH UID 6:*"));

        assertEquals(2, ponte.enviarPendentes());
        assertEquals("a fila atravessou o reinicio e saiu toda", 0, depois.comprovantesNaFila());
        saida.esperar(1);
    }
}
