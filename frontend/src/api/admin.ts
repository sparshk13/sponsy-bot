/**
 * Admin queries and mutations for user management and audit log (CODE-14).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "./client";
import type { paths } from "./schema";

export type AdminUser =
  paths["/api/admin/users"]["get"]["responses"]["200"]["content"]["application/json"][number];
export type CreateUserPayload =
  paths["/api/admin/users"]["post"]["requestBody"]["content"]["application/json"];
export type UpdateUserPayload =
  paths["/api/admin/users/{user_id}"]["put"]["requestBody"]["content"]["application/json"];
export type AuditLogEntry =
  paths["/api/admin/audit"]["get"]["responses"]["200"]["content"]["application/json"][number];

export function useAdminUsers() {
  return useQuery<AdminUser[], Error>({
    queryKey: ["admin", "users"],
    queryFn: () => apiRequest<AdminUser[]>("/api/admin/users"),
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateUserPayload) =>
      apiRequest<AdminUser>("/api/admin/users", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, payload }: { userId: number; payload: UpdateUserPayload }) =>
      apiRequest<AdminUser>(`/api/admin/users/${userId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
  });
}

export function useAdminAudit() {
  return useQuery<AuditLogEntry[], Error>({
    queryKey: ["admin", "audit"],
    queryFn: () => apiRequest<AuditLogEntry[]>("/api/admin/audit"),
  });
}

export type TemplateItem =
  paths["/api/admin/templates"]["get"]["responses"]["200"]["content"]["application/json"][number];
export type CreateTemplatePayload =
  paths["/api/admin/templates"]["post"]["requestBody"]["content"]["application/json"];
export type UpdateTemplatePayload =
  paths["/api/admin/templates/{template_id}"]["put"]["requestBody"]["content"]["application/json"];

export function useTemplates() {
  return useQuery<TemplateItem[], Error>({
    queryKey: ["admin", "templates"],
    queryFn: () => apiRequest<TemplateItem[]>("/api/admin/templates"),
  });
}

export function useCreateTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CreateTemplatePayload) =>
      apiRequest<TemplateItem>("/api/admin/templates", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "templates"] });
    },
  });
}

export function useUpdateTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ templateId, payload }: { templateId: number; payload: UpdateTemplatePayload }) =>
      apiRequest<TemplateItem>(`/api/admin/templates/${templateId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "templates"] });
    },
  });
}

export function useDeleteTemplate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (templateId: number) =>
      apiRequest<void>(`/api/admin/templates/${templateId}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "templates"] });
    },
  });
}

export type BrochureItem =
  paths["/api/admin/brochures"]["get"]["responses"]["200"]["content"]["application/json"][number];

export function useBrochures() {
  return useQuery<BrochureItem[], Error>({
    queryKey: ["admin", "brochures"],
    queryFn: () => apiRequest<BrochureItem[]>("/api/admin/brochures"),
  });
}

export function useUploadBrochure() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ tier, file }: { tier: string; file: File }) => {
      const formData = new FormData();
      formData.append("tier", tier);
      formData.append("file", file);
      return apiRequest<BrochureItem>("/api/admin/brochures", {
        method: "POST",
        body: formData,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "brochures"] });
    },
  });
}

export type SystemStatus =
  paths["/api/admin/system"]["get"]["responses"]["200"]["content"]["application/json"];

export function useSystemStatus() {
  return useQuery<SystemStatus, Error>({
    queryKey: ["admin", "system"],
    queryFn: () => apiRequest<SystemStatus>("/api/admin/system"),
  });
}

export function useRevokeAllSessions() {
  return useMutation({
    mutationFn: () =>
      apiRequest<{ message: string }>("/api/admin/revoke-sessions", {
        method: "POST",
      }),
  });
}

export function useResetUser2FA() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: number) =>
      apiRequest<{ message: string }>(`/api/admin/users/${userId}/reset-2fa`, {
        method: "POST",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
  });
}

export function useEraseContact() {
  return useMutation({
    mutationFn: (contactId: number) =>
      apiRequest<{ message: string }>(`/api/admin/contacts/${contactId}/erase`, {
        method: "POST",
      }),
  });
}

