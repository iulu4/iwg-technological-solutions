
import os
import sqlite3
import uuid
from pathlib import Path
from functools import wraps

from flask import (
    Flask, render_template_string, request, redirect,
    url_for, session, flash
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename


# =========================================================
# CONFIGURAÇÕES DA IWG
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

EXTENSOES = {"jpg", "jpeg", "png", "webp"}


# =========================================================
# BANCO DE DADOS
# =========================================================

def conectar():
    conn = sqlite3.connect(BANCO)
    conn.row_factory = sqlite3.Row
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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS administradores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE NOT NULL,
                senha TEXT NOT NULL
            )
        """)

        admin = conn.execute(
            "SELECT id FROM administradores WHERE usuario = ?",
            ("iulu",)
        ).fetchone()

        if not admin:
            conn.execute(
                "INSERT INTO administradores (usuario, senha) VALUES (?, ?)",
                ("iulu", generate_password_hash("iulu"))
            )

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

            for nome, categoria, descricao, preco in iniciais:
                conn.execute("""
                    INSERT INTO produtos
                    (nome, categoria, descricao, preco)
                    VALUES (?, ?, ?, ?)
                """, (nome, categoria, descricao, preco))


iniciar_banco()


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

def dinheiro(valor):
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def imagem_url(nome):
    if nome:
        return url_for("static", filename="produtos/" + nome)
    return ""


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


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return func(*args, **kwargs)
    return wrapper


# =========================================================
# MODELO VISUAL DO SITE
# =========================================================

BASE_HTML = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ titulo }} | IWG Technological Solutions</title>

<style>
* { box-sizing: border-box; }

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
    margin: 0 auto 15px auto;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: {{ fundo }};
    overflow: hidden;
    box-shadow: 0 4px 15px rgba(247, 192, 74, 0.2);
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
    letter-spacing: 0.5px;
}

.sub-titulo {
    color: #9CA3AF;
    font-size: 12px;
    font-style: italic;
    margin-bottom: 6px;
}

.sub-marca {
    color: #9CA3AF;
    font-size: 11px;
}

nav {
    display: flex;
    justify-content: center;
    flex-wrap: wrap;
    gap: 12px;
    padding: 16px;
    background: #080C38;
    border-bottom: 1px solid {{ borda }};
}

nav a {
    color: {{ ouro }};
    font-size: 14px;
    padding: 8px 12px;
}

.container {
    width: 92%;
    max-width: 1150px;
    margin: 30px auto;
}

.banner {
    padding: 45px 25px;
    background: linear-gradient(135deg, #0A0E45, #111A55);
    border: 1px solid {{ borda }};
    border-radius: 16px;
    text-align: center;
    margin-bottom: 35px;
}

.banner h2 {
    color: {{ ouro }};
    font-size: 30px;
    margin-top: 0;
}

.banner p {
    color: #D1D5DB;
    line-height: 1.7;
}

.botao {
    display: inline-block;
    background: {{ ouro }};
    color: #020526;
    font-weight: bold;
    padding: 11px 18px;
    border: 0;
    border-radius: 7px;
    cursor: pointer;
    margin: 5px;
}

.botao-secundario {
    background: transparent;
    color: {{ ouro }};
    border: 1px solid {{ ouro }};
}

h2.secao {
    color: {{ ouro }};
    margin: 30px 0 18px;
}

.filtros {
    display: flex;
    flex-wrap: wrap;
    gap: 9px;
    margin-bottom: 20px;
}

.filtros a {
    padding: 9px 13px;
    border: 1px solid {{ borda }};
    border-radius: 20px;
    color: white;
    font-size: 13px;
}

.filtros a:hover {
    background: {{ ouro }};
    color: #020526;
}

.grade {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
    gap: 20px;
}

.produto {
    background: {{ card }};
    border: 1px solid {{ borda }};
    border-radius: 13px;
    overflow: hidden;
    padding-bottom: 18px;
}

.produto img {
    width: 100%;
    height: 190px;
    object-fit: cover;
    background: #101641;
}

.sem-imagem {
    height: 190px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: {{ ouro }};
    font-size: 45px;
}

.produto-conteudo { padding: 15px; }

.produto h3 { color: {{ ouro }}; }

.produto p {
    color: #C4C8D5;
    line-height: 1.5;
    font-size: 14px;
}

.preco {
    font-size: 20px;
    color: {{ ouro }};
    font-weight: bold;
    margin: 14px 0;
}

.formulario {
    background: {{ card }};
    border: 1px solid {{ borda }};
    padding: 24px;
    border-radius: 12px;
    max-width: 650px;
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
}

td, th {
    border-bottom: 1px solid {{ borda }};
    padding: 12px;
    text-align: left;
}

th { color: {{ ouro }}; }

.aviso {
    padding: 12px;
    background: #111A55;
    border-radius: 8px;
    color: #D1D5DB;
    margin: 15px 0;
}

footer {
    text-align: center;
    padding: 30px 15px;
    color: #9CA3AF;
    border-top: 1px solid {{ borda }};
    margin-top: 50px;
    font-size: 13px;
}

.flash {
    background: #182653;
    border: 1px solid {{ ouro }};
    padding: 12px;
    border-radius: 8px;
    margin: 12px 0;
    color: white;
}

@media(max-width: 600px) {
    .banner h2 { font-size: 23px; }
    header { padding: 25px 10px; }
    .container { width: 94%; }
    td, th { padding: 7px; font-size: 12px; }
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
    <div class="sub-titulo">(Analista de sistemas e engenheiro de software)</div>
    <div class="sub-marca">IWG Technological Solutions • Catálogo Oficial</div>
</header>

<nav>
    <a href="{{ url_for('inicio') }}">Início</a>
    <a href="{{ url_for('inicio') }}#catalogo">Catálogo</a>
    <a href="{{ url_for('inicio') }}#servicos">Serviços</a>
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
      <a href="https://instagram.com/iulumozart" target="_blank">Instagram</a> |
      <a href="https://linkedin.com/in/iuluwayner" target="_blank">LinkedIn</a> |
      <a href="https://wa.me/{{ whatsapp }}" target="_blank">WhatsApp</a>
    </p>
    <p>© IWG Technological Solutions</p>
    <a href="{{ url_for('admin_login') }}">Área administrativa</a>
</footer>

</body>
</html>
"""


