package br.com.caracore.pdv.sms;

/**
 * Lançada quando a permissão SEND_SMS foi negada ou não foi concedida.
 */
public class SmsPermissionException extends PdvSmsException {

    public SmsPermissionException() {
        super("Permissão SEND_SMS negada", "Permissão Enviar e receber SMS negada. Ative em Configurações do app.");
    }

    public SmsPermissionException(Throwable cause) {
        super("Permissão SEND_SMS negada", "Permissão Enviar e receber SMS negada.", cause);
    }
}
