import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "./client";

export interface DashboardPipelineStage {
  stage: string;
  label: string;
  count: number;
}

export interface DashboardOrganizerStat {
  user_id: number;
  name: string;
  assigned_count: number;
  contacted_count: number;
  secured_count: number;
  secured_cash_inr: number;
}

export interface DashboardNonCashOutcome {
  id: number;
  company_name: string;
  kind: string;
  description?: string | null;
  confirmed_at: string;
}

export interface DashboardData {
  total_targets: number;
  pipeline: DashboardPipelineStage[];
  contacted_count: number;
  replied_count: number;
  response_rate: number;
  interested_count: number;
  interest_rate: number;
  declined_count: number;
  secured_count: number;
  total_cash_inr: number;
  non_cash_outcomes: DashboardNonCashOutcome[];
  organizers: DashboardOrganizerStat[];
}

export interface MemoryEntry {
  id: number;
  company_name: string;
  company_domain: string;
  campaign_name: string;
  kind: string;
  amount_inr?: number | null;
  description?: string | null;
  confirmed_at: string;
  ask_worked?: string | null;
  tier?: string | null;
}

export interface MemoryData {
  entries: MemoryEntry[];
  total_cash_inr: number;
  total_sponsors: number;
}

export function useDashboard() {
  return useQuery<DashboardData>({
    queryKey: ["dashboard"],
    queryFn: () => apiRequest<DashboardData>("/api/dashboard"),
  });
}

export function useMemory() {
  return useQuery<MemoryData>({
    queryKey: ["memory"],
    queryFn: () => apiRequest<MemoryData>("/api/memory"),
  });
}

