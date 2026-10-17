import json
import os
import re
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any, Optional

from src.tools import (
    AVAILABLE_TOOLS_SPEC,
    execute_tool,
    search_products,
    get_product_details,
    search_order,
    query_policies,
    get_store_info,
)
from src.database import normalize_text


SYSTEM_PROMPT = """Você é o assistente virtual inteligente da "Empório da Música", loja tradicional de instrumentos musicais fundada em 2008 em Campo Grande/MS.

Sua Persona:
- Tom de voz: Amigável, acolhedor e atencioso, como um músico amigo que entende muito do assunto e está pronto para ajudar, mantendo sempre o profissionalismo e a cordialidade.
- Nunca seja ríspido ou impessoal. Demonstre paixão pela música.

Diretrizes e Regras Essenciais:
1. ESCOPO DA LOJA:
   - A Empório da Música comercializa EXCLUSIVAMENTE instrumentos musicais (violões, guitarras, contrabaixos, baterias, teclados, pianos, sopro, cordas orquestrais, ukuleles).
   - A loja NÃO vende acessórios (como cordas/encordoamentos, palhetas, cabos, cases, suportes, pedais de efeito ou amplificadores).
   - Se o cliente perguntar sobre acessórios, esclareça educadamente o foco exclusivo em instrumentos e sugira procurar lojas parceiras especializadas em acessórios.

2. PRECISÃO DAS INFORMAÇÕES (CONSULTA OBRIGATÓRIA A FERRAMENTAS):
   - NUNCA invente preços, promoções ou disponibilidade de estoque.
   - Sempre consulte as ferramentas disponíveis para obter os dados reais do catálogo ou do pedido do cliente.

3. CONDIÇÕES COMERCIAIS E POLÍTICAS:
   - Pagamento via PIX: concede 5% de desconto sobre o preço de tabela, MAS NÃO é cumulativo com produtos já em promoção ativa.
   - Parcelamento no cartão: até 12x sem juros (respeitando parcelas mínimas: até 3x sem mínimo para valores acima de R$ 50; 4x a 6x mínimo de R$ 80/parcela; 7x a 12x mínimo de R$ 100/parcela).
   - Trocas e Devoluções: Devolução por arrependimento de compras online em até 7 dias corridos após o recebimento (CDC Art. 49), com frete por conta da loja e reembolso total em até 10 dias úteis. Defeitos de fábrica são cobertos pela loja em até 30 dias corridos e após isso pelo fabricante.
   - Frete: Na Grande Campo Grande, frete grátis para compras acima de R$ 500,00 (ou taxa fixa de R$ 35,00 abaixo desse valor), entrega por motoboy em 1 a 3 dias úteis. Demais localidades via Correios (PAC/SEDEX) ou Jadlog.
   - Horários e Localização: Segunda a sexta das 09:00 às 18:00, sábados das 09:00 às 13:00. Rua 14 de Maio, 3200 — Centro, Campo Grande - MS.

4. MENSAGENS FORA DE ESCOPO:
   - Caso o cliente pergunte algo totalmente fora do contexto da loja (ex.: culinária, esportes, assuntos aleatórios), responda de maneira simpática, mas lembre-o com carinho de que seu objetivo ali é ajudá-lo com instrumentos musicais e atendimento da Empório da Música.
"""


