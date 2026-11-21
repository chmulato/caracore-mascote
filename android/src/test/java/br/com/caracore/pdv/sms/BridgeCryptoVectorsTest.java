package br.com.caracore.pdv.sms;

import org.junit.Test;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

/**
 * Vetores gerados pelo cifrador do Gaspar (gaspar/sms/crypto.py) na mesma maquina
 * que roda a ponte de e-mail. Eles provam que o celular abre exatamente o que o
 * computador escreve: chave de 32 bytes, AES-GCM com IV de 12 bytes na frente e
 * etiqueta de 16 no fim, sem dados autenticados extras.
 *
 * O IV e aleatorio, entao o sentido provado aqui e Java decifrando o blob do Python.
 * No caminho inverso o teste confere o formato do que o Java produz.
 */
public class BridgeCryptoVectorsTest {

    // ---------------------------------------------------------------- vector 1
    // Segredo com 18 bytes: mais curto que a chave, entao o Gaspar deriva SHA-256.
    static final String SEGREDO_CURTO_B64 = "Z2FzcGFyLXBvbnRlLWN1cnRh";
    static final String BLOB_CURTO_B64 =
            "tfijoU/1dOPF6p1pZ+1OKPYYAuX/dMRg1CCf7RjSX73ij0OpCvm+IYPtPezDw9x4tbSI/ySNOCbxsMzLKxdf"
                    + "HzyfEfoPBnL81sDExY23Mfx5ie14GZP253oJY5nUanDicdl5KFSk4m+Zb/Vf7WxNzFn8NgjBUgh"
                    + "Ja67msZ6LdikwcIab4COT/Bim8xshsRIzjERB92zRgslnW+69fNi6fU9yRgYTrkBYOUFBgEzgcG"
                    + "+56iXrVE6nDJZNV48e8+eUeU+1MdIg+XtkDAyu";
    static final String CLARO_PEDIDO =
            "{\"v\":1,\"tipo\":\"pedido\",\"referencia\":\"pdv-0001\",\"origem\":\"PDV\","
                    + "\"id_externo\":\"NF-77\",\"para\":\"+5541999998888\","
                    + "\"texto\":\"Ola, sua nota fiscal 77 esta pronta.\",\"quando\":1766000000.0}";

    // ---------------------------------------------------------------- vector 2
    // Segredo com os 32 bytes exatos: a chave e o proprio segredo decodificado.
    private static final String SEGREDO_EXATO_B64 = "csQIe53lPqgTl+lCJvdRNPUUlSPRQR6Vi5a/w6EjR0w=";
    private static final String BLOB_EXATO_B64 =
            "LuEy3Qvw+/BK4OEWeFo/BPQFDe/QG+f+XOaHr95tNwvDxNjiW+2abVXnvQ0u+fAHKHi0EiGkh9verJEWRNlE"
                    + "/eJBiBvVLjjPlyKrzyWgwdDnt3UA7h7MmdBWsogbdmWw4opgHKu2cUpdAVmT0auddD6MyIGWga"
                    + "IRCMzGSaBYh3Kf1gSv93yXSG9kATVRz551H0T8z8wCH2jmGUD+adHdaSbJVhOUjjzBi4yg3afP0w==";
    private static final String CLARO_COMPROVANTE =
            "{\"v\":1,\"tipo\":\"comprovante\",\"referencia\":\"pdv-0001\",\"para\":\"+5541999998888\","
                    + "\"estado\":\"entregue\",\"quando\":1766000060.0,\"dispositivo\":\"celular-loja\"}";

    // ---------------------------------------------------------------- vector 3
    // Segredo com 48 bytes: sobra material, o Gaspar corta nos primeiros 32.
    private static final String SEGREDO_LONGO_B64 =
            "l9ByRVNsUTEjYFvTzS0PlmdWV84CSB8kcWqeXyy6U0yXN2mwy2Yb7Y74V9Mui26m";
    private static final String BLOB_LONGO_B64 =
            "wCKyUDxbKhSwffQnD4tlY4H3tng+RbCHggQ/2gx150rFoI8lcwkf1Cfupay34034iMqO7FDLA+6VpAnEzvjK"
                    + "4ZGiqBUztcqyVZ/AhAOm0DmvmkKJ9YlgJHRhAmd2jVM1d2ZxaK3ATlQp6MimMblfrDBufvuKlOz"
                    + "T/U1BofzAtfOLAcDg6q4PjcubpfPOHeLxWkbOYpTMrGz7xmo79JH+o4YwcaQB2DGqEDv2UXm/if"
                    + "3HdDuNxS0ltyV6EawAL85dCifMh7KD8UtbCnQN9IYyiMrX6dgKT1Ziw4j0cZsa5AllZDpfJHbD";
    private static final String CLARO_RESPOSTA =
            "{\"v\":1,\"tipo\":\"resposta\",\"referencia\":\"hub-0002\",\"de\":\"+5541988887777\","
                    + "\"texto\":\"Nao vou conseguir retirar hoje, pode remarcar? Coracao e nota R$ 12,34\","
                    + "\"quando\":1766000100.0,\"dispositivo\":\"celular-loja\"}";

