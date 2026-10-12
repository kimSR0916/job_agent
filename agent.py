"""개인용 공고 수집 및 Discord 알림. Python 표준 라이브러리만 사용."""
import argparse
import html
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from career import connection, job_sort_key, load_goal
from network import tls_context

ROOT = Path(__file__).resolve().parent


def request_json(url, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": "PersonalJobAgent/0.1",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=30, context=tls_context()) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        # 예외 원문에는 비밀 webhook URL이 포함될 수 있으므로 출력하지 않습니다.
        raise RuntimeError(f"외부 서비스 HTTP 오류 {exc.code}") from None
    except urllib.error.URLError:
        raise RuntimeError("외부 서비스 연결 실패") from None
    except TimeoutError:
        raise RuntimeError("외부 서비스 응답 시간 초과") from None


def clean(value):
    return html.unescape(re.sub(r"<[^>]+>", " ", value or ""))


def collect(source, config=None, goal=None):
    company = source["company"]
    slug = urllib.parse.quote(company, safe="")
    if source["provider"] == "lever":
        items = request_json(f"https://api.lever.co/v0/postings/{slug}?mode=json")
        for item in items:
            categories = item.get("categories", {})
            yield {
                "id": f"lever:{company}:{item['id']}", "company": source.get("name", company),
                "title": item["text"], "url": item["hostedUrl"],
                "location": categories.get("location", "미확인"),
                "work_type": categories.get("commitment", ""),
                "source_domain": source.get("domain", ""),
                "description": clean(item.get("description", "")) + " " + " ".join(
                    clean(part.get("content", "")) for part in item.get("lists", [])),
            }
    elif source["provider"] == "greenhouse":
        result = request_json(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true")
        for item in result["jobs"]:
            yield {
                "id": f"greenhouse:{company}:{item['id']}", "company": company,
                "title": item["title"], "url": item["absolute_url"],
                "location": item.get("location", {}).get("name", "미확인"),
                "source_domain": source.get("domain", ""),
                "description": clean(item.get("content", "")),
            }
    elif source["provider"] == "smartrecruiters":
        base = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
        offset, limit = 0, 100
        while True:
            result = request_json(f"{base}?limit={limit}&offset={offset}")
            items = result["content"]
            for item in items:
                job = {
                    "id": f"smartrecruiters:{company}:{item['id']}",
                    "company": source.get("name", company), "title": item["name"],
                    "source_domain": source.get("domain", ""),
                    "work_type": item.get("typeOfEmployment", {}).get("label", ""),
                    "experience_level": item.get("experienceLevel", {}).get("label", ""),
                    "description": "",
                    "location": ", ".join(str(item.get("location", {}).get(key, ""))
                                          for key in ("city", "region", "country") if item.get("location", {}).get(key)),
                }
                # 목록의 직함·채용 형태로 후보를 좁혀 상세 조회 횟수를 줄입니다.
                if config is not None and not matches(job, config, goal):
                    continue
                detail = request_json(f"{base}/{urllib.parse.quote(str(item['id']), safe='')}")
                job["description"] = "\n".join(clean(section.get("text", "")) for section in
                                                detail.get("jobAd", {}).get("sections", {}).values())
                job["url"] = detail.get("applyUrl") or f"https://jobs.smartrecruiters.com/{slug}/{item['id']}"
                yield job
            offset += len(items)
            if not items or offset >= result["totalFound"]:
                break
    else:
        raise ValueError("지원하지 않는 공고 수집 제공자")


def matches(job, config, goal=None):
    title = job["title"].lower()
    body = job["description"].lower()
    if any(word.lower() in title for word in config["exclude_keywords"]):
        return False
    # 학위 우대 조건을 경력 제한으로 오인하지 않도록 'experience/경력'에 한정.
    if re.search(r"\b(?:[3-9]|\d{2,})\+?\s*years?\s+(?:of\s+)?(?:\w+\s+){0,4}experience", body):
        return False
    if re.search(r"경력\s*[3-9]\s*년\s*이상", body):
        return False
    industry_candidate = (goal is not None and goal.get("role_scope") == "industry_entry"
                          and bool(connection(job, goal)["keyword_evidence"]["domain"]))
    level_text = " ".join((title, job.get("work_type", "").lower(), job.get("experience_level", "").lower()))
    return ((industry_candidate or any(word.lower() in title for word in config["role_keywords"]))
            and any(word.lower() in level_text for word in config["level_keywords"]))


def connect(path):
    db = sqlite3.connect(path)
    db.execute("""CREATE TABLE IF NOT EXISTS jobs (
        user_id TEXT, job_id TEXT, payload TEXT NOT NULL,
        discord_sent INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(user_id, job_id))""")
    db.commit()
    return db


def enqueue(db, user, job):
    db.execute("INSERT INTO jobs(user_id, job_id, payload) VALUES (?, ?, ?) "
               "ON CONFLICT(user_id, job_id) DO UPDATE SET payload=excluded.payload",
               (user, job["id"], json.dumps(job, ensure_ascii=False)))
    db.commit()


def deliver(db, user, sender):
    pending = db.execute("SELECT job_id, payload FROM jobs WHERE user_id=? AND discord_sent=0",
                         (user,)).fetchall()
    pending.sort(key=lambda row: job_sort_key(json.loads(row[1])), reverse=True)
    for job_id, payload in pending:
        sender(json.loads(payload))
        db.execute("UPDATE jobs SET discord_sent=1 WHERE user_id=? AND job_id=?", (user, job_id))
        db.commit()


def notify(job):
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook.startswith("https://discord.com/api/webhooks/"):
        raise RuntimeError(".env에 유효한 DISCORD_WEBHOOK_URL을 설정하세요")
    career = job.get("career_connection")
    detail = (f"\n분야: {career.get('preferred_domain', '미확인')}\n"
              f"목표 연결: {career['category']}\n{career['reason']}") if career else ""
    request_json(webhook + ("&" if "?" in webhook else "?") + "wait=true", {
        "content": f"새 채용 공고 · {job['company']}\n{job['title']}\n{job['location']}\n{job['url']}{detail}"[:1900],
        "allowed_mentions": {"parse": []},
    })


def run(config, dry_run):
    found = []
    goal_file = config.get("career_goal_file")
    goal_path = ROOT / goal_file if goal_file else None
    goal = load_goal(goal_path) if goal_path and goal_path.exists() else None
    for source in config["sources"]:
        try:
            found.extend(job for job in collect(source, config, goal) if matches(job, config, goal))
        except (RuntimeError, ValueError, KeyError, TypeError):
            print(f"수집 실패: {source['provider']} / {source['company']} (다음 실행에서 재시도)", flush=True)
    if goal:
        for job in found:
            job["career_connection"] = connection(job, goal)
        found.sort(key=job_sort_key, reverse=True)
    if dry_run:
        print(json.dumps(found, ensure_ascii=False, indent=2))
        return
    (ROOT / "data").mkdir(exist_ok=True)
    with connect(ROOT / "data/jobs.sqlite3") as db:
        for job in found:
            enqueue(db, config["user_id"], job)
        try:
            deliver(db, config["user_id"], notify)
        except RuntimeError as exc:
            print(f"알림 실패: {exc}. 미전송 공고는 다음 실행에서 재시도합니다.", flush=True)
    print(f"이번 실행 조건 일치 공고: {len(found)}건", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="외부 전송 및 DB 저장 없이 공고 미리보기")
    parser.add_argument("--loop", action="store_true", help="프로세스가 실행되는 동안 주기적으로 수집")
    args = parser.parse_args()
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.strip() and not line.lstrip().startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    config = json.loads((ROOT / "config.json").read_text())
    if config["interval_minutes"] <= 0:
        parser.error("interval_minutes는 양수여야 합니다")
    while True:
        run(config, args.dry_run)
        if not args.loop:
            break
        time.sleep(config["interval_minutes"] * 60)


if __name__ == "__main__":
    main()
