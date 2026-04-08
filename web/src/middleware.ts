import { NextResponse } from "next/server";

// Auth removed — dashboard is publicly accessible
export function middleware() {
  return NextResponse.next();
}

export const config = {
  matcher: [],
};
