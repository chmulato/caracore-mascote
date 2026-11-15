package br.com.caracore.pdv.sms;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class BackupTokenTest {

    @Test
    public void gerarDevolveTrintaEDoisCaracteresHex() {
        assertEquals(32, BackupToken.gerar().length());
        assertTrue(BackupToken.gerar().matches("[0-9a-f]{32}"));
    }

    @Test
    public void tokensGeradosSaoDiferentes() {
        assertNotEquals(BackupToken.gerar(), BackupToken.gerar());
    }

    @Test
    public void tokenIgualConfere() {
        assertTrue(BackupToken.confere("abc123", "abc123"));
    }

    @Test
    public void espacosDoEnvioSaoIgnorados() {
        assertTrue(BackupToken.confere("  abc123  ", "abc123"));
    }

    @Test
    public void tokenAusenteOuVazioRecusa() {
        assertFalse(BackupToken.confere(null, "abc123"));
        assertFalse(BackupToken.confere("", "abc123"));
        assertFalse(BackupToken.confere("abc123", null));
        assertFalse(BackupToken.confere("abc123", ""));
    }

    @Test
    public void tokenDiferenteRecusa() {
        assertFalse(BackupToken.confere("abc124", "abc123"));
    }
}
