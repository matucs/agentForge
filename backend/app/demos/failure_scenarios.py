"""Failure-injection demos (spec §13). Scenarios 2-4 are fully real without
any LLM: a real disposable git fixture repo, a real commit standing in for
"Developer just wrote this", then the real deterministic tail of the
pipeline (QA/Security/Verification/Policy) runs for real against it.
Reviewer's approval is the scenario's *simulated setup* (explicitly labeled
as such, never hidden) — everything downstream of it is real code doing
real work. Scenario 1 needs an actual LLM Reviewer call and is gated on
real credentials, same "Integration unavailable" pattern as `make eval`.
"""

import asyncio
import subprocess
import sys
import tempfile
from pathlib import Path

from app.agents.reviewer import run_reviewer
from app.config import get_settings
from app.db.repositories import ProjectRepository, RunRepository, TaskRepository
from app.db.session import async_session_factory
from app.git_integration import git_ops
from app.orchestration.nodes import policy_node, qa_node, security_node, verification_node
from app.orchestration.state import AgentState

_BASE_REF = "main"


def _has_real_llm_credentials() -> bool:
    settings = get_settings()
    return bool(settings.anthropic_api_key or settings.openai_api_key)


def _init_repo(tmp_dir: str) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_dir, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "main"], cwd=tmp_dir, check=True)


def _commit(tmp_dir: str, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=tmp_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=tmp_dir, check=True)


async def _make_run(name: str, repo_path: str) -> str:
    async with async_session_factory() as session:
        project = await ProjectRepository(session).create(
            name=f"demo-{name}", repo_path=repo_path, description=None
        )
        task = await TaskRepository(session).create(
            project_id=project.id, title=name, requirement_text=f"Demo: {name}"
        )
        run = await RunRepository(session).create(task_id=task.id)
        await session.commit()
        return run.id


def _initial_state(run_id: str, repo_path: str) -> AgentState:
    return AgentState(
        run_id=run_id,
        task_id="demo",
        requirement_text="demo",
        repo_path=repo_path,
        plan=None,
        architecture=None,
        research=None,
        review_findings=[],  # simulated Reviewer approval — see module docstring
        test_results=[],
        security_findings=[],
        verification_result=None,
        final_decision=None,
        iteration_count=0,
        status="running",
        error=None,
    )


async def _run_deterministic_tail(state: AgentState) -> AgentState:
    """Runs the real qa_node -> security_node -> verification_node ->
    policy_node in sequence, merging each node's real return into state —
    the same merge LangGraph performs, done explicitly here since this demo
    invokes the deterministic tail directly rather than through the full
    graph (Planner/Architect/Researcher/Developer/Reviewer are not real LLM
    calls in this scenario)."""
    for node in (qa_node, security_node, verification_node, policy_node):
        update = await node(state)
        state = {**state, **update}  # type: ignore[typeddict-item]
    return state


async def scenario_2_qa_overrides_reviewer() -> dict:
    """QA's real test execution catches what the (simulated) Reviewer
    approval missed. This is the spec's single most important
    demonstration: the LLM is not the final source of truth."""
    with tempfile.TemporaryDirectory(prefix="agentforge-demo-") as tmp_dir:
        _init_repo(tmp_dir)
        Path(tmp_dir, "app.py").write_text("def add(a, b):\n    return a + b\n")
        Path(tmp_dir, "test_app.py").write_text(
            "from app import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
        )
        _commit(tmp_dir, "initial commit")

        run_id = await _make_run("scenario-2", tmp_dir)
        git_ops.ensure_branch(tmp_dir, "agentforge/demo-scenario-2", base_ref=_BASE_REF)
        # The "Developer" introduces a real bug — subtraction instead of
        # addition — while a real Reviewer step is simulated as approving
        # it (review_findings=[] below, not a real LLM call).
        Path(tmp_dir, "app.py").write_text("def add(a, b):\n    return a - b\n")
        _commit(tmp_dir, "implement add() [demo: contains a real bug]")

        async with async_session_factory() as session:
            await RunRepository(session).update(
                run_id, branch_name="agentforge/demo-scenario-2"
            )
            await session.commit()

        final_state = await _run_deterministic_tail(_initial_state(run_id, tmp_dir))

    return {
        "run_id": run_id,
        "test_results": final_state["test_results"],
        "verification_result": final_state["verification_result"],
        "final_decision": final_state["final_decision"],
    }


async def scenario_3_security_blocks_secret() -> dict:
    """Security's real static scan catches a real secret-shaped string
    committed directly to the repo (standing in for "Developer just wrote
    this"), and the real Verification Gate blocks on it."""
    with tempfile.TemporaryDirectory(prefix="agentforge-demo-") as tmp_dir:
        _init_repo(tmp_dir)
        Path(tmp_dir, "app.py").write_text("def add(a, b):\n    return a + b\n")
        Path(tmp_dir, "test_app.py").write_text(
            "from app import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
        )
        _commit(tmp_dir, "initial commit")

        run_id = await _make_run("scenario-3", tmp_dir)
        git_ops.ensure_branch(tmp_dir, "agentforge/demo-scenario-3", base_ref=_BASE_REF)
        Path(tmp_dir, "config.py").write_text('AWS_KEY = "AKIAABCDEFGHIJKLMNOP"\n')
        _commit(tmp_dir, "add config [demo: contains a real hardcoded secret]")

        async with async_session_factory() as session:
            await RunRepository(session).update(
                run_id, branch_name="agentforge/demo-scenario-3"
            )
            await session.commit()

        final_state = await _run_deterministic_tail(_initial_state(run_id, tmp_dir))

    return {
        "run_id": run_id,
        "security_findings": final_state["security_findings"],
        "verification_result": final_state["verification_result"],
        "final_decision": final_state["final_decision"],
    }


