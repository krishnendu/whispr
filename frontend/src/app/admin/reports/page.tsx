import { redirect } from "next/navigation";

import { api } from "@/lib/api";
import { requireUser } from "@/lib/session";

import { ReportsTable } from "./table";

export default async function AdminReportsPage() {
  const { token, user } = await requireUser();
  if (!user.is_operator) redirect("/home");
  const { reports } = await api.adminReports(token);
  return <ReportsTable token={token} initial={reports} />;
}
