"""공고 원문의 문장과 섹션 제목에서 요구사항을 추출합니다. 외부 AI 호출 없음."""
import re
from html import unescape

FIELDS = {
    'responsibilities': '주요 업무', 'required': '필수 역량', 'preferred': '우대 조건',
    'experience': '경력', 'education': '학력', 'authorization': '비자·취업 자격',
    'arrangement': '근무 조건',
}
PREFERRED = r'preferred|nice[- ]to[- ]have|desirable|bonus|a plus|advantage|what we value|우대|가점'
REQUIRED = r'requirements?|qualifications?|what (?:you|we) (?:need|bring|require|expect|look for)|must|minimum|필수|자격.?요건|지원.?자격'
RESPONSIBILITIES = r'responsibilit|job description|what you(?:.ll| will) do|the role|your (?:role|mission)|담당.?업무|주요.?업무|수행.?업무'


def plain(value):
    text = re.sub(r'<(?:br\s*/?|/(?:p|div|li|ul|ol|h[1-6]))\s*>', '\n', value or '', flags=re.I)
    text = unescape(re.sub(r'<[^>]+>', '', text))
    return '\n'.join(re.sub(r'[ \t]+', ' ', line).strip() for line in text.splitlines()).strip()


def heading_type(text):
    if re.search(PREFERRED, text, re.I):
        return 'preferred'
    if re.search(REQUIRED, text, re.I):
        return 'required'
    if re.search(RESPONSIBILITIES, text, re.I):
        return 'responsibilities'
    return None


def summarize(job):
    fields = {key: [] for key in FIELDS}
    sections = job.get('sections') or [{'heading':'','text':job.get('description','')}]
    for section in sections:
        context = heading_type(section.get('heading',''))
        for line in plain(section.get('text','')).splitlines():
            line = re.sub(r'^\s*[•*\-]+\s*', '', line).strip()
            if not line:
                continue
            # 짧은 독립 제목만 이후 문장의 섹션으로 취급합니다.
            label = heading_type(line)
            if label and re.fullmatch(
                    r'(?:required|minimum|preferred|basic)?\s*(?:qualifications?|requirements?|skills?|responsibilities)|'
                    r'what (?:we|you) (?:value|need|bring|require|expect)|job description|your (?:role|mission)|'
                    r'필수.?역량|우대.?사항|자격.?요건|지원.?자격|담당.?업무|주요.?업무',
                    line.rstrip(':：').strip(), re.I):
                context=label
                continue
            for sentence in re.split(r'(?<=[.!?。])\s+(?=[A-Z가-힣])', line):
                preferred = context=='preferred' or bool(re.search(PREFERRED,sentence,re.I))
                special = None
                if re.search(r'visa|sponsor|right to work|work authori[sz]|eligible to work|citizen|citizenship|security clearance|비자|시민권|국적|취업.?자격|근로.?자격|보안.?인가',sentence,re.I):
                    special='authorization'
                elif re.search(r'years?.{0,45}experience|experience.{0,45}years?|경력.{0,15}년|신입|no (?:prior )?experience',sentence,re.I):
                    special='experience'
                elif re.search(r'degree|bachelor|master|ph\.?d|graduate in|graduat(?:e|ing) (?:between|by|in)|학위|학사|석사|박사|졸업',sentence,re.I):
                    special='education'
                elif re.search(r'\bremote\b|\bhybrid\b|on[- ]site|onsite|relocat|based in|work(?:ing)? (?:hours|days)|재택|원격|출근|근무.?시간|근무지',sentence,re.I):
                    special='arrangement'
                field = 'preferred' if preferred else special or context
                if not field and re.search(r'\bmust\b|\brequired\b|필수',sentence,re.I):
                    field='required'
                if field and sentence not in fields[field] and len(fields[field])<2:
                    fields[field].append(sentence)
    return fields


def brief(text, limit=100):
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text)<=limit:
        return text
    head=text[:limit-1]
    if ' ' in head:
        head=head.rsplit(' ',1)[0]
    return head+'…'


def render(summary):
    lines=['**요구사항 · 원문 발췌**']
    for field,label in FIELDS.items():
        texts=[brief(text, 95) for text in summary[field]]
        lines.append(f'• **{label}**: '+(' / '.join(texts) if texts else '원문 확인'))
    lines.append('영문 조건은 원문을 유지합니다. 생략된 내용은 공고 링크에서 확인해 주세요.')
    return '\n'.join(lines)
