package br.com.caracore.pdv.sms;

import java.util.ArrayList;
import java.util.List;

/**
 * As linhas de texto que a barra guarda nas preferencias do app: uma por recado
 * aberto, por comprovante na fila ou por pedido que precisa voltar pelo mesmo
 * caminho por onde entrou.
 *
 * O separador e a linha: o que tem controle dentro sai limpo, e o que nao abre
 * fica de fora sem derrubar o resto da guarda.
 */
final class GuardaDeLinhas {

    private GuardaDeLinhas() {
    }

    /** As linhas guardadas, na ordem em que entraram. */
    static List<String> ler(String texto) {
        List<String> linhas = new ArrayList<>();
        if (texto == null) {
            return linhas;
        }
        for (String pedaco : texto.split("\n")) {
            String limpa = pedaco.trim();
            if (!limpa.isEmpty()) {
                linhas.add(limpa);
            }
        }
        return linhas;
    }

    static String escrever(List<?> linhas) {
        StringBuilder sb = new StringBuilder();
        for (Object linha : linhas) {
            if (sb.length() > 0) {
                sb.append('\n');
            }
            sb.append(linha);
        }
        return sb.toString();
    }

    /** O que nao pode entrar na guarda: o separador de linha e o proprio controle. */
    static String limpar(String texto) {
        if (texto == null) {
            return "";
        }
        StringBuilder sb = new StringBuilder(texto.length());
        for (int i = 0; i < texto.length(); i++) {
            char c = texto.charAt(i);
            if (c < ' ' || c == 127) {
                sb.append(' ');
            } else {
                sb.append(c);
            }
        }
        return sb.toString().trim();
    }

    /** Os mais velhos saem primeiro: o que acabou de chegar e o que ainda tem o que contar. */
    static <T> void aparar(List<T> itens, int teto) {
        while (itens.size() > teto) {
            itens.remove(0);
        }
    }
}
