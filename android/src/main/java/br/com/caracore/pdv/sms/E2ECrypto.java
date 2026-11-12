package br.com.caracore.pdv.sms;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.security.AlgorithmParameters;
import java.security.KeyFactory;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.KeyStore;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.interfaces.ECPublicKey;
import java.security.spec.ECGenParameterSpec;
import java.security.spec.ECParameterSpec;
import java.security.spec.ECPoint;
import java.security.spec.ECPublicKeySpec;
import java.security.spec.PKCS8EncodedKeySpec;

import javax.crypto.Cipher;
import javax.crypto.KeyAgreement;
import javax.crypto.KeyGenerator;
import javax.crypto.Mac;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;

/**
 * Criptografia de ponta a ponta entre o aplicativo e o computador do PDV.
 * O celular guarda o par EC P-256 (chave privada protegida pelo Android Keystore);
 * cada pedido traz uma chave efêmera (ECDH + HKDF-SHA256) e o texto em AES-256-GCM.
 */
public final class E2ECrypto {

    private static final String KEYSTORE = "AndroidKeyStore";
    private static final String WRAP_ALIAS = "pdv_sms_e2e_wrap";
    private static final String CURVE = "secp256r1";
    private static final String ALG = "AES/GCM/NoPadding";
    private static final int GCM_TAG = 128;
    private static final int IV_LEN = 12;
    private static final int POINT_LEN = 65;
    private static final int TAG_LEN = 16;
    private static final byte[] SALT = "gaspar-sms-e2e-v1".getBytes(StandardCharsets.UTF_8);
    private static final byte[] INFO = "pdv-phone".getBytes(StandardCharsets.UTF_8);

    private E2ECrypto() {
    }

    /** Devolve a chave pública (Base64) criando o par na primeira vez. */
    public static synchronized String ensureKeyPair(Context context) throws Exception {
        SmsPreferences prefs = new SmsPreferences(context);
        String publicB64 = prefs.getE2ePublicKey();
        String privateB64 = prefs.getE2ePrivateKey();
        if (publicB64 != null && !publicB64.isEmpty() && privateB64 != null && !privateB64.isEmpty()) {
            return publicB64;
        }
        KeyPairGenerator generator = KeyPairGenerator.getInstance("EC");
        generator.initialize(new ECGenParameterSpec(CURVE));
        KeyPair pair = generator.generateKeyPair();
        byte[] point = encodePoint(((ECPublicKey) pair.getPublic()).getW());
        prefs.setE2eKeys(wrap(pair.getPrivate().getEncoded()), Base64.encodeToString(point, Base64.NO_WRAP));
        PdvSmsLogger.i("E2ECrypto", "Par de chaves de ponta a ponta criado.");
        return Base64.encodeToString(point, Base64.NO_WRAP);
    }

    public static String getPublicKeyBase64(Context context) {
        String value = new SmsPreferences(context).getE2ePublicKey();
        return value != null ? value : "";
    }

