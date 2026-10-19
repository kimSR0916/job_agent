"""최종 목표와 이력서를 연결하는 경로 초안 및 공고 우선순위.

키워드 기반 첫 버전입니다. 역량 검증, 합격 가능성 예측을 하지 않습니다.
"""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent


def keywords(text, words):
    return [word for word in words if re.search(
        r"(?<![A-Za-z0-9_])" + re.escape(word) + r"(?![A-Za-z0-9_])" if word.isascii() else re.escape(word),
        text, flags=re.I)]


def load_goal(path):
    goal = json.loads(path.read_text(encoding="utf-8"))
    for field in ("final_goal", "preferred_domain"):
        if not isinstance(goal.get(field), str) or not goal[field].strip():
            raise ValueError(f"{field}를 입력하세요")
    for field in ("domain_keywords", "analysis_keywords", "bridge_keywords", "competencies", "routes"):
        if not isinstance(goal.get(field), list) or not goal[field]:
            raise ValueError(f"{field} 설정이 필요합니다")
    groups = goal.get("domain_priorities", [])
    if not isinstance(groups, list) or any(not isinstance(group, dict)
            or not isinstance(group.get("name"), str) or not group["name"].strip()
            or not isinstance(group.get("keywords"), list) or not group["keywords"]
            or any(not isinstance(word, str) or not word.strip() for word in group["keywords"])
            for group in groups):
        raise ValueError("domain_priorities에는 분야 이름과 키워드를 순서대로 입력하세요")
    return goal


def connection(job, goal):
    text = " ".join(job.get(key, "") for key in ("company", "title", "description"))
    domain = keywords(text, goal["domain_keywords"])
    groups = goal.get("domain_priorities", [])
    preferred, domain_priority, domain_evidence = "분야 미확인", 0, []
    for index, group in enumerate(groups):
        explicit_domain = job.get("source_domain", "")
        if explicit_domain and explicit_domain != group["name"]:
            continue
        hits = [f"수집처 설정: {explicit_domain}"] if explicit_domain else keywords(text, group["keywords"])
        if hits:
            preferred, domain_priority, domain_evidence = group["name"], len(groups) - index, hits
            domain = list(dict.fromkeys(domain + hits))
            break
    analysis = keywords(text, goal["analysis_keywords"])
    bridge = keywords(text, goal["bridge_keywords"])
    if domain and goal.get("role_scope") == "analysis_development":
        category, priority = "희망 업계 분석·개발 후보", 3
        reason = "희망 업계의 분석·개발 직무 후보입니다. 이력서와 공고의 필수 요건을 비교해야 합니다."
    elif domain and goal.get("role_scope") == "industry_entry":
        category, priority = "희망 업계 진입 후보", 3
        reason = "희망 업계 관련 표현이 있습니다. 직무를 분석·개발로 제한하지 않으며 이력서와 필수 요건을 비교해야 합니다."
    elif domain and analysis:
        category, priority = "스포츠 분석 관련 단서", 3
        reason = "스포츠와 분석 업무의 표현이 함께 있습니다. 실제 경기 분석 업무인지 본문 확인이 필요합니다."
    elif domain and bridge:
        category, priority = "스포츠 기술 직무 관련 단서", 2
        reason = "스포츠 분야의 기술 경험 후보입니다. 희망 업무와 맞는지는 업무 범위 확인이 필요합니다."
    elif bridge:
        category, priority = "중간 기술 경험 후보", 1
        reason = "데이터·개발 관련 표현이 있습니다. 희망 업계로 이동할 때 활용할 수 있는 경험인지 확인하세요."
    else:
        category, priority = "최종 목표 연관 미확인", 0
        reason = "현재 키워드로는 최종 목표와의 연결 근거를 찾지 못했습니다."
    return {"category": category, "priority": priority, "reason": reason,
            "preferred_domain": preferred,
            "domain_priority": domain_priority if priority >= 2 else 0,
            "domain_evidence": domain_evidence,
            "keyword_evidence": {"domain": domain, "analysis": analysis, "bridge": bridge}}


def job_sort_key(job):
    info = job.get("career_connection", {})
    return info.get("domain_priority", 0), info.get("priority", 0)


def resume_evidence(resume, competencies):
    results = []
    for competency in competencies:
        lines = [line.strip() for line in resume.splitlines()
                 if keywords(line, competency["keywords"])]
        results.append({"name": competency["name"], "evidence": lines[:3],
                        "status": "언급 있음 · 수준 확인 필요" if lines else "이력서에서 미확인",
                        "checkpoint": competency["checkpoint"]})
    return results


