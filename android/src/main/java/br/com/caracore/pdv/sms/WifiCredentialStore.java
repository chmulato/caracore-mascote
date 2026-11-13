package br.com.caracore.pdv.sms;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * Guarda o nome e a senha da rede da loja cifrados por uma chave do Android Keystore.
 * A senha só é devolvida quando a tela confirma que o dono do celular autorizou.
 */
public final class WifiCredentialStore {

    private static final String PREFS = "pdv_wifi_prefs";
    private static final String KEY_SSID = "wifi_ssid_enc";
    private static final String KEY_SENHA = "wifi_senha_enc";
    private static final String KEYSTORE = "AndroidKeyStore";
    private static final String ALIAS = "gaspar_wifi_key";
    private static final String ALG = "AES/GCM/NoPadding";
    private static final int IV_LEN = 12;

    private WifiCredentialStore() {
    }

    private static SharedPreferences prefs(Context context) {
        return context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private static SecretKey chave() throws Exception {
        KeyStore ks = KeyStore.getInstance(KEYSTORE);
        ks.load(null);
        if (ks.containsAlias(ALIAS)) {
            KeyStore.Entry entry = ks.getEntry(ALIAS, null);
            if (entry instanceof KeyStore.SecretKeyEntry) {
                return ((KeyStore.SecretKeyEntry) entry).getSecretKey();
            }
        }
        KeyGenerator kg = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE);
        kg.init(new KeyGenParameterSpec.Builder(ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build());
        return kg.generateKey();
    }

    private static String cifrar(String texto) throws Exception {
        Cipher c = Cipher.getInstance(ALG);
        c.init(Cipher.ENCRYPT_MODE, chave());
        byte[] iv = c.getIV();
        byte[] dados = c.doFinal(texto.getBytes(StandardCharsets.UTF_8));
        ByteBuffer out = ByteBuffer.allocate(iv.length + dados.length);
        out.put(iv);
        out.put(dados);
        return Base64.encodeToString(out.array(), Base64.NO_WRAP);
    }

    private static String decifrar(String b64) throws Exception {
        byte[] bruto = Base64.decode(b64, Base64.NO_WRAP);
        ByteBuffer buf = ByteBuffer.wrap(bruto);
        byte[] iv = new byte[IV_LEN];
        buf.get(iv);
        byte[] dados = new byte[buf.remaining()];
        buf.get(dados);
        Cipher c = Cipher.getInstance(ALG);
        c.init(Cipher.DECRYPT_MODE, chave(), new GCMParameterSpec(128, iv));
        return new String(c.doFinal(dados), StandardCharsets.UTF_8);
    }

    public static boolean guardar(Context context, String ssid, String senha) {
        if (ssid == null || ssid.trim().isEmpty() || senha == null || senha.isEmpty()) {
            return false;
        }
        try {
            prefs(context).edit()
                    .putString(KEY_SSID, cifrar(ssid.trim()))
                    .putString(KEY_SENHA, cifrar(senha))
                    .apply();
            return true;
        } catch (Exception e) {
            PdvSmsLogger.i("WifiStore", "nao foi possivel guardar: " + e.getClass().getSimpleName());
            return false;
        }
    }

    public static boolean temRede(Context context) {
        return prefs(context).getString(KEY_SSID, null) != null;
    }

    /** Nome da rede guardada; não é segredo e pode ser mostrado no painel. */
    public static String ssid(Context context) {
        String enc = prefs(context).getString(KEY_SSID, null);
        if (enc == null) return null;
        try {
            return decifrar(enc);
        } catch (Exception e) {
            return null;
        }
    }

    public static boolean temSenha(Context context) {
        return prefs(context).getString(KEY_SENHA, null) != null;
    }

    /** Só devolve a senha com autorização explícita da tela. */
    public static String senha(Context context, boolean autorizado) {
        if (!autorizado) return null;
        String enc = prefs(context).getString(KEY_SENHA, null);
        if (enc == null) return null;
        try {
            return decifrar(enc);
        } catch (Exception e) {
            return null;
        }
    }
}
