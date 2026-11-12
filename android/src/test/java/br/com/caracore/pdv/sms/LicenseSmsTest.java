package br.com.caracore.pdv.sms;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class LicenseSmsTest {

    private static final String OFICIAL = "11999998888";
    private static final String CORPO_OK = "CC-LICENSE:CC-202611-deadbeef";

    @Test
    public void semNumeroConfiguradoNaoAceita() {
        LicenseSms.Resultado r = LicenseSms.avaliar("+55 11 99999-8888", CORPO_OK, null);
        assertEquals(LicenseSms.Motivo.NUMERO_NAO_CONFIGURADO, r.getMotivo());
        assertFalse(r.isAceita());
    }

    @Test
    public void numeroCurtoNaoServeComoOficial() {
        LicenseSms.Resultado r = LicenseSms.avaliar("29000", CORPO_OK, "29000");
        assertEquals(LicenseSms.Motivo.NUMERO_NAO_CONFIGURADO, r.getMotivo());
    }

    @Test
    public void remetenteDiferenteNaoAceita() {
        LicenseSms.Resultado r = LicenseSms.avaliar("+55 11 88888-7777", CORPO_OK, OFICIAL);
        assertEquals(LicenseSms.Motivo.REMETENTE_DIVERGENTE, r.getMotivo());
    }

    @Test
    public void remetenteComPaisAceita() {
        LicenseSms.Resultado r = LicenseSms.avaliar("+55 11 99999-8888", CORPO_OK, OFICIAL);
        assertTrue(r.isAceita());
        assertEquals("CC-202611-deadbeef", r.getChave());
    }

    @Test
    public void prefixoCaracoreKeyAceita() {
        LicenseSms.Resultado r = LicenseSms.avaliar("11999998888", "CARACORE-KEY: CC-202612-0123abcd", OFICIAL);
        assertTrue(r.isAceita());
        assertEquals("CC-202612-0123abcd", r.getChave());
    }

    @Test
    public void chaveForaDoFormatoNaoAceita() {
        LicenseSms.Resultado r = LicenseSms.avaliar("+55 11 99999-8888", "CC-LICENSE: liberado", OFICIAL);
        assertEquals(LicenseSms.Motivo.CHAVE_INVALIDA, r.getMotivo());
    }

    @Test
    public void mensagemSemPrefixoEhIgnorada() {
        LicenseSms.Resultado r = LicenseSms.avaliar("+55 11 99999-8888", "bom dia", OFICIAL);
        assertEquals(LicenseSms.Motivo.CHAVE_AUSENTE, r.getMotivo());
    }

    @Test
    public void numeroValidoExigeDezADigitos() {
        assertFalse(LicenseSms.numeroValido("119999888"));
        assertTrue(LicenseSms.numeroValido("1199998888"));
        assertTrue(LicenseSms.numeroValido("+55 (11) 99999-8888"));
        assertFalse(LicenseSms.numeroValido("55119999988880000"));
        assertFalse(LicenseSms.numeroValido(null));
    }
}
