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
import android.util.JsonReader;

import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;

import java.io.ByteArrayInputStream;
import java.io.InputStreamReader;
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
 * TCP 49998: recebe comando JSON criptografado (AES), ex.: {"action":"send_sms","number":"...","message":"..."}.
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
            dispatchCommand(json);
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

    private void dispatchCommand(String json) {
        try {
            JsonReader reader = new JsonReader(new InputStreamReader(new ByteArrayInputStream(json.getBytes(StandardCharsets.UTF_8)), StandardCharsets.UTF_8));
            reader.beginObject();
            String action = null;
            String number = null;
            String message = null;
            while (reader.hasNext()) {
                String name = reader.nextName();
                if ("action".equals(name)) action = reader.nextString();
                else if ("number".equals(name)) number = reader.nextString();
                else if ("message".equals(name)) message = reader.nextString();
                else reader.skipValue();
            }
            reader.endObject();
            reader.close();

            if ("send_sms".equals(action) && number != null && !number.trim().isEmpty() && message != null) {
                SmsPreferences prefs = new SmsPreferences(this);
                if (!prefs.isAtivo()) return;
                number = number.trim().replaceAll("[^+0-9]", "");
                if (number.isEmpty()) return;
                SmsManager.getDefault().sendTextMessage(number, null, message, null, null);
                PdvSmsLogger.i("GatewayListener", "SMS enviado para " + number);
            }
        } catch (Exception e) {
            PdvSmsLogger.i("GatewayListener", "dispatchCommand: " + e.getMessage());
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
