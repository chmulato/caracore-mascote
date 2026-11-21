package br.com.caracore.pdv.sms;

import org.junit.Test;

import java.util.HashMap;
import java.util.Map;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

/**
 * O caminho por onde cada pedido entrou, guardado para que o comprovante volte pelo
 * mesmo: o radio avisa a entrega minutos depois, so com o identificador. O que se
 * confere aqui e o pedido que nao pode perder o aviso (a loja esta na rua, sem
 * Wi-Fi) e o que nao pode mudar de fila (o comprovante do PDV nunca volta ao Hub).
 */
public class TrilhaDoPedidoTest {

    private static final String CAIXA_DO_GASPAR = "gaspar@pdv.local";
    private static final String NUMERO = "+5541999998888";

    private static final class Guarda implements ChaveValor {
        final Map<String, String> valores = new HashMap<>();

        @Override
        public String texto(String chave) {
            return valores.get(chave);
        }

        @Override
        public void gravarTexto(String chave, String valor) {
            if (valor == null) {
                valores.remove(chave);
            } else {
                valores.put(chave, valor);
            }
        }
    }

    @Test
    public void semTrilhaONaoConhecido() {
        TrilhaDoPedido trilhas = new TrilhaDoPedido(new Guarda());
        assertEquals(0, trilhas.tamanho());
        assertNull(trilhas.de("pdv-0001"));
    }

    @Test
    public void aTrilhaSobreviveAoReinicioComTodosOsCampos() {
        Guarda store = new Guarda();
        new TrilhaDoPedido(store).registrar("pdv-0001", "PDV",
                TrilhaDoPedido.CANAL_EMAIL, NUMERO, CAIXA_DO_GASPAR);
        TrilhaDoPedido.Registro trilha = new TrilhaDoPedido(store).de("pdv-0001");
        assertNotNull(trilha);
        assertEquals("pdv-0001", trilha.jobId);
        assertEquals("PDV", trilha.origem);
        assertEquals(NUMERO, trilha.para);
        assertEquals(CAIXA_DO_GASPAR, trilha.destino);
        assertTrue(trilha.porEmail());
    }

    @Test
    public void oWiFiTambemTemTrilhaMasSemEnderecoDeVolta() {
        Guarda store = new Guarda();
        new TrilhaDoPedido(store).registrar("hub-0001", "HUB",
                TrilhaDoPedido.CANAL_WIFI, NUMERO, "");
        TrilhaDoPedido.Registro trilha = new TrilhaDoPedido(store).de("hub-0001");
        assertNotNull(trilha);
        assertEquals("HUB", trilha.origem);
        assertFalse("pelo Wi-Fi quem responde e o proprio PDV", trilha.porEmail());
        assertEquals("", trilha.destino);
    }

    @Test
    public void aMesmaOrigemNaoMudaDeCanal() {
        Guarda store = new Guarda();
        TrilhaDoPedido trilhas = new TrilhaDoPedido(store);
        trilhas.registrar("pdv-0001", "PDV", TrilhaDoPedido.CANAL_WIFI, NUMERO, "");
        trilhas.registrar("pdv-0001", "PDV", TrilhaDoPedido.CANAL_EMAIL, NUMERO, CAIXA_DO_GASPAR);
        assertEquals("registrar de novo e atualizar, nao duplicar", 1, trilhas.tamanho());
        assertTrue(trilhas.de("pdv-0001").porEmail());
    }

    @Test
    public void oMaisNovoFicaQuandoAGuardaEnche() {
        TrilhaDoPedido trilhas = new TrilhaDoPedido(new Guarda());
        for (int i = 0; i <= TrilhaDoPedido.LIMITE; i++) {
            trilhas.registrar("pdv-" + i, "PDV", TrilhaDoPedido.CANAL_EMAIL, NUMERO, CAIXA_DO_GASPAR);
        }
        assertEquals(TrilhaDoPedido.LIMITE, trilhas.tamanho());
        assertNull("o mais velho ja foi devolvido a muito tempo", trilhas.de("pdv-0"));
        assertNotNull(trilhas.de("pdv-" + TrilhaDoPedido.LIMITE));
    }

