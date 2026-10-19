"""공개 M2M100 모델을 CPU에서 직접 실행하는 한국어 번역. 외부 추론 API 없음."""
import os
import re

MODEL = 'facebook/m2m100_418M'
REVISION = '55c2e61bbf05dfb8d7abccdc3fae6fc8512fd636'
CACHE_VERSION = REVISION + ':ko-v1'


class TranslationBudgetReached(RuntimeError):
    pass


def validate(source, target):
    if not isinstance(target, str) or not re.search(r'[가-힣]', target):
        raise RuntimeError('한국어 번역 결과를 확인하지 못했습니다')
    if any(number not in re.findall(r'\d+', target) for number in re.findall(r'\d+', source)):
        raise RuntimeError('번역에서 경력·졸업 연도 등의 숫자가 달라졌습니다')
    negative = re.sub(r'\bnot only\b', '', source, flags=re.I)
    if re.search(r"\b(?:no|not|without|cannot|unavailable|can't|isn't|doesn't|won't)\b", negative, re.I):
        if not re.search(r'없|않|아니|불가|못|말아|금지', target):
            raise RuntimeError('번역에서 부정 조건을 확인하지 못했습니다')
    return target.strip()


class KoreanTranslator:
    def __init__(self, db, settings=None):
        self.db, self.settings = db, settings or {}
        self.translated_jobs = 0
        self._model = self._tokenizer = self._torch = None
        db.execute('''CREATE TABLE IF NOT EXISTS translations (
            version TEXT, source TEXT, target TEXT, PRIMARY KEY(version,source))''')
        db.commit()

    def _load(self):
        if self._model is not None:
            return
        try:
            import torch
            from transformers import M2M100ForConditionalGeneration, M2M100Tokenizer
        except ImportError:
            raise RuntimeError('번역 실행 패키지가 없습니다. translation-requirements.txt를 설치하세요') from None
        print('한국어 번역 모델 준비 중 (CPU 직접 실행)', flush=True)
        torch.set_num_threads(min(4, os.cpu_count() or 1))
        self._torch = torch
        try:
            self._tokenizer = M2M100Tokenizer.from_pretrained(MODEL, revision=REVISION, src_lang='en')
            self._model = M2M100ForConditionalGeneration.from_pretrained(
                MODEL, revision=REVISION, use_safetensors=False).to('cpu').eval()
        except (OSError, ValueError):
            raise RuntimeError('번역 모델 다운로드 또는 로딩 실패') from None

    def _segments(self, text):
        # 긴 조건도 뒤를 잘라 버리지 않고 전체 단어를 작은 묶음으로 나눕니다.
        if len(self._tokenizer.encode(text, add_special_tokens=False)) <= 220:
            return [text]
        chunks, current = [], []
        for word in text.split():
            proposed = ' '.join(current + [word])
            if current and len(self._tokenizer.encode(proposed, add_special_tokens=False)) > 220:
                chunks.append(' '.join(current))
                current = []
            current.append(word)
        if current:
            chunks.append(' '.join(current))
        return chunks

    def _translate(self, texts):
        self._load()
        translated = []
        for text in texts:
            parts = []
            for segment in self._segments(text):
                encoded = self._tokenizer(segment, return_tensors='pt', truncation=False)
                with self._torch.inference_mode():
                    tokens = self._model.generate(**encoded, forced_bos_token_id=self._tokenizer.get_lang_id('ko'),
                        max_new_tokens=384, num_beams=2, do_sample=False)
                if self._tokenizer.eos_token_id not in tokens[0].tolist()[2:]:
                    raise RuntimeError('번역이 길이 제한 안에 완료되지 않았습니다')
                parts.append(self._tokenizer.batch_decode(tokens, skip_special_tokens=True)[0])
            translated.append(' '.join(parts))
        return translated

    def __call__(self, summary):
        originals = list(dict.fromkeys(text for texts in summary.values() for text in texts))
        resolved, missing = {}, []
        for text in originals:
            if re.search(r'[가-힣]', text) or not re.search(r'[A-Za-z]', text):
                resolved[text] = text
                continue
            row = self.db.execute('SELECT target FROM translations WHERE version=? AND source=?',
                                  (CACHE_VERSION,text)).fetchone()
            if row:
                resolved[text] = validate(text,row[0])
            else:
                missing.append(text)
        if missing:
            if self.translated_jobs >= self.settings.get('max_jobs_per_run', 10):
                raise TranslationBudgetReached('번역 처리 한도에 도달했습니다. 남은 공고는 다음 실행에서 처리합니다')
            self.translated_jobs += 1
            targets = self._translate(missing)
            if len(targets) != len(missing):
                raise RuntimeError('번역 결과 개수가 원문과 다릅니다')
            checked = [(source,validate(source,target)) for source,target in zip(missing,targets)]
            for source,target in checked:
                resolved[source] = target
                self.db.execute('INSERT OR REPLACE INTO translations VALUES (?,?,?)', (CACHE_VERSION,source,target))
            self.db.commit()
        return {key:[resolved[text] for text in texts] for key,texts in summary.items()}
