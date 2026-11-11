package br.com.caracore.pdv.sms;

/**
 * Lançada quando os argumentos do intent (number, body) são inválidos ou ausentes.
 */
public class SmsValidationException extends PdvSmsException {

    public SmsValidationException(String message) {
        super(message, message);
    }

    public SmsValidationException(String technicalMessage, String userMessage) {
        super(technicalMessage, userMessage);
    }
}
