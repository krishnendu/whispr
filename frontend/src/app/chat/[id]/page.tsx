import { notFound } from "next/navigation";

import { api } from "@/lib/api";
import { requireUser } from "@/lib/session";

import { ChatClient } from "./client";

export default async function ChatPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { token } = await requireUser();
  const { id } = await params;
  const convoId = Number(id);
  if (!Number.isFinite(convoId)) notFound();

  try {
    const convo = await api.getConversation(token, convoId);
    return <ChatClient token={token} initial={convo} />;
  } catch {
    notFound();
  }
}
