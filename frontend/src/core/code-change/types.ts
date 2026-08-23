import { type TestProfile } from "./profiles";

export type PatchMode = "external" | "agent";

export interface CodeChangeProject {
  project_id: string;
  name: string;
  repo_path: string;
  repo_url: string;
  default_branch: string;
  test_profile: TestProfile;
  owner_id: string;
}

export interface CodeChangeTask {
  task_id: string;
  project_id: string;
  requirement: string;
  status: string;
  attempt_count: number;
  max_attempts: number;
  source_commit: string;
  patch_mode: PatchMode;
  agent_model_name: string;
  agent_thread_id: string;
  agent_run_id: string;
  agent_rationale: string;
  agent_changed_files: string[];
  worker_id: string;
  error: string;
  error_code: string;
  last_error: string;
  pr_body_path: string;
  approval_note: string;
  created_at: string;
  updated_at: string;
}

export interface CreateProjectInput {
  name: string;
  repo_path: string;
  test_profile: TestProfile;
  repo_url?: string;
  default_branch?: string;
}

export interface CreateTaskInput {
  requirement: string;
  patch_text?: string;
  patch_mode?: PatchMode;
  agent_model_name?: string;
}

export interface ReviewTaskInput {
  decision: "approve" | "request_changes";
  note?: string;
}
