package br.com.caracore.pdv.sms;

import android.content.Context;
import android.content.SharedPreferences;
import android.text.TextUtils;

import java.util.ArrayList;
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
    private static final String KEY_QUOTA_DAY = "quota_day";
    private static final String KEY_QUOTA_COUNT = "quota_count";
    private static final String KEY_LAST_SEQUENCE = "last_sequence";
    private static final String KEY_SEEN_JOBS = "seen_jobs";
    /** Permite que o PDV peça confirmação de operações sensíveis neste celular. */
    private static final String KEY_CONFIRMACAO_ATIVA = "confirmacao_ativa";
    /** Par de chaves da criptografia de ponta a ponta (privada protegida pelo Keystore). */
    private static final String KEY_E2E_PRIVATE = "e2e_private";
    private static final String KEY_E2E_PUBLIC = "e2e_public";

    public static final int DAILY_LIMIT = 300;
    private static final int SEEN_JOBS_LIMIT = 100;

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

    public boolean isConfirmacaoAtiva() {
        return prefs.getBoolean(KEY_CONFIRMACAO_ATIVA, true);
    }

    public void setConfirmacaoAtiva(boolean ativa) {
        prefs.edit().putBoolean(KEY_CONFIRMACAO_ATIVA, ativa).apply();
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
     * Vazio ou null = nenhum SMS de licença é aceito (a tela de configuração preenche).
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
        String novo = secret != null ? secret.trim() : null;
        String atual = getGatewaySharedSecret();
        boolean mudou = novo == null ? atual != null : !novo.equals(atual);
        if (mudou) {
            prefs.edit().remove(KEY_LAST_SEQUENCE).remove(KEY_SEEN_JOBS).apply();
        }
        prefs.edit().putString(KEY_GATEWAY_SHARED_SECRET, novo).apply();
    }

    public String getE2ePrivateKey() {
        return prefs.getString(KEY_E2E_PRIVATE, null);
    }

    public String getE2ePublicKey() {
        return prefs.getString(KEY_E2E_PUBLIC, null);
    }

    public void setE2eKeys(String wrappedPrivateKey, String publicKey) {
        prefs.edit()
                .putString(KEY_E2E_PRIVATE, wrappedPrivateKey)
                .putString(KEY_E2E_PUBLIC, publicKey)
                .apply();
    }

    /** Consome uma unidade da cota local do dia; false quando o celular atingiu o teto. */
    public synchronized boolean consumeSmsQuota() {
        Calendar cal = Calendar.getInstance();
        int hoje = cal.get(Calendar.YEAR) * 1000 + cal.get(Calendar.DAY_OF_YEAR);
        int dia = prefs.getInt(KEY_QUOTA_DAY, 0);
        int usados = dia == hoje ? prefs.getInt(KEY_QUOTA_COUNT, 0) : 0;
        if (usados >= DAILY_LIMIT) {
            return false;
        }
        prefs.edit().putInt(KEY_QUOTA_DAY, hoje).putInt(KEY_QUOTA_COUNT, usados + 1).commit();
        return true;
    }

    public long getLastSequence() {
        return prefs.getLong(KEY_LAST_SEQUENCE, 0L);
    }

    public void setLastSequence(long sequencia) {
        if (sequencia > 0) {
            prefs.edit().putLong(KEY_LAST_SEQUENCE, sequencia).apply();
        }
    }

    /** True quando o identificador do pedido ja foi aceito por este celular. */
    public synchronized boolean isKnownJobId(String id) {
        String texto = id != null ? id.trim() : "";
        if (texto.isEmpty()) {
            return false;
        }
        for (String visto : readSeenJobs()) {
            if (visto.equals(texto)) {
                return true;
            }
        }
        return false;
    }

    public synchronized void rememberJobId(String id) {
        String texto = id != null ? id.trim() : "";
        if (texto.isEmpty()) {
            return;
        }
        ArrayList<String> ids = new ArrayList<>();
        for (String visto : readSeenJobs()) {
            if (!visto.equals(texto)) {
                ids.add(visto);
            }
        }
        ids.add(texto);
        while (ids.size() > SEEN_JOBS_LIMIT) {
            ids.remove(0);
        }
        prefs.edit().putString(KEY_SEEN_JOBS, TextUtils.join("|", ids)).apply();
    }

    private String[] readSeenJobs() {
        String texto = prefs.getString(KEY_SEEN_JOBS, "");
        if (texto == null || texto.isEmpty()) {
            return new String[0];
        }
        return texto.split("\\|");
    }

    public String getPdvBaseUrl() {
        return prefs.getString(KEY_PDV_BASE_URL, null);
    }

    public void setPdvBaseUrl(String url) {
        prefs.edit().putString(KEY_PDV_BASE_URL, url != null ? url.trim() : null).apply();
    }
}
