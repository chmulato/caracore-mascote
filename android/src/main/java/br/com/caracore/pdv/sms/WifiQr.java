package br.com.caracore.pdv.sms;

/**
 * Monta o texto padrão de QR de Wi‑Fi (lido pela câmera de qualquer celular)
 * e escapa os caracteres reservados do formato.
 */
public final class WifiQr {

    private WifiQr() {
    }

    public static String payload(String ssid, String senha) {
        return "WIFI:T:WPA;S:" + escapar(ssid) + ";P:" + escapar(senha) + ";H:false;;";
    }

    static String escapar(String valor) {
        if (valor == null) return "";
        StringBuilder out = new StringBuilder(valor.length() + 8);
        for (int i = 0; i < valor.length(); i++) {
            char c = valor.charAt(i);
            if (c == '\\' || c == ';' || c == ',' || c == ':' || c == '"') {
                out.append('\\');
            }
            out.append(c);
        }
        return out.toString();
    }
}
