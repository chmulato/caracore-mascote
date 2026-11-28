package br.com.caracore.pdv.sms;

import org.json.JSONObject;
import org.junit.Test;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

/**
 * As regras de leitura e escrita da ponte de e-mail, conferidas com o envelope
 * que o Gaspar no computador escreveu de verdade (BridgeCryptoVectorsTest).
 */
public class EmailEnvelopeTest {

    private static final GatewayCrypto CIFRA =
            new GatewayCrypto(Base64.getDecoder().decode(BridgeCryptoVectorsTest.SEGREDO_CURTO_B64));

    private static JSONObject abreCorpoDoGaspar(String blobBase64) throws Exception {
        String limpo = EmailEnvelope.corpoLimpo(blobBase64);
        return EmailEnvelope.abrir(CIFRA, Base64.getDecoder().decode(limpo));
    }

    @Test
    public void leOPedidoQueOGasparEscreveuNoComputador() throws Exception {
        JSONObject pedido = abreCorpoDoGaspar(BridgeCryptoVectorsTest.BLOB_CURTO_B64);
        assertEquals(1, pedido.getInt("v"));
        assertEquals("pedido", pedido.getString("tipo"));
        assertEquals("pdv-0001", pedido.getString("referencia"));
        assertEquals("PDV", pedido.getString("origem"));
        assertEquals("NF-77", pedido.getString("id_externo"));
        assertEquals("+5541999998888", pedido.getString("para"));
        assertEquals("Ola, sua nota fiscal 77 esta pronta.", pedido.getString("texto"));
    }

    @Test
    public void juntaOCorpoQueOservidorQuebrouEmColunas() throws Exception {
        StringBuilder quebrado = new StringBuilder();
        String blob = BridgeCryptoVectorsTest.BLOB_CURTO_B64;
        for (int i = 0; i < blob.length(); i += 54) {
            quebrado.append(blob, i, Math.min(i + 54, blob.length())).append("\r\n");
        }
        assertEquals(blob.length(), EmailEnvelope.corpoLimpo(quebrado.toString()).length());
        assertEquals("pdv-0001", abreCorpoDoGaspar(quebrado.toString()).getString("referencia"));
    }

    @Test
    public void recusaCorpoVazioOuQueNaoEBase64() {
        assertEquals("corpo de e-mail vazio", motivoDe(() -> EmailEnvelope.corpoLimpo("  \r\n  ")));
        assertEquals("corpo de e-mail nao e base64", motivoDe(() -> EmailEnvelope.corpoLimpo("Ola!,tudo bem?")));
    }

    @Test
    public void recusaBlobCurtoDemaisParaSerEnvelope() {
        assertEquals("corpo de e-mail curto demais", motivoDe(() -> EmailEnvelope.abrir(CIFRA, new byte[27])));
        assertEquals("corpo de e-mail curto demais", motivoDe(() -> EmailEnvelope.abrir(CIFRA, null)));
    }

    @Test
    public void recusaEnvelopeQueNAoAbreComEstaChave() {
        byte[] blob = Base64.getDecoder().decode(BridgeCryptoVectorsTest.BLOB_CURTO_B64);
        GatewayCrypto outra = new GatewayCrypto(Base64.getDecoder().decode("csQIe53lPqgTl+lCJvdRNPUUlSPRQR6Vi5a/w6EjR0w="));
        assertEquals("envelope nao abre com esta chave", motivoDe(() -> EmailEnvelope.abrir(outra, blob)));
    }

    @Test
    public void recusaVersaoOuTipoQueNaoConhecemos() throws Exception {
        byte[] v2 = EmailEnvelope.selar(CIFRA, new JSONObject("{\"v\":2,\"tipo\":\"pedido\"}"));
        assertEquals("versao de envelope desconhecida", motivoDe(() -> EmailEnvelope.abrir(CIFRA, v2)));
        byte[] spam = EmailEnvelope.selar(CIFRA, new JSONObject("{\"v\":1,\"tipo\":\"propaganda\"}"));
        assertEquals("tipo de envelope desconhecido", motivoDe(() -> EmailEnvelope.abrir(CIFRA, spam)));
    }

