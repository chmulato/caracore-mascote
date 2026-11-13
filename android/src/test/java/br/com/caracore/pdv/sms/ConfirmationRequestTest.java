package br.com.caracore.pdv.sms;

import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

public class ConfirmationRequestTest {

    private static final long AGORA = 1_760_000_000_000L;

    private static ConfirmationRequest pedido(String tipo, long valor, String referencia, long prazoSegundos) {
        return new ConfirmationRequest("pedido-1", tipo, referencia, valor, "cliente pediu",
                AGORA + prazoSegundos * 1000L, AGORA, "");
    }

    @Test
    public void aceitaDescontoDentroDasRegras() {
        assertNull(pedido(ConfirmationRequest.TIPO_DESCONTO, 1500L, "VENDA-10", 120).validar(AGORA));
    }

    @Test
    public void recusaTipoDesconhecido() {
        assertEquals("tipo", pedido("estorno", 1500L, "VENDA-10", 120).validar(AGORA));
    }

    @Test
    public void recusaPrazoCurtoDemais() {
        assertEquals("prazo", pedido(ConfirmationRequest.TIPO_SANGRIA, 500L, "CX-1", 20).validar(AGORA));
    }

    @Test
    public void recusaPrazoLongoDemais() {
        assertEquals("prazo", pedido(ConfirmationRequest.TIPO_CANCELAMENTO, 500L, "VENDA-9", 901).validar(AGORA));
    }

    @Test
    public void recusaValorAcimaDoTeto() {
        assertEquals("valor", pedido(ConfirmationRequest.TIPO_DESCONTO,
                ConfirmationRequest.VALOR_MAXIMO_CENTAVOS + 1, "VENDA-10", 120).validar(AGORA));
    }

    @Test
    public void recusaIdentificadorComCaracteresInvalidos() {
        ConfirmationRequest r = new ConfirmationRequest("pedido 1", ConfirmationRequest.TIPO_DESCONTO,
                "VENDA-10", 100L, "", AGORA + 120_000L, AGORA, "");
        assertEquals("identificador", r.validar(AGORA));
    }

    @Test
    public void recusaReferenciaVazia() {
        assertEquals("referencia", pedido(ConfirmationRequest.TIPO_DESCONTO, 100L, "", 120).validar(AGORA));
    }

    @Test
    public void expiraNoPrazo() {
        ConfirmationRequest r = pedido(ConfirmationRequest.TIPO_DESCONTO, 100L, "VENDA-10", 30);
        assertFalse(r.expirado(AGORA + 29_000L));
        assertTrue(r.expirado(AGORA + 30_000L));
    }

    @Test
    public void formataValorETipo() {
        ConfirmationRequest r = pedido(ConfirmationRequest.TIPO_SANGRIA, 123_456L, "CX-77", 120);
        assertEquals("R$ 1234,56", r.valorFormatado());
        assertEquals("sangria", r.tituloTipo());
        assertTrue(r.detalhes().contains("CX-77"));
    }

    @Test
    public void reconhecePedidoDeTeste() {
        ConfirmationRequest r = new ConfirmationRequest("t1", ConfirmationRequest.TIPO_DESCONTO,
                "TESTE", 100L, "", AGORA + 60_000L, AGORA, "teste");
        assertTrue(r.ehTeste());
        assertFalse(pedido(ConfirmationRequest.TIPO_DESCONTO, 100L, "VENDA-1", 60).ehTeste());
    }
}
