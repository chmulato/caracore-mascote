package br.com.caracore.pdv.sms;

import org.json.JSONObject;

import java.io.IOException;
import java.util.Collections;
import java.util.List;

/**
 * A conversa da ponte de e-mail, do mesmo jeito que o Gaspar no computador a conversa.
 *
 * Cada volta faz duas coisas: le a caixa atras do ultimo UID lido, abre o que tem a
 * nossa marca e entrega ao radio do celular; e devolve os comprovantes que ainda
 * faltam, pela saida SMTP. As recusas do servidor se separam das duvidas: o que ele
 * recusou pode tentar de novo, o que entrou sem responder nao reenvia nunca.
 *
 * Nada aqui toca em API do Android. As pecas de fora (soquetes, segredos por origem,
 * memoria e despacho) entram por interfaces, para dar para conferir a conversa inteira
 * com servidores falsos na maquina de testes.
 */
public final class EmailBridge {

    /** Onde fica cada servidor e quem assina os recados. Nenhum segredo aqui. */
    public static final class Configuracao {
        public String hostDaCaixa = "";
        public int portaDaCaixa = 993;
        public String hostDaSaida = "";
        public int portaDaSaida = 465;
        /** true = porta 587 com STARTTLS; false = porta 465 ja cifrada. */
        public boolean starttls = false;
        public String usuario = "";
        /** Vazio significa a caixa de entrada. */
        public String caixa = "";
        public String remetente = "";
        public String dominioDoCarimbo = EmailEnvelope.DOMINIO_MESSAGE_ID;
        public String nomeDoAparelho = "celular";
        public int tempoLimiteMs = 30000;
    }

    /** Como abrir o soquete de cada lado. Em producao e TLS; no teste e o servidor local. */
    public interface Fabricas {
        ImapClient.Fabrica caixa();

        SmtpClient.Fabrica saida();
    }

    /** Os segredos da ponte. A senha de app vem do Keystore; a chave, do pareamento de cada origem. */
    public interface Credenciais {
        String senhaDeApp() throws IOException;

        /** A chave em base64 do pareamento daquela origem, ou null quando aquela origem nao foi pareada. */
        String chaveDaPonte(String origem);
    }

    /**
     * Entrega o pedido ao radio e devolve o estado que o comprovante leva, ou null
     * quando nao ha o que avisar. O destino e o endereco de quem escreveu: quem
     * despacho pelo e-mail precisa saber para onde o aviso do radio volta.
     */
    public interface Despacho {
        String executar(String origem, String referencia, String para, String texto, String destino);
    }

    /** Um comprovante a devolver, com o endereco para onde ele volta. */
    public static final class Comprovante {
        public final String origem;
        public final String referencia;
        public final String para;
        public final String estado;
        public final String destino;
        public final long quandoEmSegundos;

        public Comprovante(String origem, String referencia, String para, String estado,
                           String destino, long quandoEmSegundos) {
            this.origem = origem == null ? "" : origem;
            this.referencia = referencia == null ? "" : referencia;
            this.para = para == null ? "" : para;
            this.estado = estado == null ? "" : estado;
            this.destino = destino == null ? "" : destino;
            this.quandoEmSegundos = quandoEmSegundos;
        }
    }

    /** O que a ponte aprendeu entre uma volta e outra. */
    public interface Memoria {
        int ultimoUid();

        void marcarUid(int uid);

        boolean jaLido(String mensagemId);

        void marcarLido(String mensagemId);

        void anotarComprovante(Comprovante comprovante);

        /** Copia defensiva: a ponte percorre a fila enquanto ela muda. */
        List<Comprovante> comprovantesPendentes();

        void esquecerComprovante(String referencia);
    }

    private final Fabricas fabricas;
    private final Configuracao ajustes;
    private final Credenciais credenciais;
    private final B64 base64;
    private final Despacho despacho;
    private final Memoria memoria;

    /** Recados com a nossa marca que nao abriram: alguem escrevendo no nosso formato sem a nossa chave. */
    private int corposSemAbertura;
    private int recadosDaPonte;
    private int origensSemPareamento;
    private int duvidas;
    private int confirmados;
    private int recusasDoServidor;
    private String ultimoErro = "";
    private String ultimaRecusa = "";

