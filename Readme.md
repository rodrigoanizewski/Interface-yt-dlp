# ▼ yt-dlp GUI — Post-Production Edition

> Interface gráfica profissional para o **yt-dlp**, construída com foco em **pós-produção de vídeo**. Baixe, converta e prepare clipes prontos para DaVinci Resolve, Premiere Pro e Avid Media Composer — sem tocar em linha de comando.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square&logo=python)
![yt-dlp](https://img.shields.io/badge/yt--dlp-latest-orange?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey?style=flat-square)

---

## Funcionalidades

### Download
- Cola URL de vídeo individual, playlist ou canal e clica em Analisar — título, canal, duração, FPS da fonte e thumbnail carregam automaticamente
- Suporte a qualquer site compatível com yt-dlp (YouTube, Vimeo, Twitter/X, Twitch, Reddit e centenas de outros)
- Barra de progresso real alimentada pelo `progress_hook` nativo do yt-dlp, com velocidade em MB/s e ETA
- Download de playlist completa ou vídeo único com um toggle

### Perfis de Saída Profissional
| Perfil | Codec | Container | Ideal para |
|---|---|---|---|
| Original (MP4/MKV) | H.264 / HEVC original | mp4 / mkv | Uso geral, streaming |
| ProRes 422 HQ | `prores_ks -profile:v 3` | .mov | DaVinci Resolve, Premiere, Final Cut |
| DNxHR HQ | `dnxhd -profile:v dnxhr_hq` | .mxf | Avid Media Composer, Windows |
| H.264 CFR | `libx264 -crf 18` + AAC | .mp4 | DaVinci Resolve versão gratuita |

### Ferramentas para Editores
- **CFR forçado** — Dropdown com 23.976 / 24 / 25 / 29.97 / 30 / 50 / 60 fps. Injeta `-vf fps=N` no pipeline FFmpeg, eliminando dessincronização de áudio causada por VFR (Variable Frame Rate) no DaVinci e Premiere
- **Modo B-Roll / Somente Vídeo** — Baixa apenas o stream de vídeo puro na resolução máxima disponível, sem processar áudio. Reduz tempo de download e tamanho do arquivo para material de apoio
- **Fix DaVinci Resolve Free (WAV PCM 24-bit)** — Converte o áudio para PCM sem compressão (`-acodec pcm_s24le`). Resolve o bug histórico de "Media Offline" e áudio mudo causado por AAC em containers HEVC na versão gratuita do DaVinci no Windows
- **Remoção de silêncio** — Aplica filtro `silenceremove` do FFmpeg com threshold -60dB no início e fim do clipe. Útil para voz em off, entrevistas e tutoriais
- **Preservação de metadados de tempo** — Escreve a data de upload original no container via `FFmpegMetadata`. O Media Pool do DaVinci e o Premiere ordenam clips cronologicamente usando esse campo
- **Embed de thumbnail** — Insere a capa do vídeo como artwork no arquivo final (MP3, MP4, MKV) via `EmbedThumbnail`
- **Embed de metadados e legendas** — Título, artista, data e legendas embutidos diretamente no container

### Templates de Nome de Arquivo
- `Titulo.ext` — padrão limpo
- `[Data] - Titulo.ext` — organização cronológica automática
- `Canal - Titulo.ext` — organização por fonte

### Robustez e UX
- **Gestão de cookies** — Sem cookies / arquivo `cookies.txt` / leitura direta do navegador (Chrome, Firefox, Brave, Edge). Essencial para conteúdo com restrição de idade ou login
- **User-Agent real** — Envia header de navegador Chrome em todas as requisições para reduzir detecção como bot
- **Verificação de FFmpeg** — Badge visual no cabeçalho ao iniciar. Avisa sobre funcionalidades indisponíveis sem interromper o uso
- **Atualização com 1 clique** — Botão "Atualizar yt-dlp" executa `pip install -U yt-dlp` em background e exibe a versão instalada
- **Tratamento de erros tipado** — Mensagens claras para Vídeo Privado, Rate Limit 429, Restrição de Acesso, FFmpeg ausente, Erro de Rede e URL não suportada — o app nunca fecha por erro
- **Toast notification** — Notificação flutuante ao concluir cada download
- **Histórico de sessão** — Últimos 5 downloads com status visual (✔ / ✘ / ⬇) e horário
- **Botão "Abrir Pasta"** — Ativo após conclusão, abre o explorador de arquivos diretamente na pasta de destino
- **Encerramento limpo** — Se fechado durante um download, sinaliza o yt-dlp e mata processos FFmpeg filhos antes de destruir a janela, evitando processos zumbi consumindo CPU

---

## Instalação

### 1. Clone o repositório
```bash
git clone https://github.com/rodrigoanizewski/ytdlp-gui.git
cd ytdlp-gui
```

### 2. Instale as dependências Python
```bash
pip install -r requirements.txt
```

> O pacote `imageio[ffmpeg]` incluído no `requirements.txt` **baixa um FFmpeg portátil automaticamente** durante a instalação. Não é necessário instalar o FFmpeg manualmente em nenhuma plataforma.

### 3. Execute
```bash
python ytdlp_gui.py
```

---

## Requisitos

| Dependência | Versão mínima | Função |
|---|---|---|
| Python | 3.10+ | Runtime |
| customtkinter | 5.2.0+ | Interface gráfica dark mode |
| yt-dlp | 2024.1.0+ | Motor de download |
| Pillow | 10.0.0+ | Carregamento de thumbnails |
| requests | 2.31.0+ | Fetch de thumbnails via HTTP |
| imageio[ffmpeg] | 2.34.0+ | FFmpeg portátil embutido (baixado automaticamente via pip) |

---

## Uso rápido

1. Cole a URL no campo e clique **Analisar** (ou pressione `Enter`)
2. Escolha o **Perfil de Saída** — para edição, use ProRes 422 ou H.264 CFR
3. Se for usar no DaVinci Resolve Free no Windows, marque **Audio WAV PCM 24-bit**
4. Para B-Roll, marque **Somente Vídeo** e selecione 4K na resolução
5. Defina a **pasta de destino**
6. Clique **BAIXAR**

---

## Estrutura do projeto

```
ytdlp-gui/
├── ytdlp_gui.py       # Aplicação principal
├── requirements.txt   # Dependências Python
└── README.md          # Este arquivo
```

---

## Licença

MIT — livre para uso pessoal e comercial.