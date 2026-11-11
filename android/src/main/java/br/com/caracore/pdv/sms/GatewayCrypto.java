package br.com.caracore.pdv.sms;

import android.util.Base64;

import java.nio.ByteBuffer;
import java.security.MessageDigest;
import java.util.Arrays;

import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;

/**
 * Descriptografia AES-256-GCM para comandos recebidos do PDV (mesma chave que mobile.gateway.shared.secret).
 */
public final class GatewayCrypto {

    private static final String ALG = "AES/GCM/NoPadding";
    private static final int GCM_TAG = 128;
    private static final int IV_LEN = 12;
    private static final int KEY_BYTES = 32;

    private final SecretKeySpec key;

    public GatewayCrypto(byte[] keyBytes) {
        if (keyBytes == null || keyBytes.length < KEY_BYTES) {
            try {
                MessageDigest md = MessageDigest.getInstance("SHA-256");
                keyBytes = md.digest(keyBytes != null ? keyBytes : new byte[0]);
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
        }
        byte[] k = new byte[KEY_BYTES];
        System.arraycopy(keyBytes, 0, k, 0, Math.min(KEY_BYTES, keyBytes.length));
        this.key = new SecretKeySpec(k, "AES");
    }

    public static GatewayCrypto fromBase64(String secretBase64) {
        if (secretBase64 == null || secretBase64.trim().isEmpty()) return null;
        try {
            byte[] decoded = Base64.decode(secretBase64.trim(), Base64.NO_WRAP);
            return new GatewayCrypto(decoded);
        } catch (Exception e) {
            return null;
        }
    }

    public byte[] decrypt(byte[] encrypted) throws Exception {
        if (encrypted == null || encrypted.length < IV_LEN) throw new IllegalArgumentException("Dados inválidos");
        ByteBuffer buf = ByteBuffer.wrap(encrypted);
        byte[] iv = new byte[IV_LEN];
        buf.get(iv);
        byte[] cipher = new byte[buf.remaining()];
        buf.get(cipher);
        Cipher c = Cipher.getInstance(ALG);
        c.init(Cipher.DECRYPT_MODE, key, new GCMParameterSpec(GCM_TAG, iv));
        return c.doFinal(cipher);
    }
}