def render_site(conteudo, titulo="Início"):
    quantidade = sum(session.get("carrinho", {}).values())

    return render_template_string(
        BASE_HTML,
        conteudo=conteudo,
        titulo=titulo,
        fundo=AZUL_FUNDO,
        ouro=COR_OURO,
        card=COR_CARD,
        borda=COR_BORDA,
        whatsapp=WHATSAPP,
        quantidade_carrinho=quantidade
    )


# =========================================================
# SITE PÚBLICO
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
        <h2>Tecnologia que transforma ideias em soluções.</h2>
        <p>
        Bem-vindo à IWG Technological Solutions.
        Soluções digitais, desenvolvimento de software,
        eletrônicos e importações.
        </p>
        <a class="botao" href="#catalogo">Conheça nosso catálogo</a>
        <a class="botao botao-secundario"
           href="https://wa.me/{{ whatsapp }}">Fale conosco</a>
    </section>

    <section id="servicos">
        <h2 class="secao">Nossas soluções</h2>
        <div class="grade">
            <div class="produto produto-conteudo">
                <h3>Desenvolvimento de Software</h3>
                <p>Criação de sistemas, automações e soluções personalizadas.</p>
            </div>
            <div class="produto produto-conteudo">
                <h3>Consultoria em Tecnologia</h3>
                <p>Arquitetura de sistemas e orientação tecnológica.</p>
            </div>
            <div class="produto produto-conteudo">
                <h3>Eletrônicos e Importações</h3>
                <p>Produtos e acessórios tecnológicos selecionados.</p>
            </div>
        </div>
    </section>

    <section id="catalogo">
        <h2 class="secao">Catálogo IWG</h2>

        <div class="filtros">
            <a href="{{ url_for('inicio') }}">Todos</a>
            {% for cat in categorias %}
            <a href="{{ url_for('inicio', categoria=cat['categoria']) }}">
                {{ cat['categoria'] }}
            </a>
            {% endfor %}
        </div>

        <div class="grade">
        {% for p in produtos %}
            <article class="produto">
                {% if p['imagem'] %}
                    <img src="{{ url_for('static', filename='produtos/' + p['imagem']) }}"
                         alt="{{ p['nome'] }}">
                {% else %}
                    <div class="sem-imagem">IWG</div>
                {% endif %}

                <div class="produto-conteudo">
                    <small>{{ p['categoria'] }}</small>
                    <h3>{{ p['nome'] }}</h3>
                    <p>{{ p['descricao'] }}</p>
                    <div class="preco">{{ dinheiro(p['preco']) }}</div>

                    <a class="botao"
                       href="{{ url_for('produto', pid=p['id']) }}">
                       Ver detalhes
                    </a>

                    <form method="post"
                          action="{{ url_for('adicionar_carrinho', pid=p['id']) }}">
                        <button class="botao botao-secundario" type="submit">
                            Adicionar ao carrinho
                        </button>
                    </form>
                </div>
            </article>
        {% else %}
            <p>Nenhum produto cadastrado nesta categoria.</p>
        {% endfor %}
        </div>
    </section>

    <div class="aviso">
        Imagens e valores ilustrativos ou sujeitos à disponibilidade.
        Consulte nossa equipe antes de concluir sua compra.
    </div>
    """

    conteudo = render_template_string(
        html,
        produtos=produtos,
        categorias=categorias,
        dinheiro=dinheiro,
        whatsapp=WHATSAPP
    )

    return render_site(conteudo)


@app.route("/produto/<int:pid>")
def produto(pid):
    with conectar() as conn:
        p = conn.execute(
            "SELECT * FROM produtos WHERE id = ? AND ativo = 1",
            (pid,)
        ).fetchone()

    if not p:
        return redirect(url_for("inicio"))

    html = """
    <div class="formulario">
        {% if p['imagem'] %}
        <img style="width:100%;max-height:350px;object-fit:contain"
             src="{{ url_for('static', filename='produtos/' + p['imagem']) }}">
        {% endif %}

        <h2 style="color:{{ ouro }}">{{ p['nome'] }}</h2>
        <p>{{ p['descricao'] }}</p>
        <p>Categoria: {{ p['categoria'] }}</p>
        <div class="preco">{{ dinheiro(p['preco']) }}</div>

        <form method="post" action="{{ url_for('adicionar_carrinho', pid=p['id']) }}">
            <button class="botao">Adicionar ao carrinho</button>
        </form>

        <a class="botao botao-secundario" href="{{ url_for('inicio') }}">
            Voltar ao catálogo
        </a>
    </div>
    """

    conteudo = render_template_string(
        html, p=p, dinheiro=dinheiro, ouro=COR_OURO
    )

    return render_site(conteudo, p["nome"])


# =========================================================
# CARRINHO E PEDIDOS
# =========================================================

@app.route("/adicionar/<int:pid>", methods=["POST"])
def adicionar_carrinho(pid):
    with conectar() as conn:
        p = conn.execute(
            "SELECT id FROM produtos WHERE id = ? AND ativo = 1",
            (pid,)
        ).fetchone()

    if p:
        carrinho = session.get("carrinho", {})
        chave = str(pid)
        carrinho[chave] = carrinho.get(chave, 0) + 1
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
            p = conn.execute(
                "SELECT * FROM produtos WHERE id = ? AND ativo = 1",
                (pid,)
            ).fetchone()

            if p:
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
    <table>
        <tr>
            <th>Produto</th>
            <th>Qtd.</th>
            <th>Subtotal</th>
            <th></th>
        </tr>

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

    <h2 style="color:{{ ouro }}">Total: {{ dinheiro(total) }}</h2>

    <form method="post" action="{{ url_for('finalizar_pedido') }}">
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


@app.route("/remover-carrinho/<int:pid>")
def remover_carrinho(pid):
    carrinho = session.get("carrinho", {})
    carrinho.pop(str(pid), None)
    session["carrinho"] = carrinho
    return redirect(url_for("carrinho"))


@app.route("/finalizar", methods=["POST"])
def finalizar_pedido():
    nome = request.form.get("nome", "").strip()
    observacoes = request.form.get("observacoes", "").strip()

    if not nome:
        flash("Informe seu nome.")
        return redirect(url_for("carrinho"))

    itens = []
    total = 0

    with conectar() as conn:
        for pid, quantidade in session.get("carrinho", {}).items():
            p = conn.execute(
                "SELECT * FROM produtos WHERE id = ? AND ativo = 1",
                (pid,)
            ).fetchone()

            if p:
                subtotal = p["preco"] * quantidade
                total += subtotal
                itens.append(
                    f"{p['nome']} - {quantidade} unidade(s) - {dinheiro(subtotal)}"
                )

    if not itens:
        flash("Seu carrinho está vazio.")
        return redirect(url_for("carrinho"))

    mensagem = (
        "Olá! Gostaria de fazer um pedido na IWG.\\n\\n"
        f"Cliente: {nome}\\n\\n"
        + "\\n".join(itens)
        + f"\\n\\nTotal: {dinheiro(total)}"
        + f"\\nObservações: {observacoes}"
    )

    from urllib.parse import quote
    link = "https://wa.me/" + WHATSAPP + "?text=" + quote(mensagem)

    session["carrinho"] = {}

    return redirect(link)


# =========================================================
# ADMINISTRAÇÃO
# =========================================================

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "")
        senha = request.form.get("senha", "")

        with conectar() as conn:
            admin = conn.execute(
                "SELECT * FROM administradores WHERE usuario = ?",
                (usuario,)
            ).fetchone()

        if admin and check_password_hash(admin["senha"], senha):
            session["admin"] = True
            session["usuario"] = usuario
            return redirect(url_for("admin_painel"))

        flash("Usuário ou senha incorretos.")

    html = """
    <div class="formulario">
        <h2 style="color:{{ ouro }}">Acesso administrativo IWG</h2>

        <form method="post">
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


