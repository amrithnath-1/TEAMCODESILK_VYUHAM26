export type Role = "ADMIN" | "STAFF";

export interface SessionUser {
  username: string;
  display_name: string;
  role: Role;
  employee_id: string | null;
}

export interface Skill {
  skill_name: string;
  level: "Beginner" | "Intermediate" | "Advanced" | "Expert";
  is_verified: boolean;
  evidence_source: string;
}

export interface EmployeeScores {
  employee_id: string;
  name: string;
  email: string;
  designation: string;
  department: string;
  manager: string;
  years_exp: number;
  status: string;
  weekly_capacity_hrs: number;
  committed_hrs: number;
  meeting_hrs: number;
  leave_hrs: number;
  free_capacity_hrs: number;
  skill_score: number;
  performance_score: number | null;
  availability_score: number;
  workload_score: number;
  collaboration_score: number;
  level: string;
  sufficient_evidence: boolean;
  dispute_status: string;
  dispute_note: string | null;
  preferred_tasks: string[];
  learning_goals: string[];
  evidence_metrics: Record<string, number>;
  skills: Skill[];
}

export interface Task {
  id: string;
  project_id: string;
  title: string;
  description: string;
  required_skills: Record<string, string>;
  estimated_hours: number;
  priority: "Low" | "Medium" | "High" | "Critical";
  deadline_days: number;
  dependencies: string[];
  deliverable_criteria: string;
  status: string;
  assigned_to: string | null;
  progress_pct: number;
  dependency_status?: { task_id: string; status: string }[];
  why_me?: string | null;
  suitability_score?: number | null;
}

export interface Candidate {
  employee_id: string;
  employee_name: string;
  designation: string;
  eligible: boolean;
  suitability_score: number;
  free_hrs_before: number;
  utilization_after_pct: number;
  factor_breakdown: Record<string, number>;
  hard_violations: string[];
  warnings: string[];
  new_hire_protected: boolean;
}

export interface Approval {
  approval_id: string;
  decision_id: string;
  kind: "INITIAL_ALLOCATION" | "REALLOCATION";
  task_id: string;
  task_title: string;
  priority: string;
  previous_owner: string | null;
  recommended_new_owner_id: string | null;
  recommended_new_owner_name: string | null;
  suitability_score: number;
  post_utilization_pct: number;
  explanation: string;
  shortlist: Candidate[];
  status: "PENDING" | "APPROVED" | "REJECTED";
  manager_comments: string | null;
  created_at: string;
  decided_by: string | null;
}

export interface Assignment {
  id: string;
  task_id: string;
  employee_id: string;
  suitability_score: number;
  factor_breakdown: Record<string, number>;
  explanation_rationale: string;
  tradeoffs_flagged: string[];
  status: string;
}

export interface AuditEntry {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  entity_id: string;
  details: Record<string, unknown>;
  prev_hash: string;
  sha256_proof: string;
}

export interface Weights {
  skill_match: number;
  availability: number;
  workload_balance: number;
  priority_alignment: number;
  past_performance: number;
  development_opportunity: number;
}

export interface Project {
  id: string;
  name: string;
  business_objective: string;
  priority: string;
  deadline_days: number;
  status: string;
}

export interface Summary {
  total_employees: number;
  total_tasks: number;
  workload_gini_index: number;
  overloaded_count: number;
  on_leave_count: number;
  team_free_hrs: number;
  weights: Weights;
  employees: EmployeeScores[];
  tasks: Task[];
  projects: Project[];
  pending_approvals: Approval[];
  decided_approvals: Approval[];
  assignments: Assignment[];
  decisions: { id: string; agent_name: string; recommended_action: string; risk_level: string; requires_approval: boolean }[];
  recent_audits: AuditEntry[];
  ledger_status: { valid: boolean; entries: number; broken_at: string | null; head?: string };
}

export interface Allocation {
  task_id: string;
  task_title: string;
  priority: string;
  status: string;
  approval_id?: string | null;
  recommended: Candidate | null;
  shortlist: Candidate[];
  explanation: string;
}

export interface Risk {
  type: string;
  level: "Low" | "Medium" | "High" | "Critical";
  entity: string;
  detail: string;
}

export interface SkillGap {
  skill: string;
  required_level: string;
  tasks: string[];
  demand_hrs: number;
  verified_holders: string[];
  self_reported_holders: string[];
  available_holders: number;
  supply_hrs: number;
  severity: "Low" | "Medium" | "High" | "Critical";
  training_recommendations: { employee_id: string; name: string; recommendation: string }[];
}

export interface ChatMessage {
  from: "user" | "agent";
  text: string;
  agent?: string;
  trace?: string[];
}
