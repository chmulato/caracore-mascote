package br.com.caracore.pdv.sms;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * As chaves de pareamento que o celular tem, uma por produto.
 *
 * Cada pedido que entra por Wi-Fi foi escrito com a chave de quem o mandou. Para
 * saber quem mandou, o celular tenta abrir com as chaves que tem: a que abre e o
 * autor. Depois disso a origem declarada no comando ainda tem de bater com a chave
 * que abriu: sem isto um pedido do Hub entraria pela fila do PDV, que tem teto,
 * licenca e tela proprios.
 *
 * O pareamento antigo, de uma chave so para a loja inteira, ainda abre: ele vem
 * antes da isolacao e continua valendo. A limitacao e declarada: enquanto a loja
 * tiver uma unica chave, a origem que manda e a que o comando diz, e o celular nao
 * tem como conferir.
 */
public final class PareamentoPorOrigem {

    public static final String PDV = "PDV";
    public static final String HUB = "HUB";

    /** As origens que a barra conhece. O que nao esta aqui nao tem fila nem cota. */
    public static final String[] ORIGENS = {PDV, HUB};

    /** Onde moram as chaves: em producao as preferencias do app, no teste um mapa. */
    public interface Fonte {
        /** A chave em base64 daquela origem, ou null quando aquela loja nao esta pareada. */
        String chaveDaOrigem(String origem);
    }

    /** Uma chave e os produtos que ela pode ter escrito. */
    public static final class Par {
        private final String chave;
        private final GatewayCrypto cifra;
        private final List<String> origens = new ArrayList<>();

        private Par(String chave, GatewayCrypto cifra) {
            this.chave = chave;
            this.cifra = cifra;
        }

        /** A origem deste pareamento: a primeira que usa esta chave. */
        public String origem() {
            return origens.get(0);
        }

        /** Se a origem declarada no comando pode ter saido desta chave. */
        public boolean servePara(String origem) {
            return origem == null || origem.trim().isEmpty() || origens.contains(origem.trim());
        }

        /** Null quando o blob nao foi escrito com esta chave. */
        public byte[] abrir(byte[] blob) {
            if (blob == null) {
                return null;
            }
            try {
                return cifra.decrypt(blob);
            } catch (Exception naoAbriu) {
                return null;
            }
        }

        /** A resposta volta cifrada pela mesma chave que abriu o pedido. */
        public byte[] selar(byte[] claro) throws IOException {
            try {
                return cifra.encrypt(claro);
            } catch (Exception falhou) {
                throw new IOException("nao deu para cifrar a resposta");
            }
        }

        private boolean mesmaDe(String outraChave) {
            return chave.equals(outraChave);
        }
    }

    /** O blob aberto e quem o escreveu. */
    public static final class Aberto {
        public final Par par;
        public final byte[] claro;

        private Aberto(Par par, byte[] claro) {
            this.par = par;
            this.claro = claro;
        }

        public String texto() {
            return new String(claro, StandardCharsets.UTF_8);
        }
    }

    private final List<Par> pares = new ArrayList<>();

    public PareamentoPorOrigem(Fonte fonte, B64 base64) {
        montar(fonte, base64);
    }

    public boolean pareado() {
        return !pares.isEmpty();
    }

    /** O pareamento daquela origem, ou null quando aquela loja nao tem chave propria nem legado. */
    public Par daOrigem(String origem) {
        if (origem == null || origem.trim().isEmpty()) {
            return null;
        }
        String pedida = origem.trim();
        for (Par par : pares) {
            if (par.servePara(pedida)) {
                return par;
            }
        }
        return null;
    }

    /**
     * Abre o blob com a primeira chave que o abre e devolve junto quem abriu. Null
     * quando nenhuma chave da loja abre o recado: o conteudo nunca sai de uma chave
     * que nao e a de quem mandou, e a origem declarada no comando e conferida contra
     * o par devolvido ({@link Par#servePara(String)}).
     */
    public Aberto abrir(byte[] blob) {
        for (Par par : pares) {
            byte[] claro = par.abrir(blob);
            if (claro != null) {
                return new Aberto(par, claro);
            }
        }
        return null;
    }

    /** O que o painel mostra: as origens com chave, sem nunca mostrar a chave. */
    public String origensPareadas() {
        StringBuilder sb = new StringBuilder();
        for (String origem : ORIGENS) {
            if (daOrigem(origem) == null) {
                continue;
            }
            if (sb.length() > 0) {
                sb.append(' ');
            }
            sb.append(origem);
        }
        return sb.toString();
    }

    // ------------------------------------------------------------------ montagem

    private void montar(Fonte fonte, B64 base64) {
        for (String origem : ORIGENS) {
            String chave = chaveDe(fonte, origem);
            if (chave == null) {
                continue;
            }
            Par mesma = mesmaChave(chave);
            if (mesma != null) {
                // a chave do pareamento unico cobre os dois produtos: a origem passa a ser a do comando
                mesma.origens.add(origem);
                continue;
            }
            Par novo = abrirChave(chave, base64);
            if (novo == null) {
                continue;
            }
            novo.origens.add(origem);
            pares.add(novo);
        }
    }

    /** A chave daquela origem, com a reserva no pareamento unico de antes. */
    private static String chaveDe(Fonte fonte, String origem) {
        try {
            String chave = fonte.chaveDaOrigem(origem);
            if (chave == null) {
                return null;
            }
            String limpa = chave.trim();
            return limpa.isEmpty() ? null : limpa;
        } catch (RuntimeException quebrou) {
            return null;
        }
    }

    private Par mesmaChave(String chave) {
        for (Par par : pares) {
            if (par.mesmaDe(chave)) {
                return par;
            }
        }
        return null;
    }

    /** O que nao decodifica nao e pareamento: a loja fica de fora em vez de derrubar o servico. */
    private static Par abrirChave(String chave, B64 base64) {
        try {
            return new Par(chave, new GatewayCrypto(base64.decodificar(chave)));
        } catch (RuntimeException invalida) {
            return null;
        }
    }
}
