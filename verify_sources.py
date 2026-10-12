"""공식 API를 실제 조회해 수집 결과만 저장합니다. 알림은 전송하지 않습니다."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
from zoneinfo import ZoneInfo
import agent


def main():
    config = json.loads((agent.ROOT / "config.json").read_text())
    goal = agent.load_goal(agent.ROOT / config["career_goal_file"])
    def check(source):
        try:
            jobs = list(agent.collect(source, config, goal))
            matches = [job for job in jobs if agent.matches(job, config, goal)]
            return {"company": source.get("name", source["company"]), "provider": source["provider"],
                    "status": "ok", "collected": len(jobs), "matched": len(matches),
                    "note": "SmartRecruiters는 목록에서 신입 후보를 선별한 뒤 상세 본문을 조회합니다.",
                    "jobs": [{"title": job["title"], "url": job["url"], "location": job["location"],
                              "career_connection": agent.connection(job, goal)} for job in matches]}
        except (RuntimeError, KeyError, ValueError, TypeError) as exc:
            return {"company": source.get("name", source["company"]), "status": "error", "error": str(exc)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(check, config["sources"]))
    output = {"checked_at": datetime.now(ZoneInfo("Asia/Seoul")).isoformat(), "sources": results}
    path = agent.ROOT / "data/source-verification.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    for result in results:
        print(result["company"], result["status"], "조건 일치:", result.get("matched", "미확인"))
    print("검증 결과:", path)
    if any(result["status"] == "error" for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
