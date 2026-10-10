"""Pipeline sem Colab, Drive ou API paga de IA."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlparse


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def chapter(value):
    if not re.fullmatch(r'[1-9]\d{0,5}', str(value)):
        raise ValueError('Informe apenas o número do capítulo, por exemplo 1.')
    return f'capitulo_{value}'


def parse_link(link):
    u = urlparse(link.strip())
    if u.scheme != 'https' or u.hostname not in ('t.me', 'telegram.me'):
        raise ValueError('Use o link https://t.me/canal/123 ou https://t.me/c/123/456.')
    parts = u.path.strip('/').split('/')
    if len(parts) == 3 and parts[0] == 'c' and all(p.isdigit() for p in parts[1:]):
        return int('-100' + parts[1]), int(parts[2])
    if len(parts) == 3 and parts[0] == 's':
        parts = parts[1:]
    if len(parts) == 2 and re.fullmatch(r'[A-Za-z0-9_]+', parts[0]) and parts[1].isdigit():
        return parts[0], int(parts[1])
    raise ValueError('Link de mensagem não reconhecido.')


async def download(link, target):
    from telethon import TelegramClient
    from telethon.sessions import StringSession
    entity, message_id = parse_link(link)
    client = TelegramClient(StringSession(os.environ['TELEGRAM_SESSION']),
                            int(os.environ['TELEGRAM_API_ID']), os.environ['TELEGRAM_API_HASH'])
    await client.connect()
    try:
        if not await client.is_user_authorized():
            raise ValueError('Sessão Telegram inválida. Gere novamente o Secret TELEGRAM_SESSION.')
        msg = await client.get_messages(entity, ids=message_id)
        if not msg or not msg.file or not (msg.file.mime_type or '').startswith('video/'):
            raise ValueError('Mensagem sem vídeo ou conta sem acesso ao canal.')
        await msg.download_media(file=str(target))
    finally:
        await client.disconnect()


def probe(path):
    data = subprocess.check_output(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)])
    return json.loads(data)


def plan_scenes(segments, duration):
    # Pausas >= 2 segundos após 15s; cortes com limite rígido de 60s.
    # Cobertura contínua: nenhum trecho entre cortes é descartado.
    pauses = sorted({float(s['end']) for s, n in zip(segments, segments[1:])
                     if float(n['start']) - float(s['end']) >= 2})
    scenes, start = [], 0.0
    while start < duration - 0.001:
        limit = min(start + 60, duration)
        candidates = [p for p in pauses if start + 15 <= p <= limit]
        end = candidates[-1] if candidates else limit
        scenes.append({'cena': f'cena_{len(scenes)+1:02d}', 'inicio': round(start, 3),
                       'fim': round(end, 3), 'transcricao': ' '.join(
                           s['text'].strip() for s in segments if s['start'] < end and s['end'] > start)})
        start = end
    return scenes


def prepare(args):
    from faster_whisper import WhisperModel
    name = chapter(args.capitulo)
    work = Path('trabalho') / name
    work.mkdir(parents=True, exist_ok=True)
    original, converted = work / 'original.mp4', work / 'convertido_4x3.mp4'
    asyncio.run(download(args.link, original))
    metadata = probe(original)
    if not any(s['codec_type'] == 'audio' for s in metadata['streams']):
        raise ValueError('Vídeo sem faixa de áudio.')
    duration = float(metadata['format']['duration'])
    audio = work / 'audio.wav'
    run('ffmpeg', '-y', '-v', 'error', '-i', original, '-vn', '-ac', '1', '-ar', '16000', audio)
    model = WhisperModel('small', device='cpu', compute_type='int8', cpu_threads=4)
    stream, _ = model.transcribe(str(audio), language='pt', beam_size=5, vad_filter=True)
    segments = []
    for seg in stream:
        segments.append({'start': seg.start, 'end': seg.end, 'text': seg.text.strip()})
        write_json(work / 'transcricao.json', segments)
    if not segments:
        raise ValueError('Não foram encontradas falas. Verifique o áudio.')
    # Mesma resolução e redimensionamento direto da etapa 3.
    run('ffmpeg', '-y', '-v', 'error', '-i', original, '-vf', 'scale=1280:960,setsar=1',
        '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23', '-c:a', 'aac', '-movflags', '+faststart', converted)
    scenes = plan_scenes(segments, duration)
    manifest = {'capitulo': int(args.capitulo), 'execucao': os.getenv('GITHUB_RUN_ID', 'local'),
                'duracao': duration, 'cenas': scenes}
    write_json(work / 'cenas.json', manifest)
    review = Path('saida') / name / 'revisao'
    review.mkdir(parents=True, exist_ok=True)
    write_json(review / 'transcricao_por_cena.json', manifest)
    write_json(review / 'textos_modelo.json', {'capitulo': int(args.capitulo), 'execucao': manifest['execucao'],
        'cenas': {s['cena']: {'titulo': '', 'pergunta': '', 'legenda': '', 'hashtags': []} for s in scenes}})
    (review / 'transcricao_por_cena.txt').write_text('\n\n'.join(
        f"{s['cena']} | {s['inicio']:.3f}s a {s['fim']:.3f}s\n{s['transcricao']}" for s in scenes), encoding='utf-8')
    original.unlink()
    audio.unlink()
    print(f'Preparação concluída: {len(scenes)} cenas; execução {manifest["execucao"]}.')


def choose(spec, available):
    if spec.strip().lower() == 'todas':
        return available
    numbers = set()
    for part in spec.split(','):
        if not re.fullmatch(r'\s*\d+(\s*-\s*\d+)?\s*', part):
            raise ValueError('Use todas, 1,3,5 ou 1-10.')
        bounds = [int(v) for v in part.split('-')]
        if len(bounds) == 2 and bounds[0] > bounds[1]:
            raise ValueError('Intervalo invertido.')
        if max(bounds) > len(available) or min(bounds) < 1:
            raise ValueError('Cena fora do capítulo.')
        numbers.update(range(bounds[0], bounds[-1] + 1))
    return [s for i, s in enumerate(available, 1) if i in numbers]


def panel(text, path, size, color, font_path, max_font):
    from PIL import Image, ImageDraw, ImageFont
    from pilmoji import Pilmoji
    from pilmoji.source import EmojiCDNSource
    EmojiCDNSource.STYLE = 'apple'
    img = Image.new('RGBA', size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    question = color == 'question'
    width = 1000 if question else size[0]
    height = 170 if question else size[1]
    if question:
        draw.rounded_rectangle((10, 10, 1010, 180), radius=45, fill=(0, 0, 0, 60))
        draw.rounded_rectangle((0, 0, 1000, 170), radius=45,
                               fill='white', outline=(230, 230, 230), width=3)
    with Pilmoji(img, source=EmojiCDNSource) as renderer:
        for font_size in range(max_font, 11, -2):
            font = ImageFont.truetype(font_path, font_size)
            lines, line = [], ''
            too_wide = False
            for word in text.split():
                if renderer.getsize(word, font=font)[0] > width-80:
                    too_wide = True
                candidate = (line + ' ' + word).strip()
                if line and renderer.getsize(candidate, font=font)[0] > width-80:
                    lines.append(line)
                    line = word
                else:
                    line = candidate
            lines.append(line)
            heights = [renderer.getsize(line, font=font)[1] for line in lines]
            total = sum(heights) + (len(lines)-1)*10
            if not too_wide and total <= height-(55 if question else 10) and (not question or len(lines)<=2):
                break
        else:
            raise ValueError('Texto longo demais. Reduza o título ou pergunta.')
        y = (height-total-(35 if question else 0))/2
        for i, (line, line_height) in enumerate(zip(lines, heights)):
            x = (width-renderer.getsize(line, font=font)[0])/2
            fill = 'black' if question else ('#ffcd00' if i == 1 else 'white')
            if not question:
                renderer.text((x+5, y+5), line, font=font, fill=(0, 0, 0, 190))
            renderer.text((x, y), line, font=font, fill=fill)
            y += line_height+10
        if question:
            subfont = ImageFont.truetype(font_path, 25)
            subtext = 'Fala nos comentários'
            x = (width-draw.textlength(subtext, font=subfont))/2
            draw.text((x, y), subtext, font=subfont, fill=(220, 0, 0))
    img.save(path)


def finish(args):
    from PIL import Image
    name = chapter(args.capitulo)
    work = Path('trabalho') / name
    manifest = json.loads((work/'cenas.json').read_text(encoding='utf-8'))
    if manifest['capitulo'] != int(args.capitulo):
        raise ValueError('O pacote pertence a outro capítulo.')
    texts_path = Path('textos') / f'{name}.json'
    texts = json.loads(texts_path.read_text(encoding='utf-8'))
    if texts['capitulo'] != manifest['capitulo'] or str(texts['execucao']) != str(manifest['execucao']):
        raise ValueError('Arquivo de textos não corresponde à execução da preparação.')
    scenes = choose(args.cenas, manifest['cenas'])
    for scene in scenes:
        entry = texts['cenas'].get(scene['cena'], {})
        if not all(isinstance(entry.get(k), str) and entry[k].strip() for k in ('titulo', 'pergunta', 'legenda')):
            raise ValueError(f"Preencha título, pergunta e legenda de {scene['cena']}.")
        if not isinstance(entry.get('hashtags', []), list) or not all(isinstance(t, str) for t in entry.get('hashtags', [])):
            raise ValueError('Hashtags devem ser uma lista de textos.')
    out = Path('saida') / name
    out.mkdir(parents=True, exist_ok=True)
    font = 'assets/Anton-Regular.ttf'
    if not Path(font).exists():
        font = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    bg = Path('assets/fundo.jpg')
    if not bg.exists():
        bg = work/'fundo.png'
        Image.new('RGB', (1280, 1920), '#101b30').save(bg)
    with Image.open(bg) as img:
        if img.size != (1280, 1920):
            raise ValueError('O fundo precisa medir 1280 × 1920. Ajuste assets/fundo.jpg.')
    for scene in scenes:
        entry = texts['cenas'][scene['cena']]
        title_img, question_img = work/'titulo.png', work/'pergunta.png'
        panel(entry['titulo'], title_img, (1103, 300), 'title', font, 85)
        panel(entry['pergunta'], question_img, (1020, 190), 'question', font, 37)
        length = scene['fim']-scene['inicio']
        start_question = max(0, length-7)
        final = out/f"{scene['cena']}_final.mp4"
        filters = (f'[0:v]setsar=1[b];[1:v]setpts=PTS-STARTPTS[v];'
                   f'[b][v]overlay=(W-w)/2:(H-h)/2[base];'
                   f'[base][2:v]overlay=(W-w)/2:212[t];'
                   f"[t][3:v]overlay=(W-w)/2:1400:enable='gte(t,{start_question})'[out]")
        run('ffmpeg', '-y', '-v', 'error', '-loop', '1', '-framerate', '30', '-i', bg,
            '-ss', scene['inicio'], '-t', length, '-i', work/'convertido_4x3.mp4',
            '-loop', '1', '-i', title_img, '-loop', '1', '-i', question_img,
            '-filter_complex_threads', '1', '-filter_complex', filters, '-map', '[out]', '-map', '1:a:0',
            '-t', length, '-r', '30', '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
            '-threads', '4', '-c:a', 'aac', '-movflags', '+faststart', final)
        tags = ' '.join(t if t.startswith('#') else '#'+t for t in entry.get('hashtags', []))
        final.with_suffix('.txt').write_text(entry['legenda'].strip()+'\n\n'+tags+'\n', encoding='utf-8')
        print(f'Finalizada {scene["cena"]}')
    write_json(out/'resumo.json', {'capitulo': manifest['capitulo'], 'cenas': [s['cena'] for s in scenes]})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('etapa', choices=['preparar', 'finalizar'])
    parser.add_argument('--capitulo', required=True)
    parser.add_argument('--link', default='')
    parser.add_argument('--cenas', default='todas')
    args = parser.parse_args()
    (prepare if args.etapa == 'preparar' else finish)(args)

