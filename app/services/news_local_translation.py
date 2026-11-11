"""Offline language detection and optional preinstalled CPU translation.

Models are provisioned at release time; no downloads or requests occur here.
Only public article titles and summaries are translated, never source bodies.
"""
from functools import lru_cache
import json
import os
from pathlib import Path
import re
from threading import RLock

_LOCK = RLock()


class _BpeTokenizer:
    def __init__(self, root, code):
        from sacremoses import MosesTokenizer, MosesDetokenizer, MosesPunctNormalizer
        from subword_nmt.apply_bpe import BPE
        self.tokenizer = MosesTokenizer(lang=code)
        self.detokenizer = MosesDetokenizer(lang='en')
        self.normalizer = MosesPunctNormalizer(lang=code)
        with (root / 'bpe.model').open(encoding='utf-8') as stream:
            self.bpe = BPE(stream)

    def encode(self, text, out_type=str):
        tokens = self.tokenizer.tokenize(self.normalizer.normalize(text))
        return ' '.join(self.bpe.segment_tokens(tokens)).split()

    def decode(self, tokens):
        return self.detokenizer.detokenize(' '.join(tokens).replace('@@ ', '').split())


@lru_cache(maxsize=1)
def _detector():
    from langid.langid import LanguageIdentifier, model
    return LanguageIdentifier.from_modelstring(model, norm_probs=True)


@lru_cache(maxsize=8192)
def language(text):
    sample = re.sub(r'<[^>]*>|&[a-zA-Z#0-9]+;', ' ', str(text or ''))[:4000]
    if len(re.findall(r'\w', sample)) < 12:
        return 'und'
    with _LOCK:
        code, probability = _detector().classify(sample)
    return code if probability >= .90 else 'und'


@lru_cache(maxsize=1)
def _engine(directory):
    import ctranslate2
    import sentencepiece
    root = Path(directory)
    metadata = json.loads((root / 'metadata.json').read_text(encoding='utf-8'))
    if metadata.get('to_code') != 'en':
        raise ValueError('Local News model must translate into English')
    tokenizer = (sentencepiece.SentencePieceProcessor(model_file=str(root / 'sentencepiece.model'))
                 if (root / 'sentencepiece.model').is_file() else _BpeTokenizer(root, metadata['from_code']))
    # The Spanish BPE model repeats tokens under int8 on the deployment CPU;
    # its release rehearsal passes in float32. Other staged models use int8.
    compute = 'float32' if metadata['from_code'] == 'es' else 'int8'
    translator = ctranslate2.Translator(str(root / 'model'), device='cpu', compute_type=compute,
                                      inter_threads=1, intra_threads=1)
    return tokenizer, translator, metadata.get('target_prefix', '')


def translate(title, summary):
    code = language(f'{title} {summary}')
    root = Path(os.environ.get('BIOS_NEWS_TRANSLATION_MODELS') or '/app/translation-models') / code
    if code in {'en', 'und'} or not (root / 'metadata.json').is_file():
        return None
    with _LOCK:
        tokenizer, engine, prefix = _engine(str(root))
        def render(text):
            tokens = tokenizer.encode(str(text or '')[:2400], out_type=str)
            batches = [tokens[i:i + 120] for i in range(0, len(tokens), 120)]
            if not batches:
                return ''
            translated = engine.translate_batch(batches, target_prefix=[[prefix]] * len(batches) if prefix else None,
                beam_size=4, max_batch_size=8, max_input_length=150, max_decoding_length=240,
                replace_unknowns=True)
            value = ' '.join(tokenizer.decode(row.hypotheses[0]).removeprefix(prefix).strip()
                             for row in translated).replace('▁', ' ').replace('_', ' ').strip()
            if len(value) > max(120, len(str(text)) * 5) or re.search(r'(.{3,25})\1{4,}', value):
                raise ValueError('Local translation produced repetitive or oversized output')
            return value
        return {'title': render(title), 'summary': render(summary), 'source_language': code,
                'translation_method': 'local-argos-ctranslate2'}
