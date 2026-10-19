"""GitHub Actions에서 전송 기록을 명시적으로 초기화하거나 검증 후 복원합니다."""
import argparse
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import zipfile
import agent


def restore(archive, destination):
    with zipfile.ZipFile(archive) as bundle:
        if bundle.namelist() != ["jobs.sqlite3"]:
            raise ValueError("상태 파일 구성이 올바르지 않습니다")
        if bundle.getinfo("jobs.sqlite3").file_size > 128 * 1024 * 1024:
            raise ValueError("상태 파일이 허용 크기를 초과합니다")
        data = bundle.read("jobs.sqlite3")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as folder:
        candidate = Path(folder) / "jobs.sqlite3"
        candidate.write_bytes(data)
        with closing(sqlite3.connect(candidate.as_uri() + "?mode=ro", uri=True)) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("SQLite 상태 파일 손상")
            db.execute("SELECT user_id,job_id,payload,discord_sent FROM jobs LIMIT 1")
        candidate.replace(destination)


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--archive", type=Path)
    group.add_argument("--initialize", action="store_true")
    args = parser.parse_args()
    destination = agent.ROOT / "data/jobs.sqlite3"
    if args.archive:
        restore(args.archive, destination)
        print("이전 공고·전송 기록 복원 및 검증 완료")
    else:
        if destination.exists():
            raise RuntimeError("기존 기록은 초기화하지 않습니다")
        destination.parent.mkdir(exist_ok=True)
        with closing(agent.connect(destination)):
            pass
        print("최초 실행용 빈 상태 생성 완료")


if __name__ == "__main__":
    main()