    // ---------------------------------------------------------------- vector 4
    // Mesma chave do vector 1, mas o texto tem acentos: prova o UTF-8 de ponta a ponta.
    private static final String BLOB_UTF8_B64 =
            "ncCagIJR7wyw00edlpHmjtFcc8EFVDOEubr8KVXiLe3RHdUWfKzngSaH8qxewEoZpg1IeBf3wn2c7oUhsZhO"
                    + "YJxYqYDgdDDIXMEd6xBYEVCdVyHB+OaM8D1MC1UOoc+vwM4WW2xDa1IJ4X74JhXmedy7OQ+qw3A"
                    + "ZaWxXxhYMQAKOuu2A54dMk1jpagZc4WlSP6GSAs9+xeBU4/TzOsuKpckaeGS+jxaOZc03f6kjVu"
                    + "eWSG1Mavw/AAOiUkTtP0Y10kKNWvfVwAFjMLlnCQUoF/WMyDte+aL2d5f9qSS61YGHDKsIuZONh"
                    + "+8HM8MiEJE=";
    private static final String CLARO_UTF8 =
            "{\"v\":1,\"tipo\":\"resposta\",\"referencia\":\"hub-0003\",\"de\":\"+5541988887777\","
                    + "\"texto\":\"N\u00e3o vou conseguir retirar hoje - pode remarcar? "
                    + "Cora\u00e7\u00e3o, aten\u00e7\u00e3o R$ 12,34\","
                    + "\"quando\":1766000200.0,\"dispositivo\":\"celular-loja\"}";

    static GatewayCrypto cifra(String segredoBase64) {
        return new GatewayCrypto(Base64.getDecoder().decode(segredoBase64));
    }

    private static String abre(String segredoBase64, String blobBase64) throws Exception {
        byte[] bruto = Base64.getDecoder().decode(blobBase64.replace("\r", "").replace("\n", ""));
        return new String(cifra(segredoBase64).decrypt(bruto), StandardCharsets.UTF_8);
    }

    @Test
    public void abreOMesmoPedidoQueOGasparEscreveu() throws Exception {
        assertEquals(CLARO_PEDIDO, abre(SEGREDO_CURTO_B64, BLOB_CURTO_B64));
    }

    @Test
    public void abreComprovanteComChaveDeTrintaEDoisBytes() throws Exception {
        assertEquals(CLARO_COMPROVANTE, abre(SEGREDO_EXATO_B64, BLOB_EXATO_B64));
    }

    @Test
    public void abreRespostaComChaveLongaCortada() throws Exception {
        assertEquals(CLARO_RESPOSTA, abre(SEGREDO_LONGO_B64, BLOB_LONGO_B64));
    }

    @Test
    public void preservaOsAcentosDoTextoCifrado() throws Exception {
        String aberto = abre(SEGREDO_CURTO_B64, BLOB_UTF8_B64);
        assertEquals(CLARO_UTF8, aberto);
        assertTrue("esperava o texto em UTF-8 com 211 bytes",
                CLARO_UTF8.getBytes(StandardCharsets.UTF_8).length == 211);
    }

    @Test
    public void corpoQuebradoEmLinhasDeEmailAbreOMesmoEnvelope() throws Exception {
        // O servidor de e-mail quebra o corpo em colunas; o celular junta antes de decodificar.
        String quebrado = quebraEmLinhas(BLOB_CURTO_B64, 76);
        assertEquals(BLOB_CURTO_B64, semEspacos(quebrado));
        assertEquals(CLARO_PEDIDO, abre(SEGREDO_CURTO_B64, quebrado));
    }

    @Test
    public void chaveDeOutroPareamentoNaoAbreONossoEnvelope() throws Exception {
        byte[] bruto = Base64.getDecoder().decode(BLOB_CURTO_B64);
        try {
            cifra(SEGREDO_EXATO_B64).decrypt(bruto);
            fail("a etiqueta GCM deveria recusar a chave errada");
        } catch (java.security.GeneralSecurityException esperada) {
            assertTrue(esperada instanceof javax.crypto.BadPaddingException);
        }
    }

    @Test
    public void oQueOCelularEscreveTemIvNaFrenteEtiquetaNoFim() throws Exception {
        GatewayCrypto c = cifra(SEGREDO_CURTO_B64);
        byte[] claro = CLARO_PEDIDO.getBytes(StandardCharsets.UTF_8);
        byte[] blob = c.encrypt(claro);
        assertEquals(12 + claro.length + 16, blob.length);
        // IV aleatorio: duas cifragens do mesmo texto nunca saem iguais.
        assertNotEquals(Base64.getEncoder().encodeToString(blob),
                Base64.getEncoder().encodeToString(c.encrypt(claro)));
    }

    @Test
    public void oQueOCelularEscreveVoltaPeloCaminhoInverso() throws Exception {
        GatewayCrypto c = cifra(SEGREDO_LONGO_B64);
        byte[] claro = CLARO_RESPOSTA.getBytes(StandardCharsets.UTF_8);
        assertEquals(CLARO_RESPOSTA, new String(c.decrypt(c.encrypt(claro)), StandardCharsets.UTF_8));
    }

    private static String quebraEmLinhas(String texto, int colunas) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < texto.length(); i += colunas) {
            sb.append(texto, i, Math.min(i + colunas, texto.length())).append("\r\n");
        }
        return sb.toString();
    }

    private static String semEspacos(String texto) {
        return texto.replaceAll("\\s", "");
    }
}