@app.route("/admin/painel")
@admin_required
def admin_painel():
    with conectar() as conn:
        produtos = conn.execute(
            "SELECT * FROM produtos ORDER BY id DESC"
        ).fetchall()

    html = """
    <h2 class="secao">Painel administrativo IWG</h2>

    <p>Bem-vindo, {{ session.get('usuario') }}!</p>

    <a class="botao" href="{{ url_for('admin_novo') }}">
        Novo produto
    </a>

    <a class="botao botao-secundario" href="{{ url_for('admin_senha') }}">
        Alterar senha
    </a>

    <a class="botao botao-secundario" href="{{ url_for('admin_sair') }}">
        Sair
    </a>

    <table>
        <tr>
            <th>Produto</th>
            <th>Preço</th>
            <th>Status</th>
            <th>Ações</th>
        </tr>

        {% for p in produtos %}
        <tr>
            <td>{{ p['nome'] }}</td>
            <td>{{ dinheiro(p['preco']) }}</td>
            <td>{{ 'Ativo' if p['ativo'] else 'Inativo' }}</td>
            <td>
                <a href="{{ url_for('admin_editar', pid=p['id']) }}">Editar</a>
                |
                <a href="{{ url_for('admin_alternar', pid=p['id']) }}">
                    Ativar/desativar
                </a>
                |
                <a href="{{ url_for('admin_excluir', pid=p['id']) }}"
                   onclick="return confirm('Excluir este produto?')">
                    Excluir
                </a>
            </td>
        </tr>
        {% endfor %}
    </table>
    """

    conteudo = render_template_string(
        html, produtos=produtos, dinheiro=dinheiro
    )

    return render_site(conteudo, "Painel administrativo")


