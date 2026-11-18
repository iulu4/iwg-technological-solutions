
import os
import sqlite3
import uuid
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
# CONFIGURAÇÕES IWG
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
# BANCO DE DADOS E MIGRAÇÕES
# =========================================================

def conectar():
    conn = sqlite3.connect(BANCO)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


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
                ativo INTEGER DEFAULT 1
            )
        """)

        # Adiciona estoque sem apagar produtos antigos.
        colunas = [
            linha["name"]
            for linha in conn.execute(
                "PRAGMA table_info(produtos)"
            ).fetchall()
        ]

        if "estoque" not in colunas:
            conn.execute(
                "ALTER TABLE produtos ADD COLUMN estoque INTEGER DEFAULT NULL"
            )

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
# FUNÇÕES AUXILIARES
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
        produto["id"],
        IMAGEM_BANNER
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


def estoque_disponivel(produto, quantidade_atual=0):
    if produto["estoque"] is None:
        return True

    return produto["estoque"] >= quantidade_atual


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

<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://images.unsplash.com">

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

.avatar img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

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

.container {
    width: 92%;
    max-width: 1200px;
    margin: 30px auto;
}

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
        linear-gradient(90deg, rgba(2,5,38,.96), rgba(2,5,38,.75), rgba(2,5,38,.65)),
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
    text-transform: uppercase;
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
    transition: .3s;
    font-size: 13px;
}

.botao:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(247,192,74,.25);
}

.botao-secundario {
    background: transparent;
    color: {{ ouro }};
    border: 1px solid {{ ouro }};
}

.secao {
    color: {{ ouro }};
    font-size: 25px;
    margin: 45px 0 20px;
}

.subsecao {
    color: #AEB6D2;
    line-height: 1.7;
    margin-bottom: 25px;
}

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
    transition: .3s;
}

.produto:hover {
    transform: translateY(-5px);
    border-color: {{ ouro }};
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

.produto h3 {
    color: {{ ouro }};
    font-size: 17px;
    line-height: 1.4;
}

.produto p {
    color: #C4C8D5;
    line-height: 1.6;
    font-size: 13px;
    min-height: 42px;
}

.preco {
    font-size: 21px;
    color: {{ ouro }};
    font-weight: bold;
    margin: 15px 0;
}

.servico {
    background: linear-gradient(145deg, #0A0E45, #111A55);
    border: 1px solid {{ borda }};
    border-radius: 13px;
    padding: 25px;
}

.servico-icone { font-size: 35px; }
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

.filtros {
    display: flex;
    flex-wrap: wrap;
    gap: 9px;
    margin-bottom: 25px;
}

.filtros a {
    padding: 9px 15px;
    border: 1px solid {{ borda }};
    border-radius: 20px;
    color: white;
    font-size: 13px;
}

.filtros a:hover, .filtros a.ativo {
    background: {{ ouro }};
    color: #020526;
}

.formulario {
    background: {{ card }};
    border: 1px solid {{ borda }};
    padding: 24px;
    border-radius: 12px;
    max-width: 700px;
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

td, th {
    border-bottom: 1px solid {{ borda }};
    padding: 12px;
    text-align: left;
}

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

.cartao-indicador span {
    color: #AEB6D2;
    font-size: 13px;
}

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

.acoes {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
}

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
# PÁGINA INICIAL
# =========================================================

@app.route("/")
def inicio():
    categoria = request.args.get("categoria", "")

    with conectar() as conn:
        categorias = conn.execute("""
            SELECT DISTINCT categoria
            FROM produtos
            WHERE ativo = 1
            ORDER BY categoria
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
                WHERE ativo = 1
                ORDER BY id DESC
            """).fetchall()

    html = """
    <section class="banner">
        <div class="banner-conteudo">
            <div class="banner-etiqueta">
                Tecnologia • Inovação • Soluções
            </div>
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
                <div class="servico-icone">💻</div>
                <h3>Desenvolvimento de Software</h3>
                <p>Criação de sistemas, aplicativos, plataformas e soluções personalizadas.</p>
            </div>
            <div class="servico">
                <div class="servico-icone">⚙️</div>
                <h3>Automação e Inteligência</h3>
                <p>Automação de tarefas, integração de processos e ferramentas digitais.</p>
            </div>
            <div class="servico">
                <div class="servico-icone">🌐</div>
                <h3>Consultoria em Tecnologia</h3>
                <p>Arquitetura de sistemas, planejamento e orientação tecnológica.</p>
            </div>
            <div class="servico">
                <div class="servico-icone">📱</div>
                <h3>Eletrônicos e Importações</h3>
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
                <img src="{{ imagem_produto(p) }}"
                     alt="{{ p['nome'] }}" loading="lazy"
                     onerror="this.style.display='none'">
                <div class="produto-conteudo">
                    <span class="categoria">{{ p['categoria'] }}</span>
                    <h3>{{ p['nome'] }}</h3>
                    <p>{{ p['descricao'] }}</p>
                    <div class="preco">{{ dinheiro(p['preco']) }}</div>

                    {% if p['estoque'] is none %}
                        <span class="badge-status">Disponibilidade sob consulta</span>
                    {% elif p['estoque'] > 0 %}
                        <span class="badge-status">Em estoque: {{ p['estoque'] }}</span>
                    {% else %}
                        <span class="badge-status">Indisponível</span>
                    {% endif %}

                    <br><br>
                    <a class="botao"
                       href="{{ url_for('produto', pid=p['id']) }}">Ver detalhes</a>

                    {% if p['estoque'] is none or p['estoque'] > 0 %}
                    <form method="post"
                          action="{{ url_for('adicionar_carrinho', pid=p['id']) }}">
                        <input type="hidden" name="_csrf" value="{{ csrf_token() }}">
                        <button class="botao botao-secundario" type="submit">
                            Adicionar ao carrinho
                        </button>
                    </form>
                    {% endif %}
                </div>
            </article>
        {% else %}
            <p>Nenhum produto cadastrado nesta categoria.</p>
        {% endfor %}
        </div>
    </section>

    <section id="sobre" class="sobre">
        <h2>Sobre a IWG Technological Solutions</h2>
        <p>
            A IWG Technological Solutions atua na área de tecnologia,
            desenvolvimento de software, automação, eletrônicos e importações.
        </p>
        <p>
            Nosso objetivo é aproximar pessoas e empresas de soluções
            tecnológicas modernas, oferecendo ferramentas, produtos e serviços.
        </p>
        <a class="botao" href="https://wa.me/{{ whatsapp }}">Entre em contato</a>
    </section>

    <div class="aviso">
        Imagens ilustrativas e valores sujeitos à disponibilidade.
        Consulte nossa equipe antes de concluir sua compra.
    </div>
    """

    conteudo = render_template_string(
        html,
        produtos=produtos,
        categorias=categorias,
        dinheiro=dinheiro,
        imagem_produto=imagem_produto,
        categoria=categoria,
        whatsapp=WHATSAPP
    )

    return render_site(conteudo)


# =========================================================
# DETALHES DO PRODUTO
# =========================================================

@app.route("/produto/<int:pid>")
def produto(pid):
    with conectar() as conn:
        p = conn.execute("""
            SELECT * FROM produtos
            WHERE id = ? AND ativo = 1
        """, (pid,)).fetchone()

    if not p:
        return redirect(url_for("inicio"))

    html = """
    <div class="formulario">
        <img style="width:100%;max-height:350px;object-fit:contain"
             src="{{ imagem_produto(p) }}" alt="{{ p['nome'] }}">
        <h2 style="color:{{ ouro }}">{{ p['nome'] }}</h2>
        <p>{{ p['descricao'] }}</p>
        <p>Categoria: {{ p['categoria'] }}</p>
        <div class="preco">{{ dinheiro(p['preco']) }}</div>

        {% if p['estoque'] is none %}
            <p>Disponibilidade sob consulta.</p>
        {% elif p['estoque'] > 0 %}
            <p>Quantidade disponível: {{ p['estoque'] }}</p>
        {% else %}
            <p>Produto indisponível no momento.</p>
        {% endif %}

        {% if p['estoque'] is none or p['estoque'] > 0 %}
        <form method="post"
              action="{{ url_for('adicionar_carrinho', pid=p['id']) }}">
            <input type="hidden" name="_csrf" value="{{ csrf_token() }}">
            <button class="botao">Adicionar ao carrinho</button>
        </form>
        {% endif %}

        <a class="botao botao-secundario" href="{{ url_for('inicio') }}">
            Voltar ao catálogo
        </a>
    </div>
    """

    conteudo = render_template_string(
        html,
        p=p,
        dinheiro=dinheiro,
        ouro=COR_OURO,
        imagem_produto=imagem_produto
    )

    return render_site(conteudo, p["nome"])


# =========================================================
# CARRINHO
# =========================================================

@app.route("/adicionar/<int:pid>", methods=["POST"])
def adicionar_carrinho(pid):
    validar_csrf()

    with conectar() as conn:
        p = conn.execute("""
            SELECT * FROM produtos
            WHERE id = ? AND ativo = 1
        """, (pid,)).fetchone()

    if not p:
        flash("Produto não encontrado.")
        return redirect(url_for("inicio"))

    carrinho = session.get("carrinho", {})
    chave = str(pid)
    quantidade_atual = int(carrinho.get(chave, 0))

    if p["estoque"] is not None and quantidade_atual >= p["estoque"]:
        flash("Quantidade máxima disponível já está no carrinho.")
        return redirect(request.referrer or url_for("inicio"))

    carrinho[chave] = quantidade_atual + 1
    session["carrinho"] = carrinho

    flash("Produto adicionado ao carrinho!")
    return redirect(request.referrer or url_for("inicio"))


@app.route("/carrinho")
def carrinho():
    itens = []
    total = 0
    ids = session.get("carrinho", {})

    with conectar() as conn:
        for pid, quantidade in ids.items():
            p = conn.execute("""
                SELECT * FROM produtos
                WHERE id = ? AND ativo = 1
            """, (pid,)).fetchone()

            if p:
                quantidade = int(quantidade)
                subtotal = p["preco"] * quantidade
                total += subtotal
                itens.append({
                    "produto": p,
                    "quantidade": quantidade,
                    "subtotal": subtotal
                })

    html = """
    <h2 class="secao">Meu carrinho</h2>

    {% if itens %}
    <div class="tabela-responsiva">
    <table>
        <tr><th>Produto</th><th>Qtd.</th><th>Subtotal</th><th></th></tr>
        {% for item in itens %}
        <tr>
            <td>{{ item.produto['nome'] }}</td>
            <td>{{ item.quantidade }}</td>
            <td>{{ dinheiro(item.subtotal) }}</td>
            <td>
                <a href="{{ url_for('remover_carrinho', pid=item.produto['id']) }}">
                    Remover
                </a>
            </td>
        </tr>
        {% endfor %}
    </table>
    </div>

    <h2 style="color:{{ ouro }}">Total: {{ dinheiro(total) }}</h2>

    <form method="post" action="{{ url_for('finalizar_pedido') }}">
        <input type="hidden" name="_csrf" value="{{ csrf_token() }}">
        <label>Seu nome</label>
        <input name="nome" required placeholder="Digite seu nome">
        <label>Observações do pedido</label>
        <textarea name="observacoes" rows="3"></textarea>
        <button class="botao" type="submit">Finalizar pelo WhatsApp</button>
    </form>
    {% else %}
        <p>Seu carrinho está vazio.</p>
    {% endif %}

    <a class="botao botao-secundario" href="{{ url_for('inicio') }}">
        Continuar comprando
    </a>
    """

    conteudo = render_template_string(
        html,
        itens=itens,
        total=total,
        dinheiro=dinheiro,
        ouro=COR_OURO
    )

    return render_site(conteudo, "Carrinho")


@app.route("/remover-carrinho/<int:pid>", methods=["POST"])
def remover_carrinho(pid):
    validar_csrf()
    carrinho = session.get("carrinho", {})
    carrinho.pop(str(pid), None)
    session["carrinho"] = carrinho
    return redirect(url_for("carrinho"))


# =========================================================
# FINALIZAÇÃO E REGISTRO DO PEDIDO
# =========================================================

@app.route("/finalizar", methods=["POST"])
def finalizar_pedido():
    validar_csrf()

    nome = request.form.get("nome", "").strip()
    observacoes = request.form.get("observacoes", "").strip()

    if not nome:
        flash("Informe seu nome.")
        return redirect(url_for("carrinho"))

    carrinho_atual = session.get("carrinho", {})
    if not carrinho_atual:
        flash("Seu carrinho está vazio.")
        return redirect(url_for("carrinho"))

    itens = []
    total = 0

    with conectar() as conn:
        for pid, quantidade in carrinho_atual.items():
            p = conn.execute("""
                SELECT * FROM produtos
                WHERE id = ? AND ativo = 1
            """, (pid,)).fetchone()

            if not p:
                continue

            quantidade = int(quantidade)

            if p["estoque"] is not None and quantidade > p["estoque"]:
                flash(
                    f"Estoque insuficiente para {p['nome']}. "
                    "Atualize seu carrinho ou fale conosco."
                )
                return redirect(url_for("carrinho"))

            subtotal = p["preco"] * quantidade
            total += subtotal

            itens.append({
                "id": p["id"],
                "nome": p["nome"],
                "quantidade": quantidade,
                "preco": p["preco"],
                "subtotal": subtotal
            })

        if not itens:
            flash("Não foi possível localizar os produtos do pedido.")
            return redirect(url_for("carrinho"))

        cursor = conn.execute("""
            INSERT INTO pedidos (cliente, observacoes, total, status)
            VALUES (?, ?, ?, 'Recebido')
        """, (nome, observacoes, total))

        pedido_id = cursor.lastrowid

        for item in itens:
            conn.execute("""
                INSERT INTO pedido_itens
                (pedido_id, produto_id, nome_produto,
                 quantidade, preco_unitario, subtotal)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                pedido_id,
                item["id"],
                item["nome"],
                item["quantidade"],
                item["preco"],
                item["subtotal"]
            ))

    linhas = [
        f"{item['nome']} - {item['quantidade']} unidade(s) "
        f"- {dinheiro(item['subtotal'])}"
        for item in itens
    ]

    mensagem = (
        "Olá! Gostaria de fazer um pedido na IWG.\\n\\n"
        f"Pedido: #{pedido_id}\\n"
        f"Cliente: {nome}\\n\\n"
        + "\\n".join(linhas)
        + f"\\n\\nTotal: {dinheiro(total)}"
        + f"\\nObservações: {observacoes}"
    )

    link = (
        "https://wa.me/"
        + WHATSAPP
        + "?text="
        + quote(mensagem)
    )

    session["carrinho"] = {}
    flash(f"Pedido #{pedido_id} registrado! Continue pelo WhatsApp.")

    return redirect(link)


