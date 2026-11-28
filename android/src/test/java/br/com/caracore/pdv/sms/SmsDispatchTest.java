package br.com.caracore.pdv.sms;

import org.junit.Test;

import java.util.ArrayList;
import java.util.List;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

/**
 * A ordem dos portoes e o contrato dos dois canais: o que o PC (motorista android_lan)
 * e o que a ponte de e-mail esperam ler como recusa. Mudar a ordem muda o veredito
 * do lado de la, entao cada portao tem seu teste e cada recusa early tem de provar
 * que nao consumiu cota nem mexeu no radio.
 */
public class SmsDispatchTest {

    private static final String ID = "pdv-0001";
    private static final String NUMERO = "+55 (41) 99999-8888";
    // O celular so tira espaco, parenteses e traco: o sinal de mais do codigo do pais fica.
    private static final String NUMERO_LIMPO = "+5541999998888";
    private static final String TEXTO = "Sua nota fiscal 77 esta pronta.";

    private static final class Fila implements SmsDispatch.Estado {
        boolean ativo = true;
        boolean conhecido = false;
        long ultimaSequencia = 0L;
        boolean cotaLibera = true;
        boolean permissao = true;

        int cotasConsumidas = 0;
        final List<String> registrados = new ArrayList<>();

        @Override
        public boolean ativo() {
            return ativo;
        }

        @Override
        public boolean jaConhecido(String jobId) {
            return conhecido;
        }

        @Override
        public long ultimaSequencia() {
            return ultimaSequencia;
        }

        @Override
        public boolean consumirCota() {
            cotasConsumidas++;
            return cotaLibera;
        }

        @Override
        public boolean podeEnviarSms() {
            return permissao;
        }

        @Override
        public void registrar(String jobId, long sequencia) {
            registrados.add(jobId + "@" + sequencia);
        }
    }

    private static final class Radio implements SmsDispatch.Radio {
        final List<String> enviadas = new ArrayList<>();
        Exception quebra;

        @Override
        public void enviar(String numero, String texto, String jobId) throws Exception {
            if (quebra != null) {
                throw quebra;
            }
            enviadas.add(numero + "|" + texto + "|" + jobId);
        }
    }

    private final Fila fila = new Fila();
    private final Radio radio = new Radio();

    private SmsDispatch.Ack enviar(String id, long sequencia, String numero, String texto) {
        return SmsDispatch.enviar(fila, radio, id, sequencia, numero, texto);
    }

    @Test
    public void aceitaPedidoValidoEPassaORadioLimpo() {
        SmsDispatch.Ack ack = enviar(ID, 7L, NUMERO, TEXTO);
        assertTrue(ack.ok());
        assertEquals("aceito", ack.status());
        assertNull(ack.erro());
        assertEquals(1, radio.enviadas.size());
        assertEquals(NUMERO_LIMPO + "|" + TEXTO + "|" + ID, radio.enviadas.get(0));
        assertEquals(1, fila.cotasConsumidas);
        assertEquals(java.util.Arrays.asList(ID + "@7"), fila.registrados);
    }

    @Test
    public void recusaPedidoSemIdentificador() {
        SmsDispatch.Ack ack = enviar("   ", 0L, NUMERO, TEXTO);
        assertFalse(ack.ok());
        assertEquals("pedido sem identificador", ack.erro());
        assertEquals(0, fila.cotasConsumidas);
        assertTrue(radio.enviadas.isEmpty());
    }

    @Test
    public void recusaComAppInativo() {
        fila.ativo = false;
        assertEquals("app inativo", enviar(ID, 0L, NUMERO, TEXTO).erro());
        assertEquals(0, fila.cotasConsumidas);
    }

    @Test
    public void recusaPedidoIncompleto() {
        assertEquals("pedido incompleto", enviar(ID, 0L, null, TEXTO).erro());
        assertEquals("pedido incompleto", enviar(ID, 0L, "  ", TEXTO).erro());
        assertEquals("pedido incompleto", enviar(ID, 0L, NUMERO, null).erro());
    }

    @Test
    public void recusaNumeroForaDaFaixaOuSemDigito() {
        assertEquals("numero invalido", enviar(ID, 0L, "+55 (41)", TEXTO).erro());
        assertEquals("numero invalido", enviar(ID, 0L, "+5541999998888777", TEXTO).erro());
        assertEquals("numero invalido", enviar(ID, 0L, "ramal", TEXTO).erro());
        assertEquals(0, fila.cotasConsumidas);
    }

    @Test
    public void recusaTextoAcimaDoLimite() {
        StringBuilder longo = new StringBuilder();
        for (int i = 0; i <= SmsDispatch.TEXTO_MAXIMO; i++) {
            longo.append('x');
        }
        assertEquals("mensagem acima de 480 caracteres", enviar(ID, 0L, NUMERO, longo.toString()).erro());
        assertEquals(0, fila.cotasConsumidas);
    }

    @Test
    public void pedidoJaConhecidoNaoSaiDuasVezes() {
        fila.conhecido = true;
        SmsDispatch.Ack ack = enviar(ID, 9L, NUMERO, TEXTO);
        assertTrue(ack.ok());
        assertTrue(ack.repetido());
        assertEquals("repetido", ack.status());
        assertTrue(radio.enviadas.isEmpty());
        assertEquals(0, fila.cotasConsumidas);
        assertTrue(fila.registrados.isEmpty());
    }

    @Test
    public void recusaSequenciaRepisada() {
        fila.ultimaSequencia = 10L;
        SmsDispatch.Ack ack = enviar(ID, 10L, NUMERO, TEXTO);
        assertFalse(ack.ok());
        assertEquals("pedido repetido", ack.erro());
        assertEquals(0, fila.cotasConsumidas);
    }

    @Test
    public void duplicataTemVozAntesDaSequencia() {
        fila.conhecido = true;
        fila.ultimaSequencia = 10L;
        SmsDispatch.Ack ack = enviar(ID, 3L, NUMERO, TEXTO);
        assertTrue(ack.ok());
        assertEquals("repetido", ack.status());
    }

    @Test
    public void pedidoSemSequenciaNaoTropecaNaTrava() {
        fila.ultimaSequencia = 50L;
        assertTrue(enviar(ID, 0L, NUMERO, TEXTO).ok());
    }

    @Test
    public void recusaSemPermissaoDeSms() {
        fila.permissao = false;
        assertEquals("permissao de SMS negada", enviar(ID, 0L, NUMERO, TEXTO).erro());
        assertEquals(0, fila.cotasConsumidas);
        assertTrue(radio.enviadas.isEmpty());
    }

    @Test
    public void recusaQuandoOAparelhoJaUsouOCotaDoDia() {
        fila.cotaLibera = false;
        assertEquals("limite diario do celular atingido", enviar(ID, 0L, NUMERO, TEXTO).erro());
        assertEquals(1, fila.cotasConsumidas);
        assertTrue(radio.enviadas.isEmpty());
        assertTrue(fila.registrados.isEmpty());
    }

    @Test
    public void radioQuebradoNaoRegistraOPedido() {
        radio.quebra = new IllegalStateException("radio ocupado");
        SmsDispatch.Ack ack = enviar(ID, 4L, NUMERO, TEXTO);
        assertFalse(ack.ok());
        assertEquals("falha ao processar o pedido", ack.erro());
        assertTrue(fila.registrados.isEmpty());
    }
}
