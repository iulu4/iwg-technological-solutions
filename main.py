import os
import re
import uuid
import sqlite3
import secrets
from pathlib import Path
from functools import wraps
from urllib.parse import quote

from flask import (
    Flask, render_template_string, request, redirect,
    url_for, session, flash, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename


# =========================================================
# CONFIGURACOES IWG
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
UPLOAD_DIR = ASSETS_DIR / "produtos"
BANCO = BASE_DIR / "iwg_catalogo.db"

ASSETS_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(
    __name__,
    static_folder=str(ASSETS_DIR),
    static_url_path="/arquivos"
)

app.secret_key = os.environ.get(
    "IWG_SECRET_KEY",
    "iwg-chave-temporaria-trocar-antes-de-publicar"
)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

AZUL_FUNDO = "#020526"
COR_OURO = "#F7C04A"
COR_CARD = "#0A0E45"
COR_BORDA = "#3A4F7C"

WHATSAPP = "5527999243025"
INSTAGRAM = "https://instagram.com/iulumozart"
LINKEDIN = "https://linkedin.com/in/iuluwayner"
YOUTUBE = "https://www.youtube.com/channel/UC8Z1DSRn3j5Rj4zMuy5sXIQ"

EXTENSOES = {"jpg", "jpeg", "png", "webp"}

IMAGENS_PRODUTOS = {
    1: "https://images.unsplash.com/photo-1515879218367-8466d910aaa4?w=900",
    2: "https://images.unsplash.com/photo-1518770660439-4636190af475?w=900",
    3: "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=900",
    4: "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=900",
    5: "https://images.unsplash.com/photo-1550009158-9ebf69173e03?w=900",
    6: "https://images.unsplash.com/photo-1606220945770-b5b6c2c55bf1?w=900"
}

IMAGEM_BANNER = (
    "https://images.unsplash.com/photo-1518770660439-4636190af475"
    "?auto=format&fit=crop&w=2000&q=85"
)


# =========================================================
# BANCO DE DADOS
# =========================================================

def conectar():
    conn = sqlite3.connect(BANCO)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def migrar_colunas(conn, tabela, colunas):
    existentes = {
        row["name"]
        for row in conn.execute(
            f"PRAGMA table_info({tabela})"
        ).fetchall()
    }

    for nome, tipo in colunas.items():
        if nome not in existentes:
            conn.execute(
                f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}"
            )


def iniciar_banco():
    with conectar() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                categoria TEXT DEFAULT 'Produtos',
                descricao TEXT DEFAULT '',
                preco REAL DEFAULT 0,
                imagem TEXT DEFAULT '',
                ativo INTEGER DEFAULT 1,
                estoque INTEGER DEFAULT NULL
            )
        """)

        migrar_colunas(conn, "produtos", {
            "estoque": "INTEGER DEFAULT NULL",
            "ativo": "INTEGER DEFAULT 1",
            "imagem": "TEXT DEFAULT ''"
        })

        conn.execute("""
            CREATE TABLE IF NOT EXISTS administradores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente TEXT NOT NULL,
                observacoes TEXT DEFAULT '',
                total REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'Recebido',
                data_criacao TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        migrar_colunas(conn, "pedidos", {
            "telefone": "TEXT DEFAULT ''",
            "cep": "TEXT DEFAULT ''",
            "rua": "TEXT DEFAULT ''",
            "numero": "TEXT DEFAULT ''",
            "complemento": "TEXT DEFAULT ''",
            "bairro": "TEXT DEFAULT ''",
            "cidade": "TEXT DEFAULT ''",
            "estado": "TEXT DEFAULT ''",
            "codigo_rastreamento": "TEXT DEFAULT ''"
        })

        conn.execute("""
            CREATE TABLE IF NOT EXISTS pedido_itens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id INTEGER NOT NULL,
                produto_id INTEGER,
                nome_produto TEXT NOT NULL,
                quantidade INTEGER NOT NULL,
                preco_unitario REAL NOT NULL,
                subtotal REAL NOT NULL,
                FOREIGN KEY (pedido_id)
                    REFERENCES pedidos(id) ON DELETE CASCADE
            )
        """)

        admin = conn.execute(
            "SELECT id FROM administradores WHERE usuario = ?",
            ("iulu",)
        ).fetchone()

        if not admin:
            conn.execute("""
                INSERT INTO administradores (usuario, senha)
                VALUES (?, ?)
            """, ("iulu", generate_password_hash("iulu")))

        total = conn.execute(
            "SELECT COUNT(*) AS total FROM produtos"
        ).fetchone()["total"]

        if total == 0:
            iniciais = [
                ("Automação Python sob Medida", "Softwares",
                 "Automação de tarefas e processos sob medida.", 1500),
                ("Licença Acesso IWG Core", "Softwares",
                 "Soluções digitais e acesso a ferramentas IWG.", 850),
                ("Consultoria em Arquitetura", "Serviços",
                 "Consultoria em arquitetura de sistemas e software.", 2500),
                ("Kit E-books Técnicos", "Produtos",
                 "Materiais digitais para aprendizado e tecnologia.", 120),
                ("Adaptador Lightning OTG", "Eletrônicos",
                 "Acessório eletrônico. Consulte disponibilidade.", 45),
                ("Fones Apple AirPods", "Eletrônicos",
                 "Produto ilustrativo. Consulte disponibilidade.", 199)
            ]

            for produto in iniciais:
                conn.execute("""
                    INSERT INTO produtos
                    (nome, categoria, descricao, preco)
                    VALUES (?, ?, ?, ?)
                """, produto)


iniciar_banco()


# =========================================================
# FUNCOES AUXILIARES
# =========================================================

