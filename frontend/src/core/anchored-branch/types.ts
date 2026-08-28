export interface AnchorSelection {
  text: string;
  message_id?: string;
  start_offset?: number | null;
  end_offset?: number | null;
  file_path?: string;
  symbol?: string;
  code_context?: string;
}

export interface BranchRecord {
  branch_id: string;
  main_thread_id: string;
  child_thread_id: string;
  owner_id: string;
  anchor: AnchorSelection;
  main_task_summary: string;
  relevant_main_context: string[];
  main_history: string[];
  code_change_project_id: string;
  context_strategy: "FULL_HISTORY" | "ANCHOR_ONLY" | "ANCHORED_CONTEXT";
  token_budget: number;
  status: "ACTIVE" | "CLOSED";
  created_at: string;
  updated_at: string;
  closed_at: string;
}

export interface BranchMessage {
  id: string;
  role: string;
  text: string;
}
