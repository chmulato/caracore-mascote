package br.com.caracore.pdv.sms;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;

import java.io.IOException;

/**
 * O servico que roda a ponte de e-mail no celular.
 *
 * Ele da uma volta, descansa e da de novo. A volta lee a caixa atras do ultimo
 * recado aberto, entrega o pedido ao radio e devolve os comprovantes que faltam.
 * Quando o provedor nao responde a espera cresce, ate cinco minutos, para o celular
 * nao ficar batendo numa porta fechada; quando ele volta a responder a espera
 * desce outra vez. Comprovante na fila nunca espera mais do que o passo base.
 *
 * A ponte funciona por qualquer rede: em casa, na loja pelo Wi-Fi ou na rua pelo 4G.
 */
public class EmailPonteServico extends Service {

    private static final String CANAL = "gaspar_email_channel";
    /** Uma volta a cada meia minuto enquanto esta tudo bem. */
    private static final int ESPERA_BASE_MS = 30_000;
    /** O teto quando o provedor comeca a recusar: cinco minutos. */
    private static final int ESPERA_MAXIMA_MS = 300_000;

    private volatile boolean running = true;
    private Thread volta;

    @Override
    public void onCreate() {
        super.onCreate();
        criarCanal();
        startForeground(2, criarNotificacao());
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (!new EmailPreferencias(this).estaAtiva()) {
            stopSelf();
            return START_NOT_STICKY;
        }
        if (volta == null || !volta.isAlive()) {
            volta = new Thread(this::rodar, "gaspar-ponte-email");
            volta.start();
        }
        return START_STICKY;
    }

    @Override
    public void onDestroy() {
        running = false;
        super.onDestroy();
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void rodar() {
        ChaveValor store = new PreferenciasChaveValor(this);
        EmailMemoria memoria = new EmailMemoria(store);
        EmailPreferencias ajustes = new EmailPreferencias(this);
        EmailBridge ponte = new EmailBridge(new TlsDaPonte(), ajustes.configuracao(), ajustes,
                new B64DoAparelho(), new EmailDespacho(this, store), memoria);
        int espera = ESPERA_BASE_MS;
        while (running && ajustes.estaAtiva()) {
            try {
                ponte.umaVolta();
                espera = ESPERA_BASE_MS;
            } catch (IOException caiu) {
                // sem rede, sem resposta, caixa fechada: e so a volta que falhou, nao o servico
                espera = Math.min(espera * 2, ESPERA_MAXIMA_MS);
                PdvSmsLogger.i("EmailPonte", "volta: " + caiu.getMessage());
            } catch (RuntimeException quebrou) {
                espera = Math.min(espera * 2, ESPERA_MAXIMA_MS);
                PdvSmsLogger.i("EmailPonte", "volta quebrou: " + quebrou.getClass().getSimpleName());
            }
            if (memoria.comprovantesNaFila() > 0) {
                espera = Math.min(espera, ESPERA_BASE_MS);
            }
            if (!esperar(espera)) {
                break;
            }
        }
        if (!ajustes.estaAtiva()) {
            stopSelf();
        }
    }

    /** true quando pode continuar. */
    private boolean esperar(int milissegundos) {
        try {
            Thread.sleep(milissegundos);
            return true;
        } catch (InterruptedException dormiuMal) {
            Thread.currentThread().interrupt();
            return false;
        }
    }

    private void criarCanal() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
            return;
        }
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (nm == null) {
            return;
        }
        NotificationChannel canal = new NotificationChannel(CANAL,
                getString(R.string.email_canal_nome), NotificationManager.IMPORTANCE_LOW);
        canal.setDescription(getString(R.string.email_canal_desc));
        nm.createNotificationChannel(canal);
    }

    private Notification criarNotificacao() {
        Intent abre = new Intent(this, ConfigActivity.class);
        PendingIntent pi = PendingIntent.getActivity(this, 1, abre,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        return new NotificationCompat.Builder(this, CANAL)
                .setContentTitle(getString(R.string.email_notif_titulo))
                .setContentText(getString(R.string.email_notif_texto))
                .setSmallIcon(android.R.drawable.ic_dialog_email)
                .setContentIntent(pi)
                .setOngoing(true)
                .build();
    }
}
