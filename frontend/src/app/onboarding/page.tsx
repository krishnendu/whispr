import { redirect } from "next/navigation";

import { api } from "@/lib/api";
import { requireUser } from "@/lib/session";

import { OnboardingForm } from "./form";

export default async function OnboardingPage() {
  const { token, user } = await requireUser();
  if (user.onboarding_complete) redirect("/home");

  const tags = await api.tags();
  return <OnboardingForm token={token} user={user} tags={tags} />;
}
