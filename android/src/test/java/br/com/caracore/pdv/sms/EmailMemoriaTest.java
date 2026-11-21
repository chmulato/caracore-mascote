package br.com.caracore.pdv.sms;

import org.junit.Test;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

/**
 * A guarda da ponte de e-mail, conferida sobre um mapa na memoria. O que importa
 * aqui e o que o celular nao pode perder quando o android mata o servico: ate onde
 * a caixa foi lida, quais recados ja abriram e quais comprovantes ainda faltam
 * sair. E o que nao pode acontecer: a guarda cheia deitar fora o pedido mais novo,
 * ou uma linha estragada travar a volta inteira.
 */
public class EmailMemoriaTest {

    private static final String CAIXA_DO_GASPAR = "gaspar@pdv.local";
    private static final String CHAVE_FILA = "gaspar.email.fila";

    /** O mesmo contrato do SharedPreferences, so que na maquina de testes. */
    private static final class Guarda implements ChaveValor {
        final Map<String, String> valores = new HashMap<>();
        int escritas;

        @Override
        public String texto(String chave) {
            return valores.get(chave);
        }

        @Override
        public void gravarTexto(String chave, String valor) {
            escritas++;
            if (valor == null) {
                valores.remove(chave);
            } else {
                valores.put(chave, valor);
            }
        }
    }

    private static EmailBridge.Comprovante comprovante(String referencia, String estado) {
        return new EmailBridge.Comprovante("PDV", referencia, "+5541999998888", estado,
                CAIXA_DO_GASPAR, 1700000000L);
    }

    private static List<String> referencias(List<EmailBridge.Comprovante> fila) {
        List<String> nomes = new ArrayList<>();
        for (EmailBridge.Comprovante c : fila) {
            nomes.add(c.referencia);
        }
        return nomes;
    }

    @Test
    public void comecaSemNadaLidoENenhumaFila() {
        EmailMemoria guarda = new EmailMemoria(new Guarda());
        assertEquals(0, guarda.ultimoUid());
        assertFalse(guarda.jaLido("<pdv-0001@gaspar.local>"));
        assertTrue(guarda.comprovantesPendentes().isEmpty());
    }

    @Test
    public void soOUidMaisAltoFicaMarcado() {
        Guarda store = new Guarda();
        EmailMemoria guarda = new EmailMemoria(store);
        int escritas = store.escritas;
        guarda.marcarUid(7);
        guarda.marcarUid(3);
        assertEquals(7, guarda.ultimoUid());
        assertEquals("a caixa passa a procurar depois do ultimo lido", "7", store.texto("gaspar.email.uid"));
        assertEquals("o uid mais baixo nao reescreve nada", escritas + 1, store.escritas);
        assertEquals("o reinicio lee o mesmo numero", 7, new EmailMemoria(store).ultimoUid());
    }

    @Test
    public void oCarimboSobreviveAoReinicioDoServico() {
        Guarda store = new Guarda();
        new EmailMemoria(store).marcarLido("<pdv-0001@gaspar.local>");
        EmailMemoria depois = new EmailMemoria(store);
        assertTrue("o recado aberto nao pode virar pedido duas vezes",
                depois.jaLido("<pdv-0001@gaspar.local>"));
        assertFalse(depois.jaLido("<pdv-0002@gaspar.local>"));
    }

    @Test
    public void carimboRepetidoNaoDobraAGuarda() {
        EmailMemoria guarda = new EmailMemoria(new Guarda());
        guarda.marcarLido("<pdv-0001@gaspar.local>");
        guarda.marcarLido("<pdv-0001@gaspar.local>");
        assertEquals(1, guarda.carimbosGuardados());
    }

    @Test
    public void carimboVazioONaoAberto() {
        EmailMemoria guarda = new EmailMemoria(new Guarda());
        guarda.marcarLido(null);
        guarda.marcarLido("   ");
        guarda.marcarLido("<pdv-\n0001@gaspar.local>");
        assertEquals("o separador da guarda nao pode entrar no carimbo", 1, guarda.carimbosGuardados());
        assertTrue(guarda.jaLido("<pdv- 0001@gaspar.local>"));
    }

    @Test
    public void osCarimbosMaisVelhosSaoOsPrimeirosACairem() {
        EmailMemoria guarda = new EmailMemoria(new Guarda());
        for (int i = 0; i <= EmailMemoria.LIMITE_CARIMBOS; i++) {
            guarda.marcarLido("<pdv-" + i + "@gaspar.local>");
        }
        assertEquals(EmailMemoria.LIMITE_CARIMBOS, guarda.carimbosGuardados());
        assertFalse("o mais velho saiu", guarda.jaLido("<pdv-0@gaspar.local>"));
        assertTrue("o mais novo ficou",
                guarda.jaLido("<pdv-" + EmailMemoria.LIMITE_CARIMBOS + "@gaspar.local>"));
    }

