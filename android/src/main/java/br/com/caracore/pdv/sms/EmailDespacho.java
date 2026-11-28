package br.com.caracore.pdv.sms;

import android.content.Context;

/**
 * O pedido que chegou pela ponte de e-mail entra pelo mesmo portao do pedido que
 * chegou pelo Wi-Fi: mesma licenca, mesmo teto do dia, mesma conferencia de
 * repeticao. O que muda e so para onde o aviso do radio volta, e isto fica escrito
 * na trilha do pedido.
 */
public final class EmailDespacho implements EmailBridge.Despacho {

    private final Context context;
    private final ChaveValor store;

    public EmailDespacho(Context context, ChaveValor store) {
        this.context = context.getApplicationContext();
        this.store = store;
    }

    @Override
    public String executar(String origem, String referencia, String para, String texto, String destino) {
        SmsDispatch.Ack resultado = SmsDispatch.enviar(new SmsLocalState(context), new PhoneRadio(context),
                referencia, 0L, para, texto);
        if (resultado.repetido()) {
            // o primeiro aviso ja saiu: repetir seria avisar duas vezes do mesmo pedido
            return null;
        }
        if (!resultado.ok()) {
            return EmailEnvelope.ESTADO_FALHOU;
        }
        new TrilhaDoPedido(store).registrar(referencia, origem, TrilhaDoPedido.CANAL_EMAIL, para, destino);
        return EmailEnvelope.ESTADO_ENVIADO;
    }
}