def formulario_produto(p=None):
    html = """
    <div class="formulario">
        <h2 style="color:{{ ouro }}">{{ titulo }}</h2>

        <form method="post" enctype="multipart/form-data">
            <label>Nome do produto ou serviço</label>
            <input name="nome" required value="{{ p['nome'] if p else '' }}">

            <label>Categoria</label>
            <input name="categoria"
                   value="{{ p['categoria'] if p else 'Produtos' }}">

            <label>Descrição</label>
            <textarea name="descricao" rows="4">{{ p['descricao'] if p else '' }}</textarea>

            <label>Preço em reais</label>
            <input name="preco" type="number" step="0.01" min="0"
                   required value="{{ p['preco'] if p else '' }}">

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
        html, p=p, titulo="Editar produto" if p else "Novo produto",
        ouro=COR_OURO
    )


@app.route("/admin/novo", methods=["GET", "POST"])
@admin_required
def admin_novo():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        categoria = request.form.get("categoria", "Produtos").strip()
        descricao = request.form.get("descricao", "").strip()

        try:
            preco = float(request.form.get("preco", "0").replace(",", "."))
        except ValueError:
            preco = -1

        if not nome or preco < 0:
            flash("Confira o nome e o preço.")
            return redirect(url_for("admin_novo"))

        imagem = salvar_imagem(request.files.get("imagem"))

        with conectar() as conn:
            conn.execute("""
                INSERT INTO produtos
                (nome, categoria, descricao, preco, imagem)
                VALUES (?, ?, ?, ?, ?)
            """, (nome, categoria, descricao, preco, imagem))

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
        nome = request.form.get("nome", "").strip()
        categoria = request.form.get("categoria", "Produtos").strip()
        descricao = request.form.get("descricao", "").strip()

        try:
            preco = float(request.form.get("preco", "0").replace(",", "."))
        except ValueError:
            preco = -1

        if not nome or preco < 0:
            flash("Confira o nome e o preço.")
            return redirect(url_for("admin_editar", pid=pid))

        imagem = p["imagem"]
        novo_arquivo = request.files.get("imagem")

        if novo_arquivo and novo_arquivo.filename:
            nova_imagem = salvar_imagem(novo_arquivo)
            if nova_imagem:
                excluir_imagem(imagem)
                imagem = nova_imagem

        with conectar() as conn:
            conn.execute("""
                UPDATE produtos
                SET nome=?, categoria=?, descricao=?, preco=?, imagem=?
                WHERE id=?
            """, (nome, categoria, descricao, preco, imagem, pid))

        flash("Produto atualizado!")
        return redirect(url_for("admin_painel"))

    return render_site(formulario_produto(p), "Editar produto")


@app.route("/admin/alternar/<int:pid>")
@admin_required
def admin_alternar(pid):
    with conectar() as conn:
        conn.execute("""
            UPDATE produtos SET ativo = CASE WHEN ativo = 1 THEN 0 ELSE 1 END
            WHERE id = ?
        """, (pid,))

    return redirect(url_for("admin_painel"))


@app.route("/admin/excluir/<int:pid>")
@admin_required
def admin_excluir(pid):
    with conectar() as conn:
        p = conn.execute(
            "SELECT imagem FROM produtos WHERE id = ?", (pid,)
        ).fetchone()

        if p:
            excluir_imagem(p["imagem"])
            conn.execute("DELETE FROM produtos WHERE id = ?", (pid,))

    flash("Produto excluído.")
    return redirect(url_for("admin_painel"))


@app.route("/admin/senha", methods=["GET", "POST"])
@admin_required
def admin_senha():
    if request.method == "POST":
        atual = request.form.get("atual", "")
        nova = request.form.get("nova", "")
        confirmar = request.form.get("confirmar", "")

        with conectar() as conn:
            admin = conn.execute(
                "SELECT * FROM administradores WHERE usuario = ?",
                (session.get("usuario"),)
            ).fetchone()

            if not check_password_hash(admin["senha"], atual):
                flash("Senha atual incorreta.")
            elif len(nova) < 8:
                flash("A nova senha deve ter pelo menos 8 caracteres.")
            elif nova != confirmar:
                flash("As senhas não conferem.")
            else:
                conn.execute(
                    "UPDATE administradores SET senha = ? WHERE id = ?",
                    (generate_password_hash(nova), admin["id"])
                )
                flash("Senha alterada com sucesso!")
                return redirect(url_for("admin_painel"))

    html = """
    <div class="formulario">
        <h2 style="color:{{ ouro }}">Alterar senha</h2>

        <form method="post">
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


@app.route("/admin/sair")
def admin_sair():
    session.clear()
    return redirect(url_for("inicio"))


# =========================================================
# ERROS E EXECUÇÃO
# =========================================================

@app.errorhandler(413)
def arquivo_grande(e):
    flash("A imagem ultrapassa o limite de 5 MB.")
    return redirect(request.referrer or url_for("inicio"))


@app.errorhandler(404)
def pagina_nao_encontrada(e):
    return render_site(
        "<h2>Página não encontrada.</h2><a href='/'>Voltar ao início</a>",
        "Página não encontrada"
    ), 404


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8550)),
        debug=False
    )
