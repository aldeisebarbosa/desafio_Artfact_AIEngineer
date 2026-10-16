# importação de bibliotecas para a manipulação de dados, expressões regulares, banco de dados SQLite e manipulação de caminhos de arquivos

import json
import re
import sqlite3
import unicodedata
from pathlib import Path
import pandas as pd

DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "emporio.db"

STATUS_PT = {
    "delivered": "Entregue",
    "shipped": "Enviado / Em trânsito",
    "confirmed": "Confirmado (Em separação)",
    "pending": "Pendente (Aguardando confirmação de pagamento)",
    "cancelled": "Cancelado",
}

PAYMENT_PT = {
    "pix": "PIX",
    "boleto": "Boleto Bancário",
    "debit": "Cartão de Débito",
    "credit_3x": "Cartão de Crédito (3x)",
    "credit_6x": "Cartão de Crédito (6x)",
    "credit_12x": "Cartão de Crédito (12x)",
}

def normalize_text(text: str) -> str:
    """
    Normaliza o texto removendo acentos, espaços extras e convertendo para minúsculas.
    """
    if pd.isna(text) or text is None:
        return ""
    text = str(text).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).strip()

def normalize_phone(phone: str) -> str:
    """
    Normaliza o número de telefone removendo caracteres não numéricos.
    """
    if pd.isna(phone) or phone is None:
        return ""
    return re.sub(r"\D", "", str(phone))

def calculate_max_installments(price: float) -> tuple[int, float]:
    """
    Calcula o parcelamento máximo sem juros respeitando a Seção 3.1 do manual de integração da Empório da Música.
    -7x a 12x: sem juros, parcela mínima de 100,00
    -4x a 6x: sem juros, parcela mínima de 80,00
    -até 3x: sem juros, sem valor mínimo (exceto abaixo de R$50,00)
    """
    for n in range(12, 6, -1):
        if price / n >= 100:
            return n, round(price / n, 2)
    for n in range(6, 3, -1):
        if price / n >= 80:
            return n, round(price / n, 2)
    for n in range(3, 0, -1):
        if price / n >= 50 or n==1:
            return n, round(price / n, 2)
    return 1, round(price, 2)

