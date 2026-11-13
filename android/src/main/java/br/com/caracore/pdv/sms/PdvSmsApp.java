package br.com.caracore.pdv.sms;

import android.app.Application;

/**
 * Application do PDV Enviar SMS. Configura o handler global de exceções não capturadas.
 */
public class PdvSmsApp extends Application {

    @Override
    public void onCreate() {
        super.onCreate();
        Thread.UncaughtExceptionHandler defaultHandler = Thread.getDefaultUncaughtExceptionHandler();
        Thread.setDefaultUncaughtExceptionHandler(new AppExceptionHandler(defaultHandler));
        ConfirmationNotifier.criarCanal(this);
    }
}
