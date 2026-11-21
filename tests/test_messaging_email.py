"""Testes da ponte de e-mail.

Nenhum deles depende da internet: as tres conexoes entram por fabrica e os
enderecos usados sao de dominio reservado para documentacao. O grupo principal
amarra um gravador no SMTP, no IMAP, no POP3 e na resolucao de nome e prova que
a ponte desligada nao chega a esbarar nele - e que o gravador enche quando a
ponte esta ligada, porque senao o teste seria verde por enfeite.
"""

from __future__ import annotations

import base64
import imaplib
import json
import poplib
import shutil
import smtplib
import socket
import tempfile
import unittest
from email import message_from_bytes
from email.message import EmailMessage
from pathlib import Path
from unittest import mock

from gaspar.messaging.model import MAX_TEXTO, Message, MessageBrief, STATUS_FILA
from gaspar.messaging.transports import TransportRegistry
from gaspar.messaging.transports.smtp_email import (
    ASSUNTO_PREFIXO,
    ESTADO_ENTREGUE,
    ESTADO_FALHOU,
    TIPO_COMPROVANTE,
    TIPO_PEDIDO,
    TIPO_RESPOSTA,
    BridgeState,
    EmailBridgeDriver,
    EmailSettings,
    abrir_envelope,
    selar_envelope,
)
from gaspar.messaging.transport import InboundReply
from gaspar.messaging.vault import Vault

NUMERO = "11988887777"
#: a chave da ponte e a de um estranho: as duas com os 32 bytes contados, nao escritos
CHAVE_BRUTA = bytes(range(32))
CHAVE_ALHEIA = bytes(range(32, 64))
CHAVE = base64.b64encode(CHAVE_BRUTA).decode("ascii")
SENHA = "senha-de-app-de-mentirinha"


def pedido(**campo) -> Message:
    dados = {
        "id": "m-1",
        "origem": "PDV",
        "external_id": "pdv-100",
        "idempotency_key": "k-1",
        "recipient": NUMERO,
        "text": "Retire sua encomenda",
        "created_at": 1000.0,
    }
    dados.update(campo)
    return Message(**dados)


def breve(id_mensagem: str, origem: str = "PDV") -> MessageBrief:
    return MessageBrief(
        id=id_mensagem, origem=origem, external_id="pdv-100", created_at=1000.0, status=STATUS_FILA
    )


def montar_mail(assunto: str, corpo: str, message_id: str = "") -> bytes:
    mail = EmailMessage()
    mail["Subject"] = assunto
    mail["From"] = "celular@loja.test.invalid"
    mail["To"] = "loja@loja.test.invalid"
    if message_id:
        mail["Message-ID"] = message_id
    mail.set_content(corpo)
    return bytes(mail)


def recado(tipo: str, *, chave: bytes | None = None, message_id: str = "", **campo) -> bytes:
    """Um e-mail como o celular escreve na caixa postal da loja."""
    corpo = {"v": 1, "tipo": tipo, "quando": 2000.0, "dispositivo": "celular-loja"}
    corpo.update(campo)
    envelope = selar_envelope(chave or base64.b64decode(CHAVE), corpo)
    assunto = f"{ASSUNTO_PREFIXO} PDV {corpo.get('referencia', 'sem-referencia')}"
    return montar_mail(assunto, envelope, message_id)


def corpo_do_mail(bruto) -> dict:
    """Descifra pelo caminho do teste: implementacao independente do motorista."""
    if bruto.is_multipart():
        texto = ""
        for parte in bruto.walk():
            if parte.get_content_maintype() == "text":
                texto = str(parte.get_payload(decode=True) or b"", "utf-8")
                break
    else:
        texto = str(bruto.get_payload(decode=True) or b"", "utf-8")
    return abrir_envelope(base64.b64decode(CHAVE), texto)


# ------------------------------------------------------------------ dubles


class ServidorSMTP:
    """Servidor de saida de mentirinha: anota o que recebeu e pode cair de propositos."""

    def __init__(self, excecao_envio: Exception | None = None, erro_login: Exception | None = None):
        self.excecao_envio = excecao_envio
        self.erro_login = erro_login
        self.enviados: list = []
        self.logins: list[tuple[str, str]] = []
        self.fechado = False

    def login(self, usuario, senha):
        if self.erro_login is not None:
            raise self.erro_login
        self.logins.append((usuario, senha))
        return (235, b"ok")

    def send_message(self, mail):
        if self.excecao_envio is not None:
            raise self.excecao_envio
        self.enviados.append(mail)
        return {}

    def quit(self):
        self.fechado = True


class ServidorQueCaiNoMeio(ServidorSMTP):
    def send_message(self, mail):
        raise OSError("soquete fechado sem resposta")


