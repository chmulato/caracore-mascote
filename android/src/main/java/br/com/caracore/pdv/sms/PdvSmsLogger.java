package br.com.caracore.pdv.sms;

import android.util.Log;

/**
 * Logger estruturado para a aplicação. Produz logs explicativos para suporte
 * e para correlacionar mensagens exibidas ao usuário (userMessage).
 * Tag: PdvSms. Formato: [contexto] nível: mensagem | userMessage=... quando aplicável.
 */
public final class PdvSmsLogger {

    public static final String TAG = "PdvSms";

    private PdvSmsLogger() {
    }

    /**
     * Registra erro com contexto, tipo da exceção, mensagem técnica e userMessage
     * (mensagem que o app exibe ao usuário). Inclui stack trace e causa raiz quando houver.
     * Uso: em blocos catch antes de exibir Toast ou encerrar.
     *
     * @param contexto Onde ocorreu (ex: SendSms.enviar, Config.onCreate).
     * @param e        Exceção capturada.
     */
    public static void e(String contexto, Throwable e) {
        if (e == null) return;
        String tipo = e.getClass().getSimpleName();
        String tecnica = e.getMessage() != null ? e.getMessage() : "(sem mensagem técnica)";
        String userMsg = ErrorReporter.getUserMessage(e);
        String linha = String.format("[%s] ERRO: %s: %s | userMessage=%s",
                contexto, tipo, tecnica, userMsg);
        Log.e(TAG, linha, e);
        if (e.getCause() != null) {
            Throwable c = e.getCause();
            Log.e(TAG, String.format("[%s] Causa raiz: %s: %s",
                    contexto, c.getClass().getSimpleName(), c.getMessage() != null ? c.getMessage() : ""), c);
        }
    }

    /**
     * Registra aviso com contexto. Uso: situações recuperáveis ou decisões relevantes.
     */
    public static void w(String contexto, String mensagem) {
        Log.w(TAG, "[" + contexto + "] " + mensagem);
    }

    /**
     * Registra aviso com contexto e exceção.
     */
    public static void w(String contexto, String mensagem, Throwable e) {
        Log.w(TAG, "[" + contexto + "] " + mensagem, e);
    }

    /**
     * Registra informação com contexto. Uso: fluxos normais relevantes para suporte
     * (ex: SMS enviado, app ativado/desativado).
     */
    public static void i(String contexto, String mensagem) {
        Log.i(TAG, "[" + contexto + "] " + mensagem);
    }
}
