package br.com.caracore.pdv.sms;

import android.content.Context;
import android.content.SharedPreferences;

import java.util.Calendar;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Preferências da aplicação (ativo/inativo, licença, configurações).
 * Por padrão o app inicia ativo para manter compatibilidade com instalações existentes.
 */
public final class SmsPreferences {

    private static final String PREFS_NAME = "pdv_sms_prefs";
    private static final String KEY_ATIVO = "ativo";
    private static final String KEY_CHAVE_LICENCA = "chave_licenca";
    private static final String KEY_NUMERO_OFICIAL_LICENCA = "numero_oficial_licenca";
    private static final String KEY_LAST_BACKUP_TIMESTAMP = "last_backup_timestamp";
    private static final String KEY_LAST_BACKUP_STATUS = "last_backup_status";
    /** Chave compartilhada (Base64) para criptografia PDV ↔ APK — mesma do PDV (mobile.gateway.shared.secret). */
    private static final String KEY_GATEWAY_SHARED_SECRET = "gateway_shared_secret";
    /** URL base do PDV (ex.: http://192.168.1.10:8080) para setup/diagnóstico. */
    private static final String KEY_PDV_BASE_URL = "pdv_base_url";

    /** Formato CC-YYYYMM-{hex8}; usamos o grupo 1 para YYYYMM. */
    private static final Pattern PREFIX_LICENCA = Pattern.compile("^CC-(\\d{6})-[0-9a-fA-F]{8}$");

    private final SharedPreferences prefs;

    public SmsPreferences(Context context) {
        this.prefs = context.getApplicationContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }

    /**
     * Indica se o app está autorizado a enviar SMS via ADB. true = ativo.
     * Valor padrão: true.
     */
    public boolean isAtivo() {
        return prefs.getBoolean(KEY_ATIVO, true);
    }

    public void setAtivo(boolean ativo) {
        prefs.edit().putBoolean(KEY_ATIVO, ativo).apply();
    }

    // --- Licença Premium (recepção via SMS CC-LICENSE:[CHAVE]) ---

    public String getChaveLicenca() {
        return prefs.getString(KEY_CHAVE_LICENCA, null);
    }

    public void setChaveLicenca(String chave) {
        prefs.edit().putString(KEY_CHAVE_LICENCA, chave).apply();
    }

    /**
     * Número oficial da Cara Core para filtrar SMS de licença.
     * Vazio ou null = aceita qualquer remetente.
     */
    public String getNumeroOficialLicenca() {
        return prefs.getString(KEY_NUMERO_OFICIAL_LICENCA, null);
    }

    public void setNumeroOficialLicenca(String numero) {
        String n = (numero != null && !numero.trim().isEmpty()) ? numero.trim() : null;
        prefs.edit().putString(KEY_NUMERO_OFICIAL_LICENCA, n).apply();
    }

    /**
     * Verifica se a chave armazenada ainda está dentro do prazo de validade mensal.
     * Espera formato CC-YYYYMM-{hex8}. Retorna false se não houver chave ou formato inválido.
     */
    public boolean isLicencaValida() {
        String chave = getChaveLicenca();
        if (chave == null || (chave = chave.trim()).isEmpty()) {
            return false;
        }
        Matcher m = PREFIX_LICENCA.matcher(chave);
        if (!m.matches()) {
            return false;
        }
        int yyyymm = Integer.parseInt(m.group(1), 10);
        int anoChave = yyyymm / 100;
        int mesChave = yyyymm % 100;
        if (mesChave < 1 || mesChave > 12) {
            return false;
        }
        Calendar cal = Calendar.getInstance();
        int anoAtual = cal.get(Calendar.YEAR);
        int mesAtual = cal.get(Calendar.MONTH) + 1;
        int yyyymmAtual = anoAtual * 100 + mesAtual;
        return yyyymm >= yyyymmAtual;
    }

    // --- Último backup do banco (enviado pelo PDV via broadcast BACKUP_UPDATE) ---

    /** Data/hora do último backup em YYYY_MM_DD_HH_MM_SS, ou null. */
    public String getLastBackupTimestamp() {
        return prefs.getString(KEY_LAST_BACKUP_TIMESTAMP, null);
    }

    public void setLastBackupTimestamp(String timestamp) {
        prefs.edit().putString(KEY_LAST_BACKUP_TIMESTAMP, timestamp != null ? timestamp.trim() : null).apply();
    }

    /** Status do último backup: "OK", "ERRO" ou null. */
    public String getLastBackupStatus() {
        return prefs.getString(KEY_LAST_BACKUP_STATUS, null);
    }

    public void setLastBackupStatus(String status) {
        prefs.edit().putString(KEY_LAST_BACKUP_STATUS, status != null ? status.trim() : null).apply();
    }

    public String getGatewaySharedSecret() {
        return prefs.getString(KEY_GATEWAY_SHARED_SECRET, null);
    }

    public void setGatewaySharedSecret(String secret) {
        prefs.edit().putString(KEY_GATEWAY_SHARED_SECRET, secret != null ? secret.trim() : null).apply();
    }

    public String getPdvBaseUrl() {
        return prefs.getString(KEY_PDV_BASE_URL, null);
    }

    public void setPdvBaseUrl(String url) {
        prefs.edit().putString(KEY_PDV_BASE_URL, url != null ? url.trim() : null).apply();
    }
}
