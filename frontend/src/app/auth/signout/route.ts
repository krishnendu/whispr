import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export async function POST(req: Request) {
  const jar = await cookies();
  jar.delete("whispr_token");
  return NextResponse.redirect(new URL("/", req.url));
}
