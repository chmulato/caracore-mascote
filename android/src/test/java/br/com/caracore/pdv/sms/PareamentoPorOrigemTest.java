package br.com.caracore.pdv.sms;

import org.junit.Test;

import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

/**
 * O pareamento por produto no celular: quem escreveu o pedido e dono da fila dele.
 * O que se confere aqui e a porta que nao pode abrir: um pedido do Hub entrando na
 * fila do PDV (que tem teto, licenca e tela proprios) e o contrario. Tambem o que
 * nao pode quebrar: a loja com chave mal formada e o pareamento antigo de uma chave
 * so para a loja inteira.
 */
public class PareamentoPorOrigemTest {

    /** As mesmas chaves de teste dos vetores da cifra: nada aqui e segredo de producao. */
    private static final String CHAVE_PDV = "csQIe53lPqgTl+lCJvdRNPUUlSPRQR6Vi5a/w6EjR0w=";
    private static final String CHAVE_HUB = "l9ByRVNsUTEjYFvTzS0PlmdWV84CSB8kcWqeXyy6U0yXN2mwy2Yb7Y74V9Mui26m";
    private static final String CHAVE_DE_FORA = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";

    private final Bancada.B64DaMaquina base64 = new Bancada.B64DaMaquina();

    /** A fonte de producao le as preferencias; aqui e um mapa, sem pareamento por omissao. */
    private static PareamentoPorOrigem.Fonte fontePorOrigem(String pdv, String hub) {
        final Map<String, String> chaves = new HashMap<>();
        chaves.put(PareamentoPorOrigem.PDV, pdv);
        chaves.put(PareamentoPorOrigem.HUB, hub);
        return new PareamentoPorOrigem.Fonte() {
            @Override
            public String chaveDaOrigem(String origem) {
                return chaves.get(origem);
            }
        };
    }

    /** O legado: uma chave so, que o celular oferece aos dois produtos. */
    private static PareamentoPorOrigem.Fonte fonteLegado(final String chave) {
        return new PareamentoPorOrigem.Fonte() {
            @Override
            public String chaveDaOrigem(String origem) {
                return origem.isEmpty() ? null : chave;
            }
        };
    }

    private byte[] selar(String chave, String claro) throws Exception {
        return new GatewayCrypto(base64.decodificar(chave.trim())).encrypt(claro.getBytes(StandardCharsets.UTF_8));
    }

    @Test
    public void soQuemTemChaveEntra() {
        PareamentoPorOrigem pares = new PareamentoPorOrigem(fontePorOrigem(CHAVE_PDV, null), base64);
        assertTrue(pares.pareado());
        assertNotNull(pares.daOrigem("PDV"));
        assertNull("o Hub sem pareamento nao tem fila neste celular", pares.daOrigem("HUB"));
        assertEquals("PDV", pares.origensPareadas());
    }

    @Test
    public void semNenhumaChaveONaoAbre() throws Exception {
        PareamentoPorOrigem pares = new PareamentoPorOrigem(fontePorOrigem(null, null), base64);
        assertFalse(pares.pareado());
        assertNull(pares.abrir(selar(CHAVE_PDV, "{}")));
        assertEquals("", pares.origensPareadas());
    }

    @Test
    public void cadaProdutoAbreComaSuaChave() throws Exception {
        PareamentoPorOrigem pares = new PareamentoPorOrigem(fontePorOrigem(CHAVE_PDV, CHAVE_HUB), base64);
        assertEquals("PDV HUB", pares.origensPareadas());

        PareamentoPorOrigem.Aberto pdv = pares.abrir(selar(CHAVE_PDV, "{\"action\":\"send_sms\"}"));
        assertNotNull(pdv);
        assertEquals("PDV", pdv.par.origem());
        assertEquals("{\"action\":\"send_sms\"}", pdv.texto());

        PareamentoPorOrigem.Aberto hub = pares.abrir(selar(CHAVE_HUB, "{}"));
        assertNotNull(hub);
        assertEquals("HUB", hub.par.origem());
    }

    @Test
    public void origemTrocadaNaoChegaAoRadio() throws Exception {
        PareamentoPorOrigem pares = new PareamentoPorOrigem(fontePorOrigem(CHAVE_PDV, CHAVE_HUB), base64);
        assertFalse("o pedido do Hub escrito com a chave do PDV nao passa",
                pares.abrir(selar(CHAVE_PDV, "{}")).par.servePara("HUB"));
        assertFalse("e o contrario tambem", pares.abrir(selar(CHAVE_HUB, "{}")).par.servePara("PDV"));
        assertTrue(pares.abrir(selar(CHAVE_PDV, "{}")).par.servePara("PDV"));
    }

    @Test
    public void chaveDeQuemNaoEstaPareadoNaoAbreNada() throws Exception {
        PareamentoPorOrigem pares = new PareamentoPorOrigem(fontePorOrigem(CHAVE_PDV, CHAVE_HUB), base64);
        assertNull(pares.abrir(selar(CHAVE_DE_FORA, "{}")));
    }

    @Test
    public void oLegadoDeUmaChaveSoContinuaValendo() throws Exception {
        PareamentoPorOrigem pares = new PareamentoPorOrigem(fonteLegado(CHAVE_PDV), base64);
        assertEquals("uma chave, dois produtos: o painel nao inventa pareamento",
                "PDV HUB", pares.origensPareadas());
        assertTrue(pares.abrir(selar(CHAVE_PDV, "{}")).par.servePara("PDV"));
        assertTrue(pares.abrir(selar(CHAVE_PDV, "{}")).par.servePara("HUB"));
        assertEquals("quem abriu primeiro e o PDV", "PDV", pares.daOrigem("HUB").origem());
        assertNotNull("o 1.7 nao declara origem: a chave que abriu responde por ela",
                pares.abrir(selar(CHAVE_PDV, "{}")).par.servePara(null));
        assertNull(pares.abrir(selar(CHAVE_HUB, "{}")));
    }

    @Test
    public void chaveMalFormadaFicaDeForaSemDerrubarOAparecido() {
        PareamentoPorOrigem pares = new PareamentoPorOrigem(
                fontePorOrigem("nem parece base64!", CHAVE_HUB), base64);
        assertEquals("HUB", pares.origensPareadas());
        assertNotNull(pares.daOrigem("HUB"));
        assertNull(pares.daOrigem("PDV"));
    }

    @Test
    public void umaFonteQueQuebraNaoDerrubaOCelular() {
        PareamentoPorOrigem pares = new PareamentoPorOrigem(new PareamentoPorOrigem.Fonte() {
            @Override
            public String chaveDaOrigem(String origem) {
                throw new IllegalStateException("preferencia corrompida");
            }
        }, base64);
        assertFalse(pares.pareado());
    }

    @Test
    public void espacosEMaiusculasNaoMudamOAutor() throws Exception {
        PareamentoPorOrigem pares = new PareamentoPorOrigem(
                fontePorOrigem("  " + CHAVE_PDV + "  ", null), base64);
        PareamentoPorOrigem.Aberto aberto = pares.abrir(selar(CHAVE_PDV, "{}"));
        assertNotNull("a chave guardada com espacos abre do mesmo jeito", aberto);
        assertTrue(aberto.par.servePara(" pdv ".toUpperCase(Locale.US)));
        assertTrue("o comando antigo, sem origem, e do dono da chave", aberto.par.servePara(""));
        assertNull(pares.daOrigem(null));
        assertNull(pares.daOrigem("  "));
    }
}
