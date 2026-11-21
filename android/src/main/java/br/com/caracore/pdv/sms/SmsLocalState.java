package br.com.caracore.pdv.sms;

import android.content.Context;

/**
 * O estado real do celular atras dos portoes de {@link SmsDispatch}: licenca e ativacao,
 * pedidos ja vistos, sequencia, permissoes do radio e a cota do dia.
 */
public final class SmsLocalState implements SmsDispatch.Estado {

    private final Context context;
    private final SmsPreferences prefs;

    public SmsLocalState(Context context) {
        this.context = context.getApplicationContext();
        this.prefs = new SmsPreferences(this.context);
    }

    @Override
    public boolean ativo() {
        return prefs.isAtivo();
    }

    @Override
    public boolean jaConhecido(String jobId) {
        return prefs.isKnownJobId(jobId);
    }

    @Override
    public long ultimaSequencia() {
        return prefs.getLastSequence();
    }

    @Override
    public boolean consumirCota() {
        return prefs.consumeSmsQuota();
    }

    @Override
    public boolean podeEnviarSms() {
        return SetupDiagnosticHelper.checkSmsPermissions(context);
    }

    @Override
    public void registrar(String jobId, long sequencia) {
        prefs.rememberJobId(jobId);
        if (sequencia > 0) {
            prefs.setLastSequence(sequencia);
        }
    }
}
