package br.com.caracore.pdv.sms;

import android.content.Context;
import android.util.Base64;

import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * Publica a chave pública do celular no Gaspar para ativar a criptografia
 * de ponta a ponta sem precisar reler o QR de pareamento.
 * O pedido vai cifrado com a chave do pareamento (AES-GCM).
 */
public final class E2EKeySender {

    private E2EKeySender() {
    }

    public static boolean send(Context context) {
        SmsPreferences prefs = new SmsPreferences(context);
        String baseUrl = prefs.getPdvBaseUrl();
        String secret = prefs.getGatewaySharedSecret();
        String publicKey = prefs.getE2ePublicKey();
        if (baseUrl == null || baseUrl.isEmpty() || secret == null || secret.isEmpty()
                || publicKey == null || publicKey.isEmpty()) {
            return false;
        }
        GatewayCrypto crypto = GatewayCrypto.fromBase64(secret);
        if (crypto == null) {
            return false;
        }
        String endpoint = baseUrl.replaceAll("/+$", "") + "/api/mobile/key";
        HttpURLConnection conn = null;
        try {
            JSONObject payload = new JSONObject();
            payload.put("phone_public_key", publicKey);
            byte[] blob = crypto.encrypt(payload.toString().getBytes(StandardCharsets.UTF_8));

            JSONObject body = new JSONObject();
            body.put("blob", Base64.encodeToString(blob, Base64.NO_WRAP));
            byte[] bytes = body.toString().getBytes(StandardCharsets.UTF_8);

            conn = (HttpURLConnection) new URL(endpoint).openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
            conn.setConnectTimeout(3000);
            conn.setReadTimeout(3000);
            conn.setDoOutput(true);
            conn.setFixedLengthStreamingMode(bytes.length);
            try (OutputStream os = conn.getOutputStream()) {
                os.write(bytes);
            }
            int code = conn.getResponseCode();
            return code >= 200 && code < 300;
        } catch (Exception e) {
            PdvSmsLogger.i("E2EKeySender", "chave: " + e.getMessage());
            return false;
        } finally {
            if (conn != null) conn.disconnect();
        }
    }
}
