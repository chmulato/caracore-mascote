package br.com.caracore.pdv.sms;

import android.util.Base64;

/**
 * O base64 de uma linha so que o Android faz, atras da mesma costura dos testes
 * ({@link B64}). Em producao ele e usado pela ponte de e-mail e pelo pareamento;
 * nos testes entra o da maquina, porque o celular ainda roda Android 7 e la nao
 * existe o base64 do Java 8.
 */
public final class B64DoAparelho implements B64 {

    @Override
    public String codificar(byte[] dados) {
        return Base64.encodeToString(dados, Base64.NO_WRAP);
    }

    @Override
    public byte[] decodificar(String texto) {
        return Base64.decode(texto.trim(), Base64.NO_WRAP);
    }
}
