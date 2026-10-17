"""
Testes unitários e de integração para o Agente da Empório da Música.
Valida o enriquecimento de dados, as regras comerciais, as tools e os fluxos de conversação.
"""

import sys
import unittest
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent / "emporio-da-musica-agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))

from src.database import get_db_connection, calculate_max_installments
from src.tools import (
    search_products,
    get_product_details,
    search_order,
    get_store_info,
    query_policies,
)
from src.agent import EmporioAgent


class TestDatabaseAndBusinessRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = get_db_connection()

    def test_database_tables_populated(self):
        cursor = self.conn.cursor()
        for tbl in ["products", "orders", "order_items", "customers", "promotions", "categories"]:
            count = cursor.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            self.assertGreater(count, 0, f"Tabela {tbl} deveria ter registros carregados.")

    def test_installment_business_rules(self):
        # Acima de 7x exige parcela mínima de R$ 100
        n, val = calculate_max_installments(1200.0)
        self.assertEqual(n, 12)
        self.assertEqual(val, 100.0)

        # R$ 400 permite no máximo 4x de R$ 100 ou 5x de R$ 80
        n, val = calculate_max_installments(400.0)
        self.assertEqual(n, 5)
        self.assertEqual(val, 80.0)

        # R$ 150 permite 3x de R$ 50
        n, val = calculate_max_installments(150.0)
        self.assertEqual(n, 3)
        self.assertEqual(val, 50.0)


class TestAgentTools(unittest.TestCase):
    def test_search_products_max_price(self):
        results = search_products(query="violao", max_price=1000.0, only_available=True)
        self.assertGreater(len(results), 0)
        for prod in results:
            self.assertLessEqual(prod["effective_price_brl"], 1000.0)
            self.assertTrue(prod["is_available"])

    def test_get_product_details_takamine_gd20(self):
        prod = get_product_details("Takamine GD20")
        self.assertIsNotNone(prod)
        self.assertIn("Takamine GD20", prod["name"])
        self.assertEqual(prod["price_brl"], 2199.00)
        # PIX 5% sobre 2199 = 2089.05
        self.assertAlmostEqual(prod["pix_price_brl"], 2089.05, places=2)

    def test_search_order_by_id(self):
        order = search_order("1")
        self.assertIsNotNone(order)
        self.assertEqual(order["order_id"], 1)
        self.assertEqual(order["customer_name"], "Pedro Henrique Oliveira")
        self.assertGreater(len(order["items"]), 0)

    def test_get_store_info(self):
        info = get_store_info()
        self.assertEqual(info["nome"], "Empório da Música")
        self.assertIn("Campo Grande", info["cidade"])
        self.assertIn("14 de Maio", info["endereco"])

    def test_query_policies_return(self):
        policy_text = query_policies("como funciona a devolução por arrependimento")
        self.assertIsInstance(policy_text, str)
        self.assertIn("7", policy_text)


class TestEmporioAgentDialogs(unittest.TestCase):
    def setUp(self):
        self.agent = EmporioAgent(provider="local_engine")

    def test_scenario_violoes_ate_mil_reais(self):
        resp = self.agent.chat("Quais opções de violões disponíveis custando até R$1000?")
        self.assertIn("viol", resp.lower())
        self.assertTrue("R$" in resp)
        self.assertTrue("PIX" in resp)

    def test_scenario_endereco_e_horario(self):
        resp = self.agent.chat("Qual o endereço da loja?")
        self.assertIn("14 de Maio", resp)
        self.assertIn("Campo Grande", resp)

    def test_scenario_preco_takamine(self):
        resp = self.agent.chat("Quanto custa o Takamine GD20?")
        self.assertIn("Takamine GD20", resp)
        self.assertIn("2199", resp)
        self.assertIn("PIX", resp)

    def test_scenario_devolucao_arrependimento(self):
        resp = self.agent.chat("Me arrependi da minha compra, posso devolver meu pedido?")
        self.assertIn("7", resp)
        self.assertIn("arrependimento", resp.lower())

    def test_scenario_status_pedido(self):
        resp = self.agent.chat("Qual o status do pedido 1?")
        self.assertIn("Pedro Henrique", resp)
        self.assertIn("Pedido #1", resp)

    def test_scenario_fora_de_escopo_acessorios(self):
        resp = self.agent.chat("Vocês vendem encordoamento de nylon e palhetas?")
        self.assertIn("exclusivamente com instrumentos", resp.lower())
        self.assertIn("não comercializamos acessórios", resp.lower())


if __name__ == "__main__":
    unittest.main()