def _read_csv_flexible(base_name: str, data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Lê o CSV aceitando tanto 'products.csv' quanto 'desafio_tecnico_ai_eng - products.csv'."""
    candidates = [
        data_dir / f"{base_name}.csv",
        data_dir / f"desafio_tecnico_ai_eng - {base_name}.csv",
        Path(f"{base_name}.csv"),
        Path(f"desafio_tecnico_ai_eng - {base_name}.csv"),
    ]
    for path in candidates:
        if path.exists():
            return pd.read_csv(path)
    raise FileNotFoundError(f"Arquivo CSV '{base_name}.csv' não encontrado em {data_dir}.")


def build_clean_tables(data_dir: Path = DATA_DIR) -> dict[str, pd.DataFrame]:
    """Carrega, limpa e enriquece todas as 6 tabelas CSV."""
    cats = _read_csv_flexible("categories", data_dir)
    custs = _read_csv_flexible("customers", data_dir)
    items = _read_csv_flexible("order_items", data_dir)
    orders = _read_csv_flexible("orders", data_dir)
    prods = _read_csv_flexible("products", data_dir)
    promos = _read_csv_flexible("promotions", data_dir)

    # 1. Categorias normalizadas
    cats["name_norm"] = cats["name"].apply(normalize_text)

    # 2. Clientes com campos de busca normalizados
    custs["name_norm"] = custs["name"].apply(normalize_text)
    custs["email_norm"] = custs["email"].str.strip().str.lower()
    custs["phone_digits"] = custs["phone"].apply(normalize_phone)
    custs["city_norm"] = custs["city"].apply(normalize_text)

    # 3. Promoções separadas entre ativas (is_active == 1) e expiradas (is_active == 0)
    expired_map: dict[int, list[dict]] = {}
    for _, row in promos[promos["is_active"] == 0].iterrows():
        pid = int(row["product_id"])
        expired_map.setdefault(pid, []).append({
            "promotion_id": int(row["promotion_id"]),
            "description": str(row["description"]),
            "discount_percent": int(row["discount_percent"]),
        })

    active_promos = promos[promos["is_active"] == 1][
        ["product_id", "promotion_id", "discount_percent", "description"]
    ].rename(columns={
        "promotion_id": "active_promotion_id",
        "discount_percent": "active_discount_percent",
        "description": "active_promo_description",
    })

    # 4. Produtos enriquecidos com categoria, preços efetivos, PIX e parcelamento
    prods_clean = prods.merge(
        cats[["category_id", "name", "name_norm"]].rename(
            columns={"name": "category_name", "name_norm": "category_norm"}
        ),
        on="category_id",
        how="left",
    ).merge(
        active_promos,
        on="product_id",
        how="left",
    )

    prods_clean["has_active_promo"] = prods_clean["active_discount_percent"].notna().astype(int)
    prods_clean["active_discount_percent"] = prods_clean["active_discount_percent"].fillna(0).astype(int)
    prods_clean["active_promo_description"] = prods_clean["active_promo_description"].fillna("")
    prods_clean["expired_promotions_json"] = prods_clean["product_id"].map(
        lambda pid: json.dumps(expired_map.get(int(pid), []), ensure_ascii=False)
    )

    # Preço considerando promoção ativa
    prods_clean["effective_price_brl"] = (
        prods_clean["price_brl"] * (1.0 - prods_clean["active_discount_percent"] / 100.0)
    ).round(2)

    # Regra 6.2: Desconto de 5% no PIX NÃO é cumulativo com promoções ativas
    prods_clean["pix_price_brl"] = [
        eff if has_promo else round(orig * 0.95, 2)
        for orig, eff, has_promo in zip(
            prods_clean["price_brl"],
            prods_clean["effective_price_brl"],
            prods_clean["has_active_promo"],
        )
    ]

    # Regra 3.1: Cálculo de parcelamento máximo sem juros
    installments_info = [calculate_max_installments(p) for p in prods_clean["effective_price_brl"]]
    prods_clean["max_installments"] = [x[0] for x in installments_info]
    prods_clean["installment_value_brl"] = [x[1] for x in installments_info]

    # Disponibilidade imediata (ativo + estoque positivo)
    prods_clean["is_available"] = (
        (prods_clean["status"] == "active") & (prods_clean["stock_quantity"] > 0)
    ).astype(int)

    # Coluna unificada de busca textual sem acentos
    prods_clean["search_blob"] = [
        normalize_text(f"{n} {c} {d} {s}")
        for n, c, d, s in zip(
            prods_clean["name"],
            prods_clean["category_name"],
            prods_clean["description"],
            prods_clean["specs"],
        )
    ]

    # 5. Pedidos limpos e traduzidos
    orders["status_pt"] = orders["status"].map(STATUS_PT).fillna(orders["status"])
    orders["payment_method_pt"] = orders["payment_method"].map(PAYMENT_PT).fillna(orders["payment_method"])
    orders["tracking_code"] = orders["tracking_code"].fillna("")
    orders["estimated_delivery"] = orders["estimated_delivery"].fillna("")
    orders["notes"] = orders["notes"].fillna("")

    return {
        "categories": cats,
        "customers": custs,
        "order_items": items,
        "orders": orders,
        "products": prods_clean,
        "promotions": promos,
    }


def get_db_connection(db_path: Path = DB_PATH, data_dir: Path = DATA_DIR) -> sqlite3.Connection:
    """Inicializa o banco SQLite com as tabelas tratadas e retorna a conexão."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row

    tables = build_clean_tables(data_dir=data_dir)
    for table_name, df in tables.items():
        df.to_sql(table_name, conn, if_exists="replace", index=False)

    return conn


if __name__ == "__main__":
    conn = get_db_connection()
    cursor = conn.cursor()
    print("✅ Banco SQLite gerado com sucesso em:", DB_PATH)
    for tbl in ["categories", "products", "promotions", "customers", "orders", "order_items"]:
        count = cursor.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        print(f" - Tabela '{tbl}': {count} registros carregados.")