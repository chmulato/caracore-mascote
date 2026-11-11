package br.com.caracore.pdv.sms;

import android.content.Context;
import android.util.Base64;

import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * Envia ao Gaspar o comprovante cifrado do envio e da entrega do SMS.
 * A autenticação é a própria chave do pareamento (AES-GCM), não o token do PDV.
 */
public final class SmsReceiptSender {

    private SmsReceiptSender() {
    }

    public static boolean send(Context context, String id, String status, String detail) {
        SmsPreferences prefs = new SmsPreferences(context);
        String baseUrl = prefs.getPdvBaseUrl();
        String secret = prefs.getGatewaySharedSecret();
        if (baseUrl == null || baseUrl.isEmpty() || secret == null || secret.isEmpty()
                || id == null || id.isEmpty()) {
            return false;
        }
        GatewayCrypto crypto = GatewayCrypto.fromBase64(secret);
        if (crypto == null) {
            return false;
        }
        String endpoint = baseUrl.replaceAll("/+$", "") + "/api/mobile/receipt";
        for (int attempt = 0; attempt < 2; attempt++) {
            if (post(endpoint, crypto, id, status, detail)) {
                return true;
            }
            if (attempt == 0) {
                try {
                    Thread.sleep(400);
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                    break;
                }
            }
        }
        PdvSmsLogger.i("ReceiptSender", "Comprovante nao entregue ao Gaspar: " + status);
        return false;
    }

    private static boolean post(String endpoint, GatewayCrypto crypto, String id, String status, String detail) {
        HttpURLConnection conn = null;
        try {
            JSONObject payload = new JSONObject();
            payload.put("id", id);
            payload.put("status", status);
            payload.put("detail", detail == null ? "" : detail);
            payload.put("ts", System.currentTimeMillis() / 1000L);
            byte[] blob = crypto.encrypt(payload.toString().getBytes(StandardCharsets.UTF_8));

            JSONObject body = new JSONObject();
            body.put("blob", Base64.encodeToString(blob, Base64.NO_WRAP));
            byte[] bytes = body.toString().getBytes(StandardCharsets.UTF_8);

            conn = (HttpURLConnection) new URL(endpoint).openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
            conn.setConnectTimeout(2500);
            conn.setReadTimeout(2500);
            conn.setDoOutput(true);
            conn.setFixedLengthStreamingMode(bytes.length);
            try (OutputStream os = conn.getOutputStream()) {
                os.write(bytes);
            }
            int code = conn.getResponseCode();
            return code >= 200 && code < 300;
        } catch (Exception e) {
            PdvSmsLogger.i("ReceiptSender", "recibo: " + e.getMessage());
            return false;
        } finally {
            if (conn != null) conn.disconnect();
        }
    }
}
