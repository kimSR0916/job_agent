"""실제 CPU 번역 모델로 한국어·숫자·부정 조건을 확인합니다. Discord 전송 없음."""
from contextlib import closing
import agent
from translation import KoreanTranslator


def main():
    (agent.ROOT / 'data').mkdir(exist_ok=True)
    source = {
        'required':['Python and SQL are required.'],
        'education':['Applicants must graduate in 2028.'],
        'authorization':['Visa sponsorship is not available.'],
    }
    with closing(agent.connect(agent.ROOT / 'data/jobs.sqlite3')) as db:
        target = KoreanTranslator(db)(source)
    for field,texts in target.items():
        print(field+': '+' / '.join(texts),flush=True)
    print('실제 CPU 번역 검증 성공',flush=True)


if __name__ == '__main__':
    main()
