package br.com.caracore.pdv.sms;

import org.junit.Test;

import static org.junit.Assert.assertEquals;

public class WifiQrTest {

    @Test
    public void payloadSimples() {
        assertEquals("WIFI:T:WPA;S:Loja_Centro;P:senha123;H:false;;",
                WifiQr.payload("Loja_Centro", "senha123"));
    }

    @Test
    public void escapaCaracteresReservados() {
        assertEquals("WIFI:T:WPA;S:Casa\\;2;P:a\\:b\\,c\\\\d\\\"e;H:false;;",
                WifiQr.payload("Casa;2", "a:b,c\\d\"e"));
    }

    @Test
    public void naoAlteraTextoComum() {
        assertEquals("WIFI:T:WPA;S:Minha Rede;P:abcdefgh;H:false;;",
                WifiQr.payload("Minha Rede", "abcdefgh"));
    }
}
