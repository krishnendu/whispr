import { redirect } from "next/navigation";

import { api } from "@/lib/api";
import { requireUser } from "@/lib/session";

import { UsersTable } from "./table";

export default async function AdminUsersPage() {
  const { token, user } = await requireUser();
  if (!user.is_operator) redirect("/home");
  const { users } = await api.adminUsers(token);
  return <UsersTable token={token} initial={users} />;
}
