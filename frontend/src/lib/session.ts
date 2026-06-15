import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { api, type WhisprUser } from "./api";

export const AUTH_COOKIE = "whispr_token";

export async function getToken(): Promise<string | null> {
  const jar = await cookies();
  return jar.get(AUTH_COOKIE)?.value ?? null;
}

export async function getCurrentUser(): Promise<WhisprUser | null> {
  const token = await getToken();
  if (!token) return null;
  try {
    return await api.me(token);
  } catch {
    return null;
  }
}

export async function requireUser(): Promise<{ token: string; user: WhisprUser }> {
  const token = await getToken();
  if (!token) redirect("/signin");
  try {
    const user = await api.me(token);
    return { token, user };
  } catch {
    redirect("/signin");
  }
}
