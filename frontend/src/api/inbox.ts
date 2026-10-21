/**
 * TanStack Query hooks and types for the Inbox and incoming replies (CODE-14).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "./client";
import type { paths } from "./schema";

export type InboxItem =
  paths["/api/inbox"]["get"]["responses"]["200"]["content"]["application/json"][number];

export type MessageResponse =
  paths["/api/messages/{message_id}/class"]["put"]["responses"]["200"]["content"]["application/json"];

export type TodayMetrics =
  paths["/api/today"]["get"]["responses"]["200"]["content"]["application/json"];

export function useInbox(classification?: string, ownOnly?: boolean) {
  const params = new URLSearchParams();
  if (classification) params.set("classification", classification);
  if (ownOnly) params.set("own_only", "true");
  const qs = params.toString() ? `?${params.toString()}` : "";

  return useQuery<InboxItem[], Error>({
    queryKey: ["inbox", classification, ownOnly],
    queryFn: () => apiRequest<InboxItem[]>(`/api/inbox${qs}`),
  });
}

export function useToday() {
  return useQuery<TodayMetrics, Error>({
    queryKey: ["today"],
    queryFn: () => apiRequest<TodayMetrics>("/api/today"),
  });
}

export function useOverrideClassification() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      messageId,
      classification,
    }: {
      messageId: number;
      classification: string;
    }) =>
      apiRequest<MessageResponse>(`/api/messages/${messageId}/class`, {
        method: "PUT",
        body: JSON.stringify({ classification }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inbox"] });
      queryClient.invalidateQueries({ queryKey: ["today"] });
      queryClient.invalidateQueries({ queryKey: ["targets"] });
    },
  });
}

export function useConvertSuggestedReply() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      messageId,
      subject,
      body,
    }: {
      messageId: number;
      subject?: string;
      body?: string;
    }) =>
      apiRequest<MessageResponse>(`/api/messages/${messageId}/suggested-reply`, {
        method: "POST",
        body: JSON.stringify({ subject, body }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inbox"] });
      queryClient.invalidateQueries({ queryKey: ["queue"] });
      queryClient.invalidateQueries({ queryKey: ["today"] });
    },
  });
}