# =========================================================
# LOGIN ADMINISTRATIVO
# =========================================================

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        validar_csrf()

        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")

        with conectar() as conn:
            admin = conn.execute("""
                SELECT * FROM administradores
                WHERE usuario = ?
            """, (usuario,)).fetchone()

        if admin and check_password_hash(admin["senha"], senha):
            session.clear()
            session["admin"] = True
            session["usuario"] = usuario
            csrf_token()
            return redirect(url_for("admin_painel"))

        flash("Usuário ou senha incorretos.")

    html = """
    <div class="formulario">
        <h2 style="color:{{ ouro }}">Acesso administrativo IWG</h2>
        <form method="post">
            <input type="hidden" name="_csrf" value="{{ csrf_token() }}">
            <label>Usuário</label>
            <input name="usuario" required>
            <label>Senha</label>
            <input name="senha" type="password" required>
            <button class="botao" type="submit">Entrar</button>
        </form>
    </div>
    """

    return render_site(
        render_template_string(html, ouro=COR_OURO),
        "Administração"
    )


# =========================================================
# DASHBOARD ADMINISTRATIVO
# =========================================================

@app.route("/admin/painel")
@admin_required
def admin_painel():
    with conectar() as conn:
        produtos = conn.execute("""
            SELECT * FROM produtos ORDER BY id DESC
        """).fetchall()

        total_produtos = conn.execute(
            "SELECT COUNT(*) AS total FROM produtos"
        ).fetchone()["total"]

        ativos = conn.execute(
            "SELECT COUNT(*) AS total FROM produtos WHERE ativo = 1"
        ).fetchone()["total"]

        inativos = total_produtos - ativos

        pedidos_total = conn.execute(
            "SELECT COUNT(*) AS total FROM pedidos"
        ).fetchone()["total"]

        pedidos_recentes = conn.execute("""
            SELECT * FROM pedidos
            ORDER BY id DESC LIMIT 5
        """).fetchall()

    html = """
    <h2 class="secao">Painel administrativo IWG</h2>
    <p>Bem-vindo, {{ session.get('usuario') }}!</p>

    <div class="grade">
        <div class="cartao-indicador">
            <span>Total de produtos</span>
            <strong>{{ total_produtos }}</strong>
        </div>
        <div class="cartao-indicador">
            <span>Produtos ativos</span>
            <strong>{{ ativos }}</strong>
        </div>
        <div class="cartao-indicador">
            <span>Produtos inativos</span>
            <strong>{{ inativos }}</strong>
        </div>
        <div class="cartao-indicador">
            <span>Pedidos registrados</span>
            <strong>{{ pedidos_total }}</strong>
        </div>
    </div>

    <br>
    <a class="botao" href="{{ url_for('admin_novo') }}">+ Novo produto</a>
    <a class="botao" href="{{ url_for('admin_pedidos') }}">Gerenciar pedidos</a>
    <a class="botao botao-secundario" href="{{ url_for('admin_senha') }}">Alterar senha</a>

    <form method="post" action="{{ url_for('admin_sair') }}" style="display:inline">
        <input type="hidden" name="_csrf" value="{{ csrf_token() }}">
        <button class="botao botao-secundario" type="submit">Sair</button>
    </form>

    <h3 class="secao">Produtos cadastrados</h3>

    <div class="tabela-responsiva">
    <table>
        <tr>
            <th>Produto</th><th>Preço</th><th>Estoque</th>
            <th>Status</th><th>Ações</th>
        </tr>
        {% for p in produtos %}
        <tr>
            <td>{{ p['nome'] }}</td>
            <td>{{ dinheiro(p['preco']) }}</td>
            <td>
                {% if p['estoque'] is none %}
                    Sob consulta
                {% else %}
                    {{ p['estoque'] }} unidade(s)
                {% endif %}
            </td>
            <td>{{ 'Ativo' if p['ativo'] else 'Inativo' }}</td>
            <td>
                <div class="acoes">
                    <a href="{{ url_for('admin_editar', pid=p['id']) }}">Editar</a>

                    <form method="post"
                          action="{{ url_for('admin_alternar', pid=p['id']) }}">
                        <input type="hidden" name="_csrf" value="{{ csrf_token() }}">
                        <button type="submit">Ativar/desativar</button>
                    </form>

                    <form method="post"
                          action="{{ url_for('admin_excluir', pid=p['id']) }}"
                          onsubmit="return confirm('Excluir este produto?')">
                        <input type="hidden" name="_csrf" value="{{ csrf_token() }}">
                        <button type="submit">Excluir</button>
                    </form>
                </div>
            </td>
        </tr>
        {% endfor %}
    </table>
    </div>

    <h3 class="secao">Pedidos recentes</h3>
    {% if pedidos_recentes %}
    <div class="tabela-responsiva">
    <table>
        <tr><th>Número</th><th>Cliente</th><th>Total</th><th>Status</th><th></th></tr>
        {% for pedido in pedidos_recentes %}
        <tr>
            <td>#{{ pedido['id'] }}</td>
            <td>{{ pedido['cliente'] }}</td>
            <td>{{ dinheiro(pedido['total']) }}</td>
            <td>{{ pedido['status'] }}</td>
            <td><a href="{{ url_for('admin_pedido_detalhe', pedido_id=pedido['id']) }}">Ver</a></td>
        </tr>
        {% endfor %}
    </table>
    </div>
    {% else %}
        <p>Ainda não existem pedidos registrados.</p>
    {% endif %}
    """

    conteudo = render_template_string(
        html,
        produtos=produtos,
        total_produtos=total_produtos,
        ativos=ativos,
        inativos=inativos,
        pedidos_total=pedidos_total,
        pedidos_recentes=pedidos_recentes,
        dinheiro=dinheiro
    )

    return render_site(conteudo, "Painel administrativo")