    /** Abre o envelope fechado pelo PDV. AAD = identificador do pedido. */
    public static byte[] open(Context context, String envelopeBase64, byte[] aad) throws Exception {
        if (envelopeBase64 == null || envelopeBase64.isEmpty()) {
            throw new IllegalArgumentException("envelope ausente");
        }
        byte[] raw = Base64.decode(envelopeBase64, Base64.NO_WRAP);
        if (raw.length < POINT_LEN + IV_LEN + TAG_LEN || raw[0] != 0x04) {
            throw new IllegalArgumentException("envelope invalido");
        }
        String privateB64 = new SmsPreferences(context).getE2ePrivateKey();
        if (privateB64 == null || privateB64.isEmpty()) {
            throw new IllegalStateException("celular sem chave de criptografia");
        }

        BigInteger x = new BigInteger(1, slice(raw, 1, 32));
        BigInteger y = new BigInteger(1, slice(raw, 33, 32));
        AlgorithmParameters parameters = AlgorithmParameters.getInstance("EC");
        parameters.init(new ECGenParameterSpec(CURVE));
        ECParameterSpec spec = parameters.getParameterSpec(ECParameterSpec.class);
        PublicKey peer = KeyFactory.getInstance("EC")
                .generatePublic(new ECPublicKeySpec(new ECPoint(x, y), spec));

        PrivateKey mine = KeyFactory.getInstance("EC")
                .generatePrivate(new PKCS8EncodedKeySpec(unwrap(privateB64)));
        KeyAgreement agreement = KeyAgreement.getInstance("ECDH");
        agreement.init(mine);
        agreement.doPhase(peer, true);
        byte[] key = hkdf(agreement.generateSecret());

        byte[] iv = slice(raw, POINT_LEN, IV_LEN);
        byte[] body = slice(raw, POINT_LEN + IV_LEN, raw.length - POINT_LEN - IV_LEN);
        Cipher cipher = Cipher.getInstance(ALG);
        cipher.init(Cipher.DECRYPT_MODE, new SecretKeySpec(key, "AES"), new GCMParameterSpec(GCM_TAG, iv));
        cipher.updateAAD(aad);
        return cipher.doFinal(body);
    }

    private static byte[] hkdf(byte[] shared) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(SALT, "HmacSHA256"));
        byte[] prk = mac.doFinal(shared);
        mac.init(new SecretKeySpec(prk, "HmacSHA256"));
        mac.update(INFO);
        mac.update((byte) 1);
        return mac.doFinal();
    }

    private static byte[] encodePoint(ECPoint point) {
        byte[] encoded = new byte[POINT_LEN];
        encoded[0] = 0x04;
        System.arraycopy(fixed(point.getAffineX()), 0, encoded, 1, 32);
        System.arraycopy(fixed(point.getAffineY()), 0, encoded, 33, 32);
        return encoded;
    }

    private static byte[] fixed(BigInteger value) {
        byte[] raw = value.toByteArray();
        byte[] out = new byte[32];
        if (raw.length >= 32) {
            System.arraycopy(raw, raw.length - 32, out, 0, 32);
        } else {
            System.arraycopy(raw, 0, out, 32 - raw.length, raw.length);
        }
        return out;
    }

    private static byte[] slice(byte[] source, int offset, int length) {
        byte[] out = new byte[length];
        System.arraycopy(source, offset, out, 0, length);
        return out;
    }

    private static SecretKey wrappingKey() throws Exception {
        KeyStore store = KeyStore.getInstance(KEYSTORE);
        store.load(null);
        if (!store.containsAlias(WRAP_ALIAS)) {
            KeyGenerator generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE);
            generator.init(new KeyGenParameterSpec.Builder(
                    WRAP_ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .build());
            generator.generateKey();
        }
        return (SecretKey) store.getKey(WRAP_ALIAS, null);
    }

    private static String wrap(byte[] plain) throws Exception {
        Cipher cipher = Cipher.getInstance(ALG);
        cipher.init(Cipher.ENCRYPT_MODE, wrappingKey());
        byte[] iv = cipher.getIV();
        byte[] body = cipher.doFinal(plain);
        byte[] out = new byte[iv.length + body.length];
        System.arraycopy(iv, 0, out, 0, iv.length);
        System.arraycopy(body, 0, out, iv.length, body.length);
        return Base64.encodeToString(out, Base64.NO_WRAP);
    }

    private static byte[] unwrap(String text) throws Exception {
        byte[] raw = Base64.decode(text, Base64.NO_WRAP);
        if (raw.length <= IV_LEN) {
            throw new IllegalArgumentException("chave protegida invalida");
        }
        Cipher cipher = Cipher.getInstance(ALG);
        cipher.init(Cipher.DECRYPT_MODE, wrappingKey(), new GCMParameterSpec(GCM_TAG, slice(raw, 0, IV_LEN)));
        return cipher.doFinal(slice(raw, IV_LEN, raw.length - IV_LEN));
    }
}
