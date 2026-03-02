
nome = input("Digite seu nome: ")

print("\nResultado:\n")

# Carctere por caractere
for caractere in nome:
    
    valor_inteiro = ord(caractere)  # (ASCII)
    resultado_divisao = valor_inteiro / 4
    parte_inteira = valor_inteiro // 4
    resto = valor_inteiro % 4
    parte_fracionada = resultado_divisao - parte_inteira

    print(f"{caractere}")
    print(f"Valor inteiro: {valor_inteiro}")
    print(f"Divisão realizada: {valor_inteiro}/4")
    print(f"Resultado da divisão: {resultado_divisao}")
    print(f"Parte inteira da divisão: {parte_inteira}")
    print(f"Parte fracionada da divisão: {parte_fracionada}")
    print(f"Resto da divisão: {resto}")