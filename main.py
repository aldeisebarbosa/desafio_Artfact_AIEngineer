#!/usr/bin/env python3
"""
Ponto de entrada principal do Agente de Atendimento da Empório da Música.
Permite interação via CLI interativo, execução direta de consultas e simulação de cenários de teste.
"""

import argparse
import os
import sys
from pathlib import Path

# Carrega variáveis de ambiente de .env se existir
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Garante que o pacote emporio-da-musica-agent esteja acessível no PYTHONPATH
CURRENT_DIR = Path(__file__).resolve().parent
AGENT_DIR = CURRENT_DIR / "emporio-da-musica-agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(AGENT_DIR))
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from src.agent import EmporioAgent
from src.database import get_db_connection


BANNER = """
================================================================================
     🎸 EMPÓRIO DA MÚSICA — ASSISTENTE VIRTUAL DE ATENDIMENTO 🎶
          Instrumentos Musicais de Qualidade em Campo Grande/MS
================================================================================
"""

HELP_TEXT = """
Comandos úteis no chat:
  - 'sair' ou 'exit': Encerra o atendimento.
  - 'limpar' ou 'reset': Reinicia o histórico da conversa.
  - 'ajuda': Exibe estas orientações.
  - 'exemplos': Mostra perguntas sugeridas do catálogo e políticas.
"""

SAMPLE_QUERIES = [
    "Quais opções de violões disponíveis custando até R$1000?",
    "Qual o endereço da loja e horário de funcionamento?",
    "Quanto custa o Takamine GD20?",
    "Me arrependi da minha compra, posso devolver meu pedido?",
    "Qual o status do pedido número 1 e código de rastreamento?",
    "Vocês vendem encordoamento e palhetas de guitarra?",
]


def run_interactive(agent: EmporioAgent):
    print(BANNER)
    print(f"Modo ativo: Provedor [{agent.provider.upper()}] | Modelo [{agent.model}]")
    print("Digite sua mensagem para iniciar ou 'ajuda' para comandos especiais.\n")

    while True:
        try:
            user_input = input("\n👤 Você: ").strip()
            if not user_input:
                continue

            lower_cmd = user_input.lower()
            if lower_cmd in ["sair", "exit", "quit"]:
                print("\n🎸 Empório da Música: Foi um prazer atender você! Qualquer dúvida estamos à disposição. Até breve e muita música!")
                break
            elif lower_cmd in ["limpar", "reset"]:
                agent.reset_history()
                print("\n🧹 Histórico de conversa reiniciado.")
                continue
            elif lower_cmd == "ajuda":
                print(HELP_TEXT)
                continue
            elif lower_cmd == "exemplos":
                print("\n💡 Exemplos de perguntas para testar:")
                for i, q in enumerate(SAMPLE_QUERIES, 1):
                    print(f"  {i}. {q}")
                continue

            print("\n🤖 Empório da Música:")
            response = agent.chat(user_input)
            print(response)

        except (KeyboardInterrupt, EOFError):
            print("\n\nAtendimento finalizado. Até logo!")
            break


def run_examples(agent: EmporioAgent):
    print(BANNER)
    print("Executando bateria de cenários de teste reais...\n")
    for i, query in enumerate(SAMPLE_QUERIES, 1):
        print("=" * 80)
        print(f"📌 CENÁRIO {i}: \"{query}\"")
        print("=" * 80)
        response = agent.chat(query)
        print(response)
        print("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Agente de Atendimento da Empório da Música (Artefact AI Engineer Challenge)"
    )
    parser.add_argument(
        "--provider",
        choices=["local_engine", "groq", "openai", "ollama"],
        default=os.getenv("LLM_PROVIDER", "local_engine"),
        help="Provedor de LLM para execução (padrão: local_engine para execução sem custos)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Nome específico do modelo a utilizar no provedor escolhido",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Executa uma única consulta direta e imprime a resposta no terminal",
    )
    parser.add_argument(
        "--run-examples",
        action="store_true",
        help="Executa todas as perguntas de exemplo do edital em sequência",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Ativa logs detalhados de execução de ferramentas (tool calling)",
    )

    args = parser.parse_args()

    # Inicializa / verifica o banco SQLite tratado
    get_db_connection()

    agent = EmporioAgent(
        provider=args.provider,
        model=args.model,
        verbose=args.verbose,
    )

    if args.query:
        print(agent.chat(args.query))
    elif args.run_examples:
        run_examples(agent)
    else:
        run_interactive(agent)


if __name__ == "__main__":
    main()
