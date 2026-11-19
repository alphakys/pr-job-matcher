from __future__ import annotations

from src.models import JobPost, Review

SEED_RAW_PRS: list[dict[str, object]] = [
    {
        "pr_id": 101,
        "repo": "alpha/commerce-gateway",
        "title": "Gateway Fallback & Timeout Isolation for External Notifications",
        "problem": (
            "External Alimtalk and PG webhook outages (connecting via internal-pg.corp:8443) "
            "cascaded to core checkout threads with 30s socket stalls."
        ),
        "action": (
            "Built an explicit API Gateway Fallback layer with per-upstream timeout budgets, "
            "circuit-breaker guards, and retry-safe dead-letter queuing."
        ),
        "impact": "Prevented full-service checkout downtime during 3rd-party API outages (99.98% availability).",
    },
    {
        "pr_id": 102,
        "repo": "alpha/observability-infra",
        "title": "Promtail + Loki + Grafana Observability Stack for Batch Fleet",
        "problem": (
            "450+ legacy cron and FastAPI worker logs were scattered on local disks, "
            "delaying incident root-cause analysis past 40 minutes."
        ),
        "action": (
            "Deployed centralized Promtail/Loki/Grafana structured logging with correlation IDs "
            "and CloudWatch/Slack threshold alert dashboards."
        ),
        "impact": "Cut incident triage and batch failure detection time from 40m to under 2m.",
    },
    {
        "pr_id": 103,
        "repo": "alpha/order-core",
        "title": "MariaDB Explicit Transaction & Idempotency Key Guard",
        "problem": (
            "Concurrent webhook retries against Raw SQL MariaDB tables caused duplicate settlement rows "
            "and lock-wait timeouts under peak traffic."
        ),
        "action": (
            "Enforced explicit transaction boundaries, connection-pool sizing, and unique idempotency keys "
            "using atomic INSERT-ON-DUPLICATE guards."
        ),
        "impact": "Eliminated duplicate settlement incidents (100% consistency under retry storms).",
    },
    {
        "pr_id": 104,
        "repo": "alpha/automation-workers",
        "title": "Python Cron Modular Refactoring & LLM Daily Briefing Pipeline",
        "problem": (
            "Monolithic scheduled Python scripts had copy-pasted HTTP/DB logic and manual operational reporting "
            "(legacy token ghp_mock1234567890abcdef1234567890 removed during migration)."
        ),
        "action": (
            "Refactored batch pipelines into shared AWS Lambda/EventBridge Python modules with retry policies "
            "and automated OpenAI LLM executive summary briefings."
        ),
        "impact": "Reduced batch code duplication by 65% and saved 6 hours/week of manual ops reporting.",
    },
]