class ServidorIMAP:
    """Caixa postal que obedece ao cursor: so entrega o UID pedido pela busca."""

    def __init__(self, brutos: list[bytes], resposta_busca: str = "OK"):
        self.brutos = brutos
        self.resposta_busca = resposta_busca
        self.chamadas: list[str] = []
        self.senhas: list[str] = []
        self.busca = ""

    def login(self, usuario, senha):
        self.chamadas.append(f"login:{usuario}")
        self.senhas.append(senha)
        return ("OK", [b""])

    def select(self, caixa):
        self.chamadas.append(f"select:{caixa}")
        return ("OK", [str(len(self.brutos)).encode("ascii")])

    def uid(self, comando, *args):
        if comando == "SEARCH":
            alvo = str(args[-1])
            self.busca = alvo
            self.chamadas.append(f"search:{alvo}")
            if self.resposta_busca != "OK":
                return ("NO", [b""])
            inicio = int(alvo.split(":")[0])
            nomes = [str(uido) for uido in range(inicio, len(self.brutos) + 1) if uido >= inicio]
            return ("OK", [" ".join(nomes).encode("ascii")])
        self.chamadas.append(f"fetch:{args[0]}")
        bruto = self.brutos[int(args[0]) - 1]
        return ("OK", [(b"1 (BODY[] {%d}" % len(bruto), bruto), b")"])

    def logout(self):
        self.chamadas.append("logout")
        return ("BYE", [b""])


class ServidorPOP3:
    def __init__(self, brutos: list[bytes]):
        self.brutos = brutos
        self.chamadas: list[str] = []

    def user(self, usuario):
        self.chamadas.append(f"user:{usuario}")

    def pass_(self, senha):
        self.chamadas.append("pass")

    def stat(self):
        return (len(self.brutos), 1000)

    def retr(self, numero):
        return (b"+OK", self.brutos[numero - 1].split(b"\r\n"), b"")

    def quit(self):
        self.chamadas.append("quit")


# ------------------------------------------------------------------ base


class PonteDeEmail(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="gaspar-ponte-"))
        self.vault = Vault.load_or_create(self.base / "gaspar.key")
        self.arquivo_de_estado = str(self.base / "estado.json")

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def ajustes(self, **campo) -> EmailSettings:
        base = {
            "enabled": True,
            "user": "loja@loja.test.invalid",
            "password_sealed": self.vault.seal(SENHA),
            "bridge_key_sealed": self.vault.seal(CHAVE),
            "smtp_host": "smtp.test.invalid",
            "imap_host": "imap.test.invalid",
            "state_path": self.arquivo_de_estado,
        }
        base.update(campo)
        return EmailSettings(**base)

    def motorista(self, settings: EmailSettings | None = None, **fabrica) -> EmailBridgeDriver:
        """Motorista com cofre de verdade e fabrica so onde o teste pede."""
        fabricas = {nome: valor for nome, valor in fabrica.items() if valor is not None}
        return EmailBridgeDriver(settings or self.ajustes(), vault=self.vault, **fabricas)


# ---------------------------------------------------------------- envelope


class EnvelopeTeste(PonteDeEmail):
    def test_o_envelope_abre_com_a_mesma_chave(self):
        corpo = {"v": 1, "tipo": TIPO_RESPOSTA, "de": NUMERO, "texto": "quero sim"}
        selado = selar_envelope(base64.b64decode(CHAVE), corpo)
        self.assertTrue(selado.isascii(), "o corpo precisa caber num e-mail de texto")
        self.assertEqual(abrir_envelope(base64.b64decode(CHAVE), selado), corpo)

    def test_chave_diferente_nao_abre_o_envelope(self):
        selado = selar_envelope(CHAVE_BRUTA, {"v": 1, "tipo": TIPO_RESPOSTA})
        with self.assertRaises(Exception):
            abrir_envelope(CHAVE_ALHEIA, selado)

    def test_envelope_adulterado_nao_abre(self):
        chave = base64.b64decode(CHAVE)
        selado = bytearray(selar_envelope(chave, {"v": 1, "tipo": TIPO_RESPOSTA}).encode("ascii"))
        selado[24] = ord("A") if selado[24] != ord("A") else ord("B")
        with self.assertRaises(Exception):
            abrir_envelope(chave, selado.decode("ascii"))

    def test_versao_e_tipo_desconhecidos_sem_envelope(self):
        chave = base64.b64decode(CHAVE)
        for corpo in ({"v": 2, "tipo": TIPO_RESPOSTA}, {"v": 1, "tipo": "qualquer"}, {"tipo": TIPO_RESPOSTA}):
            with self.assertRaises(ValueError):
                abrir_envelope(chave, selar_envelope(chave, corpo))

    def test_texto_de_cliente_com_acento_nao_aparece_no_cabecalho(self):
        chave = base64.b64decode(CHAVE)
        selado = selar_envelope(chave, {"v": 1, "tipo": TIPO_PEDIDO, "texto": "Caf\u00e9 com leite \u00e7 \u00e3o"})
        bruto = montar_mail(f"{ASSUNTO_PREFIXO} PDV m-1", selado)
        self.assertTrue(bruto.decode("ascii").isascii(), "o recado inteiro tem de ser ASCII")
        self.assertEqual(corpo_do_mail(message_from_bytes(bruto))["texto"], "Caf\u00e9 com leite \u00e7 \u00e3o")

    def test_a_ruptura_de_linha_do_servidor_nao_quebra_a_leitura(self):
        """Corpo base64 pode chegar quebrado pelo transporte: a leitura junta os pedacos."""
        corpo = {"v": 1, "tipo": TIPO_RESPOSTA, "de": NUMERO, "texto": "quero sim", "referencia": "m-1"}
        selado = selar_envelope(base64.b64decode(CHAVE), corpo)
        quebrado = "\r\n".join(selado[i : i + 40] for i in range(0, len(selado), 40))
        bruto = montar_mail(f"{ASSUNTO_PREFIXO} PDV m-1", quebrado)
        motorista = self.motorista(imap_factory=lambda *a: ServidorIMAP([bruto]))
        self.assertEqual([reply.text for reply in motorista.poll_inbound()], ["quero sim"])


