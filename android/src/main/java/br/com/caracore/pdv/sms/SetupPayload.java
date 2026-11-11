package br.com.caracore.pdv.sms;

/**
 * Payload decodificado do QR de setup Premium+.
 * Formato: CARACORE-SETUP|ip|porta|chaveBase64|token|licenca
 */
public final class SetupPayload {
    public final String ip;
    public final int port;
    public final String keyBase64;
    public final String setupToken;
    public final String licenseToken;

    public SetupPayload(String ip, int port, String keyBase64, String setupToken, String licenseToken) {
        this.ip = ip;
        this.port = port;
        this.keyBase64 = keyBase64;
        this.setupToken = setupToken;
        this.licenseToken = licenseToken != null && !licenseToken.isEmpty() ? licenseToken : null;
    }

    public String baseUrl() {
        return "http://" + ip + ":" + port;
    }

    /** Retorna null se a string não for um payload CARACORE-SETUP válido. */
    public static SetupPayload parse(String raw) {
        if (raw == null) return null;
        String s = raw.trim();
        if (!s.startsWith("CARACORE-SETUP|")) return null;
        String[] parts = s.split("\\|", -1);
        if (parts.length < 5) return null;
        String ip = parts[1].trim();
        int port;
        try {
            port = Integer.parseInt(parts[2].trim(), 10);
        } catch (NumberFormatException e) {
            return null;
        }
        String key = parts[3].trim();
        String token = parts[4].trim();
        String license = parts.length > 5 ? parts[5].trim() : "";
        if (ip.isEmpty() || key.isEmpty() || token.isEmpty()) return null;
        return new SetupPayload(ip, port, key, token, license);
    }
}
