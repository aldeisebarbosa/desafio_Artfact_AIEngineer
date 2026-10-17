import json
import sqlite3
from typing import Any, Optional
from pathlib import Path

from src.database import get_db_connection, DB_PATH, DATA_DIR, normalize_text
from src.policies import get_policy_retriever


def _get_connection() -> sqlite3.Connection:
    """Retorna uma conexão ativa com o banco SQLite gerado."""
    if not DB_PATH.exists():
        return get_db_connection(DB_PATH, DATA_DIR)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def search_products(
    query: str = "",
    category: str = "",
    max_price: Optional[float] = None,
    only_available: bool = True,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Pesquisa produtos no catálogo da Empório da Música aplicando filtros de texto, categoria, preço máximo e estoque.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    conditions = []
    params: list[Any] = []

    if only_available:
        conditions.append("is_available = 1")

    if max_price is not None and max_price > 0:
        conditions.append("effective_price_brl <= ?")
        params.append(max_price)

    if category:
        norm_cat = f"%{normalize_text(category)}%"
        conditions.append("category_norm LIKE ?")
        params.append(norm_cat)

    if query:
        norm_words = normalize_text(query).split()
        for word in norm_words:
            if len(word) > 2:  # Evita preposições curtas
                conditions.append("search_blob LIKE ?")
                params.append(f"%{word}%")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"""
        SELECT 
            product_id, name, category_name, description, specs,
            price_brl, effective_price_brl, pix_price_brl,
            has_active_promo, active_discount_percent, active_promo_description,
            max_installments, installment_value_brl, stock_quantity, status, is_available
        FROM products
        {where_clause}
        ORDER BY effective_price_brl ASC
        LIMIT ?
    """
    params.append(limit)

    cursor.execute(sql, params)
    rows = cursor.fetchall()

    results = []
    for r in rows:
        results.append({
            "product_id": r["product_id"],
            "name": r["name"],
            "category": r["category_name"],
            "description": r["description"],
            "specs": r["specs"],
            "price_brl": r["price_brl"],
            "effective_price_brl": r["effective_price_brl"],
            "pix_price_brl": r["pix_price_brl"],
            "has_active_promo": bool(r["has_active_promo"]),
            "active_discount_percent": r["active_discount_percent"],
            "active_promo_description": r["active_promo_description"],
            "max_installments": r["max_installments"],
            "installment_value_brl": r["installment_value_brl"],
            "stock_quantity": r["stock_quantity"],
            "is_available": bool(r["is_available"]),
            "payment_summary": (
                f"R$ {r['effective_price_brl']:.2f} "
                + (f"(Promoção {r['active_discount_percent']}% OFF de R$ {r['price_brl']:.2f}) " if r["has_active_promo"] else "")
                + f"| No PIX: R$ {r['pix_price_brl']:.2f} "
                + (f"| Cartão: até {r['max_installments']}x de R$ {r['installment_value_brl']:.2f} sem juros" if r["max_installments"] > 1 else "| À vista")
            ),
        })
    return results


def get_product_details(product_query: str) -> Optional[dict[str, Any]]:
    """
    Busca os detalhes completos de um produto específico pelo nome exato, parcial ou ID.
    """
    conn = _get_connection()
    cursor = conn.cursor()

    # Tenta por ID se for numérico
    if product_query.isdigit():
        cursor.execute("SELECT * FROM products WHERE product_id = ?", (int(product_query),))
        row = cursor.fetchone()
        if row:
            return _format_product_row(row)

    # 1. Busca direta pela frase/nome
    norm = f"%{normalize_text(product_query)}%"
    cursor.execute(
        """
        SELECT * FROM products 
        WHERE search_blob LIKE ? 
        ORDER BY (name LIKE ?) DESC, effective_price_brl ASC 
        LIMIT 1
        """,
        (norm, f"%{product_query}%")
    )
    row = cursor.fetchone()
    if row:
        return _format_product_row(row)

    # 2. Busca por interseção de tokens significativos
    tokens = [t for t in normalize_text(product_query).split() if len(t) > 1]
    if tokens:
        where_tokens = " AND ".join(["search_blob LIKE ?" for _ in tokens])
        params = [f"%{t}%" for t in tokens]
        cursor.execute(
            f"""
            SELECT * FROM products 
            WHERE {where_tokens}
            ORDER BY effective_price_brl ASC 
            LIMIT 1
            """,
            params
        )
        row = cursor.fetchone()
        if row:
            return _format_product_row(row)

    return None


def _format_product_row(r: sqlite3.Row) -> dict[str, Any]:
    expired_promos = []
    if "expired_promotions_json" in r.keys() and r["expired_promotions_json"]:
        try:
            expired_promos = json.loads(r["expired_promotions_json"])
        except Exception:
            pass

    return {
        "product_id": r["product_id"],
        "name": r["name"],
        "category": r["category_name"],
        "description": r["description"],
        "specs": r["specs"],
        "price_original_brl": r["price_brl"],
        "price_brl": r["price_brl"],
        "price_effective_brl": r["effective_price_brl"],
        "pix_price_brl": r["pix_price_brl"],
        "has_active_promo": bool(r["has_active_promo"]),
        "active_discount_percent": r["active_discount_percent"],
        "active_promo_description": r["active_promo_description"],
        "expired_promotions": expired_promos,
        "max_installments": r["max_installments"],
        "installment_value_brl": r["installment_value_brl"],
        "stock_quantity": r["stock_quantity"],
        "is_available": bool(r["is_available"]),
    }


def search_order(identifier: str) -> Optional[dict[str, Any]]:
    """
    Consulta informações de pedido por número do pedido (#ID), código de rastreio ou dados do cliente (nome/e-mail/telefone).
    """
    conn = _get_connection()
    cursor = conn.cursor()

    cleaned_id = identifier.strip().replace("#", "")

    # 1. Busca por Order ID
    if cleaned_id.isdigit():
        cursor.execute(
            """
            SELECT o.*, c.name as customer_name, c.email as customer_email, c.phone as customer_phone, c.city as customer_city
            FROM orders o
            JOIN customers c ON o.customer_id = c.customer_id
            WHERE o.order_id = ?
            """,
            (int(cleaned_id),)
        )
        row = cursor.fetchone()
        if row:
            return _build_order_details(conn, row)

    # 2. Busca por código de rastreio (ex: BR...)
    cursor.execute(
        """
        SELECT o.*, c.name as customer_name, c.email as customer_email, c.phone as customer_phone, c.city as customer_city
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE UPPER(o.tracking_code) = UPPER(?)
        """,
        (identifier.strip(),)
    )
    row = cursor.fetchone()
    if row:
        return _build_order_details(conn, row)

    # 3. Busca por cliente (nome, email ou telefone)
    norm = f"%{normalize_text(identifier)}%"
    digits = re_sub_digits(identifier)
    phone_filter = f"%{digits}%" if len(digits) >= 8 else "__NO_PHONE__"
    raw_ident = identifier.strip()

    cursor.execute(
        """
        SELECT o.*, c.name as customer_name, c.email as customer_email, c.phone as customer_phone, c.city as customer_city
        FROM orders o
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE (LENGTH(?) >= 3 AND (c.name_norm LIKE ? OR c.email_norm LIKE ?)) OR c.phone_digits LIKE ?
        ORDER BY o.order_date DESC
        LIMIT 1
        """,
        (raw_ident, norm, norm, phone_filter)
    )
    row = cursor.fetchone()
    if row:
        return _build_order_details(conn, row)

    return None


def re_sub_digits(text: str) -> str:
    import re
    return re.sub(r"\D", "", text)


def _build_order_details(conn: sqlite3.Connection, order_row: sqlite3.Row) -> dict[str, Any]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT oi.quantity, p.name as product_name, p.effective_price_brl
        FROM order_items oi
        JOIN products p ON oi.product_id = p.product_id
        WHERE oi.order_id = ?
        """,
        (order_row["order_id"],)
    )
    items = [
        {"item": r["product_name"], "quantity": r["quantity"], "unit_price": r["effective_price_brl"]}
        for r in cursor.fetchall()
    ]

    return {
        "order_id": order_row["order_id"],
        "customer_name": order_row["customer_name"],
        "customer_city": order_row["customer_city"],
        "customer_email": order_row["customer_email"],
        "order_date": order_row["order_date"],
        "status": order_row["status_pt"],
        "total_brl": order_row["total_brl"],
        "payment_method": order_row["payment_method_pt"],
        "tracking_code": order_row["tracking_code"] or "Ainda não gerado",
        "estimated_delivery": order_row["estimated_delivery"] or "Aguardando postagem",
        "notes": order_row["notes"],
        "items": items,
    }


def query_policies(pergunta_ou_topico: str) -> str:
    """
    Consulta o manual de políticas da Empório da Música e retorna o trecho relevante com orientações oficiais.
    """
    retriever = get_policy_retriever()
    return retriever.get_formatted_context(pergunta_ou_topico, top_k=2)


def get_store_info() -> dict[str, Any]:
    """
    Retorna as informações cadastrais e gerais sobre a Empório da Música.
    """
    return {
        "nome": "Empório da Música",
        "fundacao": 2008,
        "cidade": "Campo Grande/MS",
        "endereco": "Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, CEP 79202-333",
        "telefone_whatsapp": "(67) 3341-4444",
        "email": "contato@emporiodamusica.com.br",
        "horario_funcionamento": {
            "segunda_a_sexta": "09:00 às 18:00",
            "sabado": "09:00 às 13:00",
            "domingo_e_feriados": "Fechado"
        },
        "catalogo_escopo": "Exclusivamente instrumentos musicais (guitarras, violões, baixos, baterias, teclados, sopro, cordas orquestrais e ukuleles). NÃO comercializa acessórios (palhetas, cordas, cabos, cases, pedais, amplificadores).",
        "politica_trocas_resumo": "Arrependimento em até 7 dias corridos (CDC Art. 49) com reembolso integral; defeito de fabricação em até 30 dias pela loja e após isso pelo fabricante.",
        "politica_frete_resumo": "Campo Grande: Grátis acima de R$ 500,00 ou R$ 35,00 fixo; Outras cidades via PAC, SEDEX ou Jadlog com rastreamento e seguro.",
        "formas_pagamento_resumo": "PIX (5% de desconto à vista, não cumulativo com promoções), Débito, Crédito até 12x sem juros (parcela mínima de R$ 100), Boleto à vista.",
    }


# Dicionário descritivo das tools para uso em function calling / ReAct
AVAILABLE_TOOLS_SPEC = [
    {
        "name": "search_products",
        "description": "Consulta o catálogo de instrumentos musicais da loja. Permite filtrar por texto/modelo, categoria, preço máximo e disponibilidade de estoque.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Termo de busca (ex: 'violão', 'yamaha', 'tagima', 'teclado')"},
                "category": {"type": "string", "description": "Nome da categoria (ex: 'Violões', 'Guitarras', 'Teclados e Pianos')"},
                "max_price": {"type": "number", "description": "Preço máximo em reais (ex: 1000.00)"},
                "only_available": {"type": "boolean", "description": "Se verdadeiro, filtra apenas instrumentos em estoque"},
            },
        },
    },
    {
        "name": "get_product_details",
        "description": "Obtém detalhes completos de um produto específico (preço original, preço promocional se houver, preço no PIX, parcelamento sem juros, especificações e estoque).",
        "parameters": {
            "type": "object",
            "properties": {
                "product_query": {"type": "string", "description": "Nome exato ou parcial do produto (ex: 'Takamine GD20', 'Yamaha C40') ou ID numérico"},
            },
            "required": ["product_query"],
        },
    },
    {
        "name": "search_order",
        "description": "Consulta status de pedidos, código de rastreamento, previsão de entrega e itens comprados por ID do pedido, código de rastreio ou nome/e-mail do cliente.",
        "parameters": {
            "type": "object",
            "properties": {
                "identifier": {"type": "string", "description": "ID do pedido (ex: '101'), código de rastreio (ex: 'BR4K7M2X9P1BR') ou nome do cliente"},
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "query_policies",
        "description": "Consulta o manual oficial de políticas e procedimentos da loja (regras de devolução/arrependimento em 7 dias, trocas, garantia, prazos e custos de frete, regras de parcelamento, promoções).",
        "parameters": {
            "type": "object",
            "properties": {
                "pergunta_ou_topico": {"type": "string", "description": "Assunto ou dúvida sobre as regras da loja (ex: 'devolução por arrependimento', 'garantia legal', 'frete sedex')"},
            },
            "required": ["pergunta_ou_topico"],
        },
    },
    {
        "name": "get_store_info",
        "description": "Retorna informações gerais institucionais da loja: endereço físico, telefone/WhatsApp, horário de funcionamento e escopo de atuação.",
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
]


TOOL_MAPPING = {
    "search_products": search_products,
    "get_product_details": get_product_details,
    "search_order": search_order,
    "query_policies": query_policies,
    "get_store_info": get_store_info,
}


def execute_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
    """Executa a ferramenta especificada passando os argumentos decodificados."""
    if tool_name not in TOOL_MAPPING:
        return {"error": f"Ferramenta desconhecida: {tool_name}"}
    func = TOOL_MAPPING[tool_name]
    try:
        return func(**arguments)
    except Exception as e:
        return {"error": f"Erro ao executar {tool_name}: {str(e)}"}
