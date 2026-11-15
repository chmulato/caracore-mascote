package br.com.caracore.pdv.sms;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;

import org.junit.Test;

public class LicenseSmsTest {

    @Test
    public void chavePuraEhAceita() {
        assertEquals("CC-202611-deadbeef", LicenseSms.chaveDe("CC-202611-deadbeef"));
    }

    @Test
    public void prefixoMinusculoEhNormalizado() {
        assertEquals("CC-202611-deadbeef", LicenseSms.chaveDe("cc-202611-deadbeef"));
    }

    @Test
    public void smsInteiroEhAceito() {
        assertEquals("CC-202612-0123abcd", LicenseSms.chaveDe("CC-LICENSE: CC-202612-0123abcd"));
    }

    @Test
    public void corpoCaracoreKeyEhAceito() {
        assertEquals("CC-202612-0123abcd", LicenseSms.chaveDe("CARACORE-KEY: CC-202612-0123abcd"));
    }

    @Test
    public void espacosSaoAparados() {
        assertEquals("CC-202611-deadbeef", LicenseSms.chaveDe("  CC-202611-deadbeef  "));
    }

    @Test
    public void formatoErradoEhRecusado() {
        assertNull(LicenseSms.chaveDe("liberado"));
        assertNull(LicenseSms.chaveDe("CC-2026-1234"));
        assertNull(LicenseSms.chaveDe("CC-202611-xyz"));
        assertNull(LicenseSms.chaveDe("CC-LICENSE: liberado"));
    }

    @Test
    public void vazioENuloSaoRecusados() {
        assertNull(LicenseSms.chaveDe(null));
        assertNull(LicenseSms.chaveDe(""));
        assertNull(LicenseSms.chaveDe("   "));
    }

    @Test
    public void telefoneNaoEhChave() {
        assertNull(LicenseSms.chaveDe("11999998888"));
    }
}