def dinheiro(valor):
    return (
        f"R$ {float(valor):,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def imagem_produto(produto):
    if produto["imagem"]:
        return url_for(
            "static",
            filename="produtos/" + produto["imagem"]
        )
    return IMAGENS_PRODUTOS.get(
        produto["id"], IMAGEM_BANNER
    )


def salvar_imagem(arquivo):
    if not arquivo or not arquivo.filename:
        return ""

    nome_original = secure_filename(arquivo.filename)

    if "." not in nome_original:
        return ""

    extensao = nome_original.rsplit(".", 1)[1].lower()

    if extensao not in EXTENSOES:
        return ""

    nome = f"{uuid.uuid4().hex}.{extensao}"
    arquivo.save(UPLOAD_DIR / nome)
    return nome


def excluir_imagem(nome):
    if not nome:
        return

    caminho = UPLOAD_DIR / nome

    if caminho.is_file() and caminho.parent == UPLOAD_DIR:
        caminho.unlink()


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(32)
    return session["_csrf"]


@app.context_processor
def disponibilizar_csrf():
    return {"csrf_token": csrf_token}


def validar_csrf():
    enviado = request.form.get("_csrf", "")
    salvo = session.get("_csrf", "")

    if not enviado or not salvo or not secrets.compare_digest(
        enviado, salvo
    ):
        abort(400, description="Token de segurança inválido.")


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return func(*args, **kwargs)
    return wrapper


def quantidade_carrinho():
    return sum(
        int(q)
        for q in session.get("carrinho", {}).values()
    )


def endereco_pedido(pedido):
    return (
        f"{pedido['rua']}, {pedido['numero']} "
        f"{pedido['complemento']} - {pedido['bairro']}, "
        f"{pedido['cidade']}/{pedido['estado']} - CEP {pedido['cep']}"
    )


# =========================================================
# VISUAL DO SITE
# =========================================================

BASE_HTML = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#020526">
<meta name="description" content="IWG Technological Solutions. Tecnologia, eletrônicos, importações e desenvolvimento de software.">
<title>{{ titulo }} | IWG Technological Solutions</title>
<style>
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
    margin: 0;
    background: {{ fundo }};
    color: white;
    font-family: Arial, Helvetica, sans-serif;
}
a { color: inherit; text-decoration: none; }
header {
    text-align: center;
    padding: 35px 20px;
    background-color: {{ card }};
    border-bottom: 1px solid {{ borda }};
}
.avatar {
    width: 140px;
    height: 140px;
    border-radius: 50%;
    border: 3px solid {{ ouro }};
    margin: 0 auto 15px;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: {{ fundo }};
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(247,192,74,.25);
}
.avatar img { width: 100%; height: 100%; object-fit: cover; }
h1 {
    color: {{ ouro }};
    font-size: 20px;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: .5px;
}
.sub-titulo {
    color: #9CA3AF;
    font-size: 12px;
    font-style: italic;
    margin-bottom: 6px;
}
.sub-marca { color: #9CA3AF; font-size: 11px; }
nav {
    display: flex;
    justify-content: center;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    padding: 16px;
    background: #080C38;
    border-bottom: 1px solid {{ borda }};
    position: sticky;
    top: 0;
    z-index: 100;
}
nav a {
    color: {{ ouro }};
    font-size: 13px;
    padding: 9px 12px;
}
nav a:hover {
    background: {{ ouro }};
    color: #020526;
    border-radius: 6px;
}
.container { width: 92%; max-width: 1200px; margin: 30px auto; }
.banner {
    min-height: 430px;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
    padding: 60px 25px;
    border: 1px solid {{ borda }};
    border-radius: 18px;
    margin-bottom: 55px;
    background:
        linear-gradient(90deg, rgba(2,5,38,.96), rgba(2,5,38,.75)),
        url("{{ imagem_banner }}");
    background-size: cover;
    background-position: center;
}
.banner-conteudo { max-width: 850px; }
.banner-etiqueta {
    color: {{ ouro }};
    font-size: 12px;
    font-weight: bold;
    letter-spacing: 3px;
}
.banner h2 {
    color: {{ ouro }};
    font-size: clamp(30px, 5vw, 52px);
    line-height: 1.15;
    margin: 20px 0;
}
.banner p {
    color: #E5E7EB;
    line-height: 1.8;
    font-size: 17px;
    max-width: 700px;
    margin: 0 auto 25px;
}
.botao {
    display: inline-block;
    background: {{ ouro }};
    color: #020526;
    font-weight: bold;
    padding: 13px 21px;
    border: 0;
    border-radius: 7px;
    cursor: pointer;
    margin: 5px;
    font-size: 13px;
}
.botao-secundario {
    background: transparent;
    color: {{ ouro }};
    border: 1px solid {{ ouro }};
}
.secao { color: {{ ouro }}; font-size: 25px; margin: 45px 0 20px; }
.subsecao { color: #AEB6D2; line-height: 1.7; margin-bottom: 25px; }
.grade {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: 22px;
}
.produto {
    background: {{ card }};
    border: 1px solid {{ borda }};
    border-radius: 13px;
    overflow: hidden;
}
.produto img {
    width: 100%;
    height: 210px;
    object-fit: cover;
    background: #101641;
}
.produto-conteudo { padding: 17px; }
.categoria {
    color: {{ ouro }};
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.produto h3 { color: {{ ouro }}; font-size: 17px; line-height: 1.4; }
.produto p { color: #C4C8D5; line-height: 1.6; font-size: 13px; }
.preco { font-size: 21px; color: {{ ouro }}; font-weight: bold; margin: 15px 0; }
.servico {
    background: linear-gradient(145deg, #0A0E45, #111A55);
    border: 1px solid {{ borda }};
    border-radius: 13px;
    padding: 25px;
}
.servico h3 { color: {{ ouro }}; font-size: 18px; }
.servico p { color: #C4C8D5; line-height: 1.7; font-size: 14px; }
.sobre {
    background: linear-gradient(135deg, #0A0E45, #080C38);
    border: 1px solid {{ borda }};
    border-radius: 15px;
    padding: 30px;
    margin-top: 50px;
    line-height: 1.8;
    color: #D1D5DB;
}
.sobre h2 { color: {{ ouro }}; }
.filtros { display: flex; flex-wrap: wrap; gap: 9px; margin-bottom: 25px; }
.filtros a {
    padding: 9px 15px;
    border: 1px solid {{ borda }};
    border-radius: 20px;
    color: white;
    font-size: 13px;
}
.filtros a:hover, .filtros a.ativo { background: {{ ouro }}; color: #020526; }
.formulario {
    background: {{ card }};
    border: 1px solid {{ borda }};
    padding: 24px;
    border-radius: 12px;
    max-width: 800px;
    margin: 25px auto;
}
input, textarea, select {
    display: block;
    width: 100%;
    padding: 12px;
    margin: 9px 0 16px;
    background: #05092F;
    color: white;
    border: 1px solid {{ borda }};
    border-radius: 6px;
}
label { color: {{ ouro }}; }
table {
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
    background: {{ card }};
}
td, th { border-bottom: 1px solid {{ borda }}; padding: 12px; text-align: left; }
th { color: {{ ouro }}; }
.aviso {
    padding: 15px;
    background: #111A55;
    border-radius: 8px;
    color: #D1D5DB;
    margin: 25px 0;
    font-size: 13px;
    line-height: 1.6;
}
.flash {
    background: #182653;
    border: 1px solid {{ ouro }};
    padding: 12px;
    border-radius: 8px;
    margin: 12px 0;
    color: white;
}
.cartao-indicador {
    background: {{ card }};
    border: 1px solid {{ borda }};
    border-radius: 12px;
    padding: 22px;
}
.cartao-indicador span { color: #AEB6D2; font-size: 13px; }
.cartao-indicador strong {
    display: block;
    color: {{ ouro }};
    font-size: 30px;
    margin-top: 10px;
}
.badge-status {
    display: inline-block;
    padding: 5px 9px;
    border: 1px solid {{ ouro }};
    border-radius: 15px;
    color: {{ ouro }};
    font-size: 11px;
}
.acoes { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.acoes form { margin: 0; }
footer {
    text-align: center;
    padding: 40px 15px;
    color: #9CA3AF;
    border-top: 1px solid {{ borda }};
    margin-top: 60px;
    font-size: 13px;
    line-height: 1.9;
    background: #05082C;
}
footer strong { color: {{ ouro }}; font-size: 16px; }
footer a { color: {{ ouro }}; margin: 0 5px; }
@media(max-width: 700px) {
    header { padding: 25px 10px; }
    .container { width: 94%; }
    .banner { min-height: 390px; padding: 35px 15px; }
    .banner h2 { font-size: 29px; }
    .banner p { font-size: 14px; }
    .secao { font-size: 22px; }
    nav { gap: 3px; padding: 10px 4px; }
    nav a { font-size: 11px; padding: 8px 7px; }
    td, th { padding: 7px; font-size: 11px; }
    .tabela-responsiva { overflow-x: auto; }
}
</style>
</head>
<body>
<header>
    <div class="avatar">
        <img src="/arquivos/logo.jpg" alt="Logo IWG"
             onerror="this.style.display='none'">
    </div>
    <h1>IWG TECHNOLOGICAL SOLUTIONS</h1>
    <div class="sub-titulo">
        (Analista de sistemas e engenheiro de software)
    </div>
    <div class="sub-marca">
        IWG Technological Solutions • Catálogo Oficial
    </div>
</header>
<nav>
    <a href="{{ url_for('inicio') }}">Início</a>
    <a href="{{ url_for('inicio') }}#catalogo">Catálogo</a>
    <a href="{{ url_for('inicio') }}#servicos">Serviços</a>
    <a href="{{ url_for('inicio') }}#sobre">Sobre</a>
    <a href="{{ url_for('carrinho') }}">Carrinho ({{ quantidade_carrinho }})</a>
    <a href="https://wa.me/{{ whatsapp }}" target="_blank">WhatsApp</a>
</nav>
<div class="container">
{% with mensagens = get_flashed_messages() %}
    {% for mensagem in mensagens %}
        <div class="flash">{{ mensagem }}</div>
    {% endfor %}
{% endwith %}
{{ conteudo|safe }}
</div>
<footer>
    <p><strong>IWG TECHNOLOGICAL SOLUTIONS</strong></p>
    <p>Tecnologia • Eletrônicos • Importações • Desenvolvimento de Software</p>
    <p>
        <a href="{{ instagram }}" target="_blank">Instagram</a> |
        <a href="{{ linkedin }}" target="_blank">LinkedIn</a> |
        <a href="{{ youtube }}" target="_blank">YouTube</a> |
        <a href="https://wa.me/{{ whatsapp }}" target="_blank">WhatsApp</a>
    </p>
    <p>© IWG Technological Solutions</p>
    <a href="{{ url_for('admin_login') }}">Área administrativa</a>
</footer>
</body>
</html>
"""


def render_site(conteudo, titulo="Início"):
    return render_template_string(
        BASE_HTML,
        conteudo=conteudo,
        titulo=titulo,
        fundo=AZUL_FUNDO,
        ouro=COR_OURO,
        card=COR_CARD,
        borda=COR_BORDA,
        whatsapp=WHATSAPP,
        instagram=INSTAGRAM,
        linkedin=LINKEDIN,
        youtube=YOUTUBE,
        imagem_banner=IMAGEM_BANNER,
        quantidade_carrinho=quantidade_carrinho()
    )


# =========================================================
# PAGINA INICIAL E CATALOGO
# =========================================================

@app.route("/")
def inicio():
    categoria = request.args.get("categoria", "")

    with conectar() as conn:
        categorias = conn.execute("""
            SELECT DISTINCT categoria FROM produtos
            WHERE ativo = 1 ORDER BY categoria
        """).fetchall()

        if categoria:
            produtos = conn.execute("""
                SELECT * FROM produtos
                WHERE ativo = 1 AND categoria = ?
                ORDER BY id DESC
            """, (categoria,)).fetchall()
        else:
            produtos = conn.execute("""
                SELECT * FROM produtos
                WHERE ativo = 1 ORDER BY id DESC
            """).fetchall()

    html = """
    <section class="banner">
        <div class="banner-conteudo">
            <div class="banner-etiqueta">Tecnologia • Inovação • Soluções</div>
            <h2>Tecnologia que transforma ideias em soluções.</h2>
            <p>
                Bem-vindo à IWG Technological Solutions.
                Desenvolvimento de software, automações,
                eletrônicos, importações e soluções digitais
                para conectar você ao futuro.
            </p>
            <a class="botao" href="#catalogo">Conheça nosso catálogo</a>
            <a class="botao botao-secundario"
               href="https://wa.me/{{ whatsapp }}">Fale conosco</a>
        </div>
    </section>

    <section id="servicos">
        <h2 class="secao">Nossas soluções</h2>
        <p class="subsecao">Tecnologia aplicada às necessidades de pessoas e empresas.</p>
        <div class="grade">
            <div class="servico">
                <h3>💻 Desenvolvimento de Software</h3>
                <p>Criação de sistemas, aplicativos, plataformas e soluções personalizadas.</p>
            </div>
            <div class="servico">
                <h3>⚙️ Automação e Inteligência</h3>
                <p>Automação de tarefas, integração de processos e ferramentas digitais.</p>
            </div>
            <div class="servico">
                <h3>🌐 Consultoria em Tecnologia</h3>
                <p>Arquitetura de sistemas, planejamento e orientação tecnológica.</p>
            </div>
            <div class="servico">
                <h3>📱 Eletrônicos e Importações</h3>
                <p>Produtos, acessórios e soluções tecnológicas selecionadas.</p>
            </div>
        </div>
    </section>

    <section id="catalogo">
        <h2 class="secao">Catálogo IWG</h2>
        <p class="subsecao">Conheça nossos produtos, serviços e soluções digitais.</p>
        <div class="filtros">
            <a class="{{ 'ativo' if not categoria else '' }}"
               href="{{ url_for('inicio') }}">Todos</a>
            {% for cat in categorias %}
                <a class="{{ 'ativo' if categoria == cat['categoria'] else '' }}"
                   href="{{ url_for('inicio', categoria=cat['categoria']) }}">
                    {{ cat['categoria'] }}
                </a>
            {% endfor %}
        </div>
        <div class="grade">
        {% for p in produtos %}
            <article class="produto">
                <a href="{{ url_for('produto_detalhe', pid=p['id']) }}">
                    <img src="{{ imagem_produto(p) }}" alt="{{ p['nome'] }}">
                </a>
                <div class="produto-conteudo">
                    <span class="categoria">{{ p['categoria'] }}</span>
                    <h3>{{ p['nome'] }}</h3>
                    <p>{{ p['descricao'] }}</p>
                    <div class="preco">{{ dinheiro(p['preco']) }}</div>
                    {% if p['estoque'] is not none %}
                        <p>Estoque: {{ p['estoque'] }}</p>
                    {% endif %}
                    <a class="botao" href="{{ url_for('produto_detalhe', pid=p['id']) }}">
                        Ver produto
                    </a>
                </div>
            </article>
        {% else %}
            <p>Nenhum produto cadastrado nesta categoria.</p>
        {% endfor %}
        </div>
    </section>

    <section class="sobre" id="sobre">
        <h2>Sobre a IWG Technological Solutions</h2>
        <p>
            A IWG Technological Solutions atua com tecnologia,
            desenvolvimento de software, automação, consultoria,
            eletrônicos e soluções digitais.
        </p>
        <p>
            Nosso compromisso é oferecer inovação, qualidade
            e atendimento próximo aos nossos clientes.
        </p>
    </section>
    """

    return render_site(
        render_template_string(
            html,
            produtos=produtos,
            categorias=categorias,
            categoria=categoria,
            dinheiro=dinheiro,
            imagem_produto=imagem_produto,
            whatsapp=WHATSAPP
        )
    )


@app.route("/produto/<int:pid>")
def produto_detalhe(pid):
    with conectar() as conn:
        produto = conn.execute(
            "SELECT * FROM produtos WHERE id=? AND ativo=1",
            (pid,)
        ).fetchone()

    if not produto:
        abort(404)

    html = """
    <h2 class="secao">{{ p['nome'] }}</h2>
    <div class="grade">
        <div class="produto">
            <img src="{{ imagem_produto(p) }}" alt="{{ p['nome'] }}">
        </div>
        <div class="produto-conteudo">
            <span class="categoria">{{ p['categoria'] }}</span>
            <p>{{ p['descricao'] }}</p>
            <div class="preco">{{ dinheiro(p['preco']) }}</div>
            {% if p['estoque'] is not none %}
                <p>Disponível: {{ p['estoque'] }}</p>
            {% endif %}
            <form method="post" action="{{ url_for('adicionar_carrinho', pid=p['id']) }}">
                <input type="hidden" name="_csrf" value="{{ csrf_token() }}">
                <label>Quantidade</label>
                <input type="number" name="quantidade" value="1" min="1" required>
                <button class="botao">Adicionar ao carrinho</button>
            </form>
            <a class="botao botao-secundario" href="{{ url_for('inicio') }}">
                Voltar ao catálogo
            </a>
        </div>
    </div>
    """

    return render_site(
        render_template_string(
            html,
            p=produto,
            imagem_produto=imagem_produto,
            dinheiro=dinheiro
        ),
        produto["nome"]
    )


# =========================================================
# CARRINHO
# =========================================================

@app.route("/adicionar-carrinho/<int:pid>", methods=["POST"])
def adicionar_carrinho(pid):
    validar_csrf()

    try:
        quantidade = int(request.form.get("quantidade", 1))
    except ValueError:
        quantidade = 1

    if quantidade < 1 or quantidade > 99:
        flash("Quantidade inválida.")
        return redirect(url_for("inicio"))

    with conectar() as conn:
        produto = conn.execute(
            "SELECT * FROM produtos WHERE id=? AND ativo=1",
            (pid,)
        ).fetchone()

    if not produto:
        flash("Produto não encontrado.")
        return redirect(url_for("inicio"))

    carrinho = session.get("carrinho", {})
    atual = int(carrinho.get(str(pid), 0))
    nova = atual + quantidade

    if produto["estoque"] is not None and nova > produto["estoque"]:
        flash("Quantidade maior que o estoque disponível.")
        return redirect(url_for("produto_detalhe", pid=pid))

    carrinho[str(pid)] = nova
    session["carrinho"] = carrinho
    flash("Produto adicionado ao carrinho!")
    return redirect(url_for("carrinho"))


@app.route("/carrinho")
def carrinho():
    carrinho_atual = session.get("carrinho", {})
    itens = []
    total = 0

    with conectar() as conn:
        for pid, quantidade in carrinho_atual.items():
            produto = conn.execute(
                "SELECT * FROM produtos WHERE id=? AND ativo=1",
                (pid,)
            ).fetchone()

            if produto:
                subtotal = produto["preco"] * int(quantidade)
                itens.append({
                    "produto": produto,
                    "quantidade": int(quantidade),
                    "subtotal": subtotal
                })
                total += subtotal

    html = """
    <h2 class="secao">Meu carrinho</h2>
    {% if itens %}
    <div class="tabela-responsiva">
    <table>
        <tr><th>Produto</th><th>Quantidade</th><th>Subtotal</th><th>Ação</th></tr>
        {% for item in itens %}
        <tr>
            <td>{{ item.produto['nome'] }}</td>
            <td>{{ item.quantidade }}</td>
            <td>{{ dinheiro(item.subtotal) }}</td>
            <td>
                <form method="post" action="{{ url_for('remover_carrinho', pid=item.produto['id']) }}">
                    <input type="hidden" name="_csrf" value="{{ csrf_token() }}">
                    <button class="botao botao-secundario">Remover</button>
                </form>
            </td>
        </tr>
        {% endfor %}
    </table>
    </div>
    <h2 class="preco">Total: {{ dinheiro(total) }}</h2>
    <a class="botao" href="{{ url_for('checkout') }}">Continuar para identificação e entrega</a>
    {% else %}
    <p>Seu carrinho está vazio.</p>
    {% endif %}
    <a class="botao botao-secundario" href="{{ url_for('inicio') }}">Voltar ao catálogo</a>
    """

    return render_site(
        render_template_string(
            html, itens=itens, total=total, dinheiro=dinheiro
        ),
        "Carrinho"
    )


@app.route("/remover-carrinho/<int:pid>", methods=["POST"])
def remover_carrinho(pid):
    validar_csrf()
    carrinho_atual = session.get("carrinho", {})
    carrinho_atual.pop(str(pid), None)
    session["carrinho"] = carrinho_atual
    flash("Produto removido.")
    return redirect(url_for("carrinho"))


# =========================================================
# CHECKOUT
# =========================================================

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    carrinho_atual = session.get("carrinho", {})

    if not carrinho_atual:
        flash("Seu carrinho está vazio.")
        return redirect(url_for("carrinho"))

    itens = []
    total = 0

    with conectar() as conn:
        for pid, quantidade in carrinho_atual.items():
            produto = conn.execute(
                "SELECT * FROM produtos WHERE id=? AND ativo=1",
                (pid,)
            ).fetchone()

            if not produto:
                continue

            quantidade = int(quantidade)

            if produto["estoque"] is not None and quantidade > produto["estoque"]:
                flash(f"Estoque insuficiente para {produto['nome']}.")
                return redirect(url_for("carrinho"))

            subtotal = produto["preco"] * quantidade
            itens.append({
                "produto": produto,
                "quantidade": quantidade,
                "subtotal": subtotal
            })
            total += subtotal

    if not itens:
        flash("Não há produtos disponíveis no carrinho.")
        return redirect(url_for("carrinho"))

    if request.method == "POST":
        validar_csrf()

        nome = request.form.get("nome", "").strip()
        telefone = re.sub(
            r"\D", "", request.form.get("telefone", "")
        )
        cpf = re.sub(r"\D", "", request.form.get("cpf", ""))
        cep = re.sub(r"\D", "", request.form.get("cep", ""))
        rua = request.form.get("rua", "").strip()
        numero = request.form.get("numero", "").strip()
        complemento = request.form.get("complemento", "").strip()
        bairro = request.form.get("bairro", "").strip()
        cidade = request.form.get("cidade", "").strip()
        estado = request.form.get("estado", "").strip().upper()
        observacoes = request.form.get("observacoes", "").strip()

        if not nome or len(nome) < 3:
            flash("Informe seu nome completo.")
            return redirect(url_for("checkout"))

        if not 10 <= len(telefone) <= 13:
            flash("Informe um telefone ou WhatsApp válido.")
            return redirect(url_for("checkout"))

        if len(cpf) != 11 or cpf == cpf[0] * 11:
            flash("Informe um CPF com 11 números válido.")
            return redirect(url_for("checkout"))

        # Validação dos dígitos verificadores do CPF.
        numeros = [int(n) for n in cpf]
        soma = sum(numeros[i] * (10 - i) for i in range(9))
        digito1 = (soma * 10) % 11
        digito1 = 0 if digito1 == 10 else digito1

        soma = sum(numeros[i] * (11 - i) for i in range(10))
        digito2 = (soma * 10) % 11
        digito2 = 0 if digito2 == 10 else digito2

        if numeros[9] != digito1 or numeros[10] != digito2:
            flash("O CPF informado não passou na validação.")
            return redirect(url_for("checkout"))

        if (
            len(cep) != 8 or not rua or not numero
            or not bairro or not cidade or len(estado) != 2
        ):
            flash("Preencha corretamente todos os campos obrigatórios do endereço.")
            return redirect(url_for("checkout"))

        with conectar() as conn:
            cursor = conn.execute("""
                INSERT INTO pedidos (
                    cliente, observacoes, total, status,
                    telefone, cep, rua, numero, complemento,
                    bairro, cidade, estado
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                nome, observacoes, total,
                "Aguardando confirmação no WhatsApp",
                telefone, cep, rua, numero, complemento,
                bairro, cidade, estado
            ))

            pedido_id = cursor.lastrowid

            for item in itens:
                produto = item["produto"]
                quantidade = item["quantidade"]

                conn.execute("""
                    INSERT INTO pedido_itens (
                        pedido_id, produto_id, nome_produto,
                        quantidade, preco_unitario, subtotal
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    pedido_id,
                    produto["id"],
                    produto["nome"],
                    quantidade,
                    produto["preco"],
                    item["subtotal"]
                ))

                if produto["estoque"] is not None:
                    conn.execute("""
                        UPDATE produtos
                        SET estoque = estoque - ?
                        WHERE id = ?
                    """, (quantidade, produto["id"]))

        endereco = (
            f"{rua}, {numero}, {complemento}, {bairro}, "
            f"{cidade}/{estado}, CEP {cep}"
        )

        mensagem = [
            "*NOVO PEDIDO - IWG TECHNOLOGICAL SOLUTIONS*",
            "",
            f"*Pedido:* #{pedido_id}",
            f"*Cliente:* {nome}",
            f"*Telefone:* {telefone}",
            f"*CPF:* {cpf}",
            f"*Endereço:* {endereco}",
            "",
            "*PRODUTOS:*"
        ]

        for item in itens:
            mensagem.append(
                f"- {item['produto']['nome']} | "
                f"Qtd: {item['quantidade']} | "
                f"Unitário: {dinheiro(item['produto']['preco'])} | "
                f"Subtotal: {dinheiro(item['subtotal'])}"
            )

        mensagem.extend([
            "",
            f"*TOTAL: {dinheiro(total)}*",
            "",
            f"*Observações:* {observacoes or 'Nenhuma'}",
            "",
            "O frete e eventuais tributos poderão gerar custos adicionais, "
            "especialmente em envios interestaduais. Os valores serão "
            "confirmados antes da finalização da compra.",
            "",
            "Após a postagem para o endereço informado, a IWG fornecerá "
            "o código de rastreamento.",
            "",
            "Este pedido aguarda confirmação pelo WhatsApp."
        ])

        session["carrinho"] = {}
        flash("Pedido registrado. Continue no WhatsApp para enviar sua solicitação.")

        url = (
            f"https://wa.me/{WHATSAPP}?text="
            f"{quote(chr(10).join(mensagem), safe='')}"
        )
        return redirect(url)

    html = """
    <h2 class="secao">Finalizar solicitação</h2>
    <div class="aviso">
        Preencha seus dados para que possamos confirmar seu pedido pelo WhatsApp.
        O CPF será enviado na mensagem do WhatsApp e não será armazenado no banco de dados.
    </div>
    <form class="formulario" method="post">
        <input type="hidden" name="_csrf" value="{{ csrf_token() }}">

        <label>Nome completo *</label>
        <input name="nome" required minlength="3">

        <label>Telefone / WhatsApp *</label>
        <input name="telefone" required placeholder="DDD + número">

        <label>CPF *</label>
        <input name="cpf" required maxlength="14" placeholder="000.000.000-00">

        <label>CEP *</label>
        <input name="cep" required maxlength="9" placeholder="00000-000">

        <label>Rua *</label>
        <input name="rua" required>

        <label>Número *</label>
        <input name="numero" required>

        <label>Complemento</label>
        <input name="complemento">

        <label>Bairro *</label>
        <input name="bairro" required>

        <label>Cidade *</label>
        <input name="cidade" required>

        <label>Estado (UF) *</label>
        <input name="estado" required maxlength="2" placeholder="ES">

        <label>Observações</label>
        <textarea name="observacoes" rows="4"></textarea>

        <h3 class="preco">Total: {{ dinheiro(total) }}</h3>
        <button class="botao">Registrar pedido e continuar no WhatsApp</button>
    </form>
    """

    return render_site(
        render_template_string(
            html, total=total, dinheiro=dinheiro
        ),
        "Finalizar pedido"
    )


# =========================================================
# LOGIN ADMINISTRATIVO
# =========================================================

@app.route("/admin", methods=["GET", "POST"])
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin"):
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        validar_csrf()

        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")

        with conectar() as conn:
            admin = conn.execute(
                "SELECT * FROM administradores WHERE usuario=?",
                (usuario,)
            ).fetchone()

        if admin and check_password_hash(admin["senha"], senha):
            session.clear()
            session["admin"] = admin["id"]
            session["usuario"] = admin["usuario"]
            flash("Bem-vindo ao painel administrativo.")
            return redirect(url_for("admin_dashboard"))

        flash("Usuário ou senha incorretos.")

    html = """
    <h2 class="secao">Área administrativa IWG</h2>
    <form class="formulario" method="post">
        <input type="hidden" name="_csrf" value="{{ csrf_token() }}">
        <label>Usuário</label>
        <input name="usuario" required>
        <label>Senha</label>
        <input type="password" name="senha" required>
        <button class="botao">Entrar</button>
    </form>
    """

    return render_site(html, "Login administrativo")


# =========================================================
# PAINEL ADMINISTRATIVO
# =========================================================

@app.route("/admin/painel")
@admin_required
def admin_dashboard():
    with conectar() as conn:
        total_produtos = conn.execute(
            "SELECT COUNT(*) AS n FROM produtos"
        ).fetchone()["n"]

        total_pedidos = conn.execute(
            "SELECT COUNT(*) AS n FROM pedidos"
        ).fetchone()["n"]

        total_vendas = conn.execute(
            "SELECT COALESCE(SUM(total),0) AS n FROM pedidos "
            "WHERE status NOT IN ('Cancelado')"
        ).fetchone()["n"]

        pedidos = conn.execute("""
            SELECT * FROM pedidos ORDER BY id DESC LIMIT 20
        """).fetchall()

        produtos = conn.execute("""
            SELECT * FROM produtos ORDER BY id DESC
        """).fetchall()

    html = """
    <h2 class="secao">Painel administrativo</h2>
    <p>Bem-vindo, {{ session.get('usuario') }}.</p>

    <div class="grade">
        <div class="cartao-indicador">
            <span>Produtos cadastrados</span>
            <strong>{{ total_produtos }}</strong>
        </div>
        <div class="cartao-indicador">
            <span>Pedidos registrados</span>
            <strong>{{ total_pedidos }}</strong>
        </div>
        <div class="cartao-indicador">
            <span>Total dos pedidos não cancelados</span>
            <strong>{{ dinheiro(total_vendas) }}</strong>
        </div>
    </div>

    <h2 class="secao">Gerenciamento</h2>
    <a class="botao" href="{{ url_for('admin_novo') }}">Cadastrar produto</a>
    <a class="botao botao-secundario" href="{{ url_for('admin_pedidos') }}">Ver pedidos</a>
    <a class="botao botao-secundario" href="{{ url_for('admin_senha') }}">Alterar senha</a>
    <a class="botao botao-secundario" href="{{ url_for('admin_logout') }}">Sair</a>

    <h2 class="secao">Produtos</h2>
    <div class="tabela-responsiva">
    <table>
        <tr><th>Produto</th><th>Preço</th><th>Estoque</th><th>Ativo</th><th>Ações</th></tr>
        {% for p in produtos %}
        <tr>
            <td>{{ p['nome'] }}</td>
            <td>{{ dinheiro(p['preco']) }}</td>
            <td>{{ p['estoque'] if p['estoque'] is not none else 'Não controlado' }}</td>
            <td>{{ 'Sim' if p['ativo'] else 'Não' }}</td>
            <td>
                <a class="botao" href="{{ url_for('admin_editar', pid=p['id']) }}">Editar</a>
                <form method="post" action="{{ url_for('admin_excluir', pid=p['id']) }}">
                    <input type="hidden" name="_csrf" value="{{ csrf_token() }}">
                    <button class="botao botao-secundario"
                        onclick="return confirm('Excluir este produto?')">
                        Excluir
                    </button>
                </form>
            </td>
        </tr>
        {% endfor %}
    </table>
    </div>

    <h2 class="secao">Pedidos recentes</h2>
    <div class="tabela-responsiva">
    <table>
        <tr><th>Número</th><th>Cliente</th><th>Total</th><th>Status</th><th>Detalhes</th></tr>
        {% for p in pedidos %}
        <tr>
            <td>#{{ p['id'] }}</td>
            <td>{{ p['cliente'] }}</td>
            <td>{{ dinheiro(p['total']) }}</td>
            <td>{{ p['status'] }}</td>
            <td><a class="botao" href="{{ url_for('admin_pedido_detalhe', pid=p['id']) }}">Abrir</a></td>
        </tr>
        {% endfor %}
    </table>
    </div>
    """

    return render_site(
        render_template_string(
            html,
            total_produtos=total_produtos,
            total_pedidos=total_pedidos,
            total_vendas=total_vendas,
            pedidos=pedidos,
            produtos=produtos,
            dinheiro=dinheiro
        ),
        "Painel administrativo"
    )


# =========================================================
# CADASTRAR PRODUTO
# =========================================================

@app.route("/admin/produto/novo", methods=["GET", "POST"])
@admin_required
def admin_novo():
    if request.method == "POST":
        validar_csrf()

        nome = request.form.get("nome", "").strip()
        categoria = request.form.get("categoria", "Produtos").strip()
        descricao = request.form.get("descricao", "").strip()

        try:
            preco = float(request.form.get("preco", "0").replace(",", "."))
            estoque_texto = request.form.get("estoque", "").strip()
            estoque = int(estoque_texto) if estoque_texto else None
        except ValueError:
            flash("Preço ou estoque inválido.")
            return redirect(url_for("admin_novo"))

        if not nome or preco < 0 or (estoque is not None and estoque < 0):
            flash("Confira os dados do produto.")
            return redirect(url_for("admin_novo"))

        imagem = salvar_imagem(request.files.get("imagem"))

        with conectar() as conn:
            conn.execute("""
                INSERT INTO produtos
                (nome, categoria, descricao, preco, imagem, estoque)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                nome, categoria, descricao, preco, imagem, estoque
            ))

        flash("Produto cadastrado com sucesso!")
        return redirect(url_for("admin_dashboard"))

    return render_site(formulario_produto(), "Novo produto")


def formulario_produto(produto=None):
    produto = produto or {
        "nome": "",
        "categoria": "Produtos",
        "descricao": "",
        "preco": 0,
        "estoque": None
    }

    html = """
    <h2 class="secao">{{ titulo_form }}</h2>
    <form class="formulario" method="post" enctype="multipart/form-data">
        <input type="hidden" name="_csrf" value="{{ csrf_token() }}">

        <label>Nome do produto</label>
        <input name="nome" value="{{ p['nome'] }}" required>

        <label>Categoria</label>
        <input name="categoria" value="{{ p['categoria'] }}" required>

        <label>Descrição</label>
        <textarea name="descricao" rows="5">{{ p['descricao'] }}</textarea>

        <label>Preço</label>
        <input name="preco" type="number" step="0.01" min="0"
               value="{{ p['preco'] }}" required>

        <label>Estoque (deixe vazio para não controlar)</label>
        <input name="estoque" type="number" min="0"
               value="{{ p['estoque'] if p['estoque'] is not none else '' }}">

        <label>Imagem do produto</label>
        <input name="imagem" type="file" accept=".jpg,.jpeg,.png,.webp">

        <button class="botao">Salvar produto</button>
        <a class="botao botao-secundario" href="{{ url_for('admin_dashboard') }}">Voltar</a>
    </form>
    """

    return render_template_string(
        html,
        p=produto,
        titulo_form="Cadastrar produto" if produto is None else "Editar produto"
    )


# =========================================================
# EDITAR PRODUTO
# =========================================================

@app.route("/admin/produto/<int:pid>/editar", methods=["GET", "POST"])
@admin_required
def admin_editar(pid):
    with conectar() as conn:
        produto = conn.execute(
            "SELECT * FROM produtos WHERE id=?",
            (pid,)
        ).fetchone()

    if not produto:
        abort(404)

    if request.method == "POST":
        validar_csrf()

        nome = request.form.get("nome", "").strip()
        categoria = request.form.get("categoria", "Produtos").strip()
        descricao = request.form.get("descricao", "").strip()

        try:
            preco = float(request.form.get("preco", "0").replace(",", "."))
            estoque_texto = request.form.get("estoque", "").strip()
            estoque = int(estoque_texto) if estoque_texto else None
        except ValueError:
            flash("Preço ou estoque inválido.")
            return redirect(url_for("admin_editar", pid=pid))

        if not nome or preco < 0 or (estoque is not None and estoque < 0):
            flash("Confira os dados do produto.")
            return redirect(url_for("admin_editar", pid=pid))

        nova_imagem = salvar_imagem(request.files.get("imagem"))
        imagem = nova_imagem or produto["imagem"]

        with conectar() as conn:
            conn.execute("""
                UPDATE produtos
                SET nome=?, categoria=?, descricao=?, preco=?,
                    imagem=?, estoque=?
                WHERE id=?
            """, (
                nome, categoria, descricao, preco,
                imagem, estoque, pid
            ))

        if nova_imagem:
            excluir_imagem(produto["imagem"])

        flash("Produto atualizado!")
        return redirect(url_for("admin_dashboard"))

    html = formulario_produto(produto)
    return render_site(html, "Editar produto")


# =========================================================
# EXCLUIR PRODUTO
# =========================================================

@app.route("/admin/produto/<int:pid>/excluir", methods=["POST"])
@admin_required
def admin_excluir(pid):
    validar_csrf()

    with conectar() as conn:
        produto = conn.execute(
            "SELECT * FROM produtos WHERE id=?",
            (pid,)
        ).fetchone()

        if produto:
            conn.execute(
                "DELETE FROM produtos WHERE id=?",
                (pid,)
            )

    if produto:
        excluir_imagem(produto["imagem"])
        flash("Produto excluído.")
    else:
        flash("Produto não encontrado.")

    return redirect(url_for("admin_dashboard"))


# =========================================================
# PEDIDOS ADMINISTRATIVOS
# =========================================================

@app.route("/admin/pedidos")
@admin_required
def admin_pedidos():
    with conectar() as conn:
        pedidos = conn.execute("""
            SELECT * FROM pedidos ORDER BY id DESC
        """).fetchall()

    html = """
    <h2 class="secao">Pedidos recebidos</h2>
    <div class="tabela-responsiva">
    <table>
        <tr>
            <th>Pedido</th><th>Cliente</th><th>Telefone</th>
            <th>Total</th><th>Status</th><th>Detalhes</th>
        </tr>
        {% for p in pedidos %}
        <tr>
            <td>#{{ p['id'] }}</td>
            <td>{{ p['cliente'] }}</td>
            <td>{{ p['telefone'] }}</td>
            <td>{{ dinheiro(p['total']) }}</td>
            <td>{{ p['status'] }}</td>
            <td><a class="botao" href="{{ url_for('admin_pedido_detalhe', pid=p['id']) }}">Abrir</a></td>
        </tr>
        {% endfor %}
    </table>
    </div>
    <a class="botao botao-secundario" href="{{ url_for('admin_dashboard') }}">Voltar</a>
    """

    return render_site(
        render_template_string(
            html, pedidos=pedidos, dinheiro=dinheiro
        ),
        "Pedidos"
    )


@app.route("/admin/pedido/<int:pid>")
@admin_required
def admin_pedido_detalhe(pid):
    with conectar() as conn:
        pedido = conn.execute(
            "SELECT * FROM pedidos WHERE id=?",
            (pid,)
        ).fetchone()

        if not pedido:
            abort(404)

        itens = conn.execute("""
            SELECT * FROM pedido_itens
            WHERE pedido_id=? ORDER BY id
        """, (pid,)).fetchall()

    html = """
    <h2 class="secao">Pedido #{{ pedido['id'] }}</h2>

    <div class="aviso">
        <strong>Cliente:</strong> {{ pedido['cliente'] }}<br>
        <strong>Telefone:</strong> {{ pedido['telefone'] }}<br>
        <strong>Endereço:</strong> {{ endereco_pedido(pedido) }}<br>
        <strong>Data:</strong> {{ pedido['data_criacao'] }}<br>
        <strong>Status:</strong> {{ pedido['status'] }}<br>
        <strong>Observações:</strong> {{ pedido['observacoes'] or 'Nenhuma' }}
    </div>

    <h3 class="secao">Produtos do pedido</h3>
    <div class="tabela-responsiva">
    <table>
        <tr><th>Produto</th><th>Quantidade</th><th>Unitário</th><th>Subtotal</th></tr>
        {% for item in itens %}
        <tr>
            <td>{{ item['nome_produto'] }}</td>
            <td>{{ item['quantidade'] }}</td>
            <td>{{ dinheiro(item['preco_unitario']) }}</td>
            <td>{{ dinheiro(item['subtotal']) }}</td>
        </tr>
        {% endfor %}
    </table>
    </div>

    <h2 class="preco">Total: {{ dinheiro(pedido['total']) }}</h2>

    <form class="formulario" method="post"
          action="{{ url_for('admin_atualizar_status', pid=pedido['id']) }}">
        <input type="hidden" name="_csrf" value="{{ csrf_token() }}">
        <label>Atualizar status</label>
        <select name="status">
            {% for s in status_opcoes %}
            <option value="{{ s }}" {{ 'selected' if pedido['status'] == s else '' }}>
                {{ s }}
            </option>
            {% endfor %}
        </select>
        <button class="botao">Salvar status</button>
    </form>

    <form class="formulario" method="post"
          action="{{ url_for('admin_rastreamento', pid=pedido['id']) }}">
        <input type="hidden" name="_csrf" value="{{ csrf_token() }}">
        <h3 class="secao">Código de rastreamento</h3>
        <label>Informe o código de rastreio</label>
        <input name="codigo_rastreamento"
               value="{{ pedido['codigo_rastreamento'] or '' }}"
               placeholder="Código de rastreamento">
        <button class="botao">Salvar e preparar WhatsApp do cliente</button>
    </form>

    {% if pedido['codigo_rastreamento'] %}
    <div class="aviso">
        Código registrado: <strong>{{ pedido['codigo_rastreamento'] }}</strong>
    </div>
    {% endif %}

    <a class="botao botao-secundario" href="{{ url_for('admin_pedidos') }}">Voltar aos pedidos</a>
    """

    status_opcoes = [
        "Aguardando confirmação no WhatsApp",
        "Em atendimento",
        "Aguardando pagamento",
        "Pago",
        "Enviado",
        "Concluído",
        "Cancelado"
    ]

    return render_site(
        render_template_string(
            html,
            pedido=pedido,
            itens=itens,
            dinheiro=dinheiro,
            endereco_pedido=endereco_pedido,
            status_opcoes=status_opcoes
        ),
        f"Pedido {pid}"
    )


# =========================================================
# ATUALIZAR STATUS
# =========================================================

@app.route("/admin/pedido/<int:pid>/status", methods=["POST"])
@admin_required
def admin_atualizar_status(pid):
    validar_csrf()

    status = request.form.get("status", "")

    permitidos = [
        "Aguardando confirmação no WhatsApp",
        "Em atendimento",
        "Aguardando pagamento",
        "Pago",
        "Enviado",
        "Concluído",
        "Cancelado"
    ]

    if status not in permitidos:
        abort(400)

    with conectar() as conn:
        conn.execute(
            "UPDATE pedidos SET status=? WHERE id=?",
            (status, pid)
        )

    flash("Status do pedido atualizado.")
    return redirect(url_for("admin_pedido_detalhe", pid=pid))


# =========================================================
# RASTREAMENTO E WHATSAPP DO CLIENTE
# =========================================================

@app.route("/admin/pedido/<int:pid>/rastreamento", methods=["POST"])
@admin_required
def admin_rastreamento(pid):
    validar_csrf()

    codigo = request.form.get("codigo_rastreamento", "").strip()

    if not codigo:
        flash("Informe o código de rastreamento.")
        return redirect(url_for("admin_pedido_detalhe", pid=pid))

    with conectar() as conn:
        pedido = conn.execute(
            "SELECT * FROM pedidos WHERE id=?",
            (pid,)
        ).fetchone()

        if not pedido:
            abort(404)

        conn.execute("""
            UPDATE pedidos
            SET codigo_rastreamento=?, status='Enviado'
            WHERE id=?
        """, (codigo, pid))

    telefone = re.sub(r"\D", "", pedido["telefone"] or "")

    if not 10 <= len(telefone) <= 13:
        flash("Código salvo, mas o telefone do cliente não é válido para WhatsApp.")
        return redirect(url_for("admin_pedido_detalhe", pid=pid))

    mensagem = (
        f"Olá, {pedido['cliente']}! Tudo bem?\n\n"
        f"Seu pedido #{pedido['id']} da IWG Technological Solutions "
        f"foi postado para o endereço informado.\n\n"
        f"*Código de rastreamento:* {codigo}\n\n"
        f"*Destino:* {endereco_pedido(pedido)}\n\n"
        "Guarde este código para acompanhar a entrega junto à transportadora.\n\n"
        "Agradecemos pela sua compra!\n"
        "IWG Technological Solutions"
    )

    url = f"https://wa.me/{telefone}?text={quote(mensagem, safe='')}"
    return redirect(url)


# =========================================================
# ALTERAR SENHA ADMINISTRATIVA
# =========================================================

@app.route("/admin/senha", methods=["GET", "POST"])
@admin_required
def admin_senha():
    if request.method == "POST":
        validar_csrf()

        atual = request.form.get("senha_atual", "")
        nova = request.form.get("nova_senha", "")
        confirmar = request.form.get("confirmar_senha", "")

        with conectar() as conn:
            admin = conn.execute(
                "SELECT * FROM administradores WHERE id=?",
                (session["admin"],)
            ).fetchone()

            if not admin or not check_password_hash(admin["senha"], atual):
                flash("Senha atual incorreta.")
                return redirect(url_for("admin_senha"))

            if len(nova) < 4:
                flash("A nova senha precisa ter pelo menos 4 caracteres.")
                return redirect(url_for("admin_senha"))

            if nova != confirmar:
                flash("A confirmação da senha não corresponde.")
                return redirect(url_for("admin_senha"))

            conn.execute("""
                UPDATE administradores SET senha=? WHERE id=?
            """, (generate_password_hash(nova), session["admin"]))

        flash("Senha alterada com sucesso!")
        return redirect(url_for("admin_dashboard"))

    html = """
    <h2 class="secao">Alterar senha</h2>
    <form class="formulario" method="post">
        <input type="hidden" name="_csrf" value="{{ csrf_token() }}">
        <label>Senha atual</label>
        <input type="password" name="senha_atual" required>
        <label>Nova senha</label>
        <input type="password" name="nova_senha" required>
        <label>Confirmar nova senha</label>
        <input type="password" name="confirmar_senha" required>
        <button class="botao">Alterar senha</button>
    </form>
    """

    return render_site(html, "Alterar senha")


# =========================================================
# SAIR DO PAINEL
# =========================================================

@app.route("/admin/sair")
def admin_logout():
    session.clear()
    flash("Você saiu do painel administrativo.")
    return redirect(url_for("inicio"))


# =========================================================
# PAGINAS DE ERRO
# =========================================================

@app.errorhandler(404)
def pagina_nao_encontrada(error):
    html = """
    <h2 class="secao">Página não encontrada</h2>
    <p>O conteúdo solicitado não foi encontrado.</p>
    <a class="botao" href="{{ url_for('inicio') }}">Voltar ao início</a>
    """
    return render_site(html, "Página não encontrada"), 404


@app.errorhandler(400)
def requisicao_invalida(error):
    html = """
    <h2 class="secao">Requisição inválida</h2>
    <p>Não foi possível processar esta solicitação.</p>
    <a class="botao" href="{{ url_for('inicio') }}">Voltar ao início</a>
    """
    return render_site(html, "Requisição inválida"), 400


@app.errorhandler(413)
def arquivo_grande(error):
    html = """
    <h2 class="secao">Arquivo muito grande</h2>
    <p>O limite para envio de arquivos é de 5 MB.</p>
    <a class="botao" href="{{ url_for('admin_dashboard') }}">Voltar</a>
    """
    return render_site(html, "Arquivo muito grande"), 413


# =========================================================
# EXECUCAO LOCAL
# =========================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
