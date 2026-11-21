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

import org.json.JSONObject;

import java.io.OutputStream;
import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.Enumeration;

/**
 * Serviço em primeiro plano que escuta o PDV na rede Wi‑Fi (Soberania Digital).
 * UDP 49999: responde a CARACORE-PDV-DISCOVER com CARACORE-APK|ip|49998.
 * TCP 49998: recebe comando JSON criptografado (AES), ex.: {"action":"send_sms","number":"...","message":"..."}
 * ou {"action":"confirmar_operacao","tipo":"desconto","referencia":"...","valor":1234,"prazo":120}.
 */
public class GatewayListenerService extends Service {

    private static final String DISCOVER_MAGIC = "CARACORE-PDV-DISCOVER";
    private static final String RESPONSE_PREFIX = "CARACORE-APK|";
    private static final int DISCOVER_PORT = 49999;
    private static final int COMMAND_PORT = 49998;
    private static final String CHANNEL_ID = "pdv_gateway_channel";

    private volatile boolean running = true;
    private Thread udpThread;
    private Thread tcpThread;

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
        startForeground(1, createNotification());
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        SmsPreferences prefs = new SmsPreferences(this);
        final PareamentoPorOrigem pareamentos =
                new PareamentoPorOrigem(prefs::getGatewaySecretFor, new B64DoAparelho());
        if (!pareamentos.pareado()) {
            stopSelf();
            return START_NOT_STICKY;
        }

        try {
            E2ECrypto.ensureKeyPair(this);
        } catch (Exception e) {
            PdvSmsLogger.i("GatewayListener", "chave de ponta a ponta: " + e.getMessage());
        }
        new Thread(() -> E2EKeySender.send(this)).start();
        new Thread(() -> ConfirmationResponder.reenviarPendentes(this)).start();

