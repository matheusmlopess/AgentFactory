// completeness.ts — types for skill completeness JSON reports
// <!-- version: 1.0.0 -->

export type AtomType =
  | "decision_path"
  | "command"
  | "error_case"
  | "data_table"
  | "external_ref"
  | "constraint";

export type AtomStatus = "preserved" | "degraded" | "missing";

export interface Atom {
  id: string;
  type: AtomType;
  description: string;
  status: AtomStatus;
  evidence: string;
}

export interface CompletenessReport {
  skill: string;
  old_ref: string;
  old_version: string;
  new_version: string;
  generated_at: string;
  score: number;
  threshold: number;
  passed: boolean;
  summary: {
    preserved: number;
    degraded: number;
    missing: number;
  };
  atoms: Atom[];
}
