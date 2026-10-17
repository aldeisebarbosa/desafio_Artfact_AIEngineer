# Exemplo 5: Situação Não Trivial — Consulta a Pedido em Tempo Real e Tratamento Fora de Escopo

**Cenário**: Cliente entra em contato para verificar o status e o código de rastreamento de uma compra existente (Pedido #1) e, logo em seguida, pergunta se é possível incluir no mesmo pacote acessórios (jogo de cordas de nylon e palhetas de guitarra).  
**Ferramentas Utilizadas**: `search_order('1')` e detecção de escopo comercial exclusivo.  
**Regras de Negócio Testadas**:
- Consulta em tempo real aos dados relacionais de pedidos, clientes e itens (`orders`, `customers` e `order_items` via SQLite).
- Recuperação fiel do nome do cliente (Pedro Henrique Oliveira), data, status traduzido ("Entregue"), total em reais, forma de pagamento e código de rastreamento oficial (`BRAB1234567BR`).
- Tratamento estrito da Seção 1.0 das Políticas da Loja: a Empório da Música comercializa **exclusivamente instrumentos musicais** e não trabalha com acessórios como palhetas, encordoamentos, cabos ou cases.
- Persona acolhedora, explicando educadamente o foco da loja e redirecionando para lojas especializadas.

---

### Transcrição da Conversa

**👤 Cliente:**  
> Olá! Gostaria de saber o status do meu pedido 1

**🤖 Empório da Música:**  
> Olá, Pedro Henrique Oliveira! Localizei o seu pedido com muito prazer! 📦  
> 
> 🏷️ **Pedido #1** (Data: 2025-10-15)  
> • **Status**: Entregue  
> • **Itens**:  
>   - 1x Martin D-28 Dreadnought Natural (R$ 11499.00)  
> • **Total**: R$ 11499.00 (PIX)  
> • **Código de Rastreamento**: `BRAB1234567BR`  
> • **Previsão de Entrega**: 2025-10-25  
> • **Destino**: Campo Grande  
> 
> Se precisar de mais alguma informação sobre o envio ou suporte, é só falar!

---

**👤 Cliente:**  
> Vocês têm jogo de cordas de nylon e palhetas para mandar junto?

**🤖 Empório da Música:**  
> Olá! Tudo bem? Que bom falar com você! 🎸  
> 
> Aqui na **Empório da Música**, nós trabalhamos **exclusivamente com instrumentos musicais** (como violões, guitarras, baixos, baterias, teclados, sopro e cordas orquestrais).  
> 
> Por isso, infelizmente **não comercializamos acessórios** (como cordas, palhetas, cabos, cases ou pedais). Para esses itens, recomendamos procurar lojas parceiras especializadas em acessórios aqui na região!  
> 
> Mas se você estiver procurando um novo instrumento para fazer um som incrível, será um prazer te apresentar as melhores opções do nosso catálogo. O que tem em mente?
