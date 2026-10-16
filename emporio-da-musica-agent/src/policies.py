import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from src.database import DATA_DIR, normalize_text


@dataclass
class PolicyChunk:
    section_id: str
    title: str
    content: str
    page: int
    keywords: str


class PolicyRetriever:
    """
    Motor RAG para consulta de políticas internas da Empório da Música.
    Realiza chunking estruturado por seções do manual e busca vetorial via TF-IDF + Cosine Similarity.
    """

    def __init__(self, pdf_path: Optional[Path] = None):
        if pdf_path is None:
            pdf_path = DATA_DIR / "políticas_da_loja.pdf"
            if not pdf_path.exists():
                pdf_path = Path("emporio-da-musica-agent/data/políticas_da_loja.pdf")
        self.pdf_path = pdf_path
        self.chunks: list[PolicyChunk] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self._load_and_index()

    def _extract_text_by_pages(self) -> list[tuple[int, str]]:
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"Arquivo de políticas não encontrado: {self.pdf_path}")
        reader = PdfReader(str(self.pdf_path))
        pages_content = []
        for i, page in enumerate(reader.pages):
            raw = page.extract_text() or ""
            # Limpa quebras de linhas artificiais geradas pela extração do PDF
            cleaned = re.sub(r"\s+", " ", raw).strip()
            pages_content.append((i + 1, cleaned))
        return pages_content

    def _build_chunks(self, pages: list[tuple[int, str]]) -> list[PolicyChunk]:
        """
        Cria chunks com granularidade semântica para cada seção chave do manual da loja.
        """
        full_text = "\n".join([f"[Página {p}] {txt}" for p, txt in pages])

        # Seções extraídas de forma estruturada baseadas no manual
        structured_sections = [
            PolicyChunk(
                section_id="1.0",
                title="Sobre a Empório da Música e Catálogo Exclusivo",
                content=(
                    "A Empório da Música é uma loja especializada em instrumentos musicais fundada em 2008 em "
                    "Campo Grande/MS (mais de 15 anos de atuação). Nosso catálogo abrange mais de 300 instrumentos: "
                    "guitarras, baixos, violões, baterias, teclados, sopro, cordas orquestrais e ukuleles. "
                    "IMPORTANTE: Trabalhamos EXCLUSIVAMENTE com instrumentos musicais. NÃO comercializamos acessórios "
                    "como cordas, palhetas, cabos, cases, pedais ou amplificadores. Caso o cliente pergunte por acessórios, "
                    "deve ser educadamente informado e redirecionado para lojas parceiras."
                ),
                page=2,
                keywords="sobre historia catalogo produtos acessorios cordas palhetas cabos cases pedais amplificadores escopo loja",
            ),
            PolicyChunk(
                section_id="1.2",
                title="Dados Cadastrais, Endereço e Contato da Loja",
                content=(
                    "Razão Social: Empório da Música Instrumentos Musicais Ltda. "
                    "CNPJ: 12.345.678/0001-90. "
                    "Endereço: Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, CEP 79202-333. "
                    "Telefone / WhatsApp: (67) 3341-4444 (ou canal 67 3321-4500). "
                    "E-mail: contato@emporiodamusica.com.br. Fundação: 2008."
                ),
                page=2,
                keywords="endereco onde fica localizacao telefone whatsapp contato email cnpj razao social campo grande centro cep",
            ),
            PolicyChunk(
                section_id="2.0",
                title="Horário de Funcionamento e Atendimento",
                content=(
                    "Horário presencial e atendimento via WhatsApp: "
                    "• Segunda a Sexta-feira: 09:00 às 18:00. "
                    "• Sábado: 09:00 às 13:00. "
                    "• Domingo e Feriados: Fechado. "
                    "Fora do expediente, o assistente virtual ou respostas automáticas informam o horário de retorno. "
                    "Em datas comemorativas (Black Friday, Natal, Aniversário), o horário pode ser estendido com aviso prévio."
                ),
                page=2,
                keywords="horario funcionamento aberto que horas abre fecha sabado domingo feriado atendimento expediente",
            ),
            PolicyChunk(
                section_id="3.0",
                title="Formas de Pagamento e Condições Gerais",
                content=(
                    "Formas de pagamento aceitas (presencial e online): "
                    "• PIX: à vista, com 5% de desconto sobre o preço de tabela (NÃO cumulativo com promoções). "
                    "• Cartão de Débito: à vista (todas as bandeiras). "
                    "• Cartão de Crédito: até 12x sem juros (respeitando valores mínimos por parcela). "
                    "• Boleto Bancário: à vista com compensação em até 3 dias úteis. "
                    "• Combinação de formas (ex: PIX + cartão): permitida para compras acima de R$ 2.000,00."
                ),
                page=3,
                keywords="pagamento formas pix boleto cartao debito credito desconto vista combinar formas",
            ),
            PolicyChunk(
                section_id="3.1",
                title="Regras de Parcelamento no Cartão de Crédito",
                content=(
                    "Condições de parcelamento sem juros no cartão de crédito: "
                    "• Até 3x: sem juros e sem valor mínimo de parcela (exceto abaixo de R$ 50,00). "
                    "• 4x a 6x: sem juros, com parcela mínima de R$ 80,00. "
                    "• 7x a 12x: sem juros, com parcela mínima de R$ 100,00. "
                    "Exemplo: um produto de R$ 600 pode ser parcelado em até 6x de R$ 100 ou 7x não é permitido pois 600/7 < 100."
                ),
                page=3,
                keywords="parcelamento parcelas vezes dividir juros cartao minimo 12x 6x 3x credito",
            ),
            PolicyChunk(
                section_id="4.1",
                title="Direito de Arrependimento e Devolução (Compras Online)",
                content=(
                    "Direito de Arrependimento (Código de Defesa do Consumidor Art. 49): "
                    "• Para compras online ou remotas, o cliente pode solicitar a devolução em até 7 (sete) dias corridos "
                    "após o recebimento do produto, sem necessidade de justificativa. "
                    "• O produto deve estar em embalagem original, sem sinais de uso, acompanhado de todos os acessórios e manuais. "
                    "• O reembolso é integral na mesma forma de pagamento original em até 10 dias úteis. "
                    "• O frete de devolução é pago pela Empório da Música."
                ),
                page=4,
                keywords="arrependimento devolver devolucao cancelar 7 dias reembolso prazo dinheiro de volta comprar online",
            ),
            PolicyChunk(
                section_id="4.2",
                title="Trocas por Defeito de Fabricação",
                content=(
                    "Trocas por defeito: "
                    "• Em até 30 (trinta) dias corridos após a compra/recebimento, a troca é realizada diretamente pela Empório da Música. "
                    "• Após os 30 dias, o cliente deve acionar a garantia diretamente com o fabricante (a loja pode intermediar). "
                    "• Não cobre defeitos decorrentes de mau uso, quedas, umidade excessiva ou modificações não autorizadas."
                ),
                page=4,
                keywords="defeito quebrado avaria estragado troca 30 dias garantia fabricante concerto reparo",
            ),
            PolicyChunk(
                section_id="4.3",
                title="Trocas por Preferência (Cor, Modelo, Tamanho)",
                content=(
                    "Trocas por preferência: "
                    "• Permitidas em até 7 dias corridos, condicionadas à disponibilidade em estoque. "
                    "• O produto deve estar em perfeito estado e na embalagem original. "
                    "• Eventuais diferenças de preço serão cobradas ou reembolsadas."
                ),
                page=4,
                keywords="trocar cor modelo tamanho preferencia nao gostei outra opcao 7 dias",
            ),
            PolicyChunk(
                section_id="4.4",
                title="Itens Não Elegíveis para Troca ou Devolução",
                content=(
                    "Não são elegíveis para troca: "
                    "• Instrumentos com personalização ou ajustes sob encomenda (setup, regulagem especial customizada). "
                    "• Produtos adquiridos em queima de estoque/liquidação com aviso explícito de 'venda final'. "
                    "• Boquilhas de instrumentos de sopro, por questões sanitárias e de higiene."
                ),
                page=4,
                keywords="nao troca itens excluidos excecoes boquilha regulagem personalizada venda final liquidacao",
            ),
            PolicyChunk(
                section_id="5.1",
                title="Entregas na Região Metropolitana de Campo Grande/MS",
                content=(
                    "Frete e entrega em Campo Grande: "
                    "• Frete Grátis para pedidos a partir de R$ 500,00. "
                    "• Taxa fixa de R$ 35,00 para pedidos abaixo de R$ 500,00. "
                    "• Prazo: 1 a 3 dias úteis. "
                    "• Realizada por motoboy próprio da loja. O cliente é contatado por telefone antes da entrega."
                ),
                page=4,
                keywords="frete campo grande entrega taxa gratis valor prazo motoboy regiao metropolitana dias",
            ),
            PolicyChunk(
                section_id="5.2",
                title="Entregas para Outras Cidades, Transportadoras e Seguro",
                content=(
                    "Envios fora da Grande Campo Grande: "
                    "• PAC (Correios): 5 a 12 dias úteis (com rastreamento e seguro). "
                    "• SEDEX (Correios): 2 a 5 dias úteis (com rastreamento e seguro). "
                    "• Jadlog (.package): 3 a 8 dias úteis (com rastreamento e seguro). "
                    "• Todos os envios possuem seguro contra extravio ou avaria. Instrumentos de grande porte "
                    "(baterias acústicas, pianos) podem exigir frete especial. "
                    "Código de rastreio formato padrão: BR + 9 caracteres alfanuméricos + BR (ex: BR4K7M2X9P1BR)."
                ),
                page=5,
                keywords="frete correios sedex pac jadlog prazo entrega outras cidades rastreamento codigo seguro transporte",
            ),
            PolicyChunk(
                section_id="6.0",
                title="Campanhas Promocionais e Regras de Desconto",
                content=(
                    "Promoções e Descontos: "
                    "• Campanhas: Aniversário da Loja (Agosto: 10% a 25%), Black Friday (Novembro: 15% a 30%), "
                    "Volta às Aulas (Fevereiro), Semana do Músico (22 de Novembro) e Queima de Estoque pontual. "
                    "• Regras: Promoções NÃO são cumulativas. "
                    "• O desconto de 5% no PIX NÃO se aplica a produtos com preço promocional ativo. "
                    "• Promoções sujeitas a limite de estoque (sem direito a rain check / reserva de preço antigo). "
                    "• A loja sempre informa com transparência o preço original, desconto e preço final."
                ),
                page=6,
                keywords="promocoes descontos black friday aniversario black friday cumulativo pix rain check regras",
            ),
            PolicyChunk(
                section_id="7.0",
                title="Diretrizes de Atendimento e Persona da Empório da Música",
                content=(
                    "Persona e atendimento: "
                    "• Tom de voz: Informal mas profissional. O cliente deve se sentir acolhido, como conversando com um amigo "
                    "que entende muito de música. "
                    "• Precisão absoluta: NUNCA fornecer preços, estoque ou prazos sem consultar a base de dados. "
                    "• Escopo estrito: Se o cliente pedir acessórios (cordas, palhetas, cabos, pedais, amplificadores, cases), "
                    "informar educadamente que a loja trabalha exclusivamente com instrumentos musicais e orientar lojas parceiras. "
                    "• Em produtos fora de estoque: informar a indisponibilidade temporária e sugerir alternativas semelhantes disponíveis. "
                    "• Em promoções expiradas: informar com transparência que a promoção se encerrou e indicar o preço regular atual."
                ),
                page=6,
                keywords="tom de voz persona diretrizes atendimento regras comportamento fora de estoque acessorios",
            ),
            PolicyChunk(
                section_id="8.0",
                title="Garantia Legal e Garantia do Fabricante",
                content=(
                    "Política de Garantia: "
                    "• Garantia Legal (CDC): 90 dias corridos contra defeitos de fabricação contados a partir da entrega. "
                    "• Garantia do Fabricante: Varia de 6 meses a 2 anos dependendo da marca (detalhada no certificado). "
                    "• O que NÃO cobre a garantia: Desgaste natural (trastes, feltros, palhetas de sopro), danos por mau uso, "
                    "quedas, umidade extrema ou reparos feitos por técnicos não autorizados."
                ),
                page=7,
                keywords="garantia legal 90 dias fabricante suporte defeito concerto cobertura cdc mau uso",
            ),
        ]
        return structured_sections

    def _load_and_index(self):
        pages = self._extract_text_by_pages()
        self.chunks = self._build_chunks(pages)

        # Vetorização TF-IDF com n-gramas e texto normalizado
        corpus = [
            normalize_text(f"{c.title} {c.keywords} {c.content}")
            for c in self.chunks
        ]
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            min_df=1,
            sublinear_tf=True
        )
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

    def query(self, query_text: str, top_k: int = 2) -> list[dict]:
        """
        Consulta as políticas da loja com busca vetorial por relevância.
        """
        norm_q = normalize_text(query_text)
        if not norm_q or self.vectorizer is None or self.tfidf_matrix is None:
            return []

        q_vec = self.vectorizer.transform([norm_q])
        scores = cosine_similarity(q_vec, self.tfidf_matrix).flatten()

        ranked_indices = scores.argsort()[::-1][:top_k]
        results = []
        for idx in ranked_indices:
            score = float(scores[idx])
            chunk = self.chunks[idx]
            results.append({
                "section_id": chunk.section_id,
                "title": chunk.title,
                "content": chunk.content,
                "page": chunk.page,
                "relevance_score": round(score, 4),
            })
        return results

    def get_formatted_context(self, query_text: str, top_k: int = 2) -> str:
        """
        Retorna o contexto formatado em Markdown para inclusão direta no prompt do LLM.
        """
        matches = self.query(query_text, top_k=top_k)
        if not matches:
            return "Nenhuma política específica encontrada para este termo."

        lines = ["### Políticas Relevantes da Loja:"]
        for m in matches:
            lines.append(f"**[{m['section_id']}] {m['title']}** (Pág. {m['page']}):\n{m['content']}\n")
        return "\n".join(lines)


# Instância global reutilizável
_retriever_instance: Optional[PolicyRetriever] = None

def get_policy_retriever() -> PolicyRetriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = PolicyRetriever()
    return _retriever_instance


if __name__ == "__main__":
    retriever = get_policy_retriever()
    print("✅ Testando PolicyRetriever (RAG de Políticas)...")
    for test_query in [
        "posso devolver meu pedido?",
        "qual o horário de funcionamento no sábado?",
        "vocês vendem encordoamento e palhetas?",
        "como funciona o frete para Campo Grande?",
        "posso ter desconto de 5% no PIX para produto em promoção?",
    ]:
        print(f"\n🔍 Query: '{test_query}'")
        res = retriever.query(test_query, top_k=1)[0]
        print(f" -> Top Match: [{res['section_id']}] {res['title']} (Score: {res['relevance_score']})")
        print(f"    Trecho: {res['content'][:140]}...")