def roadmap(goal, resume=""):
    evidence = resume_evidence(resume, goal["competencies"])
    parts = ["# 최종 목표에서 역산한 커리어 경로 초안",
             f"최종 목표: {goal['final_goal']}", f"우선 분야: {goal['preferred_domain']}",
             "분야 우선순위: " + " → ".join(group["name"] for group in goal.get("domain_priorities", [])),
             "직무 범위: " + ("업계 진입 중심 · 데이터 분석에 한정하지 않음"
                              if goal.get("role_scope") == "industry_entry" else "설정된 직무 중심"),
             f"다른 스포츠 분야 허용: {'예' if goal.get('allow_other_sports') else '아니요'}",
             "이 초안은 설정된 경로와 이력서 키워드 근거를 연결합니다. 직함만으로 보유 역량을 추정하지 않으며, "
             "언급된 기술의 숙련도·실무 성과·현재 공고의 필수 요건은 별도 확인해야 합니다. "
             "경로의 성공 가능성이나 소요 연수를 예측하지 않습니다."]
    if not resume.strip():
        parts.append("**이력서 미입력: 아래는 개인별 순위가 없는 후보 경로입니다.**")
    parts.append("## 현재 이력서에서 확인할 근거")
    parts.append("아래 역량은 직무별 비교에 쓰는 항목입니다. 모든 직무에 전부 필요한 필수 조건은 아닙니다.")
    for item in evidence:
        parts.append(f"### {item['name']} — {item['status']}")
        for line in item["evidence"]:
            parts.append(f"> {line.replace(chr(10), ' ')}")
        parts.append(f"다음 검증 기준: {item['checkpoint']}")
    parts.append("## 최종 목표로 이어지는 후보 경로")
    for route in goal["routes"]:
        parts.append(f"### {route['name']}\n\n{' → '.join(route['stages'])}")
        parts.append(f"선택할 때 확인할 조건: {route['condition']}")
        parts.append(f"다음 단계로 넘어갈 근거: {route['checkpoint']}")
        parts.append(f"경로의 한계: {route['limitation']}")
    parts.append("## 다음 공고를 검토할 기준")
    parts.append("1. 지금 이력서로 충족하는 필수 요건과 미확인 요건을 분리합니다.\n"
                 "2. 희망 업계의 공고는 직무를 분석으로 제한하지 않고 이력서와 실제 업무 요건을 비교합니다.\n"
                 "3. 팀·리그·스포츠 서비스 기업 등 어떤 조직인지와 실제 담당 업무를 구분합니다.\n"
                 "4. 목표와 연결되는 경험을 만들 수 있는 공고를 우선 검토하되, 연결이 약한 공고도 숨기지 않습니다.\n"
                 "5. 학위·졸업 시기·근무지·비자·언어 요건과 실제 지원 가능 여부를 확인합니다.")
    parts.append("## 추가로 필요한 정보")
    parts.append("이력서와 프로젝트별 본인 역할, 영어 사용 경험, 해외 이주 가능 여부, "
                 "원하는 근무 방식과 업무, 목표 시점은 아직 추가 확인이 필요합니다. "
                 "통계·수학이나 차량 공학은 해당 역량을 요구하는 직무를 검토할 때 따로 확인합니다.")
    parts.append("## 경로 설계에 참고한 공식 자료")
    for source in goal.get("sources", []):
        parts.append(f"- [{source['title']}]({source['url']}) — {source['note']}")
    return "\n\n".join(parts) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--goal", type=Path, default=ROOT / "career-goal.local.json")
    parser.add_argument("--resume", type=Path, help="UTF-8 Markdown 또는 TXT 이력서")
    parser.add_argument("--output", type=Path, default=ROOT / "data/career-roadmap.md")
    args = parser.parse_args()
    if args.resume and args.resume.suffix.lower() not in (".md", ".txt"):
        parser.error("첫 버전은 Markdown/TXT 이력서를 지원합니다. PDF/DOCX 추출은 미구현입니다.")
    goal = load_goal(args.goal)
    resume = args.resume.read_text(encoding="utf-8") if args.resume else ""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(roadmap(goal, resume), encoding="utf-8")
    print(f"커리어 경로 초안 저장: {args.output}")


if __name__ == "__main__":
    main()
