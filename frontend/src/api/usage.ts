/**
 * TanStack Query hook and types for API budget usage (BUD-09).
 */

import { useQuery } from "@tanstack/react-query";
import { apiRequest } from "./client";
import type { paths } from "./schema";

export type UsageItem =
  paths["/api/usage"]["get"]["responses"]["200"]["content"]["application/json"][number];

export function useUsage() {
  return useQuery<UsageItem[], Error>({
    queryKey: ["usage"],
    queryFn: () => apiRequest<UsageItem[]>("/api/usage"),
  });
}