    @Test
    public void escreveELeOMesmoComprovante() throws Exception {
        JSONObject corpo = EmailEnvelope.comprovante("pdv-0001", "+5541999998888",
                EmailEnvelope.ESTADO_ENTREGUE, 1766000060L, "celular-loja");
        byte[] selado = EmailEnvelope.selar(CIFRA, corpo);
        assertEquals(12 + corpo.toString().getBytes(StandardCharsets.UTF_8).length + 16, selado.length);
        JSONObject aberto = EmailEnvelope.abrir(CIFRA, selado);
        assertEquals("comprovante", aberto.getString("tipo"));
        assertEquals("pdv-0001", aberto.getString("referencia"));
        assertEquals("entregue", aberto.getString("estado"));
        assertEquals(1766000060.0, aberto.getDouble("quando"), 0.0);
        assertEquals("celular-loja", aberto.getString("dispositivo"));
    }

    @Test
    public void oQueOCelularEscreveNaoTemEspacoEntreOsCampos() throws Exception {
        JSONObject corpo = EmailEnvelope.comprovante("pdv-1", "+5541999998888",
                EmailEnvelope.ESTADO_ENVIADO, 1L, "cel");
        String json = corpo.toString();
        assertFalse(json, json.contains(": "));
        assertFalse(json, json.contains(", "));
        assertTrue(json, json.startsWith("{") && json.endsWith("}"));
    }

    @Test
    public void reconheceOAssuntoDaPonteEaSuaOrigem() {
        assertEquals("GASPAR PDV abc-123", EmailEnvelope.assunto("PDV", "abc-123"));
        assertTrue(EmailEnvelope.ehDaPonte("GASPAR HUB abc"));
        assertFalse(EmailEnvelope.ehDaPonte("Re: orcamento"));
        assertFalse(EmailEnvelope.ehDaPonte(null));
        assertEquals("PDV", EmailEnvelope.origemNoAssunto("GASPAR PDV abc-123"));
        assertEquals("HUB", EmailEnvelope.origemNoAssunto("GASPAR HUB abc-123"));
        assertEquals("PDV", EmailEnvelope.origemNoAssunto("GASPAR PDV"));
        assertEquals("", EmailEnvelope.origemNoAssunto("qualquer coisa"));
    }

    @Test
    public void traduzOAEstadoDoRadioParaOAEstadoDaPonte() {
        assertEquals("enviado", EmailEnvelope.estadoDoRadio(SmsStatusReceiver.ESTADO_SENT));
        assertEquals("entregue", EmailEnvelope.estadoDoRadio(SmsStatusReceiver.ESTADO_DELIVERED));
        assertEquals("falhou", EmailEnvelope.estadoDoRadio(SmsStatusReceiver.ESTADO_FAILED));
        assertNull(EmailEnvelope.estadoDoRadio("outra coisa"));
        assertNull(EmailEnvelope.estadoDoRadio(null));
    }

    @Test
    public void campoAusenteViraTextoVazio() {
        JSONObject corpo = new JSONObject();
        assertEquals("", EmailEnvelope.texto(corpo, "referencia"));
        assertEquals("", EmailEnvelope.texto(null, "referencia"));
    }

    private interface Acao {
        void executa() throws Exception;
    }

    private static String motivoDe(Acao acao) {
        try {
            acao.executa();
            fail("era para ter recusado");
            return null;
        } catch (EmailEnvelope.Recusa recusa) {
            return recusa.getMessage();
        } catch (Exception outra) {
            fail("recusa esperada, veio " + outra.getClass().getSimpleName() + ": " + outra.getMessage());
            return null;
        }
    }
}
