import json
import re
from pathlib import Path

from emporio_da_musica_agent.db import DATA_DIR, load_database

# Loaded once, when this module is imported.
DB = load_database()

PIX_DISCOUNT = 5  # percent, policy section 6.2
NEUTRAL_ORDER_ERROR = (
    "Não foi possível verificar este pedido com os dados informados. "
    "Peça ao cliente para conferir o número do pedido e o e-mail ou telefone do cadastro."
)

CATEGORIES = [row["name"] for row in DB.execute("SELECT name FROM categories ORDER BY category_id")]


def _load_policies() -> dict[str, str]:
    """Map section slug (file name without the number prefix) -> section text."""
    policies = {}
    for path in sorted((DATA_DIR / "policies").glob("[0-9][0-9]_*.md")):
        slug = path.stem.split("_", 1)[1]
        policies[slug] = path.read_text(encoding="utf-8")
    return policies


POLICIES = _load_policies()


# ---------- helpers ----------

def _price_info(price: float, discount_percent: float | None) -> dict:
    """Final price rules: show original + % + final when on promotion.
    PIX discount only applies when there is NO promotion (policy 6.2)."""
    if discount_percent:
        return {
            "preco_original": round(price, 2),
            "desconto_percent": discount_percent,
            "preco_final": round(price * (1 - discount_percent / 100), 2),
            "desconto_pix": "não se aplica (promoção não acumula com PIX)",
        }
    return {
        "preco": round(price, 2),
        "preco_pix": round(price * (1 - PIX_DISCOUNT / 100), 2),
    }


def _product_summary(row) -> dict:
    return {
        "id": row["product_id"],
        "nome": row["name"],
        "categoria": row["category"],
        "estoque": row["stock_quantity"],
        **_price_info(row["price_brl"], row["discount_percent"]),
    }


# Active promotion is joined in every product query.
_PRODUCT_SELECT = """
    SELECT p.product_id, p.name, p.price_brl, p.stock_quantity, p.status,
           p.description, p.specs, c.name AS category, pr.discount_percent
    FROM products p
    JOIN categories c ON c.category_id = p.category_id
    LEFT JOIN promotions pr ON pr.product_id = p.product_id AND pr.is_active = 1
"""


# ---------- tools ----------

def search_products(category: str | None = None, max_price: float | None = None,
                    text: str | None = None) -> dict:
    """List products that can be sold now (active and in stock)."""
    sql = _PRODUCT_SELECT + " WHERE p.status = 'active' AND p.stock_quantity > 0"
    params: list = []
    if category:
        sql += " AND c.name = ?"
        params.append(category)
    if max_price is not None:
        # compare against the price the customer would actually pay
        sql += " AND p.price_brl * (1 - COALESCE(pr.discount_percent, 0) / 100.0) <= ?"
        params.append(max_price)
    if text:
        sql += " AND p.name LIKE ?"
        params.append(f"%{text}%")
    rows = DB.execute(sql + " ORDER BY p.price_brl", params).fetchall()
    return {
        "produtos": [_product_summary(r) for r in rows[:10]],  # at most 10, to save tokens
        "total_encontrado": len(rows),
        "aviso": "Lista cortada nos 10 mais baratos; diga ao cliente que há mais opções."
        if len(rows) > 10 else None,
    }


def get_product_details(name: str) -> dict:
    """Details of products matching a name, in ANY status (so we can say sold out / discontinued)."""
    rows = DB.execute(_PRODUCT_SELECT + " WHERE p.name LIKE ? LIMIT 5", (f"%{name}%",)).fetchall()
    if not rows:
        return {"erro": f"Nenhum produto encontrado com o nome '{name}'."}
    products = []
    for r in rows:
        item = _product_summary(r)
        item["status"] = r["status"]  # active | discontinued | coming_soon
        item["descricao"] = r["description"]
        item["specs"] = json.loads(r["specs"]) if r["specs"] else {}
        products.append(item)
    return {"produtos": products}