class ConfiguracaoTeste(PonteDeEmail):
    def test_desligada_e_a_escolha_por_padrao(self):
        self.assertIs(EmailSettings().enabled, False)
        self.assertIn("conta", EmailSettings().faltando())

    def test_ajustes_gravados_sao_os_mesmos_lidos(self):
        original = self.ajustes(pop3_host="pop3.test.invalid", smtp_security="starttls")
        relida = EmailSettings.from_dict(original.to_dict())
        self.assertEqual(relida.to_dict(), original.to_dict())

    def test_o_arquivo_da_ponte_nunca_tem_senha_nem_chave_em_texto_claro(self):
        bruto = json.dumps(self.ajustes().to_dict())
        self.assertNotIn(SENHA, bruto)
        self.assertNotIn(CHAVE, bruto)
        self.assertIn('"password_sealed"', bruto)
        self.assertIn('"bridge_key_sealed"', bruto)
        # o segredo so aparece aberto, na mao de quem ja tem o cofre da fila
        self.assertEqual(self.vault.open(self.ajustes().bridge_key_sealed), CHAVE)

    def test_campo_futuro_nao_derruba_a_leitura(self):
        relida = EmailSettings.from_dict({"user": "loja@test.invalid", "futuro": 1})
        self.assertEqual(relida.user, "loja@test.invalid")

    def test_porta_fora_de_faixa_volta_ao_padrao(self):
        ajustes = EmailSettings(smtp_port=99999, imap_port=0, smtp_security="criativo", max_poll_messages=-5)
        self.assertEqual(ajustes.smtp_port, 465)
        self.assertEqual(ajustes.imap_port, 993)
        self.assertEqual(ajustes.smtp_security, "ssl")
        self.assertEqual(ajustes.max_poll_messages, 1)

    def test_imap_e_a_leitura_preferida_e_pop3_a_reserva(self):
        self.assertEqual(self.ajustes().protocolo_de_leitura, "imap")
        self.assertEqual(self.ajustes(imap_host="", pop3_host="pop3.test.invalid").protocolo_de_leitura, "pop3")
        self.assertEqual(self.ajustes(imap_host="", pop3_host="").protocolo_de_leitura, "")

    def test_sem_endereco_escolhido_a_conta_faz_os_dois_papeis(self):
        ajustes = self.ajustes(queue_address="", from_address="")
        self.assertEqual(ajustes.endereco_fila, "loja@loja.test.invalid")
        self.assertEqual(ajustes.endereco_remetente, "loja@loja.test.invalid")

    def test_o_registro_conhece_a_ponte_pelo_nome(self):
        registro = TransportRegistry()
        motorista = self.motorista()
        registro.register(motorista)
        registro.bind("PDV", "smtp_email")
        self.assertIs(registro.driver_for("PDV"), motorista)
        # registrar nao e vincular: o vizinho continua sem meio
        self.assertIsNone(registro.driver_for("HUB"))


# ------------------------------------------------------------ zero conexao


class ZeroConexaoTeste(PonteDeEmail):
    """O gravador: qualquer tentativa de saida de rede fica registrada aqui."""

    def alarmes(self, rede: list[str]):
        def alarme(nome):
            def disparar(*args, **kwargs):
                rede.append(f"{nome} {args[:2]}")
                raise OSError(f"rede proibida neste teste: {nome}")

            return disparar

        return [
            mock.patch.object(smtplib, "SMTP", alarme("smtplib.SMTP")),
            mock.patch.object(smtplib, "SMTP_SSL", alarme("smtplib.SMTP_SSL")),
            mock.patch.object(imaplib, "IMAP4", alarme("imaplib.IMAP4")),
            mock.patch.object(imaplib, "IMAP4_SSL", alarme("imaplib.IMAP4_SSL")),
            mock.patch.object(poplib, "POP3", alarme("poplib.POP3")),
            mock.patch.object(poplib, "POP3_SSL", alarme("poplib.POP3_SSL")),
            mock.patch.object(socket, "create_connection", alarme("socket.create_connection")),
            mock.patch.object(socket, "getaddrinfo", alarme("socket.getaddrinfo")),
        ]

    def sob_alarme(self, acao, rede: list[str]):
        alvos = self.alarmes(rede)
        for alvo in alvos:
            alvo.start()
        try:
            acao()
        finally:
            for alvo in alvos:
                alvo.stop()
        return rede

    def test_a_ponte_desligada_nao_toca_na_rede(self):
        settings = self.ajustes(enabled=False, pop3_host="pop3.test.invalid")
        # sem fabrica nenhuma: aqui sao os caminhos reais de saida do modulo que estao na mira
        motorista = self.motorista(settings)

        def mexer_na_ponte():
            self.assertIs(motorista.health().available, False)
            self.assertEqual(motorista.submit(pedido()).outcome, "indisponivel")
            self.assertEqual(motorista.poll_inbound(), [])
            self.assertIsNone(motorista.resolve_uncertain(pedido()))
            motorista.shutdown()

        self.assertEqual(self.sob_alarme(mexer_na_ponte, []), [])

    def test_o_alarme_enche_quando_a_ponte_esta_ligada(self):
        """Contra-prova do teste acima: sem ela o verde seria por enfeite."""
        envio = self.motorista()
        rede = self.sob_alarme(lambda: envio.submit(pedido()), [])
        self.assertEqual(len(rede), 1, rede)
        self.assertIn("smtplib.SMTP_SSL", rede[0])
        self.assertIn("smtp.test.invalid", rede[0])

        leitura = self.motorista(self.ajustes(imap_host="imap.test.invalid", pop3_host=""))
        rede = self.sob_alarme(lambda: leitura.poll_inbound(), [])
        self.assertEqual(len(rede), 1, rede)
        self.assertIn("imaplib.IMAP4_SSL", rede[0])
        self.assertIn("imap.test.invalid", rede[0])

    def test_meio_desligado_nao_aparece_vivo_para_a_origem(self):
        registro = TransportRegistry()
        registro.register(self.motorista(self.ajustes(enabled=False)))
        registro.bind("PDV", "smtp_email")

        def checar():
            self.assertIs(registro.health()["PDV"].available, False)

        self.assertEqual(self.sob_alarme(checar, []), [])

    def test_a_ponte_desligada_nao_chama_nem_a_fabrica_de_saida(self):
        chamada: list[tuple] = []
        motorista = self.motorista(self.ajustes(enabled=False), smtp_factory=lambda *a: chamada.append(a))
        self.assertEqual(motorista.submit(pedido()).outcome, "indisponivel")
        self.assertEqual(motorista.poll_inbound(), [])
        self.assertEqual(chamada, [])

    def test_a_ponte_ligada_sem_cofre_bate_na_porta_do_cofre(self):
        motorista = EmailBridgeDriver(self.ajustes(), vault=None)

        def mexer_na_ponte():
            self.assertIs(motorista.health().available, True, "ligada na configuracao e o que ela sabe")
            self.assertEqual(motorista.submit(pedido()).outcome, "recusado")
            self.assertEqual(motorista.poll_inbound(), [])

        self.assertEqual(self.sob_alarme(mexer_na_ponte, []), [])
        self.assertIn("cofre", motorista.ultimo_erro)


