"""Fonte de dados provisória: gera um lote sintético (mesma distribuição do
training/generate_sample_data.py) para o pipeline rodar de ponta a ponta."""

import io
import random


def gerar_lote(n: int = 200) -> bytes:
    bairros = ["Centro", "Jardins", "Vila Nova", "Boa Vista", "Industrial", "Beira Rio"]
    base = {"Centro": 6500, "Jardins": 9500, "Vila Nova": 5200,
            "Boa Vista": 4300, "Industrial": 3200, "Beira Rio": 7800}
    tipos = ["apartamento", "casa", "kitnet", "cobertura"]

    buf = io.StringIO()
    buf.write("bairro,tipo,area_m2,quartos,banheiros,vagas,idade_anos,preco\n")
    for _ in range(n):
        b, t = random.choice(bairros), random.choice(tipos)
        area = round(random.uniform(25, 250))
        quartos = max(1, min(5, round(area / 35)))
        preco = round(base[b] * area * random.uniform(0.85, 1.15), -3)
        buf.write(f"{b},{t},{area},{quartos},{max(1, quartos - 1)},"
                  f"{random.randint(0, 3)},{random.randint(0, 40)},{preco}\n")
    return buf.getvalue().encode()
