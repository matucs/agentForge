"""Developer agent (spec §5.4): implements the approved plan against a real
Git working tree. The LLM call proposes file contents; applying them to disk
and committing is deterministic and unit-tested independent of the LLM
(`apply_developer_output`), same separation of concerns as the rest of the
agents in this project.
"""

from app.agents.llm_json import complete_structured
from app.agents.schemas import ArchitectOutput, DeveloperOutput, PlannerOutput, ResearchOutput
from app.git_integration import git_ops
from app.llm.base import LLMUsage
from app.llm.factory import get_default_provider

_SYSTEM = """You are the Developer agent in an autonomous software \
engineering system. You are given a requirement, the Plan, Architecture, \
and Research produced by earlier agents, and must implement it as real \
file changes. Provide full file contents (not diffs/patches) for every \
file you create or modify, plus any test files needed to verify the \
change. Keep the change focused — only touch files necessary for this \
requirement. Respond with ONLY a JSON object matching this schema, no \
markdown fences, no prose:
{
  "files": [{"path": "relative/path.py", "content": "full file content"}],
  "test_files": [{"path": "relative/test_path.py", "content": "full file content"}],
  "summary": "one paragraph describing what changed and why"
}"""

_RETRY_SYSTEM_SUFFIX = """

Your previous attempt did not pass review/tests. You are given the specific \
feedback below — address it directly rather than repeating the same \
content. Still respond with ONLY the JSON schema above."""


def branch_name_for_task(task_id: str) -> str:
    return f"agentforge/task-{task_id}"


async def run_developer(
    requirement_text: str,
    plan: PlannerOutput,
    architecture: ArchitectOutput,
    research: ResearchOutput,
    *,
    retry_feedback: str | None = None,
) -> tuple[DeveloperOutput, LLMUsage]:
    provider = get_default_provider()
    system = _SYSTEM + (_RETRY_SYSTEM_SUFFIX if retry_feedback else "")
    prompt = (
        f"Requirement:\n{requirement_text}\n\n"
        f"Plan (JSON):\n{plan.model_dump_json()}\n\n"
        f"Architecture (JSON):\n{architecture.model_dump_json()}\n\n"
        f"Research (JSON):\n{research.model_dump_json()}"
    )
    if retry_feedback:
        prompt += f"\n\nFeedback to address:\n{retry_feedback}"

    return await complete_structured(
        provider, system=system, prompt=prompt, output_model=DeveloperOutput, max_tokens=4096
    )


def apply_developer_output(
    repo_path: str, task_id: str, output: DeveloperOutput, *, base_ref: str
) -> tuple[str, str]:
    """Applies `output` to a real Git working tree: checks out (creating if
    needed) the task branch, writes every file, commits. Returns
    (branch_name, commit_sha). Raises GitOperationError if there was nothing
    to commit (e.g. the LLM proposed no files) — never fakes a commit."""
    branch = branch_name_for_task(task_id)
    git_ops.ensure_branch(repo_path, branch, base_ref=base_ref)

    files = {f.path: f.content for f in output.files}
    files.update({f.path: f.content for f in output.test_files})
    git_ops.write_files(repo_path, files)

    message = output.summary.strip() or f"AgentForge: implement task {task_id}"
    commit_sha = git_ops.commit_all(repo_path, message)
    return branch, commit_sha
