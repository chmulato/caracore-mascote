package br.com.caracore.pdv.sms;

import android.app.Activity;
import android.widget.Toast;

/**
 * Reporta exceções já capturadas: log estruturado (PdvSmsLogger) e mensagem ao usuário (Toast).
 * O userMessage é sempre registrado no log para correlacionar o que o usuário vê com o diagnóstico.
 */
public final class ErrorReporter {

    /**
     * Registra a exceção com contexto e exibe userMessage ao usuário. Usar em blocos catch.
     *
     * @param activity  Activity para exibir Toast; pode ser null (apenas log).
     * @param contexto  Onde ocorreu (ex: SendSms.enviar, Config.onCreate).
     * @param e         Exceção capturada.
     */
    public static void show(Activity activity, String contexto, Throwable e) {
        PdvSmsLogger.e(contexto, e);
        String msg = getUserMessage(e);
        if (activity != null && !activity.isFinishing()) {
            Toast.makeText(activity, msg, Toast.LENGTH_LONG).show();
        }
    }

    /**
     * Versão sem contexto explícito; usa "App" como contexto.
     */
    public static void show(Activity activity, Throwable e) {
        show(activity, "App", e);
    }

    /**
     * Mensagem adequada para exibição ao usuário (Toast, diálogo).
     * PdvSmsException usa getUserMessage(); demais exceções: mensagem ou genérica.
     */
    public static String getUserMessage(Throwable e) {
        if (e instanceof PdvSmsException) {
            return ((PdvSmsException) e).getUserMessage();
        }
        if (e != null && e.getMessage() != null && !e.getMessage().isEmpty()) {
            return "Erro: " + e.getMessage();
        }
        return "Erro inesperado. Tente novamente.";
    }

    /**
     * Apenas log com contexto, sem Toast. Para erros em background ou quando a UI não está disponível.
     */
    public static void log(String contexto, Throwable e) {
        PdvSmsLogger.e(contexto, e);
    }

    /**
     * Apenas log, sem Toast; contexto "App".
     */
    public static void log(Throwable e) {
        log("App", e);
    }
}