async def scenario_4_migration_requires_approval() -> dict:
    """A real migration file change is classified `high` risk by the real
    policy engine and a real Approval row is created — fully real end to
    end, since risk classification never needed an LLM."""
    with tempfile.TemporaryDirectory(prefix="agentforge-demo-") as tmp_dir:
        _init_repo(tmp_dir)
        Path(tmp_dir, "app.py").write_text("def add(a, b):\n    return a + b\n")
        Path(tmp_dir, "test_app.py").write_text(
            "from app import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
        )
        _commit(tmp_dir, "initial commit")

        run_id = await _make_run("scenario-4", tmp_dir)
        git_ops.ensure_branch(tmp_dir, "agentforge/demo-scenario-4", base_ref=_BASE_REF)
        migrations_dir = Path(tmp_dir, "alembic", "versions")
        migrations_dir.mkdir(parents=True)
        (migrations_dir / "0001_add_index.py").write_text(
            "def upgrade():\n    op.create_index('ix_orders_customer_id', 'orders', "
            "['customer_id'])\n"
        )
        _commit(tmp_dir, "add index migration [demo: a real migration file]")

        async with async_session_factory() as session:
            await RunRepository(session).update(
                run_id, branch_name="agentforge/demo-scenario-4"
            )
            await session.commit()

        final_state = await _run_deterministic_tail(_initial_state(run_id, tmp_dir))

    return {
        "run_id": run_id,
        "verification_result": final_state["verification_result"],
        "final_decision": final_state["final_decision"],
    }


async def scenario_1_reviewer_catches_bug() -> dict | None:
    """Requires a real LLM Reviewer call — returns None (skipped, not
    faked) if no credentials are configured."""
    if not _has_real_llm_credentials():
        return None

    diff = (
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n+++ b/app.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def add(a, b):\n"
        "-    return a + b\n"
        "+    return a - b\n"
    )
    output, _usage = await run_reviewer(
        "Implement add(a, b) that returns the sum of its two arguments.", diff
    )
    return {"findings": [f.model_dump() for f in output.findings]}


async def run_all_scenarios() -> int:
    print("AgentForge Failure-Injection Demo\n")

    print("Scenario 2 — QA overrides a (simulated) Reviewer approval:")
    s2 = await scenario_2_qa_overrides_reviewer()
    print(f"  run_id={s2['run_id']}")
    print(f"  test_results={s2['test_results']}")
    print(f"  verification={s2['verification_result']}")
    print(f"  final_decision={s2['final_decision']}")
    s2_ok = s2["final_decision"] == "BLOCKED_BY_VERIFICATION"
    print(f"  -> {'REAL BLOCK confirmed' if s2_ok else 'UNEXPECTED — did not block'}\n")

    print("Scenario 3 — Security blocks a committed secret:")
    s3 = await scenario_3_security_blocks_secret()
    print(f"  run_id={s3['run_id']}")
    print(f"  security_findings={s3['security_findings']}")
    print(f"  final_decision={s3['final_decision']}")
    s3_ok = s3["final_decision"] == "BLOCKED_BY_VERIFICATION"
    print(f"  -> {'REAL BLOCK confirmed' if s3_ok else 'UNEXPECTED — did not block'}\n")

    print("Scenario 4 — Migration requires human approval:")
    s4 = await scenario_4_migration_requires_approval()
    print(f"  run_id={s4['run_id']}")
    print(f"  final_decision={s4['final_decision']}")
    s4_ok = s4["final_decision"] == "PENDING_HUMAN_APPROVAL"
    print(f"  -> {'REAL APPROVAL REQUIRED confirmed' if s4_ok else 'UNEXPECTED'}\n")

    print("Scenario 1 — Reviewer genuinely catches a bug (requires a real LLM):")
    s1 = await scenario_1_reviewer_catches_bug()
    if s1 is None:
        print(
            "  Integration unavailable. Configure ANTHROPIC_API_KEY or OPENAI_API_KEY "
            "to enable this feature.\n"
        )
        s1_ok = None
    else:
        print(f"  findings={s1['findings']}")
        s1_ok = len(s1["findings"]) > 0
        verdict = "Reviewer flagged the bug" if s1_ok else "Reviewer missed it (real LLM output)"
        print(f"  -> {verdict}\n")

    all_ran_ok = s2_ok and s3_ok and s4_ok
    return 0 if all_ran_ok else 1


def main() -> None:
    exit_code = asyncio.run(run_all_scenarios())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
