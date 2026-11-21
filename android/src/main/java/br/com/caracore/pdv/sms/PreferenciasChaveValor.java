package br.com.caracore.pdv.sms;

import android.content.Context;
import android.content.SharedPreferences;

/**
 * A memoria da ponte escrita nas preferencias do app. So texto: o cifrado nunca
 * fica em claro aqui, e os carimbos sao endereco de recado, nao conteudo.
 */
public final class PreferenciasChaveValor implements ChaveValor {

    private static final String ARQUIVO = "gaspar_email_bridge";

    private final SharedPreferences prefs;

    public PreferenciasChaveValor(Context context) {
        prefs = context.getApplicationContext()
                .getSharedPreferences(ARQUIVO, Context.MODE_PRIVATE);
    }

    @Override
    public String texto(String chave) {
        return prefs.getString(chave, null);
    }

    @Override
    public void gravarTexto(String chave, String valor) {
        if (valor == null) {
            prefs.edit().remove(chave).apply();
        } else {
            prefs.edit().putString(chave, valor).apply();
        }
    }
}
