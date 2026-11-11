package br.com.caracore.pdv.sms;

/**
 * Lançada quando o envio de SMS é solicitado com o app desativado pelo painel de configuração.
 */
public class SmsDisabledException extends PdvSmsException {

    public SmsDisabledException() {
        super("App desativado nas configurações", "App desativado. Ative em Configurações.");
    }
}