def list_active_promotions() -> dict:
    rows = DB.execute(
        _PRODUCT_SELECT + " WHERE pr.discount_percent IS NOT NULL AND p.status = 'active' ORDER BY p.name"
    ).fetchall()
    return {"promocoes": [_product_summary(r) for r in rows]}


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def get_order(order_id: int, email_or_phone: str) -> dict:
    """Order status, only if the contact matches the customer on that order (LGPD)."""
    order = DB.execute(
        """SELECT o.*, c.name AS customer_name, c.email, c.phone
           FROM orders o JOIN customers c ON c.customer_id = o.customer_id
           WHERE o.order_id = ?""",
        (order_id,),
    ).fetchone()

    contact = (email_or_phone or "").strip()
    verified = False
    if order and contact:
        same_email = contact.lower() == order["email"].lower()
        same_phone = len(_digits(contact)) >= 8 and _digits(contact) == _digits(order["phone"])
        verified = same_email or same_phone
    if not verified:
        # Same message whether the order doesn't exist or the contact is wrong.
        return {"erro": NEUTRAL_ORDER_ERROR}

    items = DB.execute(
        """SELECT p.name, oi.quantity FROM order_items oi
           JOIN products p ON p.product_id = oi.product_id WHERE oi.order_id = ?""",
        (order_id,),
    ).fetchall()
    return {
        "cliente_primeiro_nome": order["customer_name"].split()[0],
        "pedido": order["order_id"],
        "data_pedido": order["order_date"],
        "status": order["status"],
        "total_brl": order["total_brl"],  # as stored; never recalculated
        "forma_pagamento": order["payment_method"],
        "codigo_rastreio": order["tracking_code"],
        "previsao_entrega": order["estimated_delivery"],
        "observacoes": order["notes"],
        "itens": [{"produto": i["name"], "quantidade": i["quantity"]} for i in items],
    }


def get_policy(section: str) -> dict:
    if section not in POLICIES:
        return {"erro": f"Seção inexistente. Opções: {', '.join(POLICIES)}"}
    return {"secao": section, "texto": POLICIES[section]}


# ---------- schemas the model reads ----------

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_products",
            "description": (
                "Lista produtos À VENDA agora (ativos e com estoque), ordenados por preço, com "
                "promoção ativa já aplicada. Use para sugestões e perguntas como 'quais violões até R$1000'. "
                "Máximo de 10 resultados."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    # Optional filters accept null: the model sends null for unused filters,
                    # and Groq rejects the call if the schema does not allow it.
                    "category": {"type": ["string", "null"], "enum": CATEGORIES + [None],
                                 "description": "Categoria do produto."},
                    "max_price": {"type": ["number", "null"], "description": "Preço máximo em reais."},
                    "text": {"type": ["string", "null"], "description": "Trecho do nome (marca ou modelo)."},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_details",
            "description": (
                "Detalhes de um produto pelo nome (preço, estoque, status, specs), mesmo se esgotado, "
                "descontinuado ou em breve. Use para 'quanto custa o X' ou 'tem o X?'."
            ),
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Nome ou parte do nome, ex.: 'Takamine GD20'."}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_active_promotions",
            "description": "Lista as promoções ativas hoje, com preço original, desconto e preço final.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_order",
            "description": (
                "Status de um pedido. Exige o número do pedido E o e-mail ou telefone do cadastro. "
                "Nunca chame sem os dois dados informados pelo cliente."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer", "description": "Número do pedido."},
                    "email_or_phone": {"type": "string", "description": "E-mail ou telefone do cadastro."},
                },
                "required": ["order_id", "email_or_phone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_policy",
            "description": (
                "Texto de uma seção do manual de políticas da loja (endereço e contatos, horário, pagamento, "
                "trocas e devoluções, frete, promoções, atendimento, garantia, privacidade)."
            ),
            "parameters": {
                "type": "object",
                "properties": {"section": {"type": "string", "enum": list(POLICIES)}},
                "required": ["section"],
            },
        },
    },
]

_FUNCTIONS = {
    "search_products": search_products,
    "get_product_details": get_product_details,
    "list_active_promotions": list_active_promotions,
    "get_order": get_order,
    "get_policy": get_policy,
}


def run_tool(name: str, arguments_json: str) -> str:
    """Run the tool the model asked for and return the result as a JSON string."""
    try:
        function = _FUNCTIONS[name]
        result = function(**json.loads(arguments_json or "{}"))
    except Exception as error:  # the model gets the error as information instead of crashing the app
        result = {"erro": f"Falha ao executar {name}: {error}"}
    return json.dumps(result, ensure_ascii=False)
