import { NextRequest, NextResponse } from 'next/server';
import { dispatchPendingNotifications } from '@/lib/notifications';
import { requireRole, isAuthError, isInternalAdminAuthorized } from '@/lib/auth/roles';

export async function POST(request: NextRequest) {
  try {
    const isInternal = isInternalAdminAuthorized(request);
    const auth = requireRole(request, 'admin', 'supervisor');

    if (!isInternal && isAuthError(auth)) {
      return NextResponse.json({ error: auth.error }, { status: auth.status });
    }

    const result = await dispatchPendingNotifications();
    return NextResponse.json({
      success: true,
      message: `Dispatched ${result.sent} pending notifications.`,
      ...result,
    });
  } catch (error: any) {
    console.error('Notification dispatch error:', error);
    return NextResponse.json(
      { error: error.message || 'Notification dispatch failed' },
      { status: 500 }
    );
  }
}
