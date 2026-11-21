package br.com.caracore.pdv.sms;

import android.content.Context;

/**
 * Devolve ao Gaspar o estado do radio pelo mesmo caminho por onde o pedido entrou:
 * o comprovante de um pedido que veio pela ponte de e-mail volta cifrado na caixa de
 * quem escreveu; o resto volta pelo Wi-Fi, como sempre.
 */
public final class Comprovantes {

    private Comprovantes() {
    }

    /** true quando ha para quem devolver e por onde: senao vale o caminho de sempre. */
    static boolean voltaPeloEmail(TrilhaDoPedido.Registro trilha, String estadoDoRadio) {
        return trilha != null && trilha.porEmail()
                && EmailEnvelope.estadoDoRadio(estadoDoRadio) != null && !trilha.destino.isEmpty();
    }

    public static boolean devolver(Context context, String jobId, String status, String detalhe) {
        ChaveValor store = new PreferenciasChaveValor(context);
        TrilhaDoPedido.Registro trilha = new TrilhaDoPedido(store).de(jobId);
        String estado = EmailEnvelope.estadoDoRadio(status);
        if (!voltaPeloEmail(trilha, status)) {
            return SmsReceiptSender.send(context, jobId, status, detalhe);
        }
        // a saida SMTP e do servico da ponte: aqui so entra na fila, para nao perder aviso sem rede
        new EmailMemoria(store).anotarComprovante(new EmailBridge.Comprovante(trilha.origem,
                trilha.jobId, trilha.para, estado, trilha.destino, System.currentTimeMillis() / 1000L));
        return true;
    }
}
