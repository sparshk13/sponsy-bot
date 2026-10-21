/**
 * TanStack Query hooks and types for the approval queue and messages (CODE-14).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "./client";
import type { paths } from "./schema";

export type QueueItem =
  paths["/api/queue"]["get"]["responses"]["200"]["content"]["application/json"][number];
export type MessageItem =
  paths["/api/messages/{message_id}"]["put"]["responses"]["200"]["content"]["application/json"];

export interface MessageUpdatePayload {
  subject: string;
  body: string;
}

export function useQueue() {
  return useQuery<QueueItem[], Error>({
    queryKey: ["queue"],
    queryFn: () => apiRequest<QueueItem[]>("/api/queue"),
  });
}

export function useUpdateMessage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ messageId, payload }: { messageId: number; payload: MessageUpdatePayload }) =>
      apiRequest<MessageItem>(`/api/messages/${messageId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["queue"] });
      queryClient.invalidateQueries({ queryKey: ["target"] });
    },
  });
}

export function useApproveMessage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (messageId: number) =>
      apiRequest<MessageItem>(`/api/messages/${messageId}/approve`, {
        method: "POST",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["queue"] });
      queryClient.invalidateQueries({ queryKey: ["target"] });
    },
  });
}

export function useDiscardMessage() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (messageId: number) =>
      apiRequest<MessageItem>(`/api/messages/${messageId}/discard`, {
        method: "POST",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["queue"] });
      queryClient.invalidateQueries({ queryKey: ["target"] });
    },
  });
}
