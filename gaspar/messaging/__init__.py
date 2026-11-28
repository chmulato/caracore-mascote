"""Camada de mensageria do Gaspar 2.0 (Fase Alpha).

Aqui nasce o barramento local que o PDV e o Hub vao compartilhar. Os produtos
clientes nao importam codigo deste pacote: eles escrevem na API local do
Gaspar, que e a unica dona da fila.

A Fase Alpha entrega quatro pecas:

- contrato local autenticado em ``/v2``;
- fila SQLite isolada por origem (``PDV`` ou ``HUB``);
- credenciais separadas por origem;
- interface ``SmsTransportDriver`` para os motoristas de envio.

Os motoristas reais (celular na rede local, ponte por e-mail e modem USB)
chegam nas fases seguintes. Nada aqui envia SMS de verdade.
"""

from __future__ import annotations

PHASE = "alpha"