        if (udpThread == null || !udpThread.isAlive()) {
            udpThread = new Thread(() -> runUdpDiscovery());
            udpThread.start();
        }
        if (tcpThread == null || !tcpThread.isAlive()) {
            tcpThread = new Thread(() -> runTcpServer(pareamentos));
            tcpThread.start();
        }
        return START_STICKY;
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        running = false;
        super.onDestroy();
    }

    private void runUdpDiscovery() {
        try (DatagramSocket socket = new DatagramSocket(DISCOVER_PORT)) {
            socket.setBroadcast(true);
            byte[] buf = new byte[256];
            DatagramPacket packet = new DatagramPacket(buf, buf.length);
            while (running) {
                try {
                    socket.setSoTimeout(2000);
                    socket.receive(packet);
                    String received = new String(packet.getData(), 0, packet.getLength(), StandardCharsets.UTF_8).trim();
                    if (DISCOVER_MAGIC.equals(received)) {
                        String localIp = getLocalIpAddress();
                        if (localIp != null) {
                            String response = RESPONSE_PREFIX + localIp + "|" + COMMAND_PORT;
                            byte[] out = response.getBytes(StandardCharsets.UTF_8);
                            DatagramPacket reply = new DatagramPacket(out, out.length, packet.getAddress(), packet.getPort());
                            socket.send(reply);
                            PdvSmsLogger.i("GatewayListener", "Discovery response sent to " + packet.getAddress());
                        }
                    }
                } catch (Exception e) {
                    if (running) PdvSmsLogger.i("GatewayListener", "UDP: " + e.getMessage());
                }
            }
        } catch (Exception e) {
            PdvSmsLogger.i("GatewayListener", "UDP socket: " + e.getMessage());
        }
    }

    private void runTcpServer(PareamentoPorOrigem pareamentos) {
        try (ServerSocket server = new ServerSocket(COMMAND_PORT)) {
            server.setSoTimeout(3000);
            while (running) {
                try {
                    Socket client = server.accept();
                    new Thread(() -> handleClient(client, pareamentos)).start();
                } catch (Exception e) {
                    if (!running) break;
                }
            }
        } catch (Exception e) {
            PdvSmsLogger.i("GatewayListener", "TCP server: " + e.getMessage());
        }
    }

    private void handleClient(Socket client, PareamentoPorOrigem pareamentos) {
        try {
            client.setSoTimeout(15000);
            byte[] lenBuf = new byte[4];
            int read = readFully(client.getInputStream(), lenBuf);
            if (read != 4) return;
            int len = ByteBuffer.wrap(lenBuf).getInt();
            if (len <= 0 || len > 65536) return;
            byte[] encrypted = new byte[len];
            read = readFully(client.getInputStream(), encrypted);
            if (read != len) return;
            PareamentoPorOrigem.Aberto aberto = pareamentos.abrir(encrypted);
            if (aberto == null) {
                // nao foi escrito com uma chave desta loja: nao ha para quem responder
                PdvSmsLogger.i("GatewayListener", "comando de fora do pareamento: ignorado");
                return;
            }
            writeAck(client, aberto.par, dispatchCommand(aberto));
        } catch (Exception e) {
            PdvSmsLogger.i("GatewayListener", "handleClient: " + e.getMessage());
        } finally {
            try {
                client.close();
            } catch (Exception ignored) {
            }
        }
    }

    private static int readFully(java.io.InputStream in, byte[] buf) throws java.io.IOException {
        int total = 0;
        while (total < buf.length) {
            int n = in.read(buf, total, buf.length - total);
            if (n <= 0) break;
            total += n;
        }
        return total;
    }

    private JSONObject dispatchCommand(PareamentoPorOrigem.Aberto aberto) {
        JSONObject ack = new JSONObject();
        try {
            ack.put("ok", false);
            JSONObject entrada = new JSONObject(aberto.texto());
            String origem = texto(entrada, "origem");
            if (!aberto.par.servePara(origem)) {
                // a chave que abriu e desta loja, mas diz ser de outra: a fila errada nunca comeca
                ack.put("error", "a origem declarada nao bate com o pareamento deste celular");
                PdvSmsLogger.i("GatewayListener", "origem declarada fora do pareamento.");
                return ack;
            }
            String productora = origem == null || origem.trim().isEmpty() ? aberto.par.origem() : origem.trim();
            String action = texto(entrada, "action");
            String number = texto(entrada, "number");
            String message = texto(entrada, "message");
            String id = texto(entrada, "id");
            String base = texto(entrada, "base");
            String envelope = texto(entrada, "envelope");
            long seq = entrada.optLong("seq", 0L);
            if (id == null || id.trim().isEmpty()) {
                ack.put("error", "pedido sem identificador");
                return ack;
            }
            String jobId = id.trim();
            ack.put("id", jobId);
            try {
                ack.put("key", E2ECrypto.ensureKeyPair(this));
            } catch (Exception ignored) {
                // sem chave o PDV trabalha no modo antigo
            }
            SmsPreferences prefs = new SmsPreferences(this);
            if (base != null && !base.isEmpty()) {
                prefs.setPdvBaseUrl(base);
            }
            if ("confirmar_operacao".equals(action)) {
                return dispatchConfirmacao(ack, jobId, entrada, productora, prefs);
            }
            if (!"send_sms".equals(action)) {
                ack.put("error", "acao desconhecida");
                return ack;
            }
            if (envelope != null && !envelope.isEmpty()) {
                try {
                    byte[] plain = E2ECrypto.open(this, envelope, jobId.getBytes(StandardCharsets.UTF_8));
                    JSONObject inner = new JSONObject(new String(plain, StandardCharsets.UTF_8));
                    number = inner.optString("number", null);
                    message = inner.optString("message", null);
                } catch (Exception e) {
                    ack.put("error", "envelope invalido");
                    PdvSmsLogger.i("GatewayListener", "envelope: " + e.getMessage());
                    return ack;
                }
            }
            SmsDispatch.Ack resultado = SmsDispatch.enviar(
                    new SmsLocalState(this), new PhoneRadio(this), jobId, seq, number, message);
            if (resultado.ok()) {
                // o comprovante do radio volta por aqui, nao pela ponte de e-mail
                new TrilhaDoPedido(new PreferenciasChaveValor(this))
                        .registrar(jobId, productora, TrilhaDoPedido.CANAL_WIFI, number, "");
                ack.put("ok", true);
                ack.put("status", resultado.status());
                if (SmsDispatch.STATUS_ACEITO.equals(resultado.status())) {
                    PdvSmsLogger.i("GatewayListener", "Pedido entregue ao radio do celular.");
                }
            } else {
                ack.put("error", resultado.erro());
            }
        } catch (Exception e) {
            try {
                ack.put("ok", false);
                ack.put("error", "falha ao processar o pedido");
            } catch (Exception ignored) {
            }
            PdvSmsLogger.i("GatewayListener", "dispatchCommand: " + e.getMessage());
        }
        return ack;
    }

    /** Entrega o pedido de confirmação à tela do celular; a decisão volta por /api/mobile/confirmacao. */
    private JSONObject dispatchConfirmacao(JSONObject ack, String jobId, JSONObject entrada,
                                           String origem, SmsPreferences prefs) {
        try {
            if (!prefs.isConfirmacaoAtiva()) {
                ack.put("error", "confirmacao desligada neste celular");
                return ack;
            }
            long agora = System.currentTimeMillis();
            long prazoSegundos = entrada.optLong("prazo", 0L);
            ConfirmationRequest pedido = new ConfirmationRequest(
                    jobId,
                    texto(entrada, "tipo"),
                    texto(entrada, "referencia"),
                    entrada.optLong("valor", -1L),
                    texto(entrada, "motivo"),
                    agora + prazoSegundos * 1000L,
                    agora,
                    origem);
            String recusa = pedido.validar(agora);
            if (recusa != null) {
                ack.put("error", "pedido de confirmacao recusado: " + recusa);
                return ack;
            }
            if (!ConfirmationStore.enfileirar(this, pedido)) {
                ack.put("ok", true);
                ack.put("status", "repetido");
                return ack;
            }
            ConfirmationNotifier.notificar(this, pedido);
            ack.put("ok", true);
            ack.put("status", "aguardando");
            PdvSmsLogger.i("GatewayListener", "Pedido de confirmacao entregue a tela.");
        } catch (Exception e) {
            try {
                ack.put("ok", false);
                ack.put("error", "falha ao preparar a confirmacao");
            } catch (Exception ignored) {
            }
            PdvSmsLogger.i("GatewayListener", "dispatchConfirmacao: " + e.getMessage());
        }
        return ack;
    }

    private static String texto(JSONObject objeto, String campo) {
        if (objeto == null || !objeto.has(campo) || objeto.isNull(campo)) return null;
        return objeto.optString(campo, null);
    }

    private void writeAck(Socket client, PareamentoPorOrigem.Par par, JSONObject ack) {
        try {
            byte[] blob = par.selar(ack.toString().getBytes(StandardCharsets.UTF_8));
            OutputStream out = client.getOutputStream();
            out.write(ByteBuffer.allocate(4).putInt(blob.length).array());
            out.write(blob);
            out.flush();
        } catch (Exception e) {
            PdvSmsLogger.i("GatewayListener", "ack: " + e.getMessage());
        }
    }

    private static String getLocalIpAddress() {
        try {
            for (Enumeration<NetworkInterface> en = NetworkInterface.getNetworkInterfaces(); en.hasMoreElements(); ) {
                NetworkInterface intf = en.nextElement();
                for (Enumeration<InetAddress> enumIpAddr = intf.getInetAddresses(); enumIpAddr.hasMoreElements(); ) {
                    InetAddress inetAddress = enumIpAddr.nextElement();
                    if (!inetAddress.isLoopbackAddress() && inetAddress instanceof Inet4Address) {
                        return inetAddress.getHostAddress();
                    }
                }
            }
        } catch (Exception e) {
            // ignore
        }
        return null;
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(CHANNEL_ID,
                    getString(R.string.gateway_canal_nome), NotificationManager.IMPORTANCE_LOW);
            channel.setDescription(getString(R.string.gateway_canal_desc));
            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) nm.createNotificationChannel(channel);
        }
    }

    private Notification createNotification() {
        Intent intent = new Intent(this, ConfigActivity.class);
        PendingIntent pi = PendingIntent.getActivity(this, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        return new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle(getString(R.string.gateway_notif_titulo))
                .setContentText(getString(R.string.gateway_notif_texto))
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentIntent(pi)
                .setOngoing(true)
                .build();
    }
}
