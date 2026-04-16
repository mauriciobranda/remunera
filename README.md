# Remunera

Portal local para consulta de remuneracoes publicas da Prefeitura de Caxias do Sul-RS.

## O que este projeto faz

- Exibe uma interface para busca por nome e cargo.
- Carrega os dados diretamente de arquivos locais por periodo.
- Mostra no navegador no maximo 20 registros por pagina.
- Mostra o tempo em anos de cada pessoa na prefeitura.

## Estrutura atual

O frontend le os arquivos do periodo dentro de:

```text
frontend/public/data/01112025/
  remuneracoes_raw.json
  remuneracoes_raw.csv
frontend/public/data/01122025/
  remuneracoes_raw.json
  remuneracoes_raw.csv
frontend/public/data/01022026/
  remuneracoes_raw.json
  remuneracoes_raw.csv
frontend/public/data/01032026/
  remuneracoes_raw.json
  remuneracoes_raw.csv
```

Na tela, o periodo aparece como `01/11/2025`, `01/12/2025`, `01/02/2026` ou `01/03/2026` e aponta para a pasta local correspondente.

## Como abrir

### Requisitos

- Node.js instalado
- npm disponivel no terminal

### Passo a passo

1. Abra um terminal na pasta do frontend:
   ```powershell
   cd C:\Users\Usuario\Projetos\remunera\frontend
   ```
2. Inicie o Vite:
   ```powershell
   npm run dev
   ```
3. Abra o endereco exibido pelo comando.

## Como funciona a consulta

- O seletor de periodo recarrega os cargos e os nomes do periodo escolhido.
- A busca por nome so executa a partir de mais de 3 caracteres.
- Se um cargo for escolhido sem texto, a consulta tambem retorna resultados.
- Se a busca tiver 3 caracteres ou menos, a lista fica vazia.
- Quando houver mais de 20 registros, a pagina exibira paginacao.

## Observacoes importantes

- Este e um site nao oficial.
- Nao existe dependencia de backend local para o fluxo atual.
- Se voce adicionar outro periodo, crie outra pasta em `frontend/public/data/` usando a mesma logica do periodo.

## Estrutura relevante

- `frontend/index.html`: interface principal
- `frontend/public/data/01112025/`: periodo de novembro de 2025
- `frontend/public/data/01122025/`: periodo de dezembro de 2025
- `frontend/public/data/01022026/`: periodo de fevereiro de 2026
- `frontend/public/data/01032026/`: periodo de marco de 2026
- `data/01112025/`, `data/01122025/`, `data/01022026/`, `data/01032026/`: copias locais opcionais dos mesmos arquivos

## Adicionando um novo periodo

Crie uma nova pasta com o formato `DDMMYYYY` dentro de `frontend/public/data/` e coloque nela os arquivos:

```text
remuneracoes_raw.json
remuneracoes_raw.csv
```

Depois, adicione o periodo correspondente no combobox da tela.
