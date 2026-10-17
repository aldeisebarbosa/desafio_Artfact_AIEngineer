# Exemplo 1: Consulta ao Catálogo de Produtos com Filtro de Preço e Categoria

**Cenário**: Cliente busca violões disponíveis em estoque dentro de um orçamento de até R$ 1.000,00 e, em seguida, tira dúvidas sobre parcelamento sem juros de um modelo específico.  
**Ferramentas Utilizadas**: `search_products(query='violao', max_price=1000.0, only_available=True)` e `get_product_details('Tagima Memphis')`.  
**Regras de Negócio Testadas**:
- Filtro estrito de estoque ativo (`is_available = 1`).
- Aplicação correta de preço promocional quando existente.
- Cálculo de 5% de desconto à vista no PIX (não cumulativo com promoções).
- Cálculo das parcelas sem juros respeitando valores mínimos por faixa (Seção 3.1 das políticas).
- Política de frete grátis em Campo Grande/MS acima de R$ 500,00.

---

### Transcrição da Conversa

**👤 Cliente:**  
> Olá! Quais opções de violões disponíveis custando até R$1000?

**🤖 Empório da Música:**  
> Temos ótimas opções disponíveis de instrumentos na linha de violões custando até R$ 1000.00! Dá uma olhada nesses destaques da nossa loja:
> 
> 🎸 **Tagima Memphis AC-39 Nylon Natural**  
>    • Preço: **R$ 429.90** | À vista no PIX: **R$ 408.40**  
>    • Cartão: até **5x de R$ 85.98 sem juros**  
>    • Destaque: Violão clássico com cordas de nylon, perfeito para quem está começando. Corpo leve e confortável para longas sessões de estudo.  
> 
> 🎸 **Rozini RC-104 Nylon Estudante**  
>    • Preço: **R$ 459.90** | À vista no PIX: **R$ 436.90**  
>    • Cartão: até **5x de R$ 91.98 sem juros**  
>    • Destaque: Violão clássico de estudo da Rozini, feito com madeiras nacionais. Acabamento caprichado e preço acessível para estudantes.  
> 
> 🎸 **Shelby SN-100 Folk Aço Preto**  
>    • Preço: **R$ 549.00** | À vista no PIX: **R$ 521.55**  
>    • Cartão: até **6x de R$ 91.50 sem juros**  
>    • Destaque: Violão folk aço com visual moderno em preto. Indicado para quem busca um instrumento versátil com boa relação custo-benefício.  
> 
> 🎸 **Giannini GF-1R Aço Folk Sunburst**  
>    • Preço: **R$ 579.90** | À vista no PIX: **R$ 550.90**  
>    • Cartão: até **6x de R$ 96.65 sem juros**  
>    • Destaque: Violão folk com tampo em Spruce e acabamento Sunburst clássico. Som equilibrado e visual elegante para palco e estudo.  
> 
> 🎸 **Yamaha C40 Nylon Natural**  
>    • Preço: **R$ 599.90** | À vista no PIX: **R$ 569.90**  
>    • Cartão: até **6x de R$ 99.98 sem juros**  
>    • Destaque: Violão clássico com tampo em Spruce e fundo/laterais em Meranti. Ideal para estudantes e iniciantes, com excelente afinação e durabilidade.  
> 
> Lembrando que para Campo Grande entregamos via motoboy próprio (com frete grátis acima de R$ 500!). Algum desses modelos te chamou mais atenção?

---

**👤 Cliente:**  
> O Tagima Memphis aceita parcelamento sem juros?

**🤖 Empório da Música:**  
> Que excelente instrumento você escolheu! 🎵  
> 
> 🎸 **Tagima Memphis AC-39 Nylon Natural**  
> • **Categoria**: Violões  
> • **Disponibilidade**: Em estoque (15 unidades disponíveis)  
> 
> 💰 **Valor**: R$ 429.90  
> 
> **Condições de Pagamento Facilitadas**:  
> • **No PIX**: **R$ 408.40** (com 5% de desconto à vista!)  
> • **No Cartão de Crédito**: até **5x de R$ 85.98 sem juros**  
> 
> ℹ️ **Sobre o instrumento**: Violão clássico com cordas de nylon, perfeito para quem está começando. Corpo leve e confortável para longas sessões de estudo.  
> 🔍 **Especificações**: {"top":"Linden","back_sides":"Linden","neck":"Nato","strings":"nylon","scale":"650mm","electronics":"no","color":"Natural"}  
> 
> Gostaria de fechar o pedido ou simular as opções de frete para a sua cidade?
