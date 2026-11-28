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
 * A senha de app do correio, cifrada por uma chave do Android Keystore que nao sai do
 * aparelho e nao se copia com o backup do app (allowBackup esta desligado). E o unico
 * segredo novo da ponte: a chave de pareamento de cada origem e a mesma do canal
 * Wi-Fi, guardada em {@link SmsPreferences}, para o pareamento nao se divergir entre
 * as duas portas de entrada.
 *
 * A tela do lojista diz que a senha esta guardada e nunca a mostra.
 */
public final class EmailKeystore {

    private static final String PREFS = "gaspar_email_segs";
    private static final String PREFIXO = "seg_";
    private static final String SENHA_DE_APP = "senha_app";
    private static final String KEYSTORE = "AndroidKeyStore";
    private static final String ALIAS = "gaspar_email_key";
    private static final String ALG = "AES/GCM/NoPadding";
    private static final int IV_LEN = 12;
    private static final int GCM_TAG = 128;

    private EmailKeystore() {
    }

    // ------------------------------------------------------------------ senha de app

    public static boolean guardarSenhaDeApp(Context context, String senha) {
        return guardar(context, SENHA_DE_APP, senha);
    }

    public static boolean temSenhaDeApp(Context context) {
        return texto(context, SENHA_DE_APP) != null;
    }

    /** Null quando nao ha senha guardada ou quando a chave do aparelho nao abre mais. */
    public static String senhaDeApp(Context context) {
        return abrir(context, SENHA_DE_APP);
    }

    public static void esquecerSenhaDeApp(Context context) {
        apagar(context, SENHA_DE_APP);
    }

    // ------------------------------------------------------------------ miudezas

    private static boolean guardar(Context context, String nome, String valor) {
        if (valor == null || valor.trim().isEmpty()) {
            apagar(context, nome);
            return false;
        }
        try {
            preferencias(context).edit()
                    .putString(PREFIXO + nome, cifrar(valor.trim())).apply();
            return true;
        } catch (Exception e) {
            PdvSmsLogger.i("EmailKeystore", "nao foi possivel guardar: " + e.getClass().getSimpleName());
            return false;
        }
    }

    private static String abrir(Context context, String nome) {
        String guardado = texto(context, nome);
        if (guardado == null) {
            return null;
        }
        try {
            return decifrar(guardado);
        } catch (Exception e) {
            // a chave do aparelho foi trocada ou apagada: o segredo se refaz na tela
            PdvSmsLogger.i("EmailKeystore", "nao foi possivel abrir: " + e.getClass().getSimpleName());
            return null;
        }
    }

    private static void apagar(Context context, String nome) {
        preferencias(context).edit().remove(PREFIXO + nome).apply();
    }

    private static String texto(Context context, String nome) {
        return preferencias(context).getString(PREFIXO + nome, null);
    }

    private static SharedPreferences preferencias(Context context) {
        return context.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private static SecretKey chave() throws Exception {
        KeyStore ks = KeyStore.getInstance(KEYSTORE);
        ks.load(null);
        if (ks.containsAlias(ALIAS)) {
            KeyStore.Entry entrada = ks.getEntry(ALIAS, null);
            if (entrada instanceof KeyStore.SecretKeyEntry) {
                return ((KeyStore.SecretKeyEntry) entrada).getSecretKey();
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
        c.init(Cipher.DECRYPT_MODE, chave(), new GCMParameterSpec(GCM_TAG, iv));
        return new String(c.doFinal(dados), StandardCharsets.UTF_8);
    }
}