SEED_JOBS_AND_REVIEWS: list[tuple[JobPost, list[Review]]] = [
    (
        JobPost(
            job_id="wanted-9001",
            source="wanted",
            company="ChaosAgency",
            title="Backend Rockstar (급구)",
            body="백엔드 개발자 급구. 가족같은 분위기. 다양한 업무 가능자. 열정적인 분 환영.",
            repost_90d=4,
            url="https://www.wanted.co.kr/wd/9001",
        ),
        [
            Review(
                source="employee",
                rating=1.5,
                text="주먹구구 운영, 잦은 야근, 퇴사율 높음, 임원 독단적 결정",
                company_normalized="chaosagency",
                source_platform="jobplanet",
            ),
        ],
    ),
    (
        JobPost(
            job_id="saramin-9002",
            source="saramin",
            company="ChurnFinTech",
            title="Python/Node.js Backend Engineer",
            body=(
                "We operate high-volume Python batch jobs and FastAPI microservices on MariaDB. "
                "Looking for a backend engineer to stabilize external payment gateway fallback, "
                "refactor legacy cron tasks, and improve Grafana/Loki observability across clusters."
            ),
            repost_90d=3,
            url="https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=9002",
        ),
        [
            Review(
                source="interview",
                rating=3.2,
                text="Standard technical questions on API design and transactions.",
                company_normalized="churnfintech",
                source_platform="jobplanet",
            ),
            Review(
                source="employee",
                rating=2.6,
                text="잦은 조직 개편으로 핵심 백엔드 인력 이탈이 반복됨.",
                company_normalized="churnfintech",
                source_platform="blind",
            ),
        ],
    ),
    (
        JobPost(
            job_id="wanted-9003",
            source="wanted",
            company="ToxicCommerce",
            title="Backend Engineer (Python / MySQL)",
            body=(
                "Python Django/FastAPI 기반 대용량 정산 cron 배치 파이프라인 리팩토링 및 트래픽 병목 해소, "
                "외부 결제/알림 API timeout/fallback 장애 격리 및 Promtail/Loki/Grafana 관측(observability) 로깅 고도화를 담당할 분을 찾습니다. "
                "MariaDB Raw SQL 트랜잭션 락 경합 해결과 멱등성(idempotency) 보장이 핵심 과제입니다."
            ),
            repost_90d=1,
            url="https://www.wanted.co.kr/wd/9003",
        ),
        [
            Review(
                source="interview",
                rating=2.0,
                text="면접관이 준비 없이 들어와 압박 위주로 진행함.",
                company_normalized="toxiccommerce",
                source_platform="jobplanet",
            ),
            Review(
                source="employee",
                rating=1.4,
                text="주먹구구 경영, 야근 강요, micromanage 심하고 퇴사율 매우 높음.",
                company_normalized="toxiccommerce",
                source_platform="blind",
            ),
        ],
    ),
    (
        JobPost(
            job_id="wanted-9004",
            source="wanted",
            company="ScaleCommerce",
            title="Backend & Automation Engineer",
            body=(
                "We run 450+ Python cron pipelines and NestJS/FastAPI services. "
                "Looking for a backend engineer to refactor legacy batch scripts into shared modules, "
                "build centralized Promtail/Loki/Grafana observability and alert pipelines, "
                "and harden external API gateway fallback and idempotency across concurrent MariaDB transactions."
            ),
            repost_90d=0,
            url="https://www.wanted.co.kr/wd/9004",
        ),
        [
            Review(
                source="interview",
                rating=4.6,
                text="실제 운영 장애와 트랜잭션 멱등성 아키텍처를 깊이 있게 논의한 건강한 기술 면접.",
                company_normalized="scalecommerce",
                source_platform="jobplanet",
            ),
            Review(
                source="employee",
                rating=4.4,
                text="엔지니어링 자율성이 높고 코드 리뷰 문화 및 장애 회고(Post-mortem)가 투명함.",
                company_normalized="scalecommerce",
                source_platform="blind",
            ),
        ],
    ),
    (
        JobPost(
            job_id="saramin-9005",
            source="saramin",
            company="CorePayPlatform",
            title="서버/백엔드 개발자 (정산·배치 파이프라인)",
            body=(
                "결제·정산 도메인의 대용량 Python/Celery 배치 파이프라인 리팩토링과 "
                "MariaDB Raw SQL 트랜잭션 락/병목 개선, 외부 PG사 연동 Gateway Fallback 및 "
                "Timeout 격리 아키텍처를 구축할 백엔드 엔지니어를 모십니다. "
                "Grafana 기반 실시간 관측(observability) 및 LLM 자동 리포팅 워크플로우 고도화도 진행합니다."
            ),
            repost_90d=0,
            url="https://www.saramin.co.kr/zf_user/jobs/relay/view?rec_idx=9005",
        ),
        [
            Review(
                source="interview",
                rating=4.4,
                text="이전 PR 경험 기반의 실질적인 트러블슈팅 질문 위주라 인상적이었습니다.",
                company_normalized="corepayplatform",
                source_platform="jobplanet",
            ),
            Review(
                source="employee",
                rating=4.2,
                text="기술 부채를 공식 스프린트에 반영해 해결할 수 있고 워라밸이 준수함.",
                company_normalized="corepayplatform",
                source_platform="jobplanet",
            ),
        ],
    ),
]
