
import os
import sqlite3
import uuid
from functools import wraps
from urllib.parse import quote

from flask import (
    Flask, render_template_string, request, redirect,
    url_for, session, send_from_directory, flash,
    get_flashed_messages, abort
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from markupsafe import escape


# =========================================================
# CONFIGURACOES
# =========================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "IWG_SECRET_KEY",
    "iwg_app_ios_chave_secreta_troque_antes_de_publicar"
)

app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

AZUL_FUNDO = "#020526"
COR_OURO = "#F7C04A"
COR_CARD = "#0A0E45"
COR_BORDA = "#3A4F7C"

WHATSAPP = "5527999243025"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BANCO = os.path.join(BASE_DIR, "iwg_catalogo.db")

PASTA_ASSETS = os.path.join(BASE_DIR, "assets")
PASTA_PRODUTOS = os.path.join(PASTA_ASSETS, "produtos")

EXTENSOES_PERMITIDAS = {"jpg", "jpeg", "png", "webp"}

USUARIO_ADMIN_INICIAL = "iulu"
SENHA_ADMIN_INICIAL = "iulu"

STATUS_PEDIDOS = [
    "Aguardando confirmação no WhatsApp",
    "Em atendimento",
    "Aguardando pagamento",
    "Pago",
    "Enviado",
    "Concluído",
    "Cancelado"
]

os.makedirs(PASTA_PRODUTOS, exist_ok=True)
os.makedirs(PASTA_ASSETS, exist_ok=True)


# =========================================================
# IMAGENS PROVISORIAS
# =========================================================

IMAGENS_PROVISORIAS = {
    "audio": (
        "https://images.unsplash.com/"
        "photo-1505740420928-5e560c06d30e"
        "?auto=format&fit=crop&w=900&q=85"
    ),
    "acessorios": (
        "https://images.unsplash.com/"
        "photo-1583394838336-acd977736f90"
        "?auto=format&fit=crop&w=900&q=85"
    ),
    "eletronicos": (
        "https://images.unsplash.com/"
        "photo-1511707171634-5f897ff02aa9"
        "?auto=format&fit=crop&w=900&q=85"
    ),
    "software": (
        "https://images.unsplash.com/"
        "photo-1498050108023-c5249f4df085"
        "?auto=format&fit=crop&w=900&q=85"
    ),
    "consultoria": (
        "https://images.unsplash.com/"
        "photo-1521737711867-e3b97375f902"
        "?auto=format&fit=crop&w=900&q=85"
    ),
    "educacao": (
        "https://images.unsplash.com/"
        "photo-1517842645767-c639042777db"
        "?auto=format&fit=crop&w=900&q=85"
    ),
    "geral": (
        "https://images.unsplash.com/"
        "photo-1519389950473-47ba0277781c"
        "?auto=format&fit=crop&w=900&q=85"
    )
}


def imagem_provisoria(categoria, nome=""):
    texto = f"{categoria or ''} {nome or ''}".lower()

    if any(p in texto for p in ["airpod", "fone", "audio", "áudio"]):
        return IMAGENS_PROVISORIAS["audio"]

    if any(p in texto for p in [
        "adaptador", "cabo", "acessorio", "acessório", "carregador"
    ]):
        return IMAGENS_PROVISORIAS["acessorios"]

    if any(p in texto for p in ["smartphone", "celular", "tablet"]):
        return IMAGENS_PROVISORIAS["eletronicos"]

    if any(p in texto for p in [
        "software", "licenca", "licença", "python",
        "automacao", "automação"
    ]):
        return IMAGENS_PROVISORIAS["software"]

    if any(p in texto for p in ["consultoria", "servico", "serviço"]):
        return IMAGENS_PROVISORIAS["consultoria"]

    if any(p in texto for p in ["ebook", "educacao", "educação", "livro"]):
        return IMAGENS_PROVISORIAS["educacao"]

    if any(p in texto for p in [
        "eletronico", "eletrônico", "importacao", "importação"
    ]):
        return IMAGENS_PROVISORIAS["eletronicos"]

    return IMAGENS_PROVISORIAS["geral"]


# =========================================================
# BANCO DE DADOS E MIGRACOES
# =========================================================

def conectar():
    conexao = sqlite3.connect(BANCO)
    conexao.row_factory = sqlite3.Row
    return conexao


def adicionar_coluna_se_nao_existir(db, tabela, coluna, definicao):
    colunas = [
        item["name"]
        for item in db.execute(
            f"PRAGMA table_info({tabela})"
        ).fetchall()
    ]

    if coluna not in colunas:
        db.execute(
            f"ALTER TABLE {tabela} ADD COLUMN {coluna} {definicao}"
        )


