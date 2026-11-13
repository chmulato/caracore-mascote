package br.com.caracore.pdv.sms;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import android.telephony.SmsManager;

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
import java.util.ArrayList;
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
        String secret = prefs.getGatewaySharedSecret();
        if (secret == null || secret.isEmpty()) {
            stopSelf();
            return START_NOT_STICKY;
        }
        final GatewayCrypto crypto = GatewayCrypto.fromBase64(secret);
        if (crypto == null) {
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
            tcpThread = new Thread(() -> runTcpServer(crypto));
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

    private void runTcpServer(GatewayCrypto crypto) {
        try (ServerSocket server = new ServerSocket(COMMAND_PORT)) {
            server.setSoTimeout(3000);
            while (running) {
                try {
                    Socket client = server.accept();
                    new Thread(() -> handleClient(client, crypto)).start();
                } catch (Exception e) {
                    if (!running) break;
                }
            }
        } catch (Exception e) {
            PdvSmsLogger.i("GatewayListener", "TCP server: " + e.getMessage());
        }
    }

    private void handleClient(Socket client, GatewayCrypto crypto) {
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
            byte[] plain = crypto.decrypt(encrypted);
            String json = new String(plain, StandardCharsets.UTF_8);
            writeAck(client, crypto, dispatchCommand(json));
        } catch (Exception e) {
            PdvSmsLogger.i("GatewayListener", "handleClient: " + e.getMessage());
        } finally {
            try { client.close(); } catch (Exception ignored) {}
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

    private JSONObject dispatchCommand(String json) {
        JSONObject ack = new JSONObject();
        try {
            ack.put("ok", false);
            JSONObject entrada = new JSONObject(json);
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
                return dispatchConfirmacao(ack, jobId, entrada, prefs);
            }
            if (!"send_sms".equals(action)) {
                ack.put("error", "acao desconhecida");
                return ack;
            }
            if (!prefs.isAtivo()) {
                ack.put("error", "app inativo");
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
            if (number == null || number.trim().isEmpty() || message == null) {
                ack.put("error", "pedido incompleto");
                return ack;
            }
            number = number.trim().replaceAll("[^+0-9]", "");
            if (number.length() < 10 || number.length() > 15) {
                ack.put("error", "numero invalido");
                return ack;
            }
            if (message.length() > 480) {
                ack.put("error", "mensagem acima de 480 caracteres");
                return ack;
            }
            if (prefs.isKnownJobId(jobId)) {
                ack.put("ok", true);
                ack.put("status", "repetido");
                return ack;
            }
            if (seq > 0 && seq <= prefs.getLastSequence()) {
                ack.put("error", "pedido repetido");
                return ack;
            }
            if (!SetupDiagnosticHelper.checkSmsPermissions(this)) {
                ack.put("error", "permissao de SMS negada");
                return ack;
            }
            if (!prefs.consumeSmsQuota()) {
                ack.put("error", "limite diario do celular atingido");
                return ack;
            }

            SmsManager sms = SmsManager.getDefault();
            ArrayList<String> parts = sms.divideMessage(message);
            ArrayList<PendingIntent> sentIntents = new ArrayList<>();
            ArrayList<PendingIntent> deliveredIntents = new ArrayList<>();
            for (int i = 0; i < parts.size(); i++) {
                sentIntents.add(statusPending(SmsStatusReceiver.ACTION_SENT, jobId, i, true));
                deliveredIntents.add(statusPending(SmsStatusReceiver.ACTION_DELIVERED, jobId, i, false));
            }
            if (parts.size() == 1) {
                sms.sendTextMessage(number, null, parts.get(0), sentIntents.get(0), deliveredIntents.get(0));
            } else {
                sms.sendMultipartTextMessage(number, null, parts, sentIntents, deliveredIntents);
            }
            ack.put("ok", true);
            ack.put("status", "aceito");
            prefs.rememberJobId(jobId);
            if (seq > 0) {
                prefs.setLastSequence(seq);
            }
            PdvSmsLogger.i("GatewayListener", "Pedido entregue ao radio do celular.");
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

    private PendingIntent statusPending(String action, String id, int part, boolean sent) {
        Intent intent = new Intent(this, SmsStatusReceiver.class);
        intent.setAction(action);
        intent.putExtra(SmsStatusReceiver.EXTRA_ID, id);
        int request = (id.hashCode() * 31 + part) * 2 + (sent ? 0 : 1);
        return PendingIntent.getBroadcast(
                this,
                request,
                intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    /** Entrega o pedido de confirmação à tela do celular; a decisão volta por /api/mobile/confirmacao. */
    private JSONObject dispatchConfirmacao(JSONObject ack, String jobId, JSONObject entrada, SmsPreferences prefs) {
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
                    texto(entrada, "origem"));
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

    private void writeAck(Socket client, GatewayCrypto crypto, JSONObject ack) {
        try {
            byte[] blob = crypto.encrypt(ack.toString().getBytes(StandardCharsets.UTF_8));
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
                    "Gateway PDV", NotificationManager.IMPORTANCE_LOW);
            channel.setDescription("CaraCore PDV envia comandos por esta rede");
            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) nm.createNotificationChannel(channel);
        }
    }

    private Notification createNotification() {
        Intent intent = new Intent(this, ConfigActivity.class);
        PendingIntent pi = PendingIntent.getActivity(this, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        return new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle("CaraCore PDV - Gateway")
                .setContentText("Aguardando PDV na rede Wi‑Fi")
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentIntent(pi)
                .setOngoing(true)
                .build();
    }
}
