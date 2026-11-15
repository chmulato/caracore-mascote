package br.com.caracore.pdv.sms;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;

/**
 * Token que o PDV envia junto do aviso de backup.
 * Sem o token, qualquer app poderia gravar um status falso no cartão de backup.
 */
final class BackupToken {

    private static final SecureRandom RANDOM = new SecureRandom();
    private static final char[] HEX = "0123456789abcdef".toCharArray();

    private BackupToken() {
    }

    static String gerar() {
        byte[] bytes = new byte[16];
        RANDOM.nextBytes(bytes);
        char[] saida = new char[bytes.length * 2];
        for (int i = 0; i < bytes.length; i++) {
            int b = bytes[i] & 0xff;
            saida[i * 2] = HEX[b >>> 4];
            saida[i * 2 + 1] = HEX[b & 0x0f];
        }
        return new String(saida);
    }

    static boolean confere(String enviado, String guardado) {
        if (enviado == null || guardado == null || guardado.isEmpty()) {
            return false;
        }
        return MessageDigest.isEqual(enviado.trim().getBytes(StandardCharsets.US_ASCII),
                guardado.getBytes(StandardCharsets.US_ASCII));
    }
}