def iniciar_banco():
    with conectar() as db:

        db.execute("""
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                preco REAL NOT NULL,
                descricao TEXT,
                categoria TEXT,
                ativo INTEGER DEFAULT 1
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS administradores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE NOT NULL,
                senha_hash TEXT NOT NULL
            )
        """)

        adicionar_coluna_se_nao_existir(
            db, "produtos", "imagem", "TEXT"
        )

        db.execute("""
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                telefone TEXT NOT NULL,
                cep TEXT NOT NULL,
                rua TEXT NOT NULL,
                numero TEXT NOT NULL,
                complemento TEXT,
                bairro TEXT NOT NULL,
                cidade TEXT NOT NULL,
                estado TEXT NOT NULL,
                observacoes TEXT,
                itens TEXT NOT NULL,
                total REAL NOT NULL,
                status TEXT NOT NULL,
                codigo_rastreio TEXT,
                data_criacao TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migracoes seguras para bancos ja existentes.
        adicionar_coluna_se_nao_existir(
            db, "pedidos", "complemento", "TEXT"
        )
        adicionar_coluna_se_nao_existir(
            db, "pedidos", "observacoes", "TEXT"
        )
        adicionar_coluna_se_nao_existir(
            db, "pedidos", "codigo_rastreio", "TEXT"
        )
        adicionar_coluna_se_nao_existir(
            db, "pedidos", "data_criacao",
            "TEXT DEFAULT CURRENT_TIMESTAMP"
        )

        quantidade = db.execute(
            "SELECT COUNT(*) FROM administradores"
        ).fetchone()[0]

        if quantidade == 0:
            senha_hash = generate_password_hash(
                SENHA_ADMIN_INICIAL,
                method="pbkdf2:sha256"
            )

            db.execute("""
                INSERT INTO administradores (usuario, senha_hash)
                VALUES (?, ?)
            """, (USUARIO_ADMIN_INICIAL, senha_hash))

        quantidade_produtos = db.execute(
            "SELECT COUNT(*) FROM produtos"
        ).fetchone()[0]

        if quantidade_produtos == 0:
            produtos_iniciais = [
                (
                    "Automação Python sob Medida",
                    1500.00,
                    "Desenvolvimento de scripts personalizados para automação.",
                    "Softwares", 1, IMAGENS_PROVISORIAS["software"]
                ),
                (
                    "Licença Acesso IWG Core",
                    850.00,
                    "Soluções digitais e acesso a ferramentas de software.",
                    "Licenças", 1, IMAGENS_PROVISORIAS["software"]
                ),
                (
                    "Consultoria em Arquitetura",
                    2500.00,
                    "Consultoria técnica em sistemas e arquitetura de software.",
                    "Consultoria", 1, IMAGENS_PROVISORIAS["consultoria"]
                ),
                (
                    "Kit E-books Técnicos",
                    120.00,
                    "Materiais digitais e conteúdos técnicos.",
                    "Educação", 1, IMAGENS_PROVISORIAS["educacao"]
                ),
                (
                    "Adaptador Lightning OTG",
                    45.00,
                    "Acessório eletrônico para dispositivos compatíveis.",
                    "Acessórios", 1, IMAGENS_PROVISORIAS["acessorios"]
                ),
                (
                    "Fones Apple AirPods",
                    199.00,
                    "Imagem ilustrativa de fones sem fio. Produto sujeito à confirmação de estoque.",
                    "Áudio", 1, IMAGENS_PROVISORIAS["audio"]
                )
            ]

            db.executemany("""
                INSERT INTO produtos
                (nome, preco, descricao, categoria, ativo, imagem)
                VALUES (?, ?, ?, ?, ?, ?)
            """, produtos_iniciais)

        else:
            produtos = db.execute("""
                SELECT id, nome, categoria
                FROM produtos
                WHERE imagem IS NULL OR imagem = ''
            """).fetchall()

            for produto in produtos:
                db.execute("""
                    UPDATE produtos SET imagem = ?
                    WHERE id = ?
                """, (
                    imagem_provisoria(
                        produto["categoria"], produto["nome"]
                    ),
                    produto["id"]
                ))


iniciar_banco()


# =========================================================
# FUNCOES AUXILIARES
# =========================================================

def formatar_preco(valor):
    return (
        f"{valor:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def converter_preco(valor):
    valor = str(valor or "").strip()
    valor = valor.replace("R$", "").replace(" ", "")

    if "," in valor:
        valor = valor.replace(".", "").replace(",", ".")

    return float(valor)


def buscar_produtos(apenas_ativos=False):
    with conectar() as db:
        if apenas_ativos:
            return db.execute("""
                SELECT * FROM produtos
                WHERE ativo = 1
                ORDER BY id DESC
            """).fetchall()

        return db.execute("""
            SELECT * FROM produtos
            ORDER BY id DESC
        """).fetchall()


def buscar_produto(pid):
    with conectar() as db:
        return db.execute("""
            SELECT * FROM produtos WHERE id = ?
        """, (pid,)).fetchone()


def buscar_categorias():
    with conectar() as db:
        return db.execute("""
            SELECT DISTINCT categoria
            FROM produtos
            WHERE ativo = 1
              AND categoria IS NOT NULL
              AND TRIM(categoria) != ''
            ORDER BY categoria
        """).fetchall()


def buscar_pedido(pid):
    with conectar() as db:
        return db.execute("""
            SELECT * FROM pedidos WHERE id = ?
        """, (pid,)).fetchone()


def administrador_obrigatorio(funcao):
    @wraps(funcao)
    def verificar(*args, **kwargs):
        if not session.get("admin_logado"):
            return redirect(url_for("admin_login"))
        return funcao(*args, **kwargs)
    return verificar


def salvar_imagem(arquivo):
    if not arquivo or not arquivo.filename:
        return None

    nome_original = secure_filename(arquivo.filename)

    if "." not in nome_original:
        raise ValueError("Arquivo sem extensão válida.")

    extensao = nome_original.rsplit(".", 1)[1].lower()

    if extensao not in EXTENSOES_PERMITIDAS:
        raise ValueError(
            "Formato não permitido. Use JPG, JPEG, PNG ou WEBP."
        )

    nome_final = f"{uuid.uuid4().hex}.{extensao}"
    caminho = os.path.join(PASTA_PRODUTOS, nome_final)
    arquivo.save(caminho)

    return f"produtos/{nome_final}"


def excluir_imagem_local(caminho):
    if not caminho:
        return

    caminho = str(caminho).replace("\\", "/")

    if not caminho.startswith("produtos/"):
        return

    nome = os.path.basename(caminho)
    arquivo = os.path.join(PASTA_PRODUTOS, nome)

    if os.path.isfile(arquivo):
        try:
            os.remove(arquivo)
        except OSError:
            pass


def obter_url_imagem(produto):
    imagem = produto["imagem"] or imagem_provisoria(
        produto["categoria"], produto["nome"]
    )

    if imagem.startswith("http://") or imagem.startswith("https://"):
        return imagem

    return url_for("servir_arquivos", filename=imagem)


def gerar_rodape():
    return f"""
    <div style="
        margin-top:40px;
        background:linear-gradient(135deg,{COR_CARD},#121858);
        border:1px solid {COR_OURO};
        border-radius:12px;
        padding:25px 20px;
        text-align:center;
        box-shadow:0 4px 15px rgba(247,192,74,.15);
    ">
        <h4 style="color:{COR_OURO};font-size:16px;margin-bottom:8px;">
            IWG Technological Solutions
        </h4>
        <p style="color:#D1D5DB;font-size:12px;line-height:1.7;">
            Tecnologia, inovação e soluções inteligentes.
            Produtos eletrônicos, importações e desenvolvimento de softwares.
        </p>
        <div style="
            font-size:11px;color:#9CA3AF;
            border-top:1px solid {COR_BORDA};
            padding-top:12px;margin-top:12px;
        ">
            © 2026 IWG — Todos os direitos reservados.
        </div>
    </div>
    """


def layout_admin(conteudo, titulo="Painel Administrativo"):
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{{ titulo }} - IWG</title>
        <style>
            * {
                box-sizing: border-box;
                font-family: -apple-system, BlinkMacSystemFont,
                'Segoe UI', Roboto, sans-serif;
            }
            body {
                margin: 0;
                padding: 20px;
                background: {{ fundo }};
                color: white;
            }
            .painel { max-width: 1000px; margin: 20px auto; }
            .cartao {
                background: {{ card }};
                border: 1px solid {{ borda }};
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 20px;
            }
            h1, h2, h3 { color: {{ ouro }}; }
            input, textarea, select {
                width: 100%;
                padding: 12px;
                margin: 7px 0 15px;
                border-radius: 7px;
                border: 1px solid {{ borda }};
                background: {{ fundo }};
                color: white;
                font-size: 14px;
            }
            input[type=file] { padding: 10px; }
            label { color: #D1D5DB; font-size: 13px; }
            button, .botao {
                display: inline-block;
                padding: 11px 15px;
                border: none;
                border-radius: 7px;
                background: {{ ouro }};
                color: {{ fundo }};
                font-weight: bold;
                text-decoration: none;
                cursor: pointer;
                font-size: 13px;
            }
            .secundario { background: {{ borda }}; color: white; }
            .perigo { background: #B91C1C; color: white; }
            .sucesso { color: #86EFAC; }
            .inativo { color: #FCA5A5; }
            .produto {
                border-bottom: 1px solid {{ borda }};
                padding: 15px 0;
            }
            .produto:last-child { border-bottom: none; }
            .acoes {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
                margin-top: 12px;
            }
            .mensagem {
                padding: 12px;
                background: #102B36;
                border: 1px solid #287A61;
                border-radius: 7px;
                margin-bottom: 15px;
            }
            .topo {
                display: flex;
                justify-content: space-between;
                align-items: center;
                flex-wrap: wrap;
                gap: 12px;
            }
            .miniatura {
                width: 105px;
                height: 85px;
                object-fit: cover;
                border-radius: 8px;
                border: 1px solid {{ borda }};
                background: {{ fundo }};
            }
            @media(max-width:600px) {
                body { padding: 10px; }
                .cartao { padding: 15px; }
            }
        </style>
    </head>
    <body>
        <main class="painel">
            {% if logado %}
            <div class="topo cartao">
                <div>
                    <h2>IWG Technological Solutions</h2>
                    <p>Área administrativa</p>
                </div>
                <div class="acoes">
                    <a class="botao secundario" href="{{ url_for('home') }}">Ver site</a>
                    <a class="botao secundario" href="{{ url_for('admin_pedidos') }}">Pedidos</a>
                    <a class="botao secundario" href="{{ url_for('admin_senha') }}">Alterar senha</a>
                    <a class="botao perigo" href="{{ url_for('admin_sair') }}">Sair</a>
                </div>
            </div>
            {% endif %}
            {% for mensagem in mensagens %}
                <div class="mensagem">{{ mensagem }}</div>
            {% endfor %}
            {{ conteudo | safe }}
        </main>
    </body>
    </html>
    """,
    titulo=titulo,
    conteudo=conteudo,
    fundo=AZUL_FUNDO,
    card=COR_CARD,
    borda=COR_BORDA,
    ouro=COR_OURO,
    logado=bool(session.get("admin_logado")),
    mensagens=get_flashed_messages()
    )


# =========================================================
# ESTILOS DO SITE
# =========================================================

ESTILOS_SITE = f"""
.container {{
    max-width:1100px;
    margin:20px auto;
    padding:0 15px;
}}
.banner-iwg {{
    position:relative;
    overflow:hidden;
    border:1px solid {COR_OURO};
    border-radius:15px;
    min-height:270px;
    padding:35px;
    margin-bottom:30px;
    background:
        linear-gradient(90deg,rgba(2,5,38,.97),rgba(10,14,69,.82)),
        url('{IMAGENS_PROVISORIAS["geral"]}');
    background-size:cover;
    background-position:center;
    display:flex;
    align-items:center;
}}
.banner-conteudo {{ max-width:650px; }}
.banner-selo {{
    color:{COR_OURO};
    font-size:11px;
    font-weight:bold;
    letter-spacing:2px;
    margin-bottom:12px;
}}
.banner-iwg h2 {{
    color:white;
    font-size:30px;
    line-height:1.2;
    margin-bottom:12px;
}}
.banner-iwg p {{
    color:#D1D5DB;
    font-size:14px;
    line-height:1.7;
    margin-bottom:20px;
}}
.botao-destaque {{
    display:inline-block;
    background:{COR_OURO};
    color:{AZUL_FUNDO};
    padding:13px 20px;
    border-radius:7px;
    text-decoration:none;
    font-size:12px;
    font-weight:bold;
}}
.botao-contorno {{
    display:inline-block;
    border:1px solid {COR_OURO};
    color:{COR_OURO};
    padding:12px 18px;
    border-radius:7px;
    text-decoration:none;
    font-size:12px;
    font-weight:bold;
    margin-left:8px;
}}
.titulo-secao {{
    color:{COR_OURO};
    font-size:15px;
    letter-spacing:.7px;
    margin:30px 0 15px;
}}
.grade-servicos {{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
    gap:14px;
    margin-bottom:30px;
}}
.servico-card {{
    background:linear-gradient(145deg,{COR_CARD},#10164D);
    border:1px solid {COR_BORDA};
    border-radius:12px;
    padding:20px;
    min-height:150px;
}}
.servico-icone {{ font-size:27px; margin-bottom:12px; }}
.servico-card h3 {{
    color:{COR_OURO};
    font-size:14px;
    margin-bottom:8px;
}}
.servico-card p {{
    color:#B8C0D4;
    font-size:12px;
    line-height:1.6;
}}
.filtros {{
    display:flex;
    flex-wrap:wrap;
    gap:8px;
    margin:15px 0 20px;
}}
.filtro {{
    display:inline-block;
    padding:9px 14px;
    border:1px solid {COR_BORDA};
    border-radius:20px;
    color:#D1D5DB;
    text-decoration:none;
    font-size:11px;
    background:{COR_CARD};
}}
.filtro.ativo {{
    background:{COR_OURO};
    border-color:{COR_OURO};
    color:{AZUL_FUNDO};
    font-weight:bold;
}}
.grid-produtos {{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(240px,1fr));
    gap:15px;
    margin-top:15px;
}}
.card-produto {{
    background:{COR_CARD};
    border:1px solid {COR_BORDA};
    border-radius:12px;
    overflow:hidden;
    display:flex;
    flex-direction:column;
    transition:transform .2s,border-color .2s;
}}
.card-produto:hover {{
    transform:translateY(-3px);
    border-color:{COR_OURO};
}}
.card-produto img {{
    width:100%;
    height:190px;
    object-fit:cover;
    background:{AZUL_FUNDO};
}}
.produto-conteudo {{
    padding:15px;
    display:flex;
    flex-direction:column;
    flex:1;
}}
.produto-categoria {{
    display:inline-block;
    align-self:flex-start;
    background:{COR_BORDA};
    color:{COR_OURO};
    font-size:9px;
    padding:4px 8px;
    border-radius:4px;
    font-weight:bold;
}}
.produto-conteudo h3 {{
    color:white;
    font-size:15px;
    margin:10px 0 7px;
}}
.produto-descricao {{
    color:#9CA3AF;
    font-size:12px;
    line-height:1.5;
    margin-bottom:15px;
}}
.produto-preco {{
    color:{COR_OURO};
    font-weight:bold;
    font-size:17px;
    margin:10px 0 12px;
}}
.botao-produto {{
    display:block;
    width:100%;
    text-align:center;
    background:{COR_OURO};
    color:{AZUL_FUNDO};
    border:0;
    padding:11px;
    border-radius:6px;
    font-weight:bold;
    font-size:12px;
    text-decoration:none;
    cursor:pointer;
}}
.botao-detalhes {{
    display:block;
    width:100%;
    text-align:center;
    color:{COR_OURO};
    border:1px solid {COR_OURO};
    padding:10px;
    border-radius:6px;
    font-weight:bold;
    font-size:12px;
    text-decoration:none;
    margin-bottom:8px;
}}
.lista-secao {{
    background-color:{COR_CARD};
    border:1px solid {COR_BORDA};
    border-radius:12px;
    overflow:hidden;
    margin-bottom:25px;
}}
.item-lista {{
    padding:14px 20px;
    border-bottom:1px solid {COR_BORDA};
    display:flex;
    justify-content:space-between;
    align-items:center;
    text-decoration:none;
    color:white;
}}
.item-lista:last-child {{ border-bottom:none; }}
@media(max-width:600px) {{
    .banner-iwg {{ min-height:290px; padding:24px 19px; }}
    .banner-iwg h2 {{ font-size:24px; }}
    .banner-iwg p {{ font-size:12px; }}
    .botao-contorno {{ margin:9px 0 0; }}
    .grid-produtos {{
        grid-template-columns:repeat(2,minmax(0,1fr));
        gap:10px;
    }}
    .card-produto img {{ height:135px; }}
    .produto-conteudo {{ padding:10px; }}
    .produto-conteudo h3 {{ font-size:12px; }}
    .produto-descricao {{ font-size:10px; }}
    .produto-preco {{ font-size:14px; }}
}}
"""


# =========================================================
# CABECALHO ORIGINAL
# =========================================================

CABECALHO_ORIGINAL = """
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
"""


# =========================================================
# PAGINA PRINCIPAL
# =========================================================

@app.route("/")
def home():
    produtos = buscar_produtos(apenas_ativos=True)
    categorias = buscar_categorias()

    categoria_selecionada = request.args.get(
        "categoria", ""
    ).strip()

    if categoria_selecionada:
        produtos = [
            p for p in produtos
            if (p["categoria"] or "").lower()
            == categoria_selecionada.lower()
        ]

    carrinho = session.get("carrinho", {})
    total_itens = sum(carrinho.values())

    topo_carrinho = ""

    if total_itens > 0:
        topo_carrinho = f"""
        <div style="text-align:right;margin-bottom:15px;">
            <a href="/carrinho" style="
                background-color:{COR_CARD};
                border:1px solid {COR_OURO};
                color:{COR_OURO};
                padding:10px 20px;
                border-radius:8px;
                text-decoration:none;
                font-weight:bold;
                font-size:13px;
                display:inline-block;">
                🛒 Ver Meu Carrinho ({total_itens} itens)
            </a>
        </div>
        """

    filtros_html = f"""
        <a class="filtro {'ativo' if not categoria_selecionada else ''}"
           href="/">Todos os produtos</a>
    """

    for categoria in categorias:
        nome_categoria = categoria["categoria"]
        ativo = (
            categoria_selecionada.lower()
            == nome_categoria.lower()
        )

        filtros_html += f"""
        <a class="filtro {'ativo' if ativo else ''}"
           href="/?categoria={quote(nome_categoria)}">
           {escape(nome_categoria)}
        </a>
        """

    cards_html = ""

    for p in produtos:
        imagem_url = obter_url_imagem(p)

        cards_html += f"""
        <div class="card-produto">
            <a href="/produto/{p['id']}" style="display:block;">
                <img src="{escape(imagem_url)}"
                     alt="{escape(p['nome'])}"
                     loading="lazy"
                     onerror="this.onerror=null;this.src='{IMAGENS_PROVISORIAS['geral']}';">
            </a>
            <div class="produto-conteudo">
                <span class="produto-categoria">
                    {escape(p['categoria'] or 'Geral')}
                </span>
                <h3>{escape(p['nome'])}</h3>
                <p class="produto-descricao">
                    {escape(p['descricao'] or '')}
                </p>
                <div style="margin-top:auto;">
                    <div class="produto-preco">
                        R$ {formatar_preco(p['preco'])}
                    </div>
                    <a class="botao-detalhes"
                       href="/produto/{p['id']}">
                        Ver detalhes
                    </a>
                    <form action="/adicionar/{p['id']}" method="POST">
                        <button class="botao-produto" type="submit">
                            Adicionar ao Carrinho
                        </button>
                    </form>
                </div>
            </div>
        </div>
        """

    if not produtos:
        cards_html = """
        <p style="color:#9CA3AF;padding:20px 0;">
            Nenhum produto encontrado nesta categoria.
            <a href="/" style="color:#F7C04A;">Ver todos os produtos</a>
        </p>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>IWG Technological Solutions</title>
        <style>
            * {{
                margin:0;
                padding:0;
                box-sizing:border-box;
                font-family:-apple-system,BlinkMacSystemFont,
                'Segoe UI',Roboto,sans-serif;
            }}
            body {{
                background-color:{AZUL_FUNDO};
                color:#ffffff;
                padding-bottom:30px;
            }}
            header {{
                text-align:center;
                padding:35px 20px;
                background-color:{COR_CARD};
                border-bottom:1px solid {COR_BORDA};
            }}
            .avatar {{
                width:140px;
                height:140px;
                border-radius:50%;
                border:3px solid {COR_OURO};
                margin:0 auto 15px auto;
                display:flex;
                align-items:center;
                justify-content:center;
                background-color:{AZUL_FUNDO};
                overflow:hidden;
                box-shadow:0 4px 15px rgba(247,192,74,.2);
            }}
            .avatar img {{
                width:100%;
                height:100%;
                object-fit:cover;
            }}
            h1 {{
                color:{COR_OURO};
                font-size:20px;
                margin-bottom:4px;
                text-transform:uppercase;
                letter-spacing:.5px;
            }}
            .sub-titulo {{
                color:#9CA3AF;
                font-size:12px;
                font-style:italic;
                margin-bottom:6px;
            }}
            .sub-marca {{ color:#9CA3AF; font-size:11px; }}
            {ESTILOS_SITE}
        </style>
    </head>
    <body>
        {CABECALHO_ORIGINAL}
        <div class="container">

            <section class="banner-iwg">
                <div class="banner-conteudo">
                    <div class="banner-selo">
                        TECNOLOGIA • INOVAÇÃO • SOLUÇÕES
                    </div>
                    <h2> Tecnologia que conecta você ao futuro.</h2>
                    <p>
                        Produtos eletrônicos, importações,
                        desenvolvimento de softwares e soluções
                        tecnológicas para pessoas e empresas.
                    </p>
                    <a class="botao-destaque" href="#catalogo">
                        CONHECER CATÁLOGO
                    </a>
                    <a class="botao-contorno"
                       href="https://wa.me/{WHATSAPP}"
                       target="_blank" rel="noopener">
                        FALAR COM A IWG
                    </a>
                </div>
            </section>

            <h3 class="titulo-secao">CANAIS & REDES SOCIAIS</h3>
            <div class="lista-secao">
                <a href="https://wa.me/{WHATSAPP}"
                   target="_blank" rel="noopener" class="item-lista">
                    <span>💬 WhatsApp Oficial</span><span>➔</span>
                </a>
                <a href="https://www.instagram.com/iulumozart"
                   target="_blank" rel="noopener" class="item-lista">
                    <span>📸 Instagram</span><span>➔</span>
                </a>
                <a href="https://www.linkedin.com/in/iuluwayner"
                   target="_blank" rel="noopener" class="item-lista">
                    <span>💼 LinkedIn Profissional</span><span>➔</span>
                </a>
                <a href="https://www.youtube.com/channel/UC8Z1DSRn3j5Rj4zMuy5sXIQ"
                   target="_blank" rel="noopener" class="item-lista">
                    <span>🔴 Canal YouTube</span><span>➔</span>
                </a>
            </div>

            <h3 class="titulo-secao">SOLUÇÕES TECNOLÓGICAS IWG</h3>
            <div class="grade-servicos">
                <div class="servico-card">
                    <div class="servico-icone">💻</div>
                    <h3>Desenvolvimento de Softwares</h3>
                    <p>Criação de sistemas, aplicações, automações e soluções digitais sob medida.</p>
                </div>
                <div class="servico-card">
                    <div class="servico-icone">🌐</div>
                    <h3>Importações</h3>
                    <p>Produtos e acessórios tecnológicos, com atendimento e consulta de disponibilidade.</p>
                </div>
                <div class="servico-card">
                    <div class="servico-icone">📱</div>
                    <h3>Eletrônicos e Acessórios</h3>
                    <p>Catálogo de produtos eletrônicos, acessórios e soluções para o dia a dia.</p>
                </div>
                <div class="servico-card">
                    <div class="servico-icone">⚙️</div>
                    <h3>Consultoria em Tecnologia</h3>
                    <p>Orientação técnica, arquitetura de sistemas e planejamento de projetos digitais.</p>
                </div>
            </div>

            {topo_carrinho}

            <section id="catalogo">
                <h3 class="titulo-secao">
                    CATÁLOGO DE PRODUTOS E SOLUÇÕES
                </h3>
                <p style="color:#9CA3AF;font-size:11px;margin-bottom:12px;">
                    Imagens ilustrativas. Consulte disponibilidade,
                    estoque e condições antes de concluir seu pedido.
                </p>
                <div class="filtros">{filtros_html}</div>
                <div class="grid-produtos">{cards_html}</div>
            </section>

            {gerar_rodape()}
        </div>
    </body>
    </html>
    """

    return render_template_string(html)


# =========================================================
# PRODUTO INDIVIDUAL
# =========================================================

@app.route("/produto/<int:pid>")
def pagina_produto(pid):
    produto = buscar_produto(pid)

    if not produto or not produto["ativo"]:
        flash("Produto não encontrado ou indisponível.")
        return redirect(url_for("home"))

    imagem_url = obter_url_imagem(produto)

    mensagem = (
        f"Olá! Tenho interesse no produto: {produto['nome']} "
        f"- R$ {formatar_preco(produto['preco'])}. "
        "Gostaria de mais informações."
    )

    whatsapp_url = (
        f"https://wa.me/{WHATSAPP}?text={quote(mensagem)}"
    )

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{escape(produto['nome'])} - IWG</title>
        <style>
            * {{ box-sizing:border-box; font-family:Arial,sans-serif; }}
            body {{ margin:0; padding:20px; background:{AZUL_FUNDO}; color:white; }}
            .detalhe {{
                max-width:950px; margin:30px auto;
                display:grid; grid-template-columns:1fr 1fr;
                gap:25px; align-items:center;
                background:{COR_CARD}; border:1px solid {COR_BORDA};
                border-radius:15px; padding:20px;
            }}
            .detalhe img {{
                width:100%; border-radius:10px;
                object-fit:cover; max-height:420px;
            }}
            .detalhe h1 {{ color:{COR_OURO}; font-size:25px; margin:15px 0; }}
            .descricao {{ color:#B8C0D4; font-size:14px; line-height:1.8; margin:15px 0; }}
            .preco {{ color:{COR_OURO}; font-size:25px; font-weight:bold; margin:20px 0; }}
            .botao {{
                display:block; text-align:center; padding:13px;
                border-radius:7px; background:{COR_OURO};
                color:{AZUL_FUNDO}; text-decoration:none;
                font-weight:bold; margin-top:10px;
            }}
            .botao-sec {{
                display:block; text-align:center; padding:13px;
                border:1px solid {COR_OURO}; color:{COR_OURO};
                text-decoration:none; border-radius:7px; margin-top:10px;
            }}
            @media(max-width:650px) {{
                .detalhe {{ grid-template-columns:1fr; }}
                .detalhe h1 {{ font-size:21px; }}
            }}
        </style>
    </head>
    <body>
        <div style="max-width:950px;margin:10px auto;">
            <a href="/" style="color:{COR_OURO};text-decoration:none;">
                ← Voltar ao catálogo IWG
            </a>
        </div>
        <main class="detalhe">
            <div>
                <img src="{escape(imagem_url)}"
                     alt="{escape(produto['nome'])}"
                     onerror="this.onerror=null;this.src='{IMAGENS_PROVISORIAS['geral']}';">
            </div>
            <div>
                <span style="background:{COR_BORDA};color:{COR_OURO};padding:6px 10px;border-radius:5px;font-size:11px;">
                    {escape(produto['categoria'] or 'Geral')}
                </span>
                <h1>{escape(produto['nome'])}</h1>
                <p class="descricao">{escape(produto['descricao'] or '')}</p>
                <div class="preco">R$ {formatar_preco(produto['preco'])}</div>
                <form action="/adicionar/{produto['id']}" method="POST">
                    <button type="submit" class="botao"
                            style="width:100%;border:0;cursor:pointer;">
                        Adicionar ao Carrinho
                    </button>
                </form>
                <a class="botao-sec" href="{whatsapp_url}"
                   target="_blank" rel="noopener">
                    Consultar pelo WhatsApp
                </a>
                <p style="color:#9CA3AF;font-size:10px;margin-top:15px;line-height:1.6;">
                    Imagens ilustrativas. Consulte disponibilidade,
                    estoque e condições comerciais.
                </p>
            </div>
        </main>
        {gerar_rodape()}
    </body>
    </html>
    """

    return render_template_string(html)


# =========================================================
# LOGIN ADMINISTRATIVO
# =========================================================

@app.route("/admin", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logado"):
        return redirect(url_for("admin_painel"))

    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "")

        with conectar() as db:
            admin = db.execute("""
                SELECT * FROM administradores
                WHERE usuario = ?
            """, (usuario,)).fetchone()

        if admin and check_password_hash(admin["senha_hash"], senha):
            session.clear()
            session["admin_logado"] = True
            session["admin_usuario"] = admin["usuario"]
            flash("Login realizado com sucesso!")
            return redirect(url_for("admin_painel"))

        flash("Usuário ou senha incorretos.")

    conteudo = f"""
    <div class="cartao" style="max-width:420px;margin:70px auto;">
        <div style="text-align:center;margin-bottom:25px;">
            <h1>IWG</h1>
            <h2>Painel Administrativo</h2>
            <p style="color:#9CA3AF;">Entre para gerenciar seu catálogo.</p>
        </div>
        <form method="POST">
            <label>Usuário</label>
            <input type="text" name="usuario"
                   placeholder="Digite seu usuário"
                   required autocomplete="username">
            <label>Senha</label>
            <input type="password" name="senha"
                   placeholder="Digite sua senha"
                   required autocomplete="current-password">
            <button type="submit" style="width:100%;">Entrar no Painel</button>
        </form>
        <p style="text-align:center;margin-top:20px;">
            <a href="/" style="color:{COR_OURO};">Voltar ao site</a>
        </p>
    </div>
    """

    return layout_admin(conteudo, "Login")


@app.route("/admin/sair")
@administrador_obrigatorio
def admin_sair():
    session.clear()
    flash("Você saiu do painel administrativo.")
    return redirect(url_for("admin_login"))


# =========================================================
# PAINEL PRINCIPAL
# =========================================================

@app.route("/admin/painel")
@administrador_obrigatorio
def admin_painel():
    produtos = buscar_produtos()

    total = len(produtos)
    ativos = sum(p["ativo"] for p in produtos)
    inativos = total - ativos

    with conectar() as db:
        total_pedidos = db.execute(
            "SELECT COUNT(*) FROM pedidos"
        ).fetchone()[0]

        pedidos_abertos = db.execute("""
            SELECT COUNT(*) FROM pedidos
            WHERE status NOT IN ('Concluído', 'Cancelado')
        """).fetchone()[0]

    lista_html = ""

    for p in produtos:
        status = (
            '<span class="sucesso">ATIVO</span>'
            if p["ativo"]
            else '<span class="inativo">INATIVO</span>'
        )

        imagem_url = obter_url_imagem(p)

        lista_html += f"""
        <div class="produto">
            <div style="display:flex;gap:15px;align-items:center;flex-wrap:wrap;">
                <img class="miniatura" src="{escape(imagem_url)}"
                     alt="Foto do produto">
                <div style="flex:1;min-width:180px;">
                    <strong>{escape(p['nome'])}</strong>
                    <p style="color:#9CA3AF;font-size:13px;margin-top:5px;">
                        {escape(p['categoria'] or 'Geral')}
                        | R$ {formatar_preco(p['preco'])}
                    </p>
                    <p style="color:#9CA3AF;font-size:12px;margin-top:5px;">
                        {status}
                    </p>
                </div>
            </div>
            <div class="acoes">
                <a class="botao" href="/admin/editar/{p['id']}">
                    Editar produto e foto
                </a>
                <form method="POST" action="/admin/alternar/{p['id']}">
                    <button type="submit" class="secundario">
                        {"Desativar" if p['ativo'] else "Ativar"}
                    </button>
                </form>
                <form method="POST" action="/admin/excluir/{p['id']}"
                      onsubmit="return confirm('Deseja excluir este produto definitivamente?');">
                    <button type="submit" class="perigo">Excluir</button>
                </form>
            </div>
        </div>
        """

    if not produtos:
        lista_html = '<p style="color:#9CA3AF;">Nenhum produto cadastrado ainda.</p>'

    conteudo = f"""
    <div class="cartao">
        <h1>Bem-vindo ao painel IWG</h1>
        <p style="color:#9CA3AF;">
            Gerencie produtos, pedidos, preços, descrições e categorias.
        </p>

        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin-top:25px;">
            <div class="cartao"><h2>{total}</h2><p>Total de produtos</p></div>
            <div class="cartao"><h2 class="sucesso">{ativos}</h2><p>Produtos ativos</p></div>
            <div class="cartao"><h2 class="inativo">{inativos}</h2><p>Produtos inativos</p></div>
            <div class="cartao"><h2>{total_pedidos}</h2><p>Total de pedidos</p></div>
            <div class="cartao"><h2>{pedidos_abertos}</h2><p>Pedidos em andamento</p></div>
        </div>

        <div class="acoes">
            <a href="/admin/novo" class="botao">+ Cadastrar novo produto</a>
            <a href="/admin/pedidos" class="botao secundario">Gerenciar pedidos</a>
        </div>
    </div>

    <div class="cartao">
        <h2>Gerenciar catálogo</h2>
        {lista_html}
    </div>
    """

    return layout_admin(conteudo)


# =========================================================
# CADASTRAR PRODUTO
# =========================================================

@app.route("/admin/novo", methods=["GET", "POST"])
@administrador_obrigatorio
def admin_novo():
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        descricao = request.form.get("descricao", "").strip()
        categoria = request.form.get("categoria", "").strip()

        try:
            preco = converter_preco(request.form.get("preco", "0"))
        except (ValueError, TypeError):
            preco = -1

        arquivo = request.files.get("imagem")
        imagem = None

        if not nome:
            flash("Informe o nome do produto.")
        elif preco < 0:
            flash("Informe um preço válido.")
        else:
            try:
                if arquivo and arquivo.filename:
                    imagem = salvar_imagem(arquivo)

                if not imagem:
                    imagem = imagem_provisoria(categoria, nome)

                with conectar() as db:
                    db.execute("""
                        INSERT INTO produtos
                        (nome, preco, descricao, categoria, ativo, imagem)
                        VALUES (?, ?, ?, ?, 1, ?)
                    """, (nome, preco, descricao, categoria, imagem))

                flash("Produto cadastrado com sucesso!")
                return redirect(url_for("admin_painel"))

            except ValueError as erro:
                flash(str(erro))

    conteudo = """
    <div class="cartao">
        <h1>Cadastrar produto</h1>
        <p style="color:#9CA3AF;font-size:13px;margin-bottom:15px;">
            Se não enviar uma foto, o sistema usará uma imagem ilustrativa.
        </p>
        <form method="POST" enctype="multipart/form-data">
            <label>Nome do produto</label>
            <input type="text" name="nome" placeholder="Ex.: Smartphone" required>
            <label>Preço (R$)</label>
            <input type="text" name="preco" placeholder="Ex.: 1999,90" required>
            <label>Categoria</label>
            <input type="text" name="categoria" placeholder="Ex.: Eletrônicos">
            <label>Descrição</label>
            <textarea name="descricao" rows="4" placeholder="Descreva o produto..."></textarea>
            <label>Foto do produto</label>
            <input type="file" name="imagem"
                   accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp">
            <p style="color:#9CA3AF;font-size:11px;margin-bottom:15px;">
                Formatos aceitos: JPG, JPEG, PNG e WEBP. Máximo de 5 MB.
            </p>
            <button type="submit">Salvar produto</button>
            <a href="/admin/painel" class="botao secundario">Cancelar</a>
        </form>
    </div>
    """

    return layout_admin(conteudo, "Novo produto")


# =========================================================
# EDITAR PRODUTO
# =========================================================

@app.route("/admin/editar/<int:pid>", methods=["GET", "POST"])
@administrador_obrigatorio
def admin_editar(pid):
    produto = buscar_produto(pid)

    if not produto:
        flash("Produto não encontrado.")
        return redirect(url_for("admin_painel"))

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        descricao = request.form.get("descricao", "").strip()
        categoria = request.form.get("categoria", "").strip()

        try:
            preco = converter_preco(request.form.get("preco", "0"))
        except (ValueError, TypeError):
            preco = -1

        arquivo = request.files.get("imagem")
        remover_foto = request.form.get("remover_foto") == "sim"

        if not nome:
            flash("O nome do produto é obrigatório.")
        elif preco < 0:
            flash("Informe um preço válido.")
        else:
            imagem_atual = produto["imagem"]

            try:
                if arquivo and arquivo.filename:
                    nova_imagem = salvar_imagem(arquivo)
                    if imagem_atual != nova_imagem:
                        excluir_imagem_local(imagem_atual)
                    imagem_atual = nova_imagem
                elif remover_foto:
                    excluir_imagem_local(imagem_atual)
                    imagem_atual = imagem_provisoria(categoria, nome)

                with conectar() as db:
                    db.execute("""
                        UPDATE produtos
                        SET nome = ?, preco = ?, descricao = ?,
                            categoria = ?, imagem = ?
                        WHERE id = ?
                    """, (
                        nome, preco, descricao,
                        categoria, imagem_atual, pid
                    ))

                flash("Produto e foto atualizados com sucesso!")
                return redirect(url_for("admin_painel"))

            except ValueError as erro:
                flash(str(erro))

    imagem_atual = produto["imagem"] or imagem_provisoria(
        produto["categoria"], produto["nome"]
    )

    if imagem_atual.startswith("http://") or imagem_atual.startswith("https://"):
        imagem_url = imagem_atual
    else:
        imagem_url = url_for("servir_arquivos", filename=imagem_atual)

    conteudo = f"""
    <div class="cartao">
        <h1>Editar produto</h1>
        <div style="margin:15px 0;">
            <label>Foto atual</label><br><br>
            <img src="{escape(imagem_url)}" alt="Foto atual"
                 style="width:100%;max-width:300px;height:200px;object-fit:cover;border-radius:10px;border:1px solid {COR_BORDA};">
        </div>
        <form method="POST" enctype="multipart/form-data">
            <label>Nome do produto</label>
            <input type="text" name="nome" value="{escape(produto['nome'])}" required>
            <label>Preço (R$)</label>
            <input type="text" name="preco" value="{formatar_preco(produto['preco'])}" required>
            <label>Categoria</label>
            <input type="text" name="categoria" value="{escape(produto['categoria'] or '')}">
            <label>Descrição</label>
            <textarea name="descricao" rows="4">{escape(produto['descricao'] or '')}</textarea>
            <label>Substituir foto</label>
            <input type="file" name="imagem" accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp">
            <p style="color:#9CA3AF;font-size:11px;margin-bottom:15px;">
                JPG, JPEG, PNG ou WEBP. Máximo de 5 MB.
            </p>
            <label style="display:flex;align-items:center;gap:8px;margin-bottom:20px;">
                <input type="checkbox" name="remover_foto" value="sim" style="width:auto;margin:0;">
                Voltar para a imagem ilustrativa
            </label>
            <button type="submit">Salvar alterações</button>
            <a href="/admin/painel" class="botao secundario">Voltar</a>
        </form>
    </div>
    """

    return layout_admin(conteudo, "Editar produto")


# =========================================================
# ATIVAR / DESATIVAR PRODUTO
# =========================================================

@app.route("/admin/alternar/<int:pid>", methods=["POST"])
@administrador_obrigatorio
def admin_alternar(pid):
    with conectar() as db:
        produto = db.execute(
            "SELECT ativo FROM produtos WHERE id = ?", (pid,)
        ).fetchone()

        if produto:
            novo_status = 0 if produto["ativo"] else 1
            db.execute(
                "UPDATE produtos SET ativo = ? WHERE id = ?",
                (novo_status, pid)
            )
            flash("Disponibilidade do produto atualizada.")

    return redirect(url_for("admin_painel"))


# =========================================================
# EXCLUIR PRODUTO
# =========================================================

@app.route("/admin/excluir/<int:pid>", methods=["POST"])
@administrador_obrigatorio
def admin_excluir(pid):
    produto = buscar_produto(pid)

    if produto:
        excluir_imagem_local(produto["imagem"])

        with conectar() as db:
            db.execute("DELETE FROM produtos WHERE id = ?", (pid,))

        flash("Produto excluído do catálogo.")

    return redirect(url_for("admin_painel"))


# =========================================================
# ALTERAR SENHA
# =========================================================

@app.route("/admin/senha", methods=["GET", "POST"])
@administrador_obrigatorio
def admin_senha():
    if request.method == "POST":
        senha_atual = request.form.get("senha_atual", "")
        senha_nova = request.form.get("senha_nova", "")
        confirmar = request.form.get("confirmar", "")
        usuario = session.get("admin_usuario")

        with conectar() as db:
            admin = db.execute("""
                SELECT * FROM administradores WHERE usuario = ?
            """, (usuario,)).fetchone()

            if not admin or not check_password_hash(
                admin["senha_hash"], senha_atual
            ):
                flash("A senha atual está incorreta.")
            elif len(senha_nova) < 8:
                flash("A nova senha precisa ter pelo menos 8 caracteres.")
            elif senha_nova != confirmar:
                flash("A confirmação da senha não corresponde.")
            else:
                nova_hash = generate_password_hash(
                    senha_nova, method="pbkdf2:sha256"
                )
                db.execute("""
                    UPDATE administradores
                    SET senha_hash = ? WHERE usuario = ?
                """, (nova_hash, usuario))

                flash("Senha alterada com sucesso!")
                return redirect(url_for("admin_painel"))

    conteudo = """
    <div class="cartao">
        <h1>Alterar senha</h1>
        <form method="POST">
            <label>Senha atual</label>
            <input type="password" name="senha_atual" required>
            <label>Nova senha</label>
            <input type="password" name="senha_nova" minlength="8" required>
            <label>Confirmar nova senha</label>
            <input type="password" name="confirmar" minlength="8" required>
            <button type="submit">Atualizar senha</button>
            <a href="/admin/painel" class="botao secundario">Voltar</a>
        </form>
    </div>
    """

    return layout_admin(conteudo, "Alterar senha")


# =========================================================
# CARRINHO
# =========================================================

@app.route("/adicionar/<int:pid>", methods=["POST"])
def adicionar(pid):
    produto = buscar_produto(pid)

    if not produto or not produto["ativo"]:
        flash("Este produto não está disponível.")
        return redirect(url_for("home"))

    carrinho = session.get("carrinho", {})
    str_pid = str(pid)
    carrinho[str_pid] = int(carrinho.get(str_pid, 0)) + 1
    session["carrinho"] = carrinho

    return redirect(url_for("carrinho"))


def calcular_carrinho():
    carrinho_sessao = session.get("carrinho", {})
    itens = []
    total = 0.0

    for str_pid, qtd in carrinho_sessao.items():
        try:
            pid = int(str_pid)
            qtd = int(qtd)
        except (ValueError, TypeError):
            continue

        if qtd <= 0:
            continue

        produto = buscar_produto(pid)

        if not produto or not produto["ativo"]:
            continue

        subtotal = float(produto["preco"]) * qtd
        total += subtotal

        itens.append({
            "id": pid,
            "nome": produto["nome"],
            "quantidade": qtd,
            "preco": float(produto["preco"]),
            "subtotal": subtotal
        })

    return itens, total


@app.route("/carrinho")
def carrinho():
    itens, total = calcular_carrinho()

    if not itens:
        conteudo = f"""
        <div style="text-align:center;padding:40px;color:#9CA3AF;">
            O seu carrinho está vazio.
            <br><br>
            <a href="/" style="color:{COR_OURO};font-weight:bold;text-decoration:none;">
                ← Voltar para a Página Principal
            </a>
        </div>
        """
    else:
        linhas = ""

        for item in itens:
            linhas += f"""
            <div style="padding:14px 20px;border-bottom:1px solid {COR_BORDA};
                        display:flex;justify-content:space-between;align-items:center;gap:10px;">
                <div>
                    <strong>{escape(item['nome'])}</strong>
                    <p style="color:#9CA3AF;font-size:11px;margin-top:5px;">
                        Quantidade: {item['quantidade']}
                        | Unitário: R$ {formatar_preco(item['preco'])}
                        | Subtotal: R$ {formatar_preco(item['subtotal'])}
                    </p>
                </div>
                <form method="POST" action="/remover/{item['id']}">
                    <button type="submit" style="background:#B91C1C;color:white;">
                        Remover
                    </button>
                </form>
            </div>
            """

        conteudo = f"""
        <h3 style="color:{COR_OURO};margin:20px 0 15px;font-size:13px;">
            SEUS ITENS SELECIONADOS
        </h3>
        <div style="background:{COR_CARD};border:1px solid {COR_BORDA};border-radius:12px;overflow:hidden;">
            {linhas}
        </div>
        <div style="background:{COR_CARD};border:1px solid {COR_BORDA};
                    border-radius:12px;padding:20px;text-align:right;margin-top:20px;">
            <h3 style="color:white;margin-bottom:15px;">
                Total Geral: R$ {formatar_preco(total)}
            </h3>
            <a href="/checkout" style="background:#25D366;color:white;text-decoration:none;
                display:block;text-align:center;padding:13px;border-radius:8px;font-weight:bold;">
                CONTINUAR PARA IDENTIFICAÇÃO E ENTREGA
            </a>
        </div>
        <div style="margin-top:15px;text-align:center;">
            <a href="/" style="color:{COR_OURO};text-decoration:none;font-size:13px;font-weight:bold;">
                ← Continuar Comprando
            </a>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Carrinho - IWG Technological Solutions</title>
        <style>
            * {{ margin:0;padding:0;box-sizing:border-box;font-family:Arial,sans-serif; }}
            body {{ background:{AZUL_FUNDO};color:white;padding-bottom:30px; }}
            .container {{ max-width:900px;margin:30px auto;padding:0 15px; }}
        </style>
    </head>
    <body>
        <div class="container">
            {conteudo}
            {gerar_rodape()}
        </div>
    </body>
    </html>
    """

    return render_template_string(html)


@app.route("/remover/<int:pid>", methods=["POST"])
def remover(pid):
    carrinho_sessao = session.get("carrinho", {})

    if str(pid) in carrinho_sessao:
        del carrinho_sessao[str(pid)]
        session["carrinho"] = carrinho_sessao

    return redirect(url_for("carrinho"))


# =========================================================
# CHECKOUT - DADOS DO CLIENTE E ENDERECO
# =========================================================

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    itens, total = calcular_carrinho()

    if not itens:
        flash("Seu carrinho está vazio.")
        return redirect(url_for("carrinho"))

    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        telefone = request.form.get("telefone", "").strip()
        cpf = request.form.get("cpf", "").strip()
        cep = request.form.get("cep", "").strip()
        rua = request.form.get("rua", "").strip()
        numero = request.form.get("numero", "").strip()
        complemento = request.form.get("complemento", "").strip()
        bairro = request.form.get("bairro", "").strip()
        cidade = request.form.get("cidade", "").strip()
        estado = request.form.get("estado", "").strip()
        observacoes = request.form.get("observacoes", "").strip()

        obrigatorios = [
            nome, telefone, cpf, cep, rua,
            numero, bairro, cidade, estado
        ]

        if not all(obrigatorios):
            flash("Preencha todos os campos obrigatórios.")
        else:
            itens_texto = []

            for item in itens:
                itens_texto.append(
                    f"{item['quantidade']}x {item['nome']} | "
                    f"Unitário: R$ {formatar_preco(item['preco'])} | "
                    f"Subtotal: R$ {formatar_preco(item['subtotal'])}"
                )

            resumo_itens = "\n".join(itens_texto)

            # CPF nao e armazenado no banco.
            with conectar() as db:
                cursor = db.execute("""
                    INSERT INTO pedidos (
                        nome, telefone, cep, rua, numero,
                        complemento, bairro, cidade, estado,
                        observacoes, itens, total, status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    nome, telefone, cep, rua, numero,
                    complemento, bairro, cidade, estado,
                    observacoes, resumo_itens, total,
                    "Aguardando confirmação no WhatsApp"
                ))

                pedido_id = cursor.lastrowid

            mensagem = (
                f"Olá! Gostaria de confirmar meu pedido na IWG.\n\n"
                f"PEDIDO Nº {pedido_id}\n\n"
                f"CLIENTE: {nome}\n"
                f"TELEFONE: {telefone}\n"
                f"CPF: {cpf}\n\n"
                f"ENDEREÇO DE ENTREGA:\n"
                f"CEP: {cep}\n"
                f"Rua: {rua}, nº {numero}\n"
                f"Complemento: {complemento or 'Não informado'}\n"
                f"Bairro: {bairro}\n"
                f"Cidade: {cidade} - {estado}\n\n"
                f"PRODUTOS:\n{resumo_itens}\n\n"
                f"TOTAL DOS PRODUTOS: R$ {formatar_preco(total)}\n\n"
                f"OBSERVAÇÕES: {observacoes or 'Nenhuma'}\n\n"
                "ATENÇÃO: frete e tributos podem gerar custos adicionais, "
                "especialmente em envios interestaduais. Favor confirmar "
                "esses valores antes de finalizar a compra.\n\n"
                "Após a postagem para o destino/endereço escolhido, "
                "a IWG fornecerá o código de rastreamento.\n\n"
                f"Solicito a confirmação do pedido nº {pedido_id}."
            )

            whatsapp_url = (
                f"https://wa.me/{WHATSAPP}?text={quote(mensagem)}"
            )

            session["carrinho"] = {}

            pagina = f"""
            <!DOCTYPE html>
            <html lang="pt-BR">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Pedido registrado - IWG</title>
                <style>
                    * {{ box-sizing:border-box;font-family:Arial,sans-serif; }}
                    body {{ background:{AZUL_FUNDO};color:white;padding:20px; }}
                    .cartao {{
                        max-width:650px;margin:50px auto;background:{COR_CARD};
                        border:1px solid {COR_OURO};border-radius:14px;
                        padding:28px;text-align:center;
                    }}
                    h1 {{ color:{COR_OURO}; }}
                    p {{ color:#D1D5DB;line-height:1.7;margin:15px 0; }}
                    a {{
                        display:block;background:#25D366;color:white;
                        text-decoration:none;padding:15px;border-radius:8px;
                        font-weight:bold;margin-top:20px;
                    }}
                </style>
            </head>
            <body>
                <div class="cartao">
                    <h1>Pedido registrado!</h1>
                    <h2>Pedido nº {pedido_id}</h2>
                    <p>
                        Seus dados e produtos foram registrados.
                        Para solicitar a confirmação, clique no botão abaixo
                        e envie a mensagem pelo WhatsApp da IWG.
                    </p>
                    <p>
                        <strong>Importante:</strong> o pedido ainda depende
                        da confirmação pelo WhatsApp.
                    </p>
                    <a href="{whatsapp_url}" target="_blank" rel="noopener">
                        ENVIAR PEDIDO PELO WHATSAPP
                    </a>
                    <p>
                        Depois de enviar a mensagem, aguarde o atendimento
                        da equipe IWG.
                    </p>
                    <a href="/" style="background:{COR_BORDA};">
                        VOLTAR AO SITE
                    </a>
                </div>
            </body>
            </html>
            """

            return render_template_string(pagina)

    linhas_itens = ""

    for item in itens:
        linhas_itens += f"""
        <li>
            {escape(item['nome'])} — {item['quantidade']} unidade(s)
            — R$ {formatar_preco(item['subtotal'])}
        </li>
        """

    conteudo = f"""
    <div class="cartao">
        <h1>Finalizar pedido</h1>
        <p style="color:#9CA3AF;">
            Informe seus dados para preparar seu pedido e a entrega.
        </p>

        <h3>Resumo do pedido</h3>
        <ul style="padding-left:20px;line-height:1.9;margin:15px 0;">
            {linhas_itens}
        </ul>
        <h2 style="color:{COR_OURO};">
            Total: R$ {formatar_preco(total)}
        </h2>

        <form method="POST">
            <h3 style="margin-top:25px;">Dados do cliente</h3>

            <label>Nome completo *</label>
            <input type="text" name="nome" required>

            <label>Telefone / WhatsApp *</label>
            <input type="tel" name="telefone" required
                   placeholder="Ex.: (27) 99999-9999">

            <label>CPF *</label>
            <input type="text" name="cpf" required
                   placeholder="Seu CPF será enviado pelo WhatsApp">

            <h3>Endereço de entrega</h3>

            <label>CEP *</label>
            <input type="text" name="cep" required>

            <label>Rua / Avenida *</label>
            <input type="text" name="rua" required>

            <label>Número *</label>
            <input type="text" name="numero" required>

            <label>Complemento</label>
            <input type="text" name="complemento">

            <label>Bairro *</label>
            <input type="text" name="bairro" required>

            <label>Cidade *</label>
            <input type="text" name="cidade" required>

            <label>Estado (UF) *</label>
            <input type="text" name="estado" maxlength="2" required
                   placeholder="Ex.: ES">

            <label>Observações</label>
            <textarea name="observacoes" rows="4"
                      placeholder="Informações adicionais sobre a entrega..."></textarea>

            <p style="color:#F7C04A;font-size:12px;line-height:1.6;">
                O frete e eventuais tributos serão confirmados antes
                da finalização da compra. O CPF será enviado pelo WhatsApp
                e não será salvo no banco de dados da loja.
            </p>

            <button type="submit" style="width:100%;margin-top:15px;">
                REGISTRAR PEDIDO E CONTINUAR NO WHATSAPP
            </button>
        </form>

        <p style="margin-top:20px;">
            <a href="/carrinho" style="color:{COR_OURO};">
                Voltar ao carrinho
            </a>
        </p>
    </div>
    """

    html = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Checkout - IWG</title>
        <style>
            * {{ box-sizing:border-box;font-family:Arial,sans-serif; }}
            body {{ margin:0;padding:20px;background:{AZUL_FUNDO};color:white; }}
            .container {{ max-width:750px;margin:25px auto; }}
            .cartao {{
                background:{COR_CARD};border:1px solid {COR_BORDA};
                border-radius:12px;padding:22px;margin-bottom:20px;
            }}
            h1,h2,h3 {{ color:{COR_OURO};margin-bottom:12px; }}
            label {{ display:block;color:#D1D5DB;font-size:13px;margin-top:12px; }}
            input,textarea {{
                width:100%;padding:12px;margin-top:6px;
                border-radius:7px;border:1px solid {COR_BORDA};
                background:{AZUL_FUNDO};color:white;font-size:14px;
            }}
            button {{
                border:0;border-radius:7px;padding:14px;
                background:{COR_OURO};color:{AZUL_FUNDO};
                font-weight:bold;cursor:pointer;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            {conteudo}
            {gerar_rodape()}
        </div>
    </body>
    </html>
    """

    return render_template_string(html)


# =========================================================
# ADMINISTRACAO DE PEDIDOS
# =========================================================

@app.route("/admin/pedidos")
@administrador_obrigatorio
def admin_pedidos():
    with conectar() as db:
        pedidos = db.execute("""
            SELECT * FROM pedidos
            ORDER BY id DESC
        """).fetchall()

    linhas = ""

    for pedido in pedidos:
        linhas += f"""
        <div class="produto">
            <h3>Pedido nº {pedido['id']}</h3>
            <p><strong>Cliente:</strong> {escape(pedido['nome'])}</p>
            <p><strong>Telefone:</strong> {escape(pedido['telefone'])}</p>
            <p><strong>Total:</strong> R$ {formatar_preco(pedido['total'])}</p>
            <p><strong>Status:</strong> {escape(pedido['status'])}</p>
            <p><strong>Data:</strong> {escape(pedido['data_criacao'] or '')}</p>
            <div class="acoes">
                <a class="botao" href="/admin/pedido/{pedido['id']}">
                    Ver pedido e atualizar
                </a>
            </div>
        </div>
        """

    if not linhas:
        linhas = "<p>Nenhum pedido registrado até o momento.</p>"

    conteudo = f"""
    <div class="cartao">
        <h1>Pedidos recebidos</h1>
        <p style="color:#9CA3AF;">
            Consulte os dados dos clientes, acompanhe os pedidos
            e informe os códigos de rastreamento.
        </p>
        {linhas}
    </div>
    """

    return layout_admin(conteudo, "Pedidos")


@app.route("/admin/pedido/<int:pid>", methods=["GET", "POST"])
@administrador_obrigatorio
def admin_pedido_detalhe(pid):
    pedido = buscar_pedido(pid)

    if not pedido:
        flash("Pedido não encontrado.")
        return redirect(url_for("admin_pedidos"))

    if request.method == "POST":
        status = request.form.get("status", "").strip()
        codigo = request.form.get("codigo_rastreio", "").strip()

        if status not in STATUS_PEDIDOS:
            flash("Status inválido.")
        else:
            with conectar() as db:
                db.execute("""
                    UPDATE pedidos
                    SET status = ?, codigo_rastreio = ?
                    WHERE id = ?
                """, (status, codigo, pid))

            flash("Pedido atualizado com sucesso!")
            return redirect(url_for("admin_pedido_detalhe", pid=pid))

    pedido = buscar_pedido(pid)

    endereco = (
        f"{pedido['rua']}, nº {pedido['numero']}, "
        f"{pedido['bairro']}, {pedido['cidade']} - "
        f"{pedido['estado']}, CEP {pedido['cep']}"
    )

    opcoes_status = ""

    for status in STATUS_PEDIDOS:
        selecionado = "selected" if status == pedido["status"] else ""
        opcoes_status += (
            f'<option value="{escape(status)}" {selecionado}>'
            f'{escape(status)}</option>'
        )

    mensagem_rastreio = (
        f"Olá, {pedido['nome']}! "
        f"Seu pedido nº {pid} da IWG foi atualizado.\n\n"
        f"Status: {pedido['status']}\n"
        f"Código de rastreamento: "
        f"{pedido['codigo_rastreio'] or 'Ainda não informado'}\n\n"
        "Agradecemos pela preferência!\n"
        "IWG Technological Solutions"
    )

    whatsapp_cliente = "".join(
        caractere for caractere in pedido["telefone"]
        if caractere.isdigit()
    )

    if len(whatsapp_cliente) in (10, 11):
        whatsapp_cliente = "55" + whatsapp_cliente

    if len(whatsapp_cliente) < 12:
        link_whatsapp = ""
    else:
        link_whatsapp = (
            f"https://wa.me/{whatsapp_cliente}"
            f"?text={quote(mensagem_rastreio)}"
        )

    botao_whatsapp = ""

    if link_whatsapp:
        botao_whatsapp = f"""
        <a class="botao" href="{link_whatsapp}"
           target="_blank" rel="noopener">
            Enviar atualização ao cliente pelo WhatsApp
        </a>
        """
    else:
        botao_whatsapp = """
        <p class="inativo">
            O telefone cadastrado não parece estar completo.
            Confira o número antes de enviar a mensagem.
        </p>
        """

    conteudo = f"""
    <div class="cartao">
        <h1>Pedido nº {pid}</h1>

        <h3>Dados do cliente</h3>
        <p><strong>Nome:</strong> {escape(pedido['nome'])}</p>
        <p><strong>Telefone:</strong> {escape(pedido['telefone'])}</p>

        <h3 style="margin-top:20px;">Endereço de entrega</h3>
        <p>{escape(endereco)}</p>
        <p><strong>Complemento:</strong> {escape(pedido['complemento'] or 'Não informado')}</p>

        <h3 style="margin-top:20px;">Produtos do pedido</h3>
        <pre style="white-space:pre-wrap;color:#D1D5DB;font-family:Arial;">
{escape(pedido['itens'])}
        </pre>

        <h2>Total: R$ {formatar_preco(pedido['total'])}</h2>

        <p><strong>Observações:</strong>
            {escape(pedido['observacoes'] or 'Nenhuma')}
        </p>

        <p><strong>Data:</strong> {escape(pedido['data_criacao'] or '')}</p>
    </div>

    <div class="cartao">
        <h2>Atualizar pedido</h2>

        <form method="POST">
            <label>Status do pedido</label>
            <select name="status" required>
                {opcoes_status}
            </select>

            <label>Código de rastreamento</label>
            <input type="text" name="codigo_rastreio"
                   value="{escape(pedido['codigo_rastreio'] or '')}"
                   placeholder="Digite o código quando o pedido for postado">

            <button type="submit">Salvar atualização</button>
        </form>

        <div class="acoes" style="margin-top:20px;">
            {botao_whatsapp}
            <a class="botao secundario" href="/admin/pedidos">
                Voltar aos pedidos
            </a>
        </div>
    </div>
    """

    return layout_admin(conteudo, f"Pedido {pid}")


# =========================================================
# ARQUIVOS E LOGO
# =========================================================

@app.route("/arquivos/<path:filename>")
def servir_arquivos(filename):
    return send_from_directory(PASTA_ASSETS, filename)


# =========================================================
# ERRO DE UPLOAD
# =========================================================

@app.errorhandler(413)
def arquivo_muito_grande(erro):
    flash("A imagem ultrapassa o limite de 5 MB.")
    return redirect(request.referrer or url_for("admin_painel"))


# =========================================================
# EXECUCAO
# =========================================================

if __name__ == "__main__":
    print("=" * 55)
    print("IWG TECHNOLOGICAL SOLUTIONS")
    print("Servidor iniciado!")
    print("Site: http://127.0.0.1:8550")
    print("Painel: http://127.0.0.1:8550/admin")
    print("Usuário inicial: iulu")
    print("Senha inicial: iulu")
    print("=" * 55)

    app.run(
        host="0.0.0.0",
        port=8550,
        debug=True
    )
