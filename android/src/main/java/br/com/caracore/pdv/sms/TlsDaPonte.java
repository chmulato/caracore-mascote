package br.com.caracore.pdv.sms;

import java.io.IOException;
import java.net.Socket;

import javax.net.ssl.SSLSocketFactory;

/**
 * Os dois soquetes cifrados da ponte: a caixa de entrada por IMAP sobre TLS e a
 * saida por SMTP. Em producao e o TLS do proprio Android; nos testes entra o
 * servidor local da maquina, por isso a ponte recebe as fabricas por fora.
 */
public final class TlsDaPonte implements EmailBridge.Fabricas {

    private final SSLSocketFactory fabrica = (SSLSocketFactory) SSLSocketFactory.getDefault();

    @Override
    public ImapClient.Fabrica caixa() {
        return this::abrir;
    }

    @Override
    public SmtpClient.Fabrica saida() {
        return this::abrir;
    }

    private Socket abrir(String host, int porta) throws IOException {
        return fabrica.createSocket(host, porta);
    }
}