    @Test
    public void aFilaSobreviveAoReinicioComTodosOsCampos() {
        Guarda store = new Guarda();
        new EmailMemoria(store).anotarComprovante(comprovante("pdv-0007", EmailEnvelope.ESTADO_ENVIADO));
        List<EmailBridge.Comprovante> fila = new EmailMemoria(store).comprovantesPendentes();
        assertEquals(1, fila.size());
        EmailBridge.Comprovante c = fila.get(0);
        assertEquals("PDV", c.origem);
        assertEquals("pdv-0007", c.referencia);
        assertEquals("+5541999998888", c.para);
        assertEquals(EmailEnvelope.ESTADO_ENVIADO, c.estado);
        assertEquals(CAIXA_DO_GASPAR, c.destino);
        assertEquals(1700000000L, c.quandoEmSegundos);
    }

    @Test
    public void oEstadoMaisNovoDoMesmoPedidoEoQueFicaNaFila() {
        EmailMemoria guarda = new EmailMemoria(new Guarda());
        guarda.anotarComprovante(comprovante("pdv-0007", EmailEnvelope.ESTADO_ENVIADO));
        guarda.anotarComprovante(comprovante("pdv-0007", EmailEnvelope.ESTADO_ENTREGUE));
        List<EmailBridge.Comprovante> fila = guarda.comprovantesPendentes();
        assertEquals(1, fila.size());
        assertEquals(EmailEnvelope.ESTADO_ENTREGUE, fila.get(0).estado);
    }

    @Test
    public void comprovanteSemReferenciaNaoEncheAFila() {
        EmailMemoria guarda = new EmailMemoria(new Guarda());
        guarda.anotarComprovante(comprovante("", EmailEnvelope.ESTADO_ENVIADO));
        guarda.anotarComprovante(null);
        assertTrue(guarda.comprovantesPendentes().isEmpty());
    }

    @Test
    public void aFilaParaNoLimiteSegurandoOsMaisNovos() {
        EmailMemoria guarda = new EmailMemoria(new Guarda());
        for (int i = 0; i <= EmailMemoria.LIMITE_FILA; i++) {
            guarda.anotarComprovante(comprovante("pdv-" + i, EmailEnvelope.ESTADO_ENVIADO));
        }
        List<String> nomes = referencias(guarda.comprovantesPendentes());
        assertEquals(EmailMemoria.LIMITE_FILA, nomes.size());
        assertFalse("o mais velho saiu sem devolver", nomes.contains("pdv-0"));
        assertTrue("o mais novo ficou", nomes.contains("pdv-" + EmailMemoria.LIMITE_FILA));
    }

    @Test
    public void linhaEstragadaNaGuardaNaoTravaAVolta() {
        Guarda store = new Guarda();
        EmailMemoria guarda = new EmailMemoria(store);
        guarda.anotarComprovante(comprovante("pdv-0001", EmailEnvelope.ESTADO_ENVIADO));
        guarda.anotarComprovante(comprovante("pdv-0002", EmailEnvelope.ESTADO_ENVIADO));
        store.valores.put(CHAVE_FILA, store.texto(CHAVE_FILA) + "\nquem escreveu isto nao e a ponte");
        EmailMemoria depois = new EmailMemoria(store);
        assertEquals("a linha ruim fica de fora, o resto segue", 2, depois.comprovantesNaFila());
        depois.esquecerComprovante("pdv-0001");
        assertEquals("so o que abriu continua na fila", 1, depois.comprovantesNaFila());
        assertFalse(store.texto(CHAVE_FILA).contains("quem escreveu isto"));
        assertEquals(1, new EmailMemoria(store).comprovantesNaFila());
    }

    @Test
    public void oQueSaiuSomeDaFilaEPorReferencia() {
        Guarda store = new Guarda();
        EmailMemoria guarda = new EmailMemoria(store);
        guarda.anotarComprovante(comprovante("pdv-0001", EmailEnvelope.ESTADO_ENVIADO));
        guarda.esquecerComprovante("pdv-0002");
        assertEquals("esquecer o que nao esta na fila nao reescreve nada", 1, guarda.comprovantesNaFila());
        guarda.esquecerComprovante("pdv-0001");
        assertEquals(0, guarda.comprovantesNaFila());
        assertTrue(new EmailMemoria(store).comprovantesPendentes().isEmpty());
    }

    @Test
    public void aVoltaPercorreUmaCopiaDaFila() {
        EmailMemoria guarda = new EmailMemoria(new Guarda());
        guarda.anotarComprovante(comprovante("pdv-0001", EmailEnvelope.ESTADO_ENVIADO));
        List<EmailBridge.Comprovante> copia = guarda.comprovantesPendentes();
        copia.clear();
        guarda.anotarComprovante(comprovante("pdv-0002", EmailEnvelope.ESTADO_ENTREGUE));
        assertEquals("mexer na copia nao mexe na guarda", 2, guarda.comprovantesPendentes().size());
    }
}
