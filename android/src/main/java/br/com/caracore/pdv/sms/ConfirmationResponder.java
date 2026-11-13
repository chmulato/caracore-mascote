package br.com.caracore.pdv.sms;

import android.content.Context;
import android.util.Base64;

import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * Devolve ao Gaspar a decisão tomada no celular, cifrada com a chave do pareamento.
 * Se o computador estiver desligado, a decisão fica guardada e é reenviada depois.
 */
public final class ConfirmationResponder {

    private ConfirmationResponder() {
    }

    public static boolean enviar(Context context, ConfirmationRequest pedido, String status, String metodo) {
        if (pedido.ehTeste()) {
            return true;
        }
        SmsPreferences prefs = new SmsPreferences(context);
        String baseUrl = prefs.getPdvBaseUrl();
        String secret = prefs.getGatewaySharedSecret();
        if (baseUrl == null || baseUrl.isEmpty() || secret == null || secret.isEmpty()) {
            return false;
        }
        GatewayCrypto crypto = GatewayCrypto.fromBase64(secret);
        if (crypto == null) {
            return false;
        }
        String endpoint = baseUrl.replaceAll("/+$", "") + "/api/mobile/confirmacao";
        boolean ok = post(endpoint, crypto, pedido.id, status, metodo);
        if (ok) {
            ConfirmationStore.marcarEnviado(context, pedido.id);
        }
        return ok;
    }

    public static void reenviarPendentes(Context context) {
        for (ConfirmationStore.Envio envio : ConfirmationStore.filaDeEnvio(context)) {
            if (!enviar(context, envio.pedido, envio.status, envio.metodo)) {
                break;
            }
        }
    }

    private static boolean post(String endpoint, GatewayCrypto crypto, String id, String status, String metodo) {
        HttpURLConnection conn = null;
        try {
            JSONObject payload = new JSONObject();
            payload.put("id", id);
            payload.put("status", status);
            payload.put("metodo", metodo == null ? "" : metodo);
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
            PdvSmsLogger.i("ConfirmationSender", "decisao: " + e.getMessage());
            return false;
        } finally {
            if (conn != null) conn.disconnect();
        }
    }
}