# =========================================================
# CADASTRO E EDIÇÃO DE PRODUTOS
# =========================================================

def formulario_produto(p=None):
    html = """
    <div class="formulario">
        <h2 style="color:{{ ouro }}">{{ titulo }}</h2>

        <form method="post" enctype="multipart/form-data">
            <input type="hidden" name="_csrf" value="{{ csrf_token() }}">

            <label>Nome do produto ou serviço</label>
            <input name="nome" required value="{{ p['nome'] if p else '' }}">

            <label>Categoria</label>
            <input name="categoria"
                   value="{{ p['categoria'] if p else 'Produtos' }}">

            <label>Descrição</label>
            <textarea name="descricao" rows="4">{{ p['descricao'] if p else '' }}</textarea>

            <label>Preço em reais</label>
            <input name="preco" type="number" step="0.01"
                   min="0" required value="{{ p['preco'] if p else '' }}">

            <label>Quantidade em estoque</label>
            <input name="estoque" type="number" min="0"
                   value="{{ p['estoque'] if p and p['estoque'] is not none else '' }}"
                   placeholder="Deixe vazio para estoque sob consulta">

            <p style="color:#AEB6D2;font-size:12px">
                Deixe o campo vazio para não controlar estoque.
                Informe zero se o produto estiver sem unidades disponíveis.
            </p>

            <label>Foto do produto</label>
            <input name="imagem" type="file" accept=".jpg,.jpeg,.png,.webp">

            {% if p and p['imagem'] %}
                <p>Imagem atual: {{ p['imagem'] }}</p>
            {% endif %}

            <button class="botao" type="submit">Salvar produto</button>
            <a class="botao botao-secundario"
               href="{{ url_for('admin_painel') }}">Cancelar</a>
        </form>
    </div>
    """

    return render_template_string(
        html,
        p=p,
        titulo="Editar produto" if p else "Novo produto",
        ouro=COR_OURO
    )


