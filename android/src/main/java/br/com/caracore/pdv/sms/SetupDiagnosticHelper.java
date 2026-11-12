package br.com.caracore.pdv.sms;

import android.content.Context;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.PowerManager;

import androidx.core.content.ContextCompat;

import android.Manifest;

import org.json.JSONObject;

import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * Auto-diagnóstico: verifica permissões SMS e bateria e reporta ao PDV.
 */
public final class SetupDiagnosticHelper {

    /**
     * Verifica se as permissões de SMS estão concedidas.
     */
    public static boolean checkSmsPermissions(Context context) {
        if (Build.VERSION.SDK_INT < 23) return true;
        return ContextCompat.checkSelfPermission(context, Manifest.permission.SEND_SMS) == PackageManager.PERMISSION_GRANTED
                && ContextCompat.checkSelfPermission(context, Manifest.permission.RECEIVE_SMS) == PackageManager.PERMISSION_GRANTED
                && ContextCompat.checkSelfPermission(context, Manifest.permission.READ_SMS) == PackageManager.PERMISSION_GRANTED;
    }

    /**
     * Verifica se o app está isento de otimização de bateria (recomendado para receber comandos).
     */
    public static boolean checkBatteryOptimizationIgnored(Context context) {
        if (Build.VERSION.SDK_INT < 23) return true;
        PowerManager pm = (PowerManager) context.getApplicationContext().getSystemService(Context.POWER_SERVICE);
        if (pm == null) return false;
        return pm.isIgnoringBatteryOptimizations(context.getPackageName());
    }

    /**
     * Envia o resultado do diagnóstico para o PDV. Executar em background.
     * @return mensagem de sucesso ou erro
     */
    public static String reportToPdv(String baseUrl, String setupToken, boolean smsOk, boolean batteryOk,
                                     String message, String phonePublicKey) {
        if (baseUrl == null || baseUrl.isEmpty() || setupToken == null || setupToken.isEmpty()) {
            return "Dados inválidos";
        }
        String urlStr = baseUrl.replaceAll("/+$", "") + "/api/mobile/diagnostic";
        HttpURLConnection conn = null;
        try {
            URL url = new URL(urlStr);
            conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json; charset=UTF-8");
            conn.setDoOutput(true);
            conn.setConnectTimeout(8000);
            conn.setReadTimeout(8000);
            JSONObject body = new JSONObject();
            body.put("token", setupToken);
            body.put("sms_ok", smsOk);
            body.put("battery_ok", batteryOk);
            body.put("message", message != null ? message : "");
            if (phonePublicKey != null && !phonePublicKey.isEmpty()) {
                body.put("phone_public_key", phonePublicKey);
            }
            byte[] bytes = body.toString().getBytes(StandardCharsets.UTF_8);
            conn.setFixedLengthStreamingMode(bytes.length);
            try (OutputStream os = conn.getOutputStream()) {
                os.write(bytes);
            }
            int code = conn.getResponseCode();
            if (code >= 200 && code < 300) {
                return null; // sucesso
            }
            return "PDV respondeu " + code;
        } catch (Exception e) {
            return e.getMessage() != null ? e.getMessage() : "Erro de rede";
        } finally {
            if (conn != null) conn.disconnect();
        }
    }
}
