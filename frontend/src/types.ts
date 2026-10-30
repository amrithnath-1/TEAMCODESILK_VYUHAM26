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
  phase?: string | null;
  milestone?: string | null;
  complexity?: number;
  acceptance_criteria: string[];
  deliverables: string[];
  subtasks: string[];
  suggested_assignee?: string | null;
  blocked: boolean;
  blocked_reason?: string | null;
  activity: { at: string; actor: string; text: string }[];
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
  change_requests: ChangeRequest[];
  ai: { configured: boolean; model: string; setup: string | null };
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

export interface ProjectProgress {
  project_id: string;
  name: string;
  status: string;
  priority: string;
  objective?: string;
  bands_pct: { verified: number; in_progress: number; blocked: number; pending: number };
  completion_pct: number;
  method: string;
  reported_by_employees_pct: number;
  reported_by_manager: { reported_pct: number; note: string; reported_by: string; created_at: string } | null;
  start_date: string;
  deadline: string;
  days_remaining: number;
  expected_pct_by_schedule: number;
  health: string;
  current_milestone: string | null;
  milestones: { name: string; done: number; total: number }[];
  open_tasks: number;
  total_tasks: number;
  overdue_tasks: string[];
  critical_blockers: { task_id: string; title: string; reason: string }[];
  last_update: string | null;
  history: { verified_pct: number; in_progress_pct: number; blocked_pct: number; pending_pct: number; created_at: string }[];
}

export interface DocumentRow {
  id: string;
  filename: string;
  version: number;
  size: number;
  ext: string;
  status: string;
  error: string | null;
  is_current: number;
  chunk_count: number;
  suspicious_count: number;
  uploaded_by: string;
  uploaded_at: string;
}

export interface EvidenceItem { text: string; document: string; location: string }

export interface Clarification {
  id: string;
  project_id: string;
  question: string;
  why: string | null;
  options: string[];
  answer: string | null;
  status: string;
}

export interface Spec {
  project_id: string;
  status: string;
  source: string | null;
  analysis: (Record<string, EvidenceItem[]> & { summary?: any; contradictions?: any; manager_notes?: any; truncated_input?: any }) | null;
  clarifications: Clarification[];
  approved_by?: string | null;
}

export interface PlanTask {
  key: string;
  title: string;
  description: string;
  phase: string;
  milestone: string;
  required_skills: Record<string, string>;
  priority: string;
  estimated_hours: number;
  complexity: number;
  deadline_days: number;
  depends_on_keys: string[];
  acceptance_criteria: string[];
  deliverables: string[];
  subtasks: string[];
  suggested_assignee_id: string | null;
  suggested_assignee_name: string | null;
  suggestion_reason: string | null;
}

export interface Plan {
  id: string;
  project_id: string;
  version: number;
  source: string;
  status: string;
  plan: { summary: string; tasks: PlanTask[]; risks: string[]; resource_gaps: string[]; phases: string[]; milestones: { name: string; due_day: number }[] };
}

export interface SkillAssessment {
  skill: string;
  score: number | null;
  confidence: string;
  evidence: { kind: string; source: string; detail: string }[];
  missing_evidence: string[];
  last_evaluated: string | null;
  history?: { score: number | null; at: string }[];
}

export interface ProLink {
  provider: string;
  label: string;
  mode: string;
  setup_note: string | null;
  status: string;
  status_detail: string | null;
  url: string | null;
  handle: string | null;
  last_checked: string | null;
  data: { languages?: Record<string, number>; public_repos?: number; recent_repositories?: { name: string; language: string | null; url: string }[] };
}

export interface ResumeResult {
  id: string;
  filename: string;
  source: string;
  uploaded_at: string;
  extracted: { skills: string[]; experience: string[]; education: string[]; certifications: string[]; projects: string[]; achievements: string[] };
  assessment: {
    label: string; criteria: string; target: string | null; skill_coverage_pct: number | null; matched_keywords: string[]; missing_keywords: string[];
    structure_score: number; skills_found: number; quantified_results_found: number; word_count: number; formatting_issues: string[]; suggestions: string[];
  };
}

export interface Intelligence {
  employee: EmployeeScores;
  profile: { bio: string; education: string[]; certifications: string[]; previous_projects: string[]; portfolio_urls: string[] };
  skills: SkillAssessment[];
  resume: ResumeResult | null;
  links: ProLink[];
  challenges: { id: string; skill: string; reason: string; status: string; resolution: string | null; created_at: string }[];
  completed: Task[];
}

export interface NotificationRow {
  id: string;
  kind: string;
  title: string;
  body: string;
  link_view: string | null;
  link_id: string | null;
  is_read: number;
  created_at: string;
}

export interface ChangeRequest {
  id: string;
  employee_id: string;
  kind: string;
  task_id: string | null;
  details: string;
  status: string;
  resolution: string | null;
  created_at: string;
}

export interface AssistantAction {
  id: string;
  action: string;
  summary: string;
  status: string;
  result: { verified: boolean; message: string; project_id?: string } | null;
}

export type Nav = (view: string, id?: string) => void;