    @Test
    public void semIdentificadorNaoHaTrilha() {
        TrilhaDoPedido trilhas = new TrilhaDoPedido(new Guarda());
        trilhas.registrar(null, "PDV", TrilhaDoPedido.CANAL_EMAIL, NUMERO, CAIXA_DO_GASPAR);
        trilhas.registrar("   ", "PDV", TrilhaDoPedido.CANAL_EMAIL, NUMERO, CAIXA_DO_GASPAR);
        trilhas.registrar("pdv-0001", "PDV", null, NUMERO, CAIXA_DO_GASPAR);
        assertEquals(0, trilhas.tamanho());
    }

    @Test
    public void linhaEstragadaNaGuardaNaoTravaONovoPedido() {
        Guarda store = new Guarda();
        TrilhaDoPedido trilhas = new TrilhaDoPedido(store);
        trilhas.registrar("pdv-0001", "PDV", TrilhaDoPedido.CANAL_EMAIL, NUMERO, CAIXA_DO_GASPAR);
        store.valores.put("gaspar.pedido.trilha", store.valores.get("gaspar.pedido.trilha")
                + "\nquem escreveu isto nao e a barra");
        assertNotNull("a linha ruim fica de fora, o pedido segue", trilhas.de("pdv-0001"));
        assertEquals(1, trilhas.tamanho());
        trilhas.registrar("pdv-0002", "PDV", TrilhaDoPedido.CANAL_EMAIL, NUMERO, CAIXA_DO_GASPAR);
        assertEquals(2, new TrilhaDoPedido(store).tamanho());
    }

    @Test
    public void oSeparadorDentroDoEnderecoNaoQuebraAGuarda() {
        Guarda store = new Guarda();
        TrilhaDoPedido trilhas = new TrilhaDoPedido(store);
        trilhas.registrar("pdv-0001", "PDV", TrilhaDoPedido.CANAL_EMAIL, NUMERO, "soltar\nlinha@pdv.local");
        assertEquals(1, trilhas.tamanho());
        assertEquals("soltar linha@pdv.local", trilhas.de("pdv-0001").destino);
    }

    @Test
    public void oComprovanteVoltaPeloEmailSoQuandoHaParaQuem() {
        TrilhaDoPedido.Registro email = new TrilhaDoPedido.Registro(
                "pdv-0001", "PDV", TrilhaDoPedido.CANAL_EMAIL, NUMERO, CAIXA_DO_GASPAR);
        assertTrue(Comprovantes.voltaPeloEmail(email, SmsStatusReceiver.ESTADO_DELIVERED));
        assertFalse("sem endereco de volta nao ha para quem escrever",
                Comprovantes.voltaPeloEmail(new TrilhaDoPedido.Registro(
                        "pdv-0001", "PDV", TrilhaDoPedido.CANAL_EMAIL, NUMERO, ""),
                        SmsStatusReceiver.ESTADO_SENT));
        assertFalse("o Wi-Fi e o caminho de sempre",
                Comprovantes.voltaPeloEmail(new TrilhaDoPedido.Registro(
                        "pdv-0001", "PDV", TrilhaDoPedido.CANAL_WIFI, NUMERO, CAIXA_DO_GASPAR),
                        SmsStatusReceiver.ESTADO_SENT));
        assertFalse("o que o radio disse que nao e comprovante nao entra na fila",
                Comprovantes.voltaPeloEmail(email, "no_rota"));
        assertFalse("o pedido que nao passou pela barra volta por Wi-Fi",
                Comprovantes.voltaPeloEmail(null, SmsStatusReceiver.ESTADO_SENT));
    }
}