    public EmailBridge(Fabricas fabricas, Configuracao ajustes, Credenciais credenciais,
                       B64 base64, Despacho despacho, Memoria memoria) {
        this.fabricas = fabricas;
        this.ajustes = ajustes;
        this.credenciais = credenciais;
        this.base64 = base64;
        this.despacho = despacho;
        this.memoria = memoria;
    }

    public int corposSemAbertura() {
        return corposSemAbertura;
    }

    public int recadosDaPonte() {
        return recadosDaPonte;
    }

    public int origensSemPareamento() {
        return origensSemPareamento;
    }

    /** Quantos comprovantes sairam e a resposta nao voltou: o computador vai desfazer a duvida pelo proprio pedido. */
    public int duvidas() {
        return duvidas;
    }

    public String ultimoErro() {
        return ultimoErro;
    }

    public int recusasDoServidor() {
        return recusasDoServidor;
    }

    /** Por que o ultimo comprovante ficou na fila. O conteudo do recado nunca aparece aqui. */
    public String ultimaRecusa() {
        return ultimaRecusa;
    }

    /** Uma volta completa: ler a caixa e devolver os comprovantes que faltam. Devolve quantos pedidos entraram. */
    public int umaVolta() throws IOException {
        int tratados = lerCaixa();
        enviarPendentes();
        return tratados;
    }

    /** Le a caixa atras do ultimo UID. Um recado ruim nao derruba a volta. */
    public int lerCaixa() throws IOException {
        int tratados = 0;
        ImapClient caixa = new ImapClient(fabricas.caixa(), ajustes.hostDaCaixa,
                ajustes.portaDaCaixa, ajustes.tempoLimiteMs);
        try {
            caixa.login(ajustes.usuario, credenciais.senhaDeApp());
            caixa.selecionar(ajustes.caixa);
            // o que ja foi lido nao se rele: se comecasse no ultimo, o mesmo recado voltaria para sempre
            List<Integer> uids = caixa.buscarUid(memoria.ultimoUid() + 1);
            Collections.sort(uids);
            for (Integer uid : uids) {
                if (uid == null) {
                    continue;
                }
                byte[] bruto = caixa.corpoDoUid(uid);
                if (uid > memoria.ultimoUid()) {
                    memoria.marcarUid(uid);
                }
                if (tratar(bruto)) {
                    tratados++;
                }
            }
            ultimoErro = "";
        } catch (IOException caiu) {
            ultimoErro = resumo(caiu);
            throw caiu;
        } finally {
            caixa.sair();
        }
        return tratados;
    }

    /** Devolve os comprovantes que estao na fila. Devolve quantos o servidor confirmou. */
    public int enviarPendentes() throws IOException {
        List<Comprovante> pendentes = memoria.comprovantesPendentes();
        if (pendentes.isEmpty()) {
            return 0;
        }
        int antes = confirmados;
        SmtpClient saida = new SmtpClient(base64);
        try {
            saida.conectar(fabricas.saida(), ajustes.hostDaSaida, ajustes.portaDaSaida,
                    ajustes.starttls, ajustes.nomeDoAparelho);
            saida.entrar(ajustes.usuario, credenciais.senhaDeApp());
            for (Comprovante comprovante : pendentes) {
                if (!devolver(saida, comprovante)) {
                    break;
                }
            }
            ultimoErro = "";
        } catch (IOException caiu) {
            ultimoErro = resumo(caiu);
            throw caiu;
        } finally {
            saida.sair();
        }
        return confirmados - antes;
    }

    // ------------------------------------------------------------------ leitura

