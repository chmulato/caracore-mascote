package br.com.caracore.pdv.sms;

/**
 * Base64 de uma linha so, sem quebras, para caber no corpo de um e-mail e no
 * AUTH LOGIN. Em producao quem faz isso e o Android; nos testes entra a
 * implementacao da maquina, porque o celular ainda roda Android 7 e la nao
 * existe o base64 do Java 8.
 */
public interface B64 {

    String codificar(byte[] dados);

    byte[] decodificar(String texto);
}