class SondaDeAcessoTeste(PonteDeEmail):
    """O botao "Testar acesso" do painel (Onda B6-6) na caixa postal da loja.

    A sonda entra, se apresenta e sai. Ela nunca le recado, nunca marca nada como
    lido e nunca escreve: um teste de acesso que mexe na caixa derruba a fila por
    tras - o celular responde, a resposta desaparece e o lojista nao sabe por que.
    """

    def test_a_ponte_desligada_nao_abre_conexao_nenhuma(self):
        chamada: list[str] = []
        motorista = self.motorista(
            self.ajustes(enabled=False),
            smtp_factory=lambda *a: chamada.append("smtp"),
            imap_factory=lambda *a: chamada.append("imap"),
        )
        checagem = motorista.testar_acesso()
        self.assertFalse(checagem.available)
        self.assertIn("desligada", checagem.reason)
        self.assertEqual(chamada, [])

    def test_a_saida_confere_e_nenhum_recado_sai_para_a_rua(self):
        servidor = ServidorSMTP()
        motorista = self.motorista(self.ajustes(imap_host=""), smtp_factory=lambda *a: servidor)
        checagem = motorista.testar_acesso()
        self.assertTrue(checagem.available, checagem.reason)
        self.assertEqual(servidor.logins, [("loja@loja.test.invalid", SENHA)])
        self.assertEqual(servidor.enviados, [])
        self.assertTrue(servidor.fechado, "a conexao de prova tem de ser fechada")
        self.assertIn("leitura esta desligada", checagem.reason)
        self.assertEqual(checagem.detail, motorista.device_id)

    def test_a_sonda_de_imap_e_so_entrar_e_sair(self):
        caixa = ServidorIMAP([])
        motorista = self.motorista(
            smtp_factory=lambda *a: ServidorSMTP(), imap_factory=lambda *a: caixa
        )
        checagem = motorista.testar_acesso()
        self.assertTrue(checagem.available, checagem.reason)
        self.assertEqual(checagem.reason, "")
        self.assertEqual(caixa.chamadas, ["login:loja@loja.test.invalid", "logout"])
        self.assertEqual(caixa.senhas, [SENHA])

    def test_a_sonda_de_pop3_sai_pelo_verbo_do_pop3(self):
        caixa = ServidorPOP3([])
        motorista = self.motorista(
            self.ajustes(imap_host="", pop3_host="pop3.test.invalid"),
            smtp_factory=lambda *a: ServidorSMTP(),
            pop3_factory=lambda *a: caixa,
        )
        checagem = motorista.testar_acesso()
        self.assertTrue(checagem.available, checagem.reason)
        self.assertEqual(caixa.chamadas, ["user:loja@loja.test.invalid", "pass", "quit"])

    def test_saida_boa_com_leitura_recusada_ainda_diz_que_da_para_enviar(self):
        def caixa_que_recusa(host, porta):
            raise imaplib.IMAP4.error("credencial recusada")

        motorista = self.motorista(
            smtp_factory=lambda *a: ServidorSMTP(), imap_factory=caixa_que_recusa
        )
        checagem = motorista.testar_acesso()
        self.assertTrue(checagem.available)
        self.assertIn("a saida confere", checagem.reason)
        self.assertIn("leitura falhou", checagem.reason)
        self.assertIn("IMAP: credencial recusada", checagem.reason)

    def test_a_caixa_que_fala_metade_tambem_vira_texto_e_nao_estouro(self):
        caixa = ServidorIMAP([])

        def login_troncado(usuario, senha):
            raise OSError("mao fechada no meio do aperto")

        caixa.login = login_troncado
        motorista = self.motorista(
            smtp_factory=lambda *a: ServidorSMTP(), imap_factory=lambda *a: caixa
        )
        self.assertIn("leitura falhou", motorista.testar_acesso().reason)

    def test_a_saida_recusada_derruba_o_acesso_e_fecha_a_conexao(self):
        recusa = smtplib.SMTPAuthenticationError(535, b"senha errada")
        servidor = ServidorSMTP(erro_login=recusa)
        motorista = self.motorista(smtp_factory=lambda *a: servidor)
        checagem = motorista.testar_acesso()
        self.assertFalse(checagem.available)
        self.assertIn("recusou a credencial", checagem.reason)
        self.assertTrue(servidor.fechado)

    def test_a_saida_que_nao_responde_devolve_o_motivo_do_sistema(self):
        def sem_resposta(host, porta):
            raise OSError("tempo esgotado")

        checagem = self.motorista(smtp_factory=sem_resposta).testar_acesso()
        self.assertFalse(checagem.available)
        self.assertIn("nao deu para falar com o servidor de saida", checagem.reason)
        self.assertIn("tempo esgotado", checagem.reason)

    def test_sem_cofre_a_sonda_reclama_antes_de_bater_na_porta(self):
        chamada: list[str] = []
        motorista = EmailBridgeDriver(
            self.ajustes(),
            vault=None,
            smtp_factory=lambda *a: chamada.append("smtp"),
            imap_factory=lambda *a: chamada.append("imap"),
        )
        checagem = motorista.testar_acesso()
        self.assertFalse(checagem.available)
        self.assertIn("cofre", checagem.reason)
        self.assertEqual(chamada, [])

    def test_a_sonda_nunca_usa_o_caminho_de_ida_e_volta(self):
        """Se a sonda chamasse ``submit`` ou ``poll_inbound``, mexeria na caixa do cliente."""

        def proibido(*_a, **_kw):
            raise AssertionError("a sonda usou o caminho de ida e volta")

        motorista = self.motorista(smtp_factory=lambda *a: ServidorSMTP())
        with mock.patch.object(motorista, "submit", proibido), mock.patch.object(
            motorista, "poll_inbound", proibido
        ):
            self.assertTrue(motorista.testar_acesso().available)