def ler_dados_produto():
    nome = request.form.get("nome", "").strip()
    categoria = request.form.get("categoria", "Produtos").strip() or "Produtos"
    descricao = request.form.get("descricao", "").strip()

    try:
        preco = float(request.form.get("preco", "0").replace(",", "."))
    except ValueError:
        preco = -1

    estoque_texto = request.form.get("estoque", "").strip()

    if estoque_texto == "":
        estoque = None
    else:
        try:
            estoque = int(estoque_texto)
        except ValueError:
            estoque = -1

    if not nome or preco < 0 or estoque is not None and estoque < 0:
        return None

    return nome, categoria, descricao, preco, estoque


@app.route("/admin/novo", methods=["GET", "POST"])
@admin_required
def admin_novo():
    if request.method == "POST":
        validar_csrf()
        dados = ler_dados_produto()

        if not dados:
            flash("Confira o nome, preço e estoque.")
            return redirect(url_for("admin_novo"))

        imagem = salvar_imagem(request.files.get("imagem"))

        with conectar() as conn:
            conn.execute("""
                INSERT INTO produtos
                (nome, categoria, descricao, preco, imagem, estoque)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (*dados, imagem, dados[4]))

        flash("Produto cadastrado com sucesso!")
        return redirect(url_for("admin_painel"))

    return render_site(formulario_produto(), "Novo produto")


@app.route("/admin/editar/<int:pid>", methods=["GET", "POST"])
@admin_required
def admin_editar(pid):
    with conectar() as conn:
        p = conn.execute(
            "SELECT * FROM produtos WHERE id = ?", (pid,)
        ).fetchone()

    if not p:
        return redirect(url_for("admin_painel"))

    if request.method == "POST":
        validar_csrf()
        dados = ler_dados_produto()

        if not dados:
            flash("Confira o nome, preço e estoque.")
            return redirect(url_for("admin_editar", pid=pid))

        imagem = p["imagem"]
        novo_arquivo = request.files.get("imagem")

        if novo_arquivo and novo_arquivo.filename:
            nova_imagem = salvar_imagem(novo_arquivo)
            if nova_imagem:
                excluir_imagem(imagem)
                imagem = nova_imagem
            else:
                flash("Formato de imagem inválido.")
                return redirect(url_for("admin_editar", pid=pid))

        with conectar() as conn:
            conn.execute("""
                UPDATE produtos
                SET nome=?, categoria=?, descricao=?,
                    preco=?, imagem=?, estoque=?
                WHERE id=?
            """, (
                dados[0], dados[1], dados[2],
                dados[3], imagem, dados[4], pid
            ))

        flash("Produto atualizado!")
        return redirect(url_for("admin_painel"))

    return render_site(formulario_produto(p), "Editar produto")


@app.route("/admin/alternar/<int:pid>", methods=["POST"])
@admin_required
def admin_alternar(pid):
    validar_csrf()

    with conectar() as conn:
        conn.execute("""
            UPDATE produtos
            SET ativo = CASE WHEN ativo = 1 THEN 0 ELSE 1 END
            WHERE id = ?
        """, (pid,))

    flash("Status do produto atualizado.")
    return redirect(url_for("admin_painel"))


@app.route("/admin/excluir/<int:pid>", methods=["POST"])
@admin_required
def admin_excluir(pid):
    validar_csrf()

    with conectar() as conn:
        p = conn.execute(
            "SELECT imagem FROM produtos WHERE id = ?", (pid,)
        ).fetchone()

        if p:
            # Os itens antigos dos pedidos permanecem preservados.
            excluir_imagem(p["imagem"])
            conn.execute(
                "DELETE FROM produtos WHERE id = ?", (pid,)
            )

    flash("Produto excluído.")
    return redirect(url_for("admin_painel"))


# =========================================================
# GESTÃO DE PEDIDOS
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
    <a class="botao botao-secundario" href="{{ url_for('admin_painel') }}">
        Voltar ao painel
    </a>

    {% if pedidos %}
    <div class="tabela-responsiva">
    <table>
        <tr>
            <th>Pedido</th><th>Data</th><th>Cliente</th>
            <th>Total</th><th>Status</th><th>Detalhes</th>
        </tr>
        {% for p in pedidos %}
        <tr>
            <td>#{{ p['id'] }}</td>
            <td>{{ p['data_criacao'] }}</td>
            <td>{{ p['cliente'] }}</td>
            <td>{{ dinheiro(p['total']) }}</td>
            <td><span class="badge-status">{{ p['status'] }}</span></td>
            <td>
                <a href="{{ url_for('admin_pedido_detalhe', pedido_id=p['id']) }}">
                    Abrir pedido
                </a>
            </td>
        </tr>
        {% endfor %}
    </table>
    </div>
    {% else %}
        <p>Nenhum pedido foi registrado ainda.</p>
    {% endif %}
    """

    conteudo = render_template_string(
        html, pedidos=pedidos, dinheiro=dinheiro
    )

    return render_site(conteudo, "Pedidos")


@app.route("/admin/pedido/<int:pedido_id>")
@admin_required
def admin_pedido_detalhe(pedido_id):
    with conectar() as conn:
        pedido = conn.execute(
            "SELECT * FROM pedidos WHERE id = ?", (pedido_id,)
        ).fetchone()

        itens = conn.execute("""
            SELECT * FROM pedido_itens
            WHERE pedido_id = ? ORDER BY id
        """, (pedido_id,)).fetchall()

    if not pedido:
        return redirect(url_for("admin_pedidos"))

    html = """
    <h2 class="secao">Pedido #{{ pedido['id'] }}</h2>

    <div class="formulario">
        <p><strong>Cliente:</strong> {{ pedido['cliente'] }}</p>
        <p><strong>Data:</strong> {{ pedido['data_criacao'] }}</p>
        <p><strong>Observações:</strong> {{ pedido['observacoes'] or 'Nenhuma' }}</p>
        <p><strong>Total:</strong> {{ dinheiro(pedido['total']) }}</p>
        <p><strong>Status atual:</strong>
            <span class="badge-status">{{ pedido['status'] }}</span>
        </p>

        <h3 style="color:{{ ouro }}">Atualizar status</h3>
        <form method="post"
              action="{{ url_for('admin_pedido_status', pedido_id=pedido['id']) }}">
            <input type="hidden" name="_csrf" value="{{ csrf_token() }}">
            <select name="status" required>
                {% for status in status_opcoes %}
                    <option value="{{ status }}"
                        {% if pedido['status'] == status %}selected{% endif %}>
                        {{ status }}
                    </option>
                {% endfor %}
            </select>
            <button class="botao" type="submit">Salvar status</button>
        </form>
    </div>

    <h3 class="secao">Itens do pedido</h3>
    <div class="tabela-responsiva">
    <table>
        <tr>
            <th>Produto</th><th>Quantidade</th>
            <th>Preço unitário</th><th>Subtotal</th>
        </tr>
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

    <a class="botao botao-secundario"
       href="{{ url_for('admin_pedidos') }}">Voltar aos pedidos</a>
    """

    conteudo = render_template_string(
        html,
        pedido=pedido,
        itens=itens,
        dinheiro=dinheiro,
        ouro=COR_OURO,
        status_opcoes=[
            "Recebido",
            "Em atendimento",
            "Aguardando pagamento",
            "Pago",
            "Concluído",
            "Cancelado"
        ]
    )

    return render_site(conteudo, f"Pedido {pedido_id}")


@app.route("/admin/pedido/<int:pedido_id>/status", methods=["POST"])
@admin_required
def admin_pedido_status(pedido_id):
    validar_csrf()

    status = request.form.get("status", "")
    permitidos = {
        "Recebido",
        "Em atendimento",
        "Aguardando pagamento",
        "Pago",
        "Concluído",
        "Cancelado"
    }

    if status not in permitidos:
        flash("Status inválido.")
        return redirect(
            url_for("admin_pedido_detalhe", pedido_id=pedido_id)
        )

    with conectar() as conn:
        conn.execute("""
            UPDATE pedidos SET status = ? WHERE id = ?
        """, (status, pedido_id))

    flash("Status do pedido atualizado.")
    return redirect(
        url_for("admin_pedido_detalhe", pedido_id=pedido_id)
    )


# =========================================================
# ALTERAÇÃO DE SENHA
# =========================================================

@app.route("/admin/senha", methods=["GET", "POST"])
@admin_required
def admin_senha():
    if request.method == "POST":
        validar_csrf()

        atual = request.form.get("atual", "")
        nova = request.form.get("nova", "")
        confirmar = request.form.get("confirmar", "")

        with conectar() as conn:
            admin = conn.execute("""
                SELECT * FROM administradores
                WHERE usuario = ?
            """, (session.get("usuario"),)).fetchone()

            if not admin or not check_password_hash(admin["senha"], atual):
                flash("Senha atual incorreta.")
            elif len(nova) < 8:
                flash("A nova senha deve ter pelo menos 8 caracteres.")
            elif nova != confirmar:
                flash("As senhas não conferem.")
            else:
                conn.execute("""
                    UPDATE administradores SET senha = ?
                    WHERE id = ?
                """, (
                    generate_password_hash(nova),
                    admin["id"]
                ))

                flash("Senha alterada com sucesso!")
                return redirect(url_for("admin_painel"))

    html = """
    <div class="formulario">
        <h2 style="color:{{ ouro }}">Alterar senha</h2>
        <form method="post">
            <input type="hidden" name="_csrf" value="{{ csrf_token() }}">
            <label>Senha atual</label>
            <input type="password" name="atual" required>
            <label>Nova senha</label>
            <input type="password" name="nova" required>
            <label>Confirmar nova senha</label>
            <input type="password" name="confirmar" required>
            <button class="botao">Alterar senha</button>
        </form>
    </div>
    """

    return render_site(
        render_template_string(html, ouro=COR_OURO),
        "Alterar senha"
    )


@app.route("/admin/sair", methods=["POST"])
@admin_required
def admin_sair():
    validar_csrf()
    session.clear()
    return redirect(url_for("inicio"))


# =========================================================
# TRATAMENTO DE ERROS
# =========================================================

@app.errorhandler(400)
def requisicao_invalida(e):
    return render_site("""
        <h2 class="secao">Requisição inválida.</h2>
        <p>Atualize a página e tente novamente.</p>
        <a class="botao" href="/">Voltar ao início</a>
    """, "Requisição inválida"), 400


@app.errorhandler(413)
def arquivo_grande(e):
    flash("A imagem ultrapassa o limite de 5 MB.")
    return redirect(request.referrer or url_for("inicio"))


@app.errorhandler(404)
def pagina_nao_encontrada(e):
    return render_site("""
        <h2 class="secao">Página não encontrada.</h2>
        <a class="botao" href="/">Voltar ao início</a>
    """, "Página não encontrada"), 404


# =========================================================
# EXECUÇÃO
# =========================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8550)),
        debug=False
    )