class EmporioAgent:
    """
    Agente de atendimento da Empório da Música.
    Opera no paradigma Tool-Use / ReAct com suporte a múltiplos provedores LLM
    (OpenAI, Groq, Ollama, Gemini) e motor determinístico inteligente para fallback offline.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        verbose: bool = False,
    ):
        self.verbose = verbose
        self.history: list[dict[str, str]] = []
        self._init_provider(provider, model, api_key)

    def _init_provider(self, provider: Optional[str], model: Optional[str], api_key: Optional[str]):
        # Identificação automática de provedor e chaves
        groq_key = api_key or os.getenv("GROQ_API_KEY")
        openai_key = api_key or os.getenv("OPENAI_API_KEY")

        if provider == "groq" or (provider is None and groq_key):
            self.provider = "groq"
            self.api_key = groq_key
            self.model = model or "llama-3.3-70b-versatile"
            self.base_url = "https://api.groq.com/openai/v1"
        elif provider == "openai" or (provider is None and openai_key):
            self.provider = "openai"
            self.api_key = openai_key
            self.model = model or "gpt-4o-mini"
            self.base_url = "https://api.openai.com/v1"
        elif provider == "ollama":
            self.provider = "ollama"
            self.api_key = "ollama"
            self.model = model or "llama3.2"
            self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        else:
            self.provider = "local_engine"
            self.api_key = None
            self.model = "rule-assisted-hybrid"
            self.base_url = None

    def reset_history(self):
        self.history = []

    def chat(self, user_message: str) -> str:
        """Processa a mensagem do usuário e retorna a resposta do agente."""
        self.history.append({"role": "user", "content": user_message})

        if self.provider == "local_engine" or not self.api_key:
            response_text = self._autonomous_engine(user_message)
        else:
            try:
                response_text = self._call_llm_with_tools(user_message)
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ Erro na chamada da API LLM ({self.provider}): {e}. Recorrendo ao motor local.")
                response_text = self._autonomous_engine(user_message)

        self.history.append({"role": "assistant", "content": response_text})
        return response_text

    def _call_llm_with_tools(self, user_message: str) -> str:
        """Executa o ciclo de Tool-Use / Function Calling usando a API OpenAI-compatible."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        tools_payload = [
            {"type": "function", "function": spec}
            for spec in AVAILABLE_TOOLS_SPEC
        ]

        messages_payload = [{"role": "system", "content": SYSTEM_PROMPT}] + self.history

        for _ in range(4):
            req_data = {
                "model": self.model,
                "messages": messages_payload,
                "tools": tools_payload,
                "tool_choice": "auto",
                "temperature": 0.4,
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(req_data).encode("utf-8"),
                headers=headers,
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_json = json.loads(resp.read().decode("utf-8"))

            choice = resp_json["choices"][0]
            message_obj = choice["message"]

            tool_calls = message_obj.get("tool_calls")
            if not tool_calls:
                return message_obj.get("content", "")

            messages_payload.append(message_obj)
            for tc in tool_calls:
                func_name = tc["function"]["name"]
                raw_args = tc["function"]["arguments"]
                call_id = tc["id"]
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                except Exception:
                    args = {}

                if self.verbose:
                    print(f"🛠️ Executando Ferramenta: {func_name} com argumentos {args}")

                tool_output = execute_tool(func_name, args)

                messages_payload.append({
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": json.dumps(tool_output, ensure_ascii=False) if not isinstance(tool_output, str) else tool_output,
                })

        return "Peço desculpas, tive uma oscilação momentânea ao processar sua consulta. Poderia repetir?"

    def _autonomous_engine(self, user_message: str) -> str:
        """
        Motor de inferência estruturado e autônomo.
        Garante funcionamento imediato e 100% fiel à persona mesmo sem credenciais externas de LLM.
        """
        norm_msg = normalize_text(user_message)

        # 1. Detecção de busca por acessórios (fora do escopo da loja)
        accessories_keywords = [
            "corda", "cordas", "encordoamento", "palheta", "palhetas",
            "cabo", "cabos", "case", "cases", "bag", "capa", "pedal", "pedais",
            "amplificador", "amplificadores", "afinador", "correia"
        ]
        if any(re.search(rf"\b{kw}\b", norm_msg) for kw in accessories_keywords):
            return (
                "Olá! Tudo bem? Que bom falar com você! 🎸\n\n"
                "Aqui na **Empório da Música**, nós trabalhamos **exclusivamente com instrumentos musicais** "
                "(como violões, guitarras, baixos, baterias, teclados, sopro e cordas orquestrais).\n\n"
                "Por isso, infelizmente **não comercializamos acessórios** (como cordas, palhetas, cabos, cases ou pedais). "
                "Para esses itens, recomendamos procurar lojas parceiras especializadas em acessórios aqui na região!\n\n"
                "Mas se você estiver procurando um novo instrumento para fazer um som incrível, será um prazer te apresentar as melhores opções do nosso catálogo. O que tem em mente?"
            )

        # 2. Detecção de dúvidas sobre Devolução / Arrependimento / Trocas / Garantia
        return_keywords = ["devolver", "devolucao", "arrependi", "arrepender", "troca", "trocar", "defeito", "garantia"]
        if any(kw in norm_msg for kw in return_keywords):
            if "arrepend" in norm_msg or "devolver" in norm_msg:
                return (
                    "Olá! Compreendemos perfeitamente a sua situação e pode ficar totalmente tranquilo(a)! 🤝\n\n"
                    "De acordo com as nossas políticas e o Código de Defesa do Consumidor (Artigo 49):\n"
                    "• Em compras online ou remotas, você tem até **7 (sete) dias corridos** após o recebimento para solicitar a devolução por arrependimento, sem necessidade de qualquer justificativa.\n"
                    "• O produto deve estar em sua embalagem original, sem sinais de uso, junto de todos os manuais e eventuais itens inclusos.\n"
                    "• O frete de devolução é **por nossa conta** e o reembolso é feito de forma integral na mesma modalidade de pagamento original em até 10 dias úteis.\n\n"
                    "Se o seu pedido estiver dentro desse prazo de 7 dias, basta nos informar o número do pedido ou seu CPF/nome para iniciarmos o procedimento com a nossa equipe de atendimento!"
                )
            elif "defeito" in norm_msg or "garantia" in norm_msg:
                return (
                    "Olá! Se o seu instrumento apresentou algum defeito, estamos aqui para te auxiliar da melhor forma! 🛠️\n\n"
                    "• **Até 30 dias corridos** da compra ou recebimento: a troca por defeito de fabricação é feita diretamente aqui pela Empório da Música.\n"
                    "• **Após 30 dias**: intermediamos o acionamento da garantia junto ao fabricante (que costuma variar de 6 meses a 2 anos, além dos 90 dias de garantia legal do CDC).\n\n"
                    "Poderia nos passar o número do seu pedido ou os detalhes do ocorrido para te orientarmos no passo a passo?"
                )

        # 3. Detecção de dúvidas sobre Informações da Loja, Endereço e Horários
        store_info_keywords = ["endereco", "onde fica", "localizacao", "horario", "funciona", "aberto", "que horas", "abre", "fecha", "sabado", "domingo", "telefone", "whatsapp", "contato"]
        if any(kw in norm_msg for kw in store_info_keywords) and not any(k in norm_msg for k in ["preco", "custa", "valor", "pedido"]):
            info = get_store_info()
            return (
                f"Olá! A **Empório da Música** está de portas abertas esperando por você em Campo Grande! 🎶\n\n"
                f"📍 **Endereço**: {info['endereco']}\n"
                f"📞 **Telefone / WhatsApp**: {info['telefone_whatsapp']}\n"
                f"✉️ **E-mail**: {info['email']}\n\n"
                f"🕒 **Horário de Funcionamento**:\n"
                f"• Segunda a Sexta: {info['horario_funcionamento']['segunda_a_sexta']}\n"
                f"• Sábados: {info['horario_funcionamento']['sabado']}\n"
                f"• Domingos e Feriados: {info['horario_funcionamento']['domingo_e_feriados']}\n\n"
                f"Venha tomar um café conosco e testar os instrumentos pessoalmente!"
            )

        # 4. Detecção de consulta sobre Pedidos / Rastreamento / Entrega
        order_keywords = ["pedido", "rastreio", "rastreamento", "status", "entrega", "onde esta"]
        extracted_digits = re.findall(r"\b\d{1,5}\b", user_message)
        tracking_match = re.findall(r"\bBR[A-Z0-9]+BR\b", user_message.upper())

        if any(kw in norm_msg for kw in order_keywords) or tracking_match:
            search_key = ""
            if extracted_digits:
                search_key = extracted_digits[0]
            elif tracking_match:
                search_key = tracking_match[0]
            else:
                # Procura por nomes de clientes
                cleaned = re.sub(r"\b(qual|o|status|do|meu|pedido|sou|rastreio|para|de)\b", "", norm_msg).strip()
                if len(cleaned) > 2:
                    search_key = cleaned

            order_data = search_order(search_key) if search_key else None
            if order_data:
                items_str = "\n".join([f"  - {it['quantity']}x {it['item']} (R$ {it['unit_price']:.2f})" for it in order_data["items"]])
                return (
                    f"Olá, {order_data['customer_name']}! Localizei o seu pedido com muito prazer! 📦\n\n"
                    f"🏷️ **Pedido #{order_data['order_id']}** (Data: {order_data['order_date']})\n"
                    f"• **Status**: {order_data['status']}\n"
                    f"• **Itens**:\n{items_str}\n"
                    f"• **Total**: R$ {order_data['total_brl']:.2f} ({order_data['payment_method']})\n"
                    f"• **Código de Rastreamento**: `{order_data['tracking_code']}`\n"
                    f"• **Previsão de Entrega**: {order_data['estimated_delivery']}\n"
                    f"• **Destino**: {order_data['customer_city']}\n\n"
                    f"Se precisar de mais alguma informação sobre o envio ou suporte, é só falar!"
                )
            elif search_key:
                return (
                    f"Olá! Consultei nosso sistema, mas não localizei nenhum pedido ativo associado a '{search_key}'.\n\n"
                    "Poderia conferir o número exato do pedido (ex: #1, #2), o código de rastreio dos Correios/Jadlog ou o nome cadastrado no ato da compra para eu consultar novamente para você?"
                )

        # 5. Detecção de consulta sobre Produto Específico (ex: Takamine GD20, Yamaha C40, etc.)
        specific_prod_match = None
        for brand in ["takamine", "yamaha", "tagima", "fender", "ibanez", "roland", "casio", "pearl", "giannini", "strinberg", "korg"]:
            if brand in norm_msg:
                specific_prod_match = brand
                break

        is_price_query = any(kw in norm_msg for kw in ["custa", "quanto e", "preco de", "valor do", "takamine", "gd20", "c40", "tw-25", "tw25"])
        if specific_prod_match or is_price_query:
            cleaned_query = re.sub(
                r"\b(quanto\s+custa|qual\s+o\s+valor|qual\s+o\s+preco|quanto\s+e|o|a|os|as|do|da|de|violao|guitarra|baixo|teclado|bateria|aceita|parcelamento|sem\s+juros|tem|em\s+estoque|sobre)\b",
                " ",
                user_message,
                flags=re.IGNORECASE,
            )
            cleaned_query = " ".join(cleaned_query.split()).strip(" ?!,.")
            prod = get_product_details(cleaned_query if cleaned_query else user_message)
            if not prod and specific_prod_match:
                prod = get_product_details(specific_prod_match)
            if prod:
                stock_msg = f"Em estoque ({prod['stock_quantity']} unidades disponíveis)" if prod["is_available"] else "Temporariamente esgotado"
                promo_tag = ""
                if prod["has_active_promo"]:
                    promo_tag = f"\n🔥 **Oferta Especial**: {prod['active_discount_percent']}% OFF ({prod['active_promo_description']})! De ~~R$ {prod['price_original_brl']:.2f}~~ por **R$ {prod['price_effective_brl']:.2f}**"
                else:
                    promo_tag = f"\n💰 **Valor**: R$ {prod['price_effective_brl']:.2f}"

                pix_msg = f"• **No PIX**: **R$ {prod['pix_price_brl']:.2f}**" + (" (Preço promocional à vista)" if prod["has_active_promo"] else " (com 5% de desconto à vista!)")
                parcela_msg = f"• **No Cartão de Crédito**: até **{prod['max_installments']}x de R$ {prod['installment_value_brl']:.2f} sem juros**" if prod["max_installments"] > 1 else "• **No Cartão**: à vista"

                return (
                    f"Que excelente instrumento você escolheu! 🎵\n\n"
                    f"🎸 **{prod['name']}**\n"
                    f"• **Categoria**: {prod['category']}\n"
                    f"• **Disponibilidade**: {stock_msg}\n"
                    f"{promo_tag}\n\n"
                    f"**Condições de Pagamento Facilitadas**:\n"
                    f"{pix_msg}\n"
                    f"{parcela_msg}\n\n"
                    f"ℹ️ **Sobre o instrumento**: {prod['description']}\n"
                    f"🔍 **Especificações**: {prod['specs']}\n\n"
                    f"Gostaria de fechar o pedido ou simular as opções de frete para a sua cidade?"
                )

        # 6. Detecção de busca por catálogo com filtro de preço / categoria (ex: violões até R$ 1000)
        price_filter = None
        # Procura números inteiros de preço (ex: 1000, 500, 2000)
        num_matches = re.findall(r"\b\d{3,5}\b", user_message)
        if num_matches and any(w in norm_msg for w in ["ate", "menos", "abaixo", "maximo", "custando", "reais", "r$"]):
            try:
                price_filter = float(num_matches[0])
            except ValueError:
                pass

        category_filter = ""
        for cat in ["violao", "violoes", "guitarra", "guitarras", "baixo", "baixos", "bateria", "baterias", "teclado", "teclados", "piano", "ukulele"]:
            if cat in norm_msg:
                category_filter = cat
                break

        if category_filter or price_filter is not None or "opcoes" in norm_msg or "catalogo" in norm_msg:
            products = search_products(query=category_filter or "violao", max_price=price_filter, only_available=True, limit=5)
            if products:
                intro = f"Temos ótimas opções disponíveis de instrumentos"
                if category_filter:
                    intro += f" na linha de {category_filter}"
                if price_filter:
                    intro += f" custando até R$ {price_filter:.2f}"
                intro += "! Dá uma olhada nesses destaques da nossa loja:\n\n"

                lines = [intro]
                for p in products:
                    promo_note = f" (🔥 Promoção {p['active_discount_percent']}% OFF!)" if p["has_active_promo"] else ""
                    lines.append(
                        f"🎸 **{p['name']}**{promo_note}\n"
                        f"   • Preço: **R$ {p['effective_price_brl']:.2f}** | À vista no PIX: **R$ {p['pix_price_brl']:.2f}**\n"
                        f"   • Cartão: até **{p['max_installments']}x de R$ {p['installment_value_brl']:.2f} sem juros**\n"
                        f"   • Destaque: {p['description'][:110]}...\n\n"
                    )
                lines.append("Lembrando que para Campo Grande entregamos via motoboy próprio (com frete grátis acima de R$ 500!). Algum desses modelos te chamou mais atenção?")
                return "".join(lines)
            else:
                return (
                    f"No momento não localizei nenhum instrumento disponível com esses filtros exatos (até R$ {price_filter:.2f}). "
                    "Mas posso verificar outras faixas de preço ou modelos equivalentes para você. Qual faixa de investimento você gostaria de consultar?"
                )

        # 7. Perguntas gerais sobre música ou saudações
        if any(w in norm_msg for w in ["ola", "oi", "bom dia", "boa tarde", "boa noite", "tudo bem"]):
            return (
                "Olá! Seja muito bem-vindo(a) à **Empório da Música**! 🎶\n\n"
                "Aqui nós respiramos instrumentos musicais. Posso te ajudar a encontrar seu próximo violão, guitarra, teclado ou bateria, "
                "consultar preços, verificar status de pedidos ou tirar dúvidas sobre nossas entregas e formas de pagamento.\n\n"
                "Como posso te ajudar hoje?"
            )

        # 8. Out of scope geral (perguntas aleatórias)
        if any(w in norm_msg for w in ["receita", "futebol", "politica", "clima", "tempo", "filme", "piada", "matematica"]):
            return (
                "Haha, essa é uma ótima pergunta! Mas o meu forte mesmo aqui na **Empório da Música** são os instrumentos musicais! 🎸🥁\n\n"
                "Estou à disposição para te ajudar a escolher o instrumento perfeito, consultar promoções, calcular opções de parcelamento ou acompanhar o status da sua compra.\n\n"
                "Em que posso te ajudar no universo musical hoje?"
            )

        # Fallback genérico cordial
        policy_context = query_policies(user_message)
        return (
            "Com certeza! Aqui na **Empório da Música** temos total dedicação ao seu atendimento.\n\n"
            "Trabalhamos com mais de 300 modelos de instrumentos musicais em pronta entrega, pagamento facilitado em até 12x sem juros no cartão ou desconto especial de 5% no PIX, além de entrega garantida com seguro.\n\n"
            "Me conta um pouco mais sobre o que você procura para que eu possa te indicar a opção ideal!"
        )
