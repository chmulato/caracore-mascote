package br.com.caracore.pdv.sms;

/**
 * Guardar texto entre uma volta da ponte e a outra, sem depender do Android.
 * Em producao quem atende isto e o SharedPreferences do app; na maquina de
 * testes entra um mapa na memoria, para dar para conferir a conversa inteira
 * sem celular.
 */
public interface ChaveValor {

    /** Null quando nada foi gravado naquela chave. */
    String texto(String chave);

    /** Null no valor apaga a chave. */
    void gravarTexto(String chave, String valor);
}
