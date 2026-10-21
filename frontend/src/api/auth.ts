/**
 * Auth hooks and queries using TanStack Query and generated API types (CODE-14).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiRequest, setCsrfToken } from "./client";
import type { paths } from "./schema";

export type SessionResponse =
  paths["/api/session"]["get"]["responses"]["200"]["content"]["application/json"];
export type UserResponse = SessionResponse["user"];
export type LoginRequest =
  paths["/api/login"]["post"]["requestBody"]["content"]["application/json"];

export type LoginResponse =
  paths["/api/login"]["post"]["responses"]["200"]["content"]["application/json"];
export type LoginCodeRequest =
  paths["/api/login/code"]["post"]["requestBody"]["content"]["application/json"];
export type TwoFactorSetupResponse =
  paths["/api/account/2fa/setup"]["post"]["responses"]["200"]["content"]["application/json"];
export type TwoFactorConfirmResponse =
  paths["/api/account/2fa/confirm"]["post"]["responses"]["200"]["content"]["application/json"];

export function useSession() {
  return useQuery<SessionResponse, Error>({
    queryKey: ["session"],
    queryFn: async () => {
      const data = await apiRequest<SessionResponse>("/api/session");
      setCsrfToken(data.csrf_token);
      return data;
    },
    retry: false,
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (credentials: LoginRequest) => {
      const res = await apiRequest<LoginResponse>("/api/login", {
        method: "POST",
        body: JSON.stringify(credentials),
      });
      if (res.requires_2fa) {
        return { requires_2fa: true, pending_token: res.pending_token, session: null };
      }
      const session = await apiRequest<SessionResponse>("/api/session");
      setCsrfToken(session.csrf_token);
      return { requires_2fa: false, pending_token: null, session };
    },
    onSuccess: (data) => {
      if (data.session) {
        queryClient.setQueryData(["session"], data.session);
      }
    },
  });
}

export function useLoginCode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: LoginCodeRequest) => {
      await apiRequest<{ message: string }>("/api/login/code", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      const session = await apiRequest<SessionResponse>("/api/session");
      setCsrfToken(session.csrf_token);
      return session;
    },
    onSuccess: (session) => {
      queryClient.setQueryData(["session"], session);
    },
  });
}

export function useSetupTwoFactor() {
  return useMutation({
    mutationFn: () =>
      apiRequest<TwoFactorSetupResponse>("/api/account/2fa/setup", {
        method: "POST",
      }),
  });
}

export function useConfirmTwoFactor() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (code: string) =>
      apiRequest<TwoFactorConfirmResponse>("/api/account/2fa/confirm", {
        method: "POST",
        body: JSON.stringify({ code }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["session"] });
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await apiRequest<{ message: string }>("/api/logout", {
        method: "POST",
      });
      setCsrfToken(null);
    },
    onSuccess: () => {
      queryClient.setQueryData(["session"], null);
      queryClient.invalidateQueries({ queryKey: ["session"] });
    },
  });
}