# ------------------------------------------------------------------ envio


class EnvioTeste(PonteDeEmail):
    def test_o_pedido_entra_na_caixa_cifrado(self):
        servidor = ServidorSMTP()
        motorista = self.motorista(smtp_factory=lambda *a: servidor)
        resultado = motorista.submit(pedido())
        self.assertEqual(resultado.outcome, "aceito")
        self.assertEqual(resultado.reference, "m-1")
        self.assertEqual(servidor.logins, [("loja@loja.test.invalid", SENHA)])
        self.assertTrue(servidor.fechado, "a conexao de saida precisa ser fechada")
        corpo = corpo_do_mail(servidor.enviados[0])
        self.assertEqual(corpo["tipo"], TIPO_PEDIDO)
        self.assertEqual(corpo["para"], NUMERO)
        self.assertEqual(corpo["texto"], "Retire sua encomenda")
        self.assertEqual(corpo["origem"], "PDV")
        self.assertEqual(corpo["referencia"], "m-1")
        self.assertEqual(corpo["id_externo"], "pdv-100")
        self.assertEqual(corpo["quando"], 1000.0)

    def test_o_cabecalho_do_pedido_nao_entrega_o_cliente(self):
        servidor = ServidorSMTP()
        motorista = self.motorista(smtp_factory=lambda *a: servidor)
        motorista.submit(pedido())
        mail = servidor.enviados[0]
        self.assertNotIn(NUMERO, str(mail["Subject"]))
        self.assertNotIn(NUMERO, str(mail["Message-ID"]))
        self.assertNotIn(NUMERO, str(mail["To"]))
        self.assertNotIn(NUMERO, str(mail["From"]))
        # o recado inteiro, cabecalho e corpo, nao contem o numero em claro
        self.assertNotIn(NUMERO.encode("ascii"), bytes(mail))

    def test_a_saida_usa_o_endereco_escolhido_para_a_fila(self):
        servidor = ServidorSMTP()
        motorista = self.motorista(
            self.ajustes(from_address="balcao@loja.test.invalid", queue_address="fila@loja.test.invalid"),
            smtp_factory=lambda *a: servidor,
        )
        motorista.submit(pedido())
        mail = servidor.enviados[0]
        self.assertEqual(str(mail["From"]), "balcao@loja.test.invalid")
        self.assertEqual(str(mail["To"]), "fila@loja.test.invalid")
        self.assertTrue(str(mail["Message-ID"]).endswith("@gaspar.local>"))

    def test_sem_endereco_escolhido_a_saida_sai_da_conta(self):
        servidor = ServidorSMTP()
        motorista = self.motorista(
            self.ajustes(from_address="", queue_address=""),
            smtp_factory=lambda *a: servidor,
        )
        motorista.submit(pedido())
        mail = servidor.enviados[0]
        self.assertEqual(str(mail["From"]), "loja@loja.test.invalid")
        self.assertEqual(str(mail["To"]), "loja@loja.test.invalid")

    def test_pedido_de_origem_inexistente_e_recusado(self):
        servidor = ServidorSMTP()
        motorista = self.motorista(smtp_factory=lambda *a: servidor)
        self.assertEqual(motorista.submit(pedido(origem="BALCAO")).outcome, "recusado")
        self.assertEqual(servidor.enviados, [])

    def test_pedido_sem_numero_valido_e_recusado_antes_de_sair(self):
        servidor = ServidorSMTP()
        motorista = self.motorista(smtp_factory=lambda *a: servidor)
        for destino in ("abc", "", None):
            self.assertEqual(motorista.submit(pedido(recipient=destino)).outcome, "recusado", destino)
        self.assertEqual(servidor.enviados, [])

    def test_o_servidor_que_recusa_a_credencial_devolve_recusado(self):
        recusa = smtplib.SMTPAuthenticationError(535, b"senha errada")
        servidor = ServidorSMTP(erro_login=recusa)
        motorista = self.motorista(smtp_factory=lambda *a: servidor)
        resultado = motorista.submit(pedido())
        self.assertEqual(resultado.outcome, "recusado")
        self.assertIn("credencial", resultado.reason)
        self.assertEqual(servidor.enviados, [])

    def test_a_saida_que_nao_abre_e_recusada(self):
        motorista = self.motorista(smtp_factory=_explodir)
        resultado = motorista.submit(pedido())
        self.assertEqual(resultado.outcome, "recusado")
        self.assertIn("servidor de saida", resultado.reason)

    def test_queda_no_meio_da_entrega_e_incerta_e_nao_reenvia(self):
        servidor = ServidorQueCaiNoMeio()
        motorista = self.motorista(smtp_factory=lambda *a: servidor)
        resultado = motorista.submit(pedido())
        self.assertEqual(resultado.outcome, "incerto")
        self.assertIn("confirmar", resultado.reason)
        self.assertEqual(servidor.enviados, [], "o pedido nao pode ser empurrado duas vezes")

    def test_o_servidor_que_devolve_codigo_de_recusa_e_recusado(self):
        recusa = smtplib.SMTPRecipientsRefused({"loja@loja.test.invalid": (550, b"caixa cheia")})
        servidor = ServidorSMTP(excecao_envio=recusa)
        motorista = self.motorista(smtp_factory=lambda *a: servidor)
        self.assertEqual(motorista.submit(pedido()).outcome, "recusado")

    def test_a_ajustes_incompleto_devolve_indisponivel(self):
        motorista = self.motorista(self.ajustes(smtp_host=""))
        resultado = motorista.submit(pedido())
        self.assertEqual(resultado.outcome, "indisponivel")
        self.assertIn("servidor de saida", resultado.reason)

    def test_a_senha_do_cofre_errada_devolve_recusado_sem_sair(self):
        settings = self.ajustes(password_sealed=self.vault.seal(SENHA + "!"), bridge_key_sealed="fora-do-cofre")
        servidor = ServidorSMTP()
        cofre_de_outra_maquina = Vault(bytes(range(64)))
        motorista = EmailBridgeDriver(settings, vault=cofre_de_outra_maquina, smtp_factory=lambda *a: servidor)
        self.assertEqual(motorista.submit(pedido()).outcome, "recusado")
        self.assertEqual(servidor.enviados, [])
        self.assertEqual(servidor.logins, [])

    def test_o_starttls_e_usado_quando_a_saida_pedir(self):
        class ComTLS(ServidorSMTP):
            def __init__(self):
                super().__init__()
                self.tls = False

            def starttls(self):
                self.tls = True

        servidor = ComTLS()
        motorista = self.motorista(self.ajustes(smtp_security="starttls"), smtp_factory=lambda *a: servidor)
        self.assertEqual(motorista.submit(pedido()).outcome, "aceito")
        self.assertTrue(servidor.tls)

    def test_a_saida_plana_existe_para_tubo_de_teste_local(self):
        servidor = ServidorSMTP()
        motorista = self.motorista(self.ajustes(smtp_security="plano"), smtp_factory=lambda *a: servidor)
        self.assertEqual(motorista.submit(pedido()).outcome, "aceito")


