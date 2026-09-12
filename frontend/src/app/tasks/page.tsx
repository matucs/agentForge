"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  createProject,
  createRun,
  createTask,
  listProjects,
  listTasks,
  startRun,
  type Project,
  type Task,
} from "@/lib/api";

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[] | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [projectId, setProjectId] = useState("");
  const [newProjectName, setNewProjectName] = useState("");
  const [newProjectRepoPath, setNewProjectRepoPath] = useState("");
  const [title, setTitle] = useState("");
  const [requirement, setRequirement] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  async function refresh() {
    const [taskData, projectData] = await Promise.all([listTasks(), listProjects()]);
    setTasks(taskData);
    setProjects(projectData);
  }

  useEffect(() => {
    refresh().catch((err) =>
      setError(err instanceof Error ? err.message : "Failed to load tasks"),
    );
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      let usedProjectId = projectId;
      if (!usedProjectId) {
        if (!newProjectName || !newProjectRepoPath) {
          throw new Error("Provide a project name and repo path, or pick an existing project.");
        }
        const project = await createProject({
          name: newProjectName,
          repo_path: newProjectRepoPath,
        });
        usedProjectId = project.id;
      }
      const task = await createTask({
        project_id: usedProjectId,
        title,
        requirement_text: requirement,
      });
      const run = await createRun(task.id);
      await startRun(run.id);

      setTitle("");
      setRequirement("");
      setNewProjectName("");
      setNewProjectRepoPath("");
      setShowForm(false);
      await refresh();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Failed to create task");
    } finally {
      setSubmitting(false);
    }
  }

  const projectNameById = Object.fromEntries(projects.map((p) => [p.id, p.name]));

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Tasks</h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-md bg-sky-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-500"
        >
          {showForm ? "Cancel" : "New task"}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="mt-6 space-y-4 rounded-xl border border-slate-800 bg-slate-900 p-5"
        >
          <div>
            <label className="block text-xs uppercase tracking-wide text-slate-500">
              Project
            </label>
            <select
              value={projectId}
              onChange={(e) => setProjectId(e.target.value)}
              className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200"
            >
              <option value="">Create a new project…</option>
              {projects.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </div>

          {!projectId && (
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-xs uppercase tracking-wide text-slate-500">
                  New project name
                </label>
                <input
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200"
                  placeholder="AgentForge"
                />
              </div>
              <div>
                <label className="block text-xs uppercase tracking-wide text-slate-500">
                  Repo path (on the backend host)
                </label>
                <input
                  value={newProjectRepoPath}
                  onChange={(e) => setNewProjectRepoPath(e.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200"
                  placeholder="/path/to/real/git/repo"
                />
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs uppercase tracking-wide text-slate-500">Title</label>
            <input
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200"
              placeholder="Add pagination to the users endpoint"
            />
          </div>

          <div>
            <label className="block text-xs uppercase tracking-wide text-slate-500">
              Requirement
            </label>
            <textarea
              required
              value={requirement}
              onChange={(e) => setRequirement(e.target.value)}
              rows={3}
              className="mt-1 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200"
              placeholder="Describe what should change and why."
            />
          </div>

          {formError && <p className="text-sm text-rose-400">{formError}</p>}

          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:opacity-50"
          >
            {submitting ? "Creating…" : "Create task and start run"}
          </button>
        </form>
      )}

      {error && <p className="mt-4 text-sm text-rose-400">{error}</p>}

      <div className="mt-6 overflow-x-auto rounded-xl border border-slate-800 bg-slate-900">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Title</th>
              <th className="px-4 py-3">Project</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {tasks === null ? (
              <tr>
                <td className="px-4 py-6 text-slate-500" colSpan={4}>
                  Loading…
                </td>
              </tr>
            ) : tasks.length === 0 ? (
              <tr>
                <td className="px-4 py-6 text-slate-500" colSpan={4}>
                  No tasks yet.
                </td>
              </tr>
            ) : (
              tasks.map((task) => (
                <tr key={task.id} className="hover:bg-slate-800/40">
                  <td className="px-4 py-3">
                    <Link href={`/tasks/${task.id}`} className="text-sky-400 hover:underline">
                      {task.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-400">
                    {projectNameById[task.project_id] ?? task.project_id.slice(0, 8)}
                  </td>
                  <td className="px-4 py-3 text-slate-400">{task.status}</td>
                  <td className="px-4 py-3 text-slate-500">
                    {new Date(task.created_at).toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}
