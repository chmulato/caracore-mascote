package br.com.caracore.pdv.sms;

/**
 * Exceção base da aplicação PDV Enviar SMS.
 * Subclasses permitem tratamento específico e mensagens orientadas ao uso.
 */
public class PdvSmsException extends RuntimeException {

    private final String userMessage;

    public PdvSmsException(String message) {
        super(message);
        this.userMessage = message;
    }

    public PdvSmsException(String message, Throwable cause) {
        super(message, cause);
        this.userMessage = message;
    }

    public PdvSmsException(String technicalMessage, String userMessage) {
        super(technicalMessage);
        this.userMessage = userMessage != null ? userMessage : technicalMessage;
    }

    public PdvSmsException(String technicalMessage, String userMessage, Throwable cause) {
        super(technicalMessage, cause);
        this.userMessage = userMessage != null ? userMessage : technicalMessage;
    }

    /**
     * Mensagem adequada para exibição ao usuário (Toast, diálogo).
     */
    public String getUserMessage() {
        return userMessage;
    }
}
