/**
 * TanStack Query hooks and types for targets, campaigns, and claims (CODE-14).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "./client";
import type { paths } from "./schema";

export type TargetItem =
  paths["/api/targets"]["get"]["responses"]["200"]["content"]["application/json"][number];
export type TargetDetail =
  paths["/api/targets/{target_id}"]["get"]["responses"]["200"]["content"]["application/json"];
export type CompanyFactItem = NonNullable<TargetDetail["facts"]>[number];
export type TargetCreatePayload =
  paths["/api/targets"]["post"]["requestBody"]["content"]["application/json"];
export type CampaignItem =
  paths["/api/admin/campaigns"]["get"]["responses"]["200"]["content"]["application/json"][number];
export type CSVImportResult =
  paths["/api/targets/import"]["post"]["responses"]["200"]["content"]["application/json"];
export type ClaimResult =
  paths["/api/targets/{target_id}/claim"]["post"]["responses"]["200"]["content"]["application/json"];
export type TargetStatusPayload =
  paths["/api/targets/{target_id}/status"]["post"]["requestBody"]["content"]["application/json"];
export type OutcomePayload =
  paths["/api/targets/{target_id}/outcome"]["post"]["requestBody"]["content"]["application/json"];
export type OutcomeItem =
  paths["/api/targets/{target_id}/outcome"]["post"]["responses"]["201"]["content"]["application/json"];


export interface TargetFilters {
  campaign_id?: number;
  status?: string;
  tier?: string;
  owner_id?: number;
  search?: string;
}

export function useCampaigns() {
  return useQuery<CampaignItem[], Error>({
    queryKey: ["campaigns"],
    queryFn: () => apiRequest<CampaignItem[]>("/api/admin/campaigns"),
  });
}

export function useTargets(filters: TargetFilters = {}) {
  const params = new URLSearchParams();
  if (filters.campaign_id !== undefined) params.set("campaign_id", String(filters.campaign_id));
  if (filters.status) params.set("status", filters.status);
  if (filters.tier) params.set("tier", filters.tier);
  if (filters.owner_id !== undefined) params.set("owner_id", String(filters.owner_id));
  if (filters.search) params.set("search", filters.search);

  const queryStr = params.toString() ? `?${params.toString()}` : "";

  return useQuery<TargetItem[], Error>({
    queryKey: ["targets", filters],
    queryFn: () => apiRequest<TargetItem[]>(`/api/targets${queryStr}`),
  });
}

export function useAddTarget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TargetCreatePayload) =>
      apiRequest<TargetItem>("/api/targets", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["targets"] });
    },
  });
}

export function useImportCSV() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (formData: FormData) =>
      apiRequest<CSVImportResult>("/api/targets/import", {
        method: "POST",
        body: formData,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["targets"] });
    },
  });
}

export function useClaimTarget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (targetId: number) =>
      apiRequest<ClaimResult>(`/api/targets/${targetId}/claim`, {
        method: "POST",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["targets"] });
    },
  });
}

export function useUnlockCooldown() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (targetId: number) =>
      apiRequest<TargetItem>(`/api/targets/${targetId}/unlock`, {
        method: "POST",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["targets"] });
    },
  });
}

export function useTargetDetail(targetId: number) {
  return useQuery<TargetDetail, Error>({
    queryKey: ["targets", targetId],
    queryFn: () => apiRequest<TargetDetail>(`/api/targets/${targetId}`),
  });
}

export function usePrepareTarget() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (targetId: number) =>
      apiRequest<TargetDetail>(`/api/targets/${targetId}/prepare`, {
        method: "POST",
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(["targets", data.id], data);
      queryClient.invalidateQueries({ queryKey: ["targets"] });
    },
  });
}

export function useRefreshResearch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (targetId: number) =>
      apiRequest<TargetDetail>(`/api/targets/${targetId}/refresh-research`, {
        method: "POST",
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(["targets", data.id], data);
      queryClient.invalidateQueries({ queryKey: ["targets"] });
    },
  });
}

export function useUpdateTargetStatus() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ targetId, payload }: { targetId: number; payload: TargetStatusPayload }) =>
      apiRequest<TargetItem>(`/api/targets/${targetId}/status`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ["targets", vars.targetId] });
      queryClient.invalidateQueries({ queryKey: ["targets"] });
    },
  });
}

export function useRecordOutcome() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ targetId, payload }: { targetId: number; payload: OutcomePayload }) =>
      apiRequest<OutcomeItem>(`/api/targets/${targetId}/outcome`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ["targets", vars.targetId] });
      queryClient.invalidateQueries({ queryKey: ["targets"] });
    },
  });
}

export type FindContactResult =
  paths["/api/targets/{target_id}/find-contact"]["post"]["responses"]["200"]["content"]["application/json"];
export type ContactUpdatePayload =
  paths["/api/targets/{target_id}/contact"]["put"]["requestBody"]["content"]["application/json"];
export type ContactItem =
  paths["/api/targets/{target_id}/contact"]["put"]["responses"]["200"]["content"]["application/json"];

export function useFindContact() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (targetId: number) =>
      apiRequest<FindContactResult>(`/api/targets/${targetId}/find-contact`, {
        method: "POST",
      }),
    onSuccess: (_, targetId) => {
      queryClient.invalidateQueries({ queryKey: ["targets", targetId] });
      queryClient.invalidateQueries({ queryKey: ["targets"] });
    },
  });
}

export function useUpdateContact() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ targetId, payload }: { targetId: number; payload: ContactUpdatePayload }) =>
      apiRequest<ContactItem>(`/api/targets/${targetId}/contact`, {
        method: "PUT",
        body: JSON.stringify(payload),
      }),
    onSuccess: (_, vars) => {
      queryClient.invalidateQueries({ queryKey: ["targets", vars.targetId] });
      queryClient.invalidateQueries({ queryKey: ["targets"] });
    },
  });
}