def _explodir(*args, **kwargs):
    raise OSError("sem saida")


# --------------------------------------------------------------- recepcao


class LeituraTeste(PonteDeEmail):
    def test_a_resposta_do_cliente_sai_da_caixa_imap(self):
        bruto = recado(TIPO_RESPOSTA, de=NUMERO, texto="quero sim", referencia="m-1")
        caixa = ServidorIMAP([bruto])
        motorista = self.motorista(imap_factory=lambda *a: caixa)
        replies = motorista.poll_inbound()
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0].sender, NUMERO)
        self.assertEqual(replies[0].text, "quero sim")
        self.assertEqual(replies[0].reference, "m-1")
        self.assertEqual(replies[0].device_id, "celular-loja")
        self.assertEqual(replies[0].received_at, 2000.0)
        self.assertEqual(caixa.senhas, [SENHA])
        self.assertEqual(caixa.chamadas[0], "login:loja@loja.test.invalid")
        self.assertIn("logout", caixa.chamadas)

    def test_o_cursor_da_caixa_nao_deixa_relr_o_mesmo_recado(self):
        bruto = recado(TIPO_RESPOSTA, de=NUMERO, texto="quero sim", referencia="m-1")
        motorista = self.motorista(imap_factory=lambda *a: ServidorIMAP([bruto]))
        self.assertEqual(len(motorista.poll_inbound()), 1)
        self.assertEqual(motorista.poll_inbound(), [], "a segunda leitura nao pode repetir a resposta")
        # e o que foi lido fica gravado no arquivo de estado
        relido = BridgeState(Path(self.arquivo_de_estado))
        self.assertEqual(relido.uid_imap, 1)
        self.assertEqual(len(relido.lidos), 1, "o recado lido fica anotado no estado")

    def test_recado_sem_carimbo_nao_se_repete_na_pop3(self):
        bruto = recado(TIPO_RESPOSTA, de=NUMERO, texto="quero sim")
        servidor = ServidorPOP3([bruto])
        settings = self.ajustes(imap_host="", pop3_host="pop3.test.invalid")
        motorista = self.motorista(settings, pop3_factory=lambda *a: servidor)
        self.assertEqual(len(motorista.poll_inbound()), 1)
        self.assertEqual(motorista.poll_inbound(), [], "sem cursor, o carimbo do recado tem de bastar")

    def test_a_leitura_por_pop3_usa_a_reserva(self):
        bruto = recado(TIPO_RESPOSTA, de=NUMERO, texto="quero sim", referencia="m-1")
        servidor = ServidorPOP3([bruto])
        settings = self.ajustes(imap_host="", pop3_host="pop3.test.invalid")
        motorista = self.motorista(settings, pop3_factory=lambda *a: servidor)
        replies = motorista.poll_inbound()
        self.assertEqual([reply.text for reply in replies], ["quero sim"])
        self.assertEqual(servidor.chamadas, ["user:loja@loja.test.invalid", "pass", "quit"])

    def test_o_comprovante_guarda_o_que_o_celular_viu(self):
        bruto = recado(TIPO_COMPROVANTE, para=NUMERO, estado=ESTADO_ENTREGUE, referencia="m-1")
        motorista = self.motorista(imap_factory=lambda *a: ServidorIMAP([bruto]))
        replies = motorista.poll_inbound()
        self.assertEqual(replies[0].text, ESTADO_ENTREGUE)
        self.assertEqual(replies[0].sender, NUMERO)
        self.assertEqual(replies[0].reference, "m-1")
        self.assertEqual(motorista.estado.recibo_de("m-1"), ESTADO_ENTREGUE)

    def test_comprovante_aprendido_desfaz_o_incerto_sem_reenviar(self):
        bruto = recado(TIPO_COMPROVANTE, para=NUMERO, estado=ESTADO_ENTREGUE, referencia="m-1")
        motorista = self.motorista(imap_factory=lambda *a: ServidorIMAP([bruto]))
        self.assertIsNone(motorista.resolve_uncertain(pedido()))
        motorista.poll_inbound()
        resultado = motorista.resolve_uncertain(pedido())
        self.assertEqual(resultado.outcome, "aceito")
        self.assertEqual(resultado.reference, "m-1")
        falho = recado(TIPO_COMPROVANTE, para=NUMERO, estado=ESTADO_FALHOU, referencia="m-2")
        outra = self.motorista(
            self.ajustes(state_path=str(self.base / "outra-caixa.json")),
            imap_factory=lambda *a: ServidorIMAP([falho]),
        )
        outra.poll_inbound()
        self.assertEqual(outra.resolve_uncertain(pedido(id="m-2")).outcome, "recusado")

    def test_o_estado_da_caixa_sobrevive_ao_reinico(self):
        bruto = recado(TIPO_COMPROVANTE, para=NUMERO, estado=ESTADO_ENTREGUE, referencia="m-9")
        self.motorista(imap_factory=lambda *a: ServidorIMAP([bruto])).poll_inbound()
        relido = BridgeState(Path(self.arquivo_de_estado))
        self.assertEqual(relido.recibo_de("m-9"), ESTADO_ENTREGUE)
        self.assertEqual(relido.uid_imap, 1)
        # motorista novo, arquivo na mao: a caixa nao e lida de novo
        servidor = ServidorIMAP([bruto])
        novo = self.motorista(imap_factory=lambda *a: servidor)
        self.assertEqual(novo.poll_inbound(), [])
        self.assertEqual(servidor.busca, "2:*")
        self.assertEqual(novo.resolve_uncertain(pedido(id="m-9")).outcome, "aceito")

    def test_a_resposta_forjada_nao_entra_na_fila(self):
        bruto = recado(TIPO_RESPOSTA, chave=CHAVE_ALHEIA, de="11911112222", texto="sim")
        motorista = self.motorista(imap_factory=lambda *a: ServidorIMAP([bruto]))
        self.assertEqual(motorista.poll_inbound(), [])
        self.assertEqual(motorista.recados_da_ponte, 1, "a marca estava no assunto")
        self.assertEqual(motorista.corpos_sem_abertura, 1, "e o corpo nao abriu")
        self.assertEqual(Path(self.arquivo_de_estado).exists(), True)

    def test_a_correspondencia_de_fora_da_ponte_e_ignorada(self):
        bruto = montar_mail("Nota fiscal da semana", "segue em anexo")
        motorista = self.motorista(imap_factory=lambda *a: ServidorIMAP([bruto]))
        self.assertEqual(motorista.poll_inbound(), [])
        self.assertEqual(motorista.recados_da_ponte, 0)

    def test_o_pedido_que_nos_mesmos_escrevemos_nao_vira_resposta(self):
        servidor = ServidorSMTP()
        self.motorista(smtp_factory=lambda *a: servidor).submit(pedido())
        bruto = bytes(servidor.enviados[0])
        leitor = self.motorista(imap_factory=lambda *a: ServidorIMAP([bruto]))
        self.assertEqual(leitor.poll_inbound(), [])
        self.assertEqual(leitor.recados_da_ponte, 1)

    def test_resposta_sem_prova_bastante_fica_na_caixa(self):
        casos = [
            recado(TIPO_RESPOSTA, de="", texto="sem remetente"),
            recado(TIPO_RESPOSTA, de="11", texto="numero curto demais"),
            recado(TIPO_RESPOSTA, de=NUMERO, texto="   "),
            recado(TIPO_COMPROVANTE, para=NUMERO, estado="esquisito"),
            recado(TIPO_COMPROVANTE, para="", estado=ESTADO_ENTREGUE),
        ]
        for bruto in casos:
            motorista = self.motorista(imap_factory=lambda *a: ServidorIMAP([bruto]))
            self.assertEqual(motorista.poll_inbound(), [], bruto[:48])
            self.assertEqual(motorista.estado.recibos, {})

    def test_resposta_longa_demais_entra_truncada_em_vez_de_jogada_fora(self):
        bruto = recado(TIPO_RESPOSTA, de=NUMERO, texto="y" * (MAX_TEXTO + 200), referencia="m-1")
        motorista = self.motorista(imap_factory=lambda *a: ServidorIMAP([bruto]))
        replies = motorista.poll_inbound()
        self.assertEqual(len(replies[0].text), MAX_TEXTO)

    def test_a_caixa_que_nao_responde_a_busca_nao_derruba_a_ronda(self):
        caixa = ServidorIMAP([], resposta_busca="NO")
        motorista = self.motorista(imap_factory=lambda *a: caixa)
        self.assertEqual(motorista.poll_inbound(), [])
        self.assertIn("busca", motorista.ultimo_erro)
        saude = motorista.health()
        self.assertTrue(saude.available, "meio ligado com leitura ruim ainda e ligado")
        self.assertIn("caixa postal", saude.reason)

    def test_a_caixa_que_explode_nao_derruba_a_ronda(self):
        motorista = self.motorista(imap_factory=_explodir)
        self.assertEqual(motorista.poll_inbound(), [])
        self.assertIn("IMAP", motorista.ultimo_erro)

    def test_a_leitura_sem_servidor_de_leitura_nao_sai(self):
        motorista = self.motorista(self.ajustes(imap_host="", pop3_host=""))
        self.assertEqual(motorista.poll_inbound(), [])

    def test_o_que_a_ponte_diz_para_o_painel_nao_tem_segredo(self):
        motorista = self.motorista(imap_factory=lambda *a: ServidorIMAP([]))
        motorista.poll_inbound()
        descricao = motorista.describe()
        self.assertEqual(descricao["nome"], "smtp_email")
        self.assertEqual(descricao["leitura"], "imap")
        self.assertEqual(descricao["ligada"], True)
        self.assertNotIn(SENHA, json.dumps(descricao))
        self.assertNotIn(CHAVE, json.dumps(descricao))
        self.assertNotIn(motorista.settings.password_sealed, json.dumps(descricao))