    /** true quando o recado era nosso, abriu e virou trabalho. */
    private boolean tratar(byte[] bruto) {
        EmailRecado recado = EmailRecado.ler(bruto);
        String assunto = recado.assunto();
        if (!EmailEnvelope.ehDaPonte(assunto)) {
            return false;
        }
        recadosDaPonte++;
        if (memoria.jaLido(recado.mensagemId())) {
            return false;
        }
        String origem = EmailEnvelope.origemNoAssunto(assunto);
        GatewayCrypto cifra = cifrarDe(origem);
        if (cifra == null) {
            origensSemPareamento++;
            return false;
        }
        JSONObject corpo;
        try {
            corpo = EmailEnvelope.abrir(cifra, base64.decodificar(EmailEnvelope.corpoLimpo(recado.corpo())));
        } catch (EmailEnvelope.Recusa | RuntimeException recusou) {
            // a marca e nossa e o conteudo nao abriu: alguem escrevendo no nosso formato
            corposSemAbertura++;
            return false;
        }
        memoria.marcarLido(recado.mensagemId());
        if (!EmailEnvelope.TIPO_PEDIDO.equals(EmailEnvelope.texto(corpo, "tipo"))) {
            return false;
        }
        String referencia = EmailEnvelope.texto(corpo, "referencia");
        if (referencia.isEmpty()) {
            return false;
        }
        // a origem do envelope tem de bater com a do assunto: senao um pedido do Hub entraria pela fila do PDV
        String origemDoEnvelope = EmailEnvelope.texto(corpo, "origem");
        if (!origemDoEnvelope.isEmpty() && !origemDoEnvelope.equals(origem)) {
            origensSemPareamento++;
            return false;
        }
        String para = EmailEnvelope.texto(corpo, "para");
        String estado = despacho.executar(origem, referencia, para, EmailEnvelope.texto(corpo, "texto"),
                recado.enderecoDe());
        if (estado == null) {
            return false;
        }
        memoria.anotarComprovante(new Comprovante(origem, referencia, para, estado,
                recado.enderecoDe(), System.currentTimeMillis() / 1000L));
        return true;
    }

    /** A chave do pareamento, aberta pelo mesmo base64 do resto da ponte; o que nao decodifica nao esta pareado. */
    private GatewayCrypto cifrarDe(String origem) {
        String chave = credenciais.chaveDaPonte(origem);
        if (chave == null) {
            return null;
        }
        try {
            return new GatewayCrypto(base64.decodificar(chave.trim()));
        } catch (RuntimeException invalida) {
            return null;
        }
    }

    // ------------------------------------------------------------------ escrita

    /** true quando pode passar ao proximo comprovante da fila. */
    private boolean devolver(SmtpClient saida, Comprovante comprovante) {
        GatewayCrypto cifra = cifrarDe(comprovante.origem);
        if (cifra == null || comprovante.destino.isEmpty()) {
            // sem pareamento ou sem endereco de volta nao ha para quem avisar: a fila nao pode entupir
            memoria.esquecerComprovante(comprovante.referencia);
            return true;
        }
        String recado;
        try {
            JSONObject corpo = EmailEnvelope.comprovante(comprovante.referencia, comprovante.para,
                    comprovante.estado, comprovante.quandoEmSegundos, ajustes.nomeDoAparelho);
            String envelope = base64.codificar(EmailEnvelope.selar(cifra, corpo));
            recado = SmtpClient.montar(ajustes.remetente, comprovante.destino,
                    EmailEnvelope.assunto(comprovante.origem, comprovante.referencia),
                    "recibo-" + comprovante.referencia + "@" + ajustes.dominioDoCarimbo, envelope);
        } catch (EmailEnvelope.Recusa naoMontou) {
            memoria.esquecerComprovante(comprovante.referencia);
            ultimaRecusa = resumo(naoMontou.getMessage());
            return true;
        }
        try {
            saida.entregar(ajustes.remetente, comprovante.destino, recado);
            memoria.esquecerComprovante(comprovante.referencia);
            confirmados++;
            return true;
        } catch (SmtpClient.Queda caiu) {
            if (SmtpClient.ETAPA_ENTREGA.equals(caiu.etapa())) {
                // o corpo saiu e a resposta nao voltou: pode ter entrado. Reenviar seria avisar duas vezes.
                memoria.esquecerComprovante(comprovante.referencia);
                duvidas++;
                return true;
            }
            recusasDoServidor++;
            ultimaRecusa = resumo(caiu.getMessage());
            return false;
        } catch (IOException caiu) {
            ultimaRecusa = resumo(caiu);
            return false;
        }
    }

    private static String resumo(String texto) {
        if (texto == null || texto.isEmpty()) {
            return "sem motivo";
        }
        String limpa = texto.replace('\r', ' ').replace('\n', ' ');
        return limpa.length() <= 160 ? limpa : limpa.substring(0, 160);
    }

    private static String resumo(Throwable causa) {
        String motivo = causa == null ? null : causa.getMessage();
        return resumo(motivo == null || motivo.isEmpty()
                ? (causa == null ? "sem motivo" : causa.getClass().getSimpleName()) : motivo);
    }
}
