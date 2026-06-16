import { redirect } from "next/navigation";

import { api } from "@/lib/api";
import { requireUser } from "@/lib/session";

import { AuditTable } from "./table";

export default async function AdminAuditPage() {
  const { token, user } = await requireUser();
  if (!user.is_operator) redirect("/home");
  const { entries } = await api.adminAuditLog(token);
  return <AuditTable token={token} initial={entries} />;
}