# ------------------------------------------------------------- correlacao


class CorrelacaoTeste(PonteDeEmail):
    def test_a_referencia_cifrada_escolhe_o_dono(self):
        motorista = self.motorista()
        dois = [breve("m-1"), breve("m-2")]
        reply = InboundReply("celular-loja", NUMERO, "quero sim", 2000.0, "m-2")
        self.assertEqual(motorista.correlate(reply, dois).id, "m-2")

    def test_referencia_fora_dos_candidatos_nao_escolhe_nada(self):
        motorista = self.motorista()
        reply = InboundReply("celular-loja", NUMERO, "quero sim", 2000.0, "m-99")
        self.assertIsNone(motorista.correlate(reply, [breve("m-1"), breve("m-2")]))

    def test_sem_referencia_nao_ha_prova(self):
        motorista = self.motorista()
        self.assertIsNone(motorista.correlate(InboundReply("cel", NUMERO, "sim", 1.0, ""), [breve("m-1")]))
        self.assertIsNone(motorista.correlate(InboundReply("cel", NUMERO, "sim", 1.0, "m-1"), []))

    def test_a_resposta_lida_prova_o_dono_diante_de_dois_candidatos(self):
        bruto = recado(TIPO_RESPOSTA, de=NUMERO, texto="quero sim", referencia="m-2")
        motorista = self.motorista(imap_factory=lambda *a: ServidorIMAP([bruto]))
        replies = motorista.poll_inbound()
        escolhidos = [motorista.correlate(reply, [breve("m-1"), breve("m-2")]) for reply in replies]
        self.assertEqual([escolhido.id for escolhido in escolhidos if escolhido], ["m-2"])


if __name__ == "__main__":
    unittest.main()
