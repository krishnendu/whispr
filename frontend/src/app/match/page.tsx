import { redirect } from "next/navigation";

import { requireUser } from "@/lib/session";

import { MatchClient } from "./client";

export default async function MatchPage() {
  const { token, user } = await requireUser();
  if (!user.onboarding_complete) redirect("/onboarding");
  return <MatchClient token={token} tags={user.tags} />;
}
