import { NextRequest, NextResponse } from 'next/server';
import { verifySessionSync } from '@/lib/auth/sessionCrypto';
import { normalizeRole } from '@/lib/auth/roles';

export async function GET(request: NextRequest) {
  try {
    const sessionCookie = request.cookies.get('elector_auth_session')?.value;
    if (!sessionCookie) {
      return NextResponse.json(
        {
          authenticated: false,
          role: null,
          username: null,
        },
        { status: 401 }
      );
    }

    const decoded = verifySessionSync(sessionCookie);
    if (!decoded) {
      return NextResponse.json(
        {
          authenticated: false,
          role: null,
          username: null,
        },
        { status: 401 }
      );
    }

    const rawRole = (decoded.role as string) || '';
    const normalizedRole = normalizeRole(rawRole);

    if (!normalizedRole) {
      return NextResponse.json(
        {
          authenticated: false,
          role: null,
          username: null,
        },
        { status: 401 }
      );
    }

    return NextResponse.json({
      authenticated: true,
      userId: decoded.userId,
      username: decoded.username || 'user',
      role: normalizedRole,
      email: decoded.email,
    });
  } catch (err: any) {
    return NextResponse.json(
      {
        authenticated: false,
        role: null,
        username: null,
      },
      { status: 401 }
    );
  }
}
