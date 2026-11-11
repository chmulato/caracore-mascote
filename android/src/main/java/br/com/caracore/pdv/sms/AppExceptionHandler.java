package br.com.caracore.pdv.sms;

import android.util.Log;

import java.io.PrintWriter;
import java.io.StringWriter;

/**
 * Tratamento centralizado de exceções não capturadas: handler global e utilitários de log.
 * Usa PdvSmsLogger para registro estruturado (contexto, userMessage, causa raiz).
 */
public final class AppExceptionHandler implements Thread.UncaughtExceptionHandler {

    private static final String CONTEXTO_UNCAUGHT = "UncaughtException";

    private final Thread.UncaughtExceptionHandler defaultHandler;

    public AppExceptionHandler(Thread.UncaughtExceptionHandler defaultHandler) {
        this.defaultHandler = defaultHandler;
    }

    @Override
    public void uncaughtException(Thread t, Throwable e) {
        PdvSmsLogger.e(CONTEXTO_UNCAUGHT, e);
        Log.e(PdvSmsLogger.TAG, "Thread que falhou: " + (t != null ? t.getName() : "null"));
        if (defaultHandler != null) {
            defaultHandler.uncaughtException(t, e);
        } else {
            android.os.Process.killProcess(android.os.Process.myPid());
            System.exit(1);
        }
    }

    /**
     * Converte o stack trace em String para registro em log ou relatório.
     */
    public static String stackTraceToString(Throwable e) {
        if (e == null) return "";
        StringWriter sw = new StringWriter();
        e.printStackTrace(new PrintWriter(sw));
        return sw.toString();
    }
}
