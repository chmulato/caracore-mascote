package br.com.caracore.pdv.sms;

/**
 * Lançada quando o envio do SMS falha (SmsManager, rede, operadora, etc.).
 */
public class SmsSendException extends PdvSmsException {

    public SmsSendException(String message) {
        super(message, "Falha ao enviar SMS. Tente novamente.");
    }

    public SmsSendException(String message, Throwable cause) {
        super(message, "Falha ao enviar SMS. Tente novamente.", cause);
    }

    public SmsSendException(Throwable cause) {
        super(cause != null ? cause.getMessage() : "Erro desconhecido", "Falha ao enviar SMS. Tente novamente.", cause);
    }
}
