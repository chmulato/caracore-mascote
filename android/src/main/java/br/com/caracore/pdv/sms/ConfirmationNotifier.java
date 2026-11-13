package br.com.caracore.pdv.sms;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

import androidx.core.app.NotificationCompat;

/**
 * Avisa o dono do celular que uma operação sensível espera decisão.
 * Toca a tela cheia quando o celular está bloqueado, como um alarme de chamada.
 */
public final class ConfirmationNotifier {

    public static final String CHANNEL_ID = "pdv_confirmacao_channel";

    private ConfirmationNotifier() {
    }

    public static void criarCanal(Context context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel canal = new NotificationChannel(CHANNEL_ID,
                    "Confirmação de operações", NotificationManager.IMPORTANCE_HIGH);
            canal.setDescription("Pedidos de desconto, cancelamento e sangria esperando decisão");
            canal.enableVibration(true);
            canal.setLockscreenVisibility(Notification.VISIBILITY_PRIVATE);
            NotificationManager nm = context.getSystemService(NotificationManager.class);
            if (nm != null) nm.createNotificationChannel(canal);
        }
    }

    public static void notificar(Context context, ConfirmationRequest pedido) {
        criarCanal(context);
        Intent abrir = new Intent(context, ConfirmationActivity.class);
        abrir.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        abrir.putExtra(ConfirmationActivity.EXTRA_ID, pedido.id);
        PendingIntent pi = PendingIntent.getActivity(context, pedido.id.hashCode(), abrir,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

        NotificationCompat.Builder b = new NotificationCompat.Builder(context, CHANNEL_ID)
                .setSmallIcon(android.R.drawable.ic_dialog_alert)
                .setContentTitle("Confirme: " + pedido.tituloTipo() + " " + pedido.valorFormatado())
                .setContentText("Venda " + pedido.referencia + " — toque para decidir")
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setCategory(NotificationCompat.CATEGORY_CALL)
                .setVisibility(NotificationCompat.VISIBILITY_PRIVATE)
                .setAutoCancel(true)
                .setContentIntent(pi)
                .setOngoing(true);

        if (Build.VERSION.SDK_INT >= 29) {
            Intent telaCheia = new Intent(context, ConfirmationActivity.class);
            telaCheia.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
            telaCheia.putExtra(ConfirmationActivity.EXTRA_ID, pedido.id);
            PendingIntent pfi = PendingIntent.getActivity(context, pedido.id.hashCode() + 1, telaCheia,
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            b.setFullScreenIntent(pfi, true);
        }
        NotificationManager nm = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm != null) nm.notify(pedido.id.hashCode(), b.build());
    }

    public static void cancelar(Context context, String id) {
        NotificationManager nm = (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (nm != null && id != null) nm.cancel(id.hashCode());
    }
}
