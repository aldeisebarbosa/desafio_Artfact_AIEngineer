# Exemplo 3: Consulta de Preço, Parcelamento e Estoque do Takamine GD20

**Cenário**: Cliente interessado em um modelo específico de violão de alta linha (`Takamine GD20`) consulta o valor, formas de pagamento (PIX e cartão de crédito parcelado sem juros), estoque disponível e especificações de madeira e encordoamento.  
**Ferramentas Utilizadas**: `get_product_details('Takamine GD20')`.  
**Regras de Negócio Testadas**:
- Recuperação precisa de instrumento específico no banco de dados SQLite.
- Cálculo de 5% de desconto à vista no PIX (preço de tabela R$ 2.199,00 -> R$ 2.089,05 à vista).
- Regra de parcelamento sem juros da Seção 3.1: para valores onde a parcela atinge o piso de R$ 100,00, libera o parcelamento máximo de até 12x (12x de R$ 183,25 sem juros).
- Informação verídica de estoque ativo (5 unidades).
- Resposta detalhada com especificações técnicas do tampo maciço em cedro.

---

### Transcrição da Conversa

**👤 Cliente:**  
> Quanto custa o Takamine GD20?

**🤖 Empório da Música:**  
> Que excelente instrumento você escolheu! 🎵  
> 
> 🎸 **Takamine GD20 Dreadnought Natural**  
> • **Categoria**: Violões  
> • **Disponibilidade**: Em estoque (5 unidades disponíveis)  
> 
> 💰 **Valor**: R$ 2199.00  
> 
> **Condições de Pagamento Facilitadas**:  
> • **No PIX**: **R$ 2089.05** (com 5% de desconto à vista!)  
> • **No Cartão de Crédito**: até **12x de R$ 183.25 sem juros**  
> 
> ℹ️ **Sobre o instrumento**: Violão dreadnought Takamine com tampo sólido em cedro. Excelente para fingerstyle com timbre quente e definido.  
> 🔍 **Especificações**: {"top":"Cedro Sólido","back_sides":"Sapele","neck":"Mogno","strings":"steel","scale":"650mm","electronics":"no","color":"Natural"}  
> 
> Gostaria de fechar o pedido ou simular as opções de frete para a sua cidade?

---

**👤 Cliente:**  
> O Takamine GD20 tem a pronta entrega no estoque agora?

**🤖 Empório da Música:**  
> Sim, perfeitamente! Temos 5 unidades do **Takamine GD20 Dreadnought Natural** novas na caixa em pronta entrega no nosso estoque em Campo Grande/MS.  
> 
> Se você estiver aqui na cidade, a entrega pode ser feita via motoboy próprio em até 24 a 48 horas úteis (e como o valor ultrapassa R$ 500, o frete é 100% grátis!). Deseja que eu reserve uma unidade para você?
