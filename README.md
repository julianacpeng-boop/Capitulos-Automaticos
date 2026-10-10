# Capítulos: Telegram → transcrição → vídeos com legenda

Sem Colab aberto, sem Drive e sem API paga de IA. O processamento roda no GitHub Actions. O Whisper é executado localmente no servidor. O GitHub pode cobrar minutos/armazenamento conforme o plano e uso: confira Billing antes de execuções longas. Não é uma promessa de custo zero.

## Instalação uma única vez

1. Crie um repositório para este projeto. Coloque o CONTEÚDO desta pasta na raiz; preserve `.github/workflows` (os arquivos YAML precisam estar nesse caminho). No celular, pode criar os dois YAML pelo botão Add file → Create new file e digitar o caminho completo. Subir o ZIP sozinho não instala o projeto.
2. Em Settings → Secrets and variables → Actions → New repository secret, cadastre `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` e `TELEGRAM_SESSION`. Nunca escreva esses valores no código nem envie a sessão no chat. Utilize suas próprias credenciais do Telegram.
3. Para gerar a sessão uma única vez: execute `pip install telethon` e o conteúdo de `gerar_sessao.py` em um computador ou Colab. Informe seu telefone e o código do Telegram quando solicitado. Copie a sessão resultante diretamente para o Secret. Não salve nem compartilhe as saídas do notebook contendo a sessão. Ela permite acessar sua conta.
4. Para manter seu fundo anterior, coloque a imagem em `assets/fundo.jpg`, com 1280 × 1920 pixels. Sem esse arquivo, o código usa fundo azul escuro. Para a fonte original, coloque `Anton-Regular.ttf` em `assets/`; caso contrário usa DejaVu Sans Bold. Emojis podem não aparecer corretamente nessa primeira versão: os textos que eu devolver podem usar títulos sem emojis.

## Uso para cada capítulo

1. Actions → **1 - Preparar capítulo** → Run workflow. Informe o número do capítulo e o link da mensagem. Pode fechar a página depois de iniciar.
2. Ao terminar, abra a execução, baixe **transcricao-capitulo-N**, extraia e envie aqui `transcricao_por_cena.json` junto com `textos_modelo.json`. Guarde o número da execução mostrado no resumo. Não precisa baixar o pacote grande de preparação.
3. Peça: “Preencha textos_modelo.json com títulos, perguntas, legendas e hashtags coerentes para cada cena, preservando capítulo, execução e identificadores. Devolva como capitulo_N.json.” Coloque o arquivo devolvido em `textos/capitulo_N.json` no GitHub.
4. Actions → **2 - Finalizar vídeos e legendas** → Run workflow. Informe capítulo, número da execução anterior e cenas: `todas`, `1,3,5` ou `1-10`. Baixe **videos-capitulo-N**. O ZIP mantém `capitulo_N/cena_01_final.mp4` e `capitulo_N/cena_01_final.txt`. A pasta durante a execução é `saida/capitulo_N/` na raiz.

Cada TXT contém a legenda da publicação e as hashtags, não uma legenda SRT sincronizada. Para baixar outro grupo de cenas depois, execute novamente a finalização com outra seleção. O vídeo convertido é reaproveitado; não precisa autenticar no Telegram outra vez nem transcrever de novo.

## Como funciona

A preparação baixa o original, transcreve o áudio em português com Whisper small e converte o vídeo inteiro para **1280 × 960 (4:3)**, igual à etapa 3. Isso redimensiona diretamente, podendo deformar imagens de outra proporção. O plano de cortes usa pausas de no mínimo 2 segundos após 15 segundos de trecho, com limite rígido de 60 segundos. Não detecta mudanças visuais de cena. Os tempos cobrem o vídeo inteiro, sem lacunas; um limite de 60 segundos pode interromper uma fala. A transcrição que cruza um limite pode constar nos dois trechos para contexto.

A finalização lê o convertido e corta somente as cenas escolhidas. Mantém o vídeo centralizado, título no alto e pergunta nos últimos 7 segundos (ou durante toda a cena se ela for menor). Os textos são produzidos por você e pelo ChatGPT entre as duas execuções; não existe chamada automática a API de IA.

Os pacotes são artefatos do Actions, disponíveis **14 dias**, e não commits de vídeos no repositório. Finalize dentro desse prazo. Capítulos diferentes são separados pelo número; para o mesmo capítulo, a execução identifica exatamente qual preparação usar. Os jobs têm timeout de 350 minutos, abaixo do limite de 6 horas do GitHub. Vídeos longos podem exceder tempo, disco ou armazenamento: comece com um vídeo curto.

## Teste inicial

Use um vídeo curto e finalize uma ou duas cenas. Verifique imagem, áudio, título, pergunta, nomes e TXT. Só depois processe capítulos inteiros. Este pacote passou por verificações locais de cortes e renderização sintética; a autenticação e execução real no GitHub precisam do primeiro teste com seus Secrets.

## Fontes técnicas

- https://docs.github.com/en/actions/tutorials/store-and-share-data
- https://docs.github.com/en/actions/reference/limits
- https://docs.github.com/en/actions/concepts/billing-and-usage
