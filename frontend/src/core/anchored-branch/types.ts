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
  root_summary: string;
  status: "ACTIVE" | "APPLIED" | "ARCHIVED";
  decision?: BranchDecision | null;
}

export interface BranchDecision {
  decision_id: string;
  branch_id: string;
  summary: string;
  actions: string[];
  constraints: string[];
  rationale: string;
  applied: boolean;
  applied_at: string;
}
