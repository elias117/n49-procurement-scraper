import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Auth removed — dashboard is publicly accessible
export function middleware(request: NextRequest) {
  return NextResponse.next();
}

export const config = {
  matcher: [],
};
